"""
Appointments App — Models
===========================
Department, DoctorProfile, DoctorSchedule, Appointment, Vitals

Key design decisions:
  • Appointment has token_number for queue management
  • Vitals is FK to Appointment (optional from appointment side)
  • DoctorProfile extends User with specialization, schedule, fee
  • Appointment status follows SDD Section 4.5 lifecycle
"""

import uuid
from datetime import date, time

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


# ─────────────────────────────────────────────────────────────────────
#  ENUMS / CHOICES
# ─────────────────────────────────────────────────────────────────────

class AppointmentStatus(models.TextChoices):
    """
    SDD Section 4.5 — Appointment Status Lifecycle.
    BOOKED → CHECKED_IN → VITALS_DONE → WITH_DOCTOR →
    CONSULTATION_DONE → AT_PHARMACY → DISPENSED → COMPLETED
    """
    BOOKED              = 'BOOKED',              'Booked'
    CHECKED_IN          = 'CHECKED_IN',          'Checked In'
    VITALS_DONE         = 'VITALS_DONE',         'Vitals Done'
    WITH_DOCTOR         = 'WITH_DOCTOR',         'With Doctor'
    CONSULTATION_DONE   = 'CONSULTATION_DONE',   'Consultation Done'
    AT_PHARMACY         = 'AT_PHARMACY',         'At Pharmacy'
    DISPENSED           = 'DISPENSED',            'Dispensed'
    COMPLETED           = 'COMPLETED',           'Completed'
    CANCELLED           = 'CANCELLED',           'Cancelled'
    NO_SHOW             = 'NO_SHOW',             'No Show'


class AppointmentType(models.TextChoices):
    BOOKED   = 'BOOKED',   'Pre-Booked'
    WALK_IN  = 'WALK_IN',  'Walk-In'


class DayOfWeek(models.IntegerChoices):
    MONDAY    = 0, 'Monday'
    TUESDAY   = 1, 'Tuesday'
    WEDNESDAY = 2, 'Wednesday'
    THURSDAY  = 3, 'Thursday'
    FRIDAY    = 4, 'Friday'
    SATURDAY  = 5, 'Saturday'
    SUNDAY    = 6, 'Sunday'


class Severity(models.TextChoices):
    MILD     = 'MILD',     'Mild'
    MODERATE = 'MODERATE', 'Moderate'
    SEVERE   = 'SEVERE',   'Severe'
    CRITICAL = 'CRITICAL', 'Critical'


# ─────────────────────────────────────────────────────────────────────
#  DEPARTMENT
# ─────────────────────────────────────────────────────────────────────

class Department(models.Model):
    """
    Hospital department / specialty.
    SDD Section 7.1 — DEPARTMENT entity.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon        = models.CharField(max_length=50, blank=True, help_text='Icon name or emoji')
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    # ── Organization (Multi-Tenant Ready) ────────────────────────────
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='departments',
        help_text='Organization this department belongs to.',
    )

    class Meta:
        db_table = 'departments'
        ordering = ['name']
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────────────────────────────
#  DOCTOR PROFILE
# ─────────────────────────────────────────────────────────────────────

class DoctorProfile(models.Model):
    """
    Extended profile for Doctor users.
    OneToOne with User (role=DOCTOR).
    SDD Section 7.1 — DOCTOR entity.
    """
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user            = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='doctor_profile',
        limit_choices_to={'role': 'DOCTOR'},
    )
    department      = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='doctors',
    )
    specialization  = models.CharField(max_length=200, blank=True)
    qualification   = models.CharField(max_length=300, blank=True)
    experience_years = models.PositiveIntegerField(default=0)
    consultation_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Consultation fee in INR.',
    )
    bio             = models.TextField(blank=True, help_text='Doctor bio for patient-facing profile.')
    rating          = models.DecimalField(
        max_digits=3, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )
    is_available    = models.BooleanField(default=True)
    max_patients_per_slot = models.PositiveIntegerField(
        default=1,
        help_text='Max concurrent patients per time slot.',
    )
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)
    # ── Organization (Multi-Tenant Ready) ────────────────────────────
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='doctor_profiles',
        help_text='Organization this doctor works for.',
    )

    class Meta:
        db_table = 'doctor_profiles'
        verbose_name = 'Doctor Profile'
        verbose_name_plural = 'Doctor Profiles'

    def __str__(self):
        return f'Dr. {self.user.full_name} — {self.specialization or "General"}'


# ─────────────────────────────────────────────────────────────────────
#  DOCTOR SCHEDULE
# ─────────────────────────────────────────────────────────────────────

class DoctorSchedule(models.Model):
    """
    Weekly recurring schedule for a doctor.
    SDD Section 7.1 — DOCTOR_SCHEDULE entity.
    """
    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor           = models.ForeignKey(
        DoctorProfile,
        on_delete=models.CASCADE,
        related_name='schedules',
    )
    day_of_week      = models.IntegerField(choices=DayOfWeek.choices)
    start_time       = models.TimeField()
    end_time         = models.TimeField()
    slot_duration_min = models.PositiveIntegerField(
        default=15,
        help_text='Duration of each slot in minutes.',
    )
    max_patients     = models.PositiveIntegerField(
        default=20,
        help_text='Maximum patients for this schedule block.',
    )
    is_active        = models.BooleanField(default=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'doctor_schedules'
        ordering = ['day_of_week', 'start_time']
        unique_together = ['doctor', 'day_of_week', 'start_time']
        verbose_name = 'Doctor Schedule'
        verbose_name_plural = 'Doctor Schedules'

    def __str__(self):
        day_name = DayOfWeek(self.day_of_week).label
        return f'{self.doctor.user.full_name} — {day_name} {self.start_time}-{self.end_time}'


# ─────────────────────────────────────────────────────────────────────
#  APPOINTMENT
# ─────────────────────────────────────────────────────────────────────

def generate_token_number(doctor, appointment_date):
    """
    Generate token number for queue management.
    Format: T-{sequence} per doctor per day.
    """
    count = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=appointment_date,
    ).exclude(
        status=AppointmentStatus.CANCELLED,
    ).count()
    return f'T-{count + 1:03d}'


class Appointment(models.Model):
    """
    Core appointment model linking patient ↔ doctor.

    SDD Section 7.1 — APPOINTMENT entity.
    Relations to prescription, vitals, medical_record, invoice
    are optional (null/blank) — not every visit creates all of them.

    Token number is used for queue management.
    """
    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Core relations
    patient          = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='patient_appointments',
        limit_choices_to={'role': 'PATIENT'},
    )
    doctor           = models.ForeignKey(
        DoctorProfile,
        on_delete=models.CASCADE,
        related_name='doctor_appointments',
    )

    # ── Organization (Multi-Tenant Ready) ────────────────────────────
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointments',
        help_text='Organization where this appointment is booked.',
    )

    # Scheduling
    appointment_date = models.DateField(db_index=True)
    time_slot        = models.TimeField()
    appointment_type = models.CharField(
        max_length=10,
        choices=AppointmentType.choices,
        default=AppointmentType.BOOKED,
    )

    # Queue management
    token_number     = models.CharField(
        max_length=10, blank=True,
        help_text='Queue token (e.g., T-042). Auto-generated.',
    )
    queue_position   = models.PositiveIntegerField(
        default=0,
        help_text='Current position in doctor queue.',
    )

    # Status lifecycle
    status           = models.CharField(
        max_length=20,
        choices=AppointmentStatus.choices,
        default=AppointmentStatus.BOOKED,
        db_index=True,
    )
    priority         = models.CharField(
        max_length=10,
        choices=Severity.choices,
        default=Severity.MILD,
        help_text='Triage priority. Higher priority = earlier in queue.',
    )

    # Visit details
    chief_complaint  = models.TextField(blank=True, help_text='Primary reason for visit.')
    notes            = models.TextField(blank=True, help_text='Additional notes from reception/nurse.')
    checked_in_at    = models.DateTimeField(null=True, blank=True)
    consultation_start = models.DateTimeField(null=True, blank=True)
    consultation_end = models.DateTimeField(null=True, blank=True)
    cancelled_reason = models.TextField(blank=True)

    # Timestamps
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'appointments'
        ordering = ['appointment_date', 'time_slot', 'queue_position']
        indexes = [
            models.Index(fields=['patient', 'status'], name='idx_appt_patient_status'),
            models.Index(fields=['doctor', 'appointment_date'], name='idx_appt_doctor_date'),
            models.Index(fields=['status', 'appointment_date'], name='idx_appt_status_date'),
            models.Index(fields=['token_number'], name='idx_appt_token'),
        ]
        verbose_name = 'Appointment'
        verbose_name_plural = 'Appointments'

    def __str__(self):
        return (
            f'{self.token_number} — {self.patient.full_name} with '
            f'Dr. {self.doctor.user.full_name} on {self.appointment_date}'
        )

    def save(self, *args, **kwargs):
        """Auto-generate token number on first save."""
        if not self.token_number:
            self.token_number = generate_token_number(
                self.doctor, self.appointment_date,
            )
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────
#  VITALS
# ─────────────────────────────────────────────────────────────────────

class Vitals(models.Model):
    """
    Patient vitals recorded by nurse during check-in.
    SDD Section 7.1 — VITALS entity.

    Linked to appointment (optional from appointment side — not every
    appointment has vitals, e.g., cancelled or no-show).
    """
    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment         = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name='vitals',
    )
    recorded_by         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_vitals',
        limit_choices_to={'role__in': ['NURSE', 'DOCTOR', 'ADMIN']},
    )

    # Blood Pressure
    blood_pressure_sys  = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(50), MaxValueValidator(300)],
        help_text='Systolic BP (mmHg)',
    )
    blood_pressure_dia  = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(30), MaxValueValidator(200)],
        help_text='Diastolic BP (mmHg)',
    )

    # Core vitals
    heart_rate          = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(30), MaxValueValidator(250)],
        help_text='Heart rate / Pulse (bpm)',
    )
    temperature         = models.DecimalField(
        max_digits=4, decimal_places=1,
        null=True, blank=True,
        help_text='Body temperature (°F)',
    )
    spo2                = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(50), MaxValueValidator(100)],
        help_text='Oxygen saturation (%)',
    )
    respiratory_rate    = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(5), MaxValueValidator(60)],
        help_text='Breaths per minute',
    )

    # Anthropometrics
    weight              = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text='Weight (kg)',
    )
    height              = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text='Height (cm)',
    )
    bmi                 = models.DecimalField(
        max_digits=4, decimal_places=1,
        null=True, blank=True,
        help_text='BMI (auto-calculated)',
    )

    # Optional
    blood_glucose       = models.DecimalField(
        max_digits=5, decimal_places=1,
        null=True, blank=True,
        help_text='Blood glucose (mg/dL)',
    )

    notes               = models.TextField(blank=True)
    recorded_at         = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'vitals'
        ordering = ['-recorded_at']
        verbose_name = 'Vitals'
        verbose_name_plural = 'Vitals'

    def __str__(self):
        return f'Vitals for {self.appointment} — BP: {self.blood_pressure_sys}/{self.blood_pressure_dia}'

    def save(self, *args, **kwargs):
        """Auto-calculate BMI if weight and height are provided."""
        if self.weight and self.height and self.height > 0:
            height_m = float(self.height) / 100
            self.bmi = round(float(self.weight) / (height_m ** 2), 1)
        super().save(*args, **kwargs)
