"""
HealthCard Models
==================
HealthCard  — patient can have multiple cards (renewal/lost/reissue), one active at a time
CardScanLog — audit trail of every QR scan
"""

import uuid
import qrcode
import io

from django.db import models
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone


class HealthCard(models.Model):
    """
    A physical health card issued to a patient.
    ForeignKey (not OneToOne) — patient can have multiple cards over time.
    Only one should be is_active=True at any time.
    """

    class CardStatus(models.TextChoices):
        ACTIVE   = 'ACTIVE',   'Active'
        EXPIRED  = 'EXPIRED',  'Expired'
        LOST     = 'LOST',     'Lost / Reported'
        REPLACED = 'REPLACED', 'Replaced'

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='health_cards',
        limit_choices_to={'role': 'PATIENT'},
    )
    # Card number mirrors the patient's user_id for easy lookup
    card_number   = models.CharField(max_length=30, unique=True, db_index=True)
    qr_code_image = models.ImageField(upload_to='healthcards/qr/', blank=True, null=True)
    status        = models.CharField(max_length=10, choices=CardStatus.choices, default=CardStatus.ACTIVE)
    is_active     = models.BooleanField(default=True, db_index=True)
    is_elite      = models.BooleanField(default=False, help_text='True if the patient purchased the Elite card.')

    issued_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='issued_cards',
    )
    issued_date   = models.DateField(default=timezone.now)
    expiry_date   = models.DateField(null=True, blank=True)
    notes         = models.TextField(blank=True)

    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Health Card'
        verbose_name_plural = 'Health Cards'

    def __str__(self):
        return f'{self.card_number} — {self.patient.full_name} ({self.status})'

    def generate_qr_code(self):
        """Generate and save QR code image encoding the card_number (= user_id)."""
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(self.card_number)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        filename = f'qr_{self.card_number}.png'
        self.qr_code_image.save(filename, ContentFile(buffer.getvalue()), save=False)

    def deactivate(self, reason: str = ''):
        """Deactivate this card (lost, replaced, expired)."""
        self.is_active = False
        self.status = reason or self.CardStatus.EXPIRED
        self.save(update_fields=['is_active', 'status', 'updated_at'])

    def save(self, *args, **kwargs):
        # Auto-set card_number from patient user_id on first save
        if not self.card_number and self.patient_id:
            from accounts.models import User
            try:
                patient = User.objects.get(pk=self.patient_id)
                self.card_number = patient.user_id
            except User.DoesNotExist:
                pass
        super().save(*args, **kwargs)


class CardScanLog(models.Model):
    """
    Audit trail — every time a health card QR is scanned.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    card        = models.ForeignKey(
        HealthCard,
        on_delete=models.CASCADE,
        related_name='scan_logs',
    )
    scanned_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='card_scans',
    )
    department  = models.CharField(max_length=100, blank=True)
    purpose     = models.CharField(
        max_length=50,
        choices=[
            ('APPOINTMENT', 'Appointment'),
            ('CONSULTATION', 'Consultation'),
            ('PHARMACY', 'Pharmacy'),
            ('BILLING', 'Billing'),
            ('GENERAL', 'General Lookup'),
        ],
        default='GENERAL',
    )
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    device_info = models.CharField(max_length=255, blank=True)
    timestamp   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Card Scan Log'
        verbose_name_plural = 'Card Scan Logs'

    def __str__(self):
        return f'{self.card.card_number} scanned by {self.scanned_by} at {self.timestamp}'
