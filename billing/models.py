"""
Billing App — Models
======================
Invoice, InvoiceItem, Payment

Key design:
  • Invoice FK to Appointment (optional — null/blank)
  • InvoiceItem for line-item breakdown
  • Payment tracks gateway transactions
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator


class PaymentStatus(models.TextChoices):
    PENDING   = 'PENDING',   'Pending'
    COMPLETED = 'COMPLETED', 'Completed'
    FAILED    = 'FAILED',    'Failed'
    REFUNDED  = 'REFUNDED',  'Refunded'
    PARTIAL   = 'PARTIAL',   'Partial'


class PaymentMethod(models.TextChoices):
    UPI         = 'UPI',         'UPI'
    CREDIT_CARD = 'CREDIT_CARD', 'Credit Card'
    DEBIT_CARD  = 'DEBIT_CARD',  'Debit Card'
    NET_BANKING = 'NET_BANKING', 'Net Banking'
    WALLET      = 'WALLET',      'Digital Wallet'
    CASH        = 'CASH',        'Cash'
    INSURANCE   = 'INSURANCE',   'Insurance'


class PaymentChannel(models.TextChoices):
    COUNTER = 'COUNTER', 'Counter'
    ONLINE  = 'ONLINE',  'Online'


class InvoiceItemType(models.TextChoices):
    CONSULTATION = 'CONSULTATION', 'Consultation Fee'
    MEDICINE     = 'MEDICINE',     'Medicine'
    LAB_TEST     = 'LAB_TEST',     'Lab Test'
    PROCEDURE    = 'PROCEDURE',    'Procedure'
    SERVICE      = 'SERVICE',      'Service Charge'
    OTHER        = 'OTHER',        'Other'


class Invoice(models.Model):
    """
    Consolidated bill for a hospital visit.
    SDD Section 7.1 — PAYMENT entity.
    FK to Appointment is optional.
    """
    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(
        max_length=30, unique=True, db_index=True,
        help_text='Auto-generated invoice number.',
    )
    appointment   = models.ForeignKey(
        'appointments.Appointment',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoices',
    )
    patient       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='patient_invoices',
        limit_choices_to={'role': 'PATIENT'},
    )
    created_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_invoices',
    )

    # Amounts
    subtotal      = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount  = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Status
    payment_status = models.CharField(
        max_length=15,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )
    notes         = models.TextField(blank=True)
    due_date      = models.DateField(null=True, blank=True)

    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'invoices'
        ordering = ['-created_at']
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'

    def __str__(self):
        return f'{self.invoice_number} — {self.patient.full_name} (₹{self.total_amount})'

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self._generate_invoice_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_invoice_number():
        from datetime import datetime
        year = datetime.now().year
        count = Invoice.objects.filter(
            created_at__year=year,
        ).count() + 1
        return f'INV-{year}-{count:05d}'

    def recalculate_totals(self):
        """Recalculate from line items."""
        self.subtotal = sum(item.total for item in self.items.all())
        self.total_amount = self.subtotal + self.tax_amount - self.discount
        self.save(update_fields=['subtotal', 'total_amount', 'updated_at'])


class InvoiceItem(models.Model):
    """Line item in an invoice."""
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice     = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    item_type   = models.CharField(max_length=15, choices=InvoiceItemType.choices)
    description = models.CharField(max_length=255)
    quantity    = models.PositiveIntegerField(default=1)
    unit_price  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total       = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        db_table = 'invoice_items'

    def __str__(self):
        return f'{self.description} — ₹{self.total}'

    def save(self, *args, **kwargs):
        self.total = self.unit_price * self.quantity
        super().save(*args, **kwargs)


class Payment(models.Model):
    """
    Payment transaction record.
    SDD Section 7.1 — PAYMENT entity.
    """
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice         = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount          = models.DecimalField(max_digits=12, decimal_places=2)
    payment_channel = models.CharField(
        max_length=15,
        choices=PaymentChannel.choices,
        default=PaymentChannel.COUNTER,
    )
    payment_method  = models.CharField(max_length=15, choices=PaymentMethod.choices)
    gateway_txn_id  = models.CharField(max_length=255, blank=True, help_text='Payment gateway transaction ID.')
    razorpay_order_id = models.CharField(max_length=255, blank=True, help_text='Razorpay Order ID.')
    status          = models.CharField(max_length=15, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    receipt_url     = models.URLField(blank=True)
    paid_at         = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']

    def __str__(self):
        return f'Payment ₹{self.amount} for {self.invoice.invoice_number} ({self.status})'
