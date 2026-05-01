"""
Prescriptions App — Service Layer
====================================
Business logic for prescription creation, pharmacy queue,
dispensing workflow, and stock management.
"""

import logging
from django.db import models, transaction
from django.utils import timezone
from .models import (
    Prescription, PrescriptionItem, PrescriptionStatus,
    PharmacyOrder, Medicine,
)

logger = logging.getLogger('prescriptions')


class PrescriptionServiceError(Exception):
    pass


class InsufficientStockError(PrescriptionServiceError):
    pass


class PrescriptionService:
    """
    Business logic for the prescription → pharmacy workflow.
    """

    @staticmethod
    @transaction.atomic
    def create_prescription(doctor, patient, appointment=None,
                            diagnosis_summary='', notes='', items_data=None):
        """
        Create a prescription with items.
        Optionally linked to an appointment.
        """
        prescription = Prescription.objects.create(
            doctor=doctor,
            patient=patient,
            appointment=appointment,
            diagnosis_summary=diagnosis_summary,
            notes=notes,
        )

        if items_data:
            for item in items_data:
                PrescriptionItem.objects.create(
                    prescription=prescription,
                    **item,
                )

        logger.info(
            'Prescription created by Dr. %s for %s (%d items)',
            doctor.full_name, patient.full_name,
            len(items_data) if items_data else 0,
        )
        return prescription

    @staticmethod
    @transaction.atomic
    def send_to_pharmacy(prescription):
        """
        Send prescription to pharmacy queue.
        Creates a PharmacyOrder and updates prescription status.
        """
        if prescription.status != PrescriptionStatus.PENDING:
            raise PrescriptionServiceError(
                f'Cannot send to pharmacy. Current status: {prescription.status}'
            )

        # Calculate total from items
        total = sum(item.line_total for item in prescription.items.all())

        order = PharmacyOrder.objects.create(
            prescription=prescription,
            total_amount=total,
        )

        prescription.status = PrescriptionStatus.AT_PHARMACY
        prescription.save(update_fields=['status', 'updated_at'])

        # Update appointment status if linked
        if prescription.appointment:
            from appointments.models import AppointmentStatus
            appt = prescription.appointment
            if appt.status == 'CONSULTATION_DONE':
                appt.status = AppointmentStatus.AT_PHARMACY
                appt.save(update_fields=['status', 'updated_at'])

        logger.info('Prescription sent to pharmacy: %s', prescription.id)
        return order

    @staticmethod
    @transaction.atomic
    def dispense_order(order, dispensed_by, dispensed_items=None, notes=''):
        """
        Pharmacist dispenses medicines.
        Updates stock quantities and marks items as dispensed.
        """
        prescription = order.prescription

        # If specific items provided, mark only those
        items = prescription.items.all()
        if dispensed_items:
            items = items.filter(id__in=dispensed_items)

        for item in items:
            # Check stock
            medicine = item.medicine
            if medicine.stock_quantity < item.quantity:
                raise InsufficientStockError(
                    f'Insufficient stock for {medicine.name}. '
                    f'Available: {medicine.stock_quantity}, Required: {item.quantity}'
                )

            # Deduct stock
            medicine.stock_quantity -= item.quantity
            medicine.save(update_fields=['stock_quantity', 'updated_at'])

            # Mark as dispensed
            item.is_dispensed = True
            item.save(update_fields=['is_dispensed'])

        # Check if all items dispensed
        all_dispensed = not prescription.items.filter(is_dispensed=False).exists()
        some_dispensed = prescription.items.filter(is_dispensed=True).exists()

        if all_dispensed:
            prescription.status = PrescriptionStatus.DISPENSED
            order.status = PharmacyOrder.OrderStatus.DISPENSED
        elif some_dispensed:
            prescription.status = PrescriptionStatus.PARTIALLY_DISPENSED
            order.status = PharmacyOrder.OrderStatus.READY

        order.dispensed_by = dispensed_by
        order.dispensed_at = timezone.now()
        order.notes = notes
        order.save(update_fields=['dispensed_by', 'dispensed_at', 'status', 'notes', 'updated_at'])
        prescription.save(update_fields=['status', 'updated_at'])

        # Update appointment status if linked
        if all_dispensed and prescription.appointment:
            from appointments.models import AppointmentStatus
            appt = prescription.appointment
            if appt.status == 'AT_PHARMACY':
                appt.status = AppointmentStatus.DISPENSED
                appt.save(update_fields=['status', 'updated_at'])

        logger.info(
            'Order dispensed by %s: %s (%s)',
            dispensed_by.full_name, order.id,
            'fully' if all_dispensed else 'partially',
        )
        return order

    @staticmethod
    def get_pharmacy_queue():
        """Get pending pharmacy orders (sorted by priority)."""
        return PharmacyOrder.objects.filter(
            status__in=[
                PharmacyOrder.OrderStatus.QUEUED,
                PharmacyOrder.OrderStatus.PREPARING,
            ],
        ).select_related(
            'prescription__patient',
            'prescription__doctor',
        ).order_by('created_at')

    @staticmethod
    def get_low_stock_medicines():
        """Get medicines below reorder level."""
        return Medicine.objects.filter(
            is_active=True,
            stock_quantity__lte=models.F('reorder_level'),
        )

    @staticmethod
    def search_medicines(query):
        """Search medicines by name or generic name."""
        return Medicine.objects.filter(
            models.Q(name__icontains=query) |
            models.Q(generic_name__icontains=query),
            is_active=True,
        )[:20]
