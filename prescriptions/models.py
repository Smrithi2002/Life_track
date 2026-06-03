"""
Prescriptions App — Models
============================
Medicine (catalog), Prescription, PrescriptionItem, PharmacyOrder

Key design:
  • Prescription FK to Appointment (optional — null/blank)
  • PrescriptionItem links to Medicine catalog
  • PharmacyOrder tracks dispensing workflow
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator


# ─────────────────────────────────────────────────────────────────────
#  ENUMS
# ─────────────────────────────────────────────────────────────────────

class PrescriptionStatus(models.TextChoices):
    PENDING             = 'PENDING',             'Pending'
    AT_PHARMACY         = 'AT_PHARMACY',         'At Pharmacy'
    PARTIALLY_DISPENSED = 'PARTIALLY_DISPENSED',  'Partially Dispensed'
    DISPENSED           = 'DISPENSED',            'Dispensed'
    CANCELLED           = 'CANCELLED',           'Cancelled'


class MedicineCategory(models.TextChoices):
    TABLET      = 'TABLET',      'Tablet'
    CAPSULE     = 'CAPSULE',     'Capsule'
    SYRUP       = 'SYRUP',       'Syrup'
    INJECTION   = 'INJECTION',   'Injection'
    CREAM       = 'CREAM',       'Cream/Ointment'
    DROPS       = 'DROPS',       'Drops'
    INHALER     = 'INHALER',     'Inhaler'
    POWDER      = 'POWDER',      'Powder'
    OTHER       = 'OTHER',       'Other'


class FrequencyChoices(models.TextChoices):
    OD   = 'OD',    'Once Daily'
    BD   = 'BD',    'Twice Daily'
    TDS  = 'TDS',   'Thrice Daily'
    QID  = 'QID',   'Four Times Daily'
    SOS  = 'SOS',   'As Needed'
    STAT = 'STAT',  'Immediately'
    HS   = 'HS',    'At Bedtime'
    AC   = 'AC',    'Before Meals'
    PC   = 'PC',    'After Meals'


# ─────────────────────────────────────────────────────────────────────
#  MEDICINE CATALOG
# ─────────────────────────────────────────────────────────────────────

class Medicine(models.Model):
    """
    Master medicine catalog.
    SDD Section 7.1 — MEDICINE entity.
    """
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name            = models.CharField(max_length=255, db_index=True)
    generic_name    = models.CharField(max_length=255, blank=True)
    category        = models.CharField(
        max_length=20,
        choices=MedicineCategory.choices,
        default=MedicineCategory.TABLET,
    )
    manufacturer    = models.CharField(max_length=255, blank=True)
    strength        = models.CharField(
        max_length=50, blank=True,
        help_text='E.g., 500mg, 250mg/5ml',
    )
    unit_price      = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )
    stock_quantity  = models.PositiveIntegerField(default=0)
    reorder_level   = models.PositiveIntegerField(
        default=10,
        help_text='Alert when stock falls below this level.',
    )
    expiry_date     = models.DateField(null=True, blank=True)
    description     = models.TextField(blank=True)
    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)
    # ── Organization (Multi-Tenant Ready) ────────────────────────────
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='medicines',
        help_text='Organization-specific medicine catalog entry.',
    )

    class Meta:
        db_table = 'medicines'
        ordering = ['name']
        verbose_name = 'Medicine'
        verbose_name_plural = 'Medicines'
        indexes = [
            models.Index(fields=['name', 'generic_name'], name='idx_med_name_generic'),
            models.Index(fields=['category'], name='idx_med_category'),
        ]

    def __str__(self):
        strength = f' ({self.strength})' if self.strength else ''
        return f'{self.name}{strength} — {self.get_category_display()}'

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.reorder_level

    @property
    def is_expired(self):
        if self.expiry_date:
            return self.expiry_date < timezone.now().date()
        return False


# ─────────────────────────────────────────────────────────────────────
#  PRESCRIPTION
# ─────────────────────────────────────────────────────────────────────

class Prescription(models.Model):
    """
    Doctor's prescription linked to an appointment.
    SDD Section 7.1 — PRESCRIPTION entity.

    FK to Appointment is optional (null/blank) — allows standalone
    prescriptions for follow-ups or external references.
    """
    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment   = models.ForeignKey(
        'appointments.Appointment',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='prescriptions',
        help_text='Optional — not every prescription comes from an appointment.',
    )
    doctor        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='prescribed_by',
        limit_choices_to={'role': 'DOCTOR'},
    )
    patient       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='patient_prescriptions',
        limit_choices_to={'role': 'PATIENT'},
    )
    status        = models.CharField(
        max_length=25,
        choices=PrescriptionStatus.choices,
        default=PrescriptionStatus.PENDING,
        db_index=True,
    )
    diagnosis_summary = models.TextField(
        blank=True,
        help_text='Brief diagnosis for pharmacy reference.',
    )
    notes         = models.TextField(blank=True, help_text='Doctor notes / instructions.')
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)
    # ── Organization (Multi-Tenant Ready) ────────────────────────────
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prescriptions',
        help_text='Organization where this prescription was issued.',
    )

    class Meta:
        db_table = 'prescriptions'
        ordering = ['-created_at']
        verbose_name = 'Prescription'
        verbose_name_plural = 'Prescriptions'
        indexes = [
            models.Index(fields=['patient', 'status'], name='idx_rx_patient_status'),
            models.Index(fields=['doctor', 'created_at'], name='idx_rx_doctor_date'),
        ]

    def __str__(self):
        return f'Rx by Dr. {self.doctor.full_name} for {self.patient.full_name}'

    @property
    def item_count(self):
        return self.items.count()

    @property
    def total_cost(self):
        return sum(item.line_total for item in self.items.all())


# ─────────────────────────────────────────────────────────────────────
#  PRESCRIPTION ITEM
# ─────────────────────────────────────────────────────────────────────

class PrescriptionItem(models.Model):
    """
    Individual medicine entry in a prescription.
    SDD Section 7.1 — PRESCRIPTION_ITEM entity.
    """
    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prescription   = models.ForeignKey(
        Prescription,
        on_delete=models.CASCADE,
        related_name='items',
    )
    medicine       = models.ForeignKey(
        Medicine,
        on_delete=models.PROTECT,
        related_name='prescription_items',
    )
    dosage         = models.CharField(
        max_length=100,
        help_text='E.g., 1 tablet, 5ml, 2 puffs',
    )
    frequency      = models.CharField(
        max_length=10,
        choices=FrequencyChoices.choices,
        default=FrequencyChoices.OD,
    )
    duration_days  = models.PositiveIntegerField(
        default=7,
        help_text='Number of days.',
    )
    quantity       = models.PositiveIntegerField(
        default=1,
        help_text='Total quantity to dispense.',
    )
    instructions   = models.TextField(
        blank=True,
        help_text='Special instructions (take with food, etc.)',
    )
    is_dispensed   = models.BooleanField(default=False)

    class Meta:
        db_table = 'prescription_items'
        verbose_name = 'Prescription Item'
        verbose_name_plural = 'Prescription Items'

    def __str__(self):
        return f'{self.medicine.name} — {self.dosage} x {self.get_frequency_display()}'

    @property
    def line_total(self):
        return self.medicine.unit_price * self.quantity


# ─────────────────────────────────────────────────────────────────────
#  PHARMACY ORDER
# ─────────────────────────────────────────────────────────────────────

class PharmacyOrder(models.Model):
    """
    Pharmacy dispensing record for a prescription.
    SDD Section 7.1 — PHARMACY_ORDER entity.
    """

    class OrderStatus(models.TextChoices):
        QUEUED    = 'QUEUED',    'Queued'
        PREPARING = 'PREPARING', 'Preparing'
        READY     = 'READY',     'Ready for Pickup'
        DISPENSED = 'DISPENSED',  'Dispensed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prescription    = models.OneToOneField(
        Prescription,
        on_delete=models.CASCADE,
        related_name='pharmacy_order',
    )
    dispensed_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='dispensed_orders',
        limit_choices_to={'role__in': ['PHARMACIST', 'ADMIN']},
    )
    status          = models.CharField(
        max_length=15,
        choices=OrderStatus.choices,
        default=OrderStatus.QUEUED,
    )
    total_amount    = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
    )
    notes           = models.TextField(blank=True)
    dispensed_at    = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pharmacy_orders'
        ordering = ['-created_at']
        verbose_name = 'Pharmacy Order'
        verbose_name_plural = 'Pharmacy Orders'

    def __str__(self):
        return f'PharmOrder for {self.prescription} — {self.status}'
