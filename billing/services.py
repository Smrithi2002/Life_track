"""Billing App — Service Layer"""
import logging
from django.db import transaction
from django.utils import timezone
from .models import Invoice, InvoiceItem, Payment, PaymentStatus

logger = logging.getLogger('billing')


class BillingService:

    @staticmethod
    @transaction.atomic
    def create_invoice(patient, created_by, appointment=None,
                       items_data=None, tax_amount=0, discount=0, notes=''):
        invoice = Invoice.objects.create(
            patient=patient,
            created_by=created_by,
            appointment=appointment,
            tax_amount=tax_amount,
            discount=discount,
            notes=notes,
        )
        if items_data:
            for item in items_data:
                InvoiceItem.objects.create(invoice=invoice, **item)
        invoice.recalculate_totals()
        logger.info('Invoice created: %s for %s', invoice.invoice_number, patient.full_name)
        return invoice

    @staticmethod
    @transaction.atomic
    def record_payment(invoice, amount, payment_method, gateway_txn_id=''):
        payment = Payment.objects.create(
            invoice=invoice,
            amount=amount,
            payment_method=payment_method,
            gateway_txn_id=gateway_txn_id,
            status=PaymentStatus.COMPLETED,
            paid_at=timezone.now(),
        )
        total_paid = sum(p.amount for p in invoice.payments.filter(status=PaymentStatus.COMPLETED))
        if total_paid >= invoice.total_amount:
            invoice.payment_status = PaymentStatus.COMPLETED
        elif total_paid > 0:
            invoice.payment_status = PaymentStatus.PARTIAL
        invoice.save(update_fields=['payment_status', 'updated_at'])

        if invoice.appointment and invoice.payment_status == PaymentStatus.COMPLETED:
            from appointments.models import AppointmentStatus
            appt = invoice.appointment
            if appt.status in ['DISPENSED', 'CONSULTATION_DONE']:
                appt.status = AppointmentStatus.COMPLETED
                appt.save(update_fields=['status', 'updated_at'])

        logger.info('Payment recorded: ₹%s for %s', amount, invoice.invoice_number)
        return payment
