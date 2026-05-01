"""
HealthCard Service
"""
from django.utils import timezone
from .models import HealthCard, CardScanLog


class HealthCardService:

    @staticmethod
    def issue_card(patient, issued_by, expiry_date=None, notes=''):
        """
        Deactivate any existing active cards, then issue a new one.
        Generates QR code automatically.
        """
        # Deactivate existing active cards
        HealthCard.objects.filter(patient=patient, is_active=True).update(
            is_active=False, status=HealthCard.CardStatus.REPLACED
        )

        card = HealthCard(
            patient=patient,
            issued_by=issued_by,
            expiry_date=expiry_date,
            notes=notes,
        )
        # card_number will be set in save() from patient.user_id
        card.save()

        # Generate and save QR code
        card.generate_qr_code()
        card.save()

        return card

    @staticmethod
    def lookup_by_card_number(card_number):
        """Find the active card by card_number (= user_id)."""
        return HealthCard.objects.filter(
            card_number=card_number,
            is_active=True,
        ).select_related('patient').first()

    @staticmethod
    def log_scan(card, scanned_by, request, purpose='GENERAL', department=''):
        """Record an audit log entry for a QR scan."""
        ip = (
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            or request.META.get('REMOTE_ADDR')
        )
        return CardScanLog.objects.create(
            card=card,
            scanned_by=scanned_by,
            department=department,
            purpose=purpose,
            ip_address=ip or None,
            device_info=request.META.get('HTTP_USER_AGENT', '')[:255],
        )

    @staticmethod
    def report_lost(card_number, reported_by):
        """Mark card as lost."""
        card = HealthCard.objects.filter(card_number=card_number, is_active=True).first()
        if card:
            card.deactivate(reason=HealthCard.CardStatus.LOST)
        return card

    @staticmethod
    def get_patient_cards(patient):
        return HealthCard.objects.filter(patient=patient).order_by('-created_at')
