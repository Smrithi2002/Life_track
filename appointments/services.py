"""
Appointments App — Service Layer
===================================
Business logic for appointment booking, status transitions,
queue management, and vitals recording.
"""

import logging
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from .models import (
    Appointment, AppointmentStatus, Vitals,
    DoctorProfile, DoctorSchedule, generate_token_number,
)

logger = logging.getLogger('appointments')


class AppointmentServiceError(Exception):
    """Base exception for appointment service errors."""
    pass


class SlotUnavailableError(AppointmentServiceError):
    """Raised when the requested slot is not available."""
    pass


class InvalidTransitionError(AppointmentServiceError):
    """Raised when an invalid status transition is attempted."""
    pass


class AppointmentService:
    """
    Core business logic for appointments.

    Methods:
      - book_appointment: Create a new appointment with token
      - check_in: Nurse checks in patient → CHECKED_IN
      - record_vitals: Nurse records vitals → VITALS_DONE
      - start_consultation: Doctor starts → WITH_DOCTOR
      - complete_consultation: Doctor completes → CONSULTATION_DONE
      - cancel_appointment: Cancel with reason
      - update_status: Generic status transition
      - get_doctor_queue: Get ordered queue for a doctor
      - get_available_slots: Get available time slots
    """

    # ── Appointment Booking ──────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def book_appointment(patient, doctor, appointment_date, time_slot,
                         appointment_type='BOOKED', chief_complaint='', notes=''):
        """
        Book a new appointment.
        Auto-generates token number for queue management.

        Raises:
            SlotUnavailableError: If the slot is fully booked.
        """
        # Check slot availability
        existing_count = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appointment_date,
            time_slot=time_slot,
        ).exclude(
            status=AppointmentStatus.CANCELLED,
        ).count()

        if existing_count >= doctor.max_patients_per_slot:
            raise SlotUnavailableError(
                'This time slot is fully booked. Please choose another slot.'
            )

        # Create appointment
        appointment = Appointment(
            patient=patient,
            doctor=doctor,
            appointment_date=appointment_date,
            time_slot=time_slot,
            appointment_type=appointment_type,
            chief_complaint=chief_complaint,
            notes=notes,
        )
        # token_number auto-generated in save()
        appointment.save()

        logger.info(
            'Appointment booked: %s for %s with Dr. %s on %s at %s',
            appointment.token_number,
            patient.full_name,
            doctor.user.full_name,
            appointment_date,
            time_slot,
        )

        return appointment

    # ── Status Transitions ───────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def check_in(appointment):
        """
        Nurse checks in a patient.
        Transition: BOOKED → CHECKED_IN
        """
        if appointment.status != AppointmentStatus.BOOKED:
            raise InvalidTransitionError(
                f'Cannot check in. Current status: {appointment.status}'
            )

        appointment.status = AppointmentStatus.CHECKED_IN
        appointment.checked_in_at = timezone.now()

        # Set queue position
        queue_pos = Appointment.objects.filter(
            doctor=appointment.doctor,
            appointment_date=appointment.appointment_date,
            status__in=[
                AppointmentStatus.CHECKED_IN,
                AppointmentStatus.VITALS_DONE,
                AppointmentStatus.WITH_DOCTOR,
            ],
        ).count()
        appointment.queue_position = queue_pos

        appointment.save(update_fields=[
            'status', 'checked_in_at', 'queue_position', 'updated_at',
        ])

        logger.info('Patient checked in: %s', appointment.token_number)
        return appointment

    @staticmethod
    @transaction.atomic
    def record_vitals(appointment, recorded_by, vitals_data):
        """
        Nurse records vitals for a checked-in patient.
        Transition: CHECKED_IN → VITALS_DONE
        Creates Vitals record and updates appointment status.
        """
        if appointment.status not in [
            AppointmentStatus.CHECKED_IN,
            AppointmentStatus.VITALS_DONE,  # Allow updating vitals
        ]:
            raise InvalidTransitionError(
                f'Cannot record vitals. Current status: {appointment.status}'
            )

        # Create or update vitals
        vitals, created = Vitals.objects.update_or_create(
            appointment=appointment,
            defaults={
                'recorded_by': recorded_by,
                **vitals_data,
            },
        )

        # Update appointment status
        if appointment.status == AppointmentStatus.CHECKED_IN:
            appointment.status = AppointmentStatus.VITALS_DONE
            appointment.save(update_fields=['status', 'updated_at'])

        logger.info('Vitals recorded for: %s', appointment.token_number)
        return vitals

    @staticmethod
    @transaction.atomic
    def start_consultation(appointment):
        """
        Doctor starts consultation.
        Transition: VITALS_DONE → WITH_DOCTOR (or CHECKED_IN → WITH_DOCTOR)
        """
        allowed = [AppointmentStatus.VITALS_DONE, AppointmentStatus.CHECKED_IN]
        if appointment.status not in allowed:
            raise InvalidTransitionError(
                f'Cannot start consultation. Current status: {appointment.status}'
            )

        appointment.status = AppointmentStatus.WITH_DOCTOR
        appointment.consultation_start = timezone.now()
        appointment.save(update_fields=[
            'status', 'consultation_start', 'updated_at',
        ])

        logger.info('Consultation started: %s', appointment.token_number)
        return appointment

    @staticmethod
    @transaction.atomic
    def complete_consultation(appointment):
        """
        Doctor completes consultation.
        Transition: WITH_DOCTOR → CONSULTATION_DONE
        """
        if appointment.status != AppointmentStatus.WITH_DOCTOR:
            raise InvalidTransitionError(
                f'Cannot complete consultation. Current status: {appointment.status}'
            )

        appointment.status = AppointmentStatus.CONSULTATION_DONE
        appointment.consultation_end = timezone.now()
        appointment.save(update_fields=[
            'status', 'consultation_end', 'updated_at',
        ])

        logger.info('Consultation completed: %s', appointment.token_number)
        return appointment

    @staticmethod
    @transaction.atomic
    def cancel_appointment(appointment, reason=''):
        """Cancel an appointment (before consultation starts)."""
        non_cancellable = [
            AppointmentStatus.WITH_DOCTOR,
            AppointmentStatus.CONSULTATION_DONE,
            AppointmentStatus.AT_PHARMACY,
            AppointmentStatus.DISPENSED,
            AppointmentStatus.COMPLETED,
            AppointmentStatus.CANCELLED,
        ]
        if appointment.status in non_cancellable:
            raise InvalidTransitionError(
                f'Cannot cancel. Current status: {appointment.status}'
            )

        appointment.status = AppointmentStatus.CANCELLED
        appointment.cancelled_reason = reason
        appointment.save(update_fields=[
            'status', 'cancelled_reason', 'updated_at',
        ])

        logger.info('Appointment cancelled: %s — %s', appointment.token_number, reason)
        return appointment

    @staticmethod
    @transaction.atomic
    def update_status(appointment, new_status, reason=''):
        """Generic status update with validation."""
        appointment.status = new_status
        if new_status == AppointmentStatus.CANCELLED:
            appointment.cancelled_reason = reason
        appointment.save(update_fields=['status', 'cancelled_reason', 'updated_at'])
        return appointment

    # ── Queue Management ─────────────────────────────────────────────

    @staticmethod
    def get_doctor_queue(doctor, appointment_date=None):
        """
        Get the ordered patient queue for a doctor on a given date.
        Returns appointments in queue order (priority + position).
        """
        if appointment_date is None:
            appointment_date = timezone.now().date()

        return Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appointment_date,
            status__in=[
                AppointmentStatus.CHECKED_IN,
                AppointmentStatus.VITALS_DONE,
                AppointmentStatus.WITH_DOCTOR,
            ],
        ).select_related('patient').order_by(
            '-priority',       # CRITICAL > SEVERE > MODERATE > MILD
            'queue_position',  # FIFO within same priority
        )

    @staticmethod
    def get_todays_appointments(doctor):
        """Get all of today's appointments for a doctor."""
        today = timezone.now().date()
        return Appointment.objects.filter(
            doctor=doctor,
            appointment_date=today,
        ).exclude(
            status=AppointmentStatus.CANCELLED,
        ).select_related('patient').order_by('time_slot')

    # ── Slot Availability ────────────────────────────────────────────

    @staticmethod
    def get_available_slots(doctor, target_date):
        """
        Get available time slots for a doctor on a given date.
        Returns list of {'time': HH:MM, 'available': int, 'total': int}
        """
        day_of_week = target_date.weekday()

        # Get doctor schedule for this day
        schedules = DoctorSchedule.objects.filter(
            doctor=doctor,
            day_of_week=day_of_week,
            is_active=True,
        )

        if not schedules.exists():
            return []

        slots = []
        for schedule in schedules:
            current = datetime.combine(target_date, schedule.start_time)
            end = datetime.combine(target_date, schedule.end_time)
            delta = timedelta(minutes=schedule.slot_duration_min)

            while current < end:
                slot_time = current.time()

                # Count booked appointments in this slot
                booked = Appointment.objects.filter(
                    doctor=doctor,
                    appointment_date=target_date,
                    time_slot=slot_time,
                ).exclude(
                    status=AppointmentStatus.CANCELLED,
                ).count()

                available = doctor.max_patients_per_slot - booked

                slots.append({
                    'time': slot_time.strftime('%H:%M'),
                    'available': max(0, available),
                    'total': doctor.max_patients_per_slot,
                    'booked': booked,
                    'is_available': available > 0,
                })

                current += delta

        return slots

    # ── Statistics ───────────────────────────────────────────────────

    @staticmethod
    def get_appointment_stats(doctor=None, date_from=None, date_to=None):
        """Get appointment statistics."""
        qs = Appointment.objects.all()

        if doctor:
            qs = qs.filter(doctor=doctor)
        if date_from:
            qs = qs.filter(appointment_date__gte=date_from)
        if date_to:
            qs = qs.filter(appointment_date__lte=date_to)

        from django.db.models import Count
        stats = qs.values('status').annotate(count=Count('id'))

        return {item['status']: item['count'] for item in stats}
