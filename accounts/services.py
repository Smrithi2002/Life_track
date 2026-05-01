"""
MedConnect — OTP Service
===========================
Handles all OTP business logic:
  • Generate 6-digit OTP
  • SHA-256 hash before storage
  • Rate limiting (1/min, 5/hour)
  • Verification with max 3 attempts
  • 5-minute expiry
  • Invalidation after use

Security (per SDD Section 10.1):
  • OTP is NEVER stored in plain text
  • SHA-256 hashing before database storage
  • Constant-time comparison for verification
  • Automatic expiry after max attempts
"""

import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import OTP

logger = logging.getLogger('accounts')


class OTPServiceError(Exception):
    """Base exception for OTP service errors."""
    pass


class OTPRateLimitError(OTPServiceError):
    """Raised when OTP request is rate-limited."""
    pass


class OTPExpiredError(OTPServiceError):
    """Raised when OTP has expired."""
    pass


class OTPMaxAttemptsError(OTPServiceError):
    """Raised when max verification attempts exceeded."""
    pass


class OTPInvalidError(OTPServiceError):
    """Raised when OTP code is invalid."""
    pass


class OTPService:
    """
    OTP generation, hashing, storage, and verification service.

    Usage:
        service = OTPService()

        # Generate & send
        otp_record = service.generate_otp(phone='+919876543210')

        # Verify
        is_valid, otp_record = service.verify_otp(
            phone='+919876543210', otp_code='123456'
        )
    """

    def __init__(self):
        self.otp_length = getattr(settings, 'OTP_LENGTH', 6)
        self.expiry_minutes = getattr(settings, 'OTP_EXPIRY_MINUTES', 5)
        self.max_attempts = getattr(settings, 'OTP_MAX_ATTEMPTS', 3)
        self.cooldown_seconds = getattr(settings, 'OTP_COOLDOWN_SECONDS', 60)
        self.hourly_limit = getattr(settings, 'OTP_HOURLY_LIMIT', 5)

    # ── OTP Generation ───────────────────────────────────────────────

    def _generate_otp_code(self):
        """Generate a cryptographically secure N-digit OTP."""
        # secrets.randbelow is CSPRNG-based
        range_start = 10 ** (self.otp_length - 1)
        range_end = (10 ** self.otp_length) - 1
        return str(secrets.randbelow(range_end - range_start + 1) + range_start)

    @staticmethod
    def _hash_otp(otp_code):
        """
        SHA-256 hash the OTP code for secure storage.
        Uses the Django SECRET_KEY as a salt/key for HMAC.
        """
        return hmac.HMAC(
            key=settings.SECRET_KEY.encode('utf-8'),
            msg=otp_code.encode('utf-8'),
            digestmod=hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _verify_hash(otp_code, stored_hash):
        """
        Constant-time comparison of OTP hash.
        Prevents timing attacks.
        """
        computed = OTPService._hash_otp(otp_code)
        return hmac.compare_digest(computed, stored_hash)

    # ── Rate Limiting ────────────────────────────────────────────────

    def _check_rate_limit(self, phone):
        """
        Enforce rate limits:
          • 1 OTP per 60 seconds (cooldown)
          • 5 OTPs per hour (hourly cap)
        """
        now = timezone.now()

        # Check cooldown: last OTP sent within cooldown window?
        cooldown_cutoff = now - timedelta(seconds=self.cooldown_seconds)
        recent_otp = OTP.objects.filter(
            phone=phone,
            created_at__gte=cooldown_cutoff,
        ).exists()

        if recent_otp:
            wait_seconds = self.cooldown_seconds
            raise OTPRateLimitError(
                f'Please wait {wait_seconds} seconds before requesting a new OTP.'
            )

        # Check hourly limit
        hour_ago = now - timedelta(hours=1)
        hourly_count = OTP.objects.filter(
            phone=phone,
            created_at__gte=hour_ago,
        ).count()

        if hourly_count >= self.hourly_limit:
            raise OTPRateLimitError(
                f'Maximum {self.hourly_limit} OTP requests per hour exceeded. '
                f'Please try again later.'
            )

    # ── Generate OTP ────────────────────────────────────────────────

    def generate_otp(self, phone):
        """
        Generate a new OTP for the given phone number.

        Steps:
          1. Enforce rate limits
          2. Invalidate any existing active OTPs for this phone
          3. Generate new OTP code
          4. Hash and store in database
          5. Return (otp_record, plain_otp_code) for sending

        Returns:
            tuple: (OTP model instance, plain_text_otp_code)

        Raises:
            OTPRateLimitError: If rate limit exceeded
        """
        # Step 1: Rate limiting
        self._check_rate_limit(phone)

        # Step 2: Invalidate all existing active OTPs for this phone
        OTP.objects.filter(
            phone=phone,
            is_expired=False,
            is_verified=False,
        ).update(is_expired=True)

        # Step 3: Generate OTP code
        otp_code = self._generate_otp_code()

        # Step 4: Hash and store
        otp_hash = self._hash_otp(otp_code)
        expires_at = timezone.now() + timedelta(minutes=self.expiry_minutes)

        otp_record = OTP.objects.create(
            phone=phone,
            otp_hash=otp_hash,
            expires_at=expires_at,
        )

        logger.info(
            'OTP generated for %s (ID: %s, expires: %s)',
            phone, otp_record.id, expires_at,
        )

        # Step 5: Return record + plain code
        # In production, the plain code is sent via SMS gateway
        return otp_record, otp_code

    # ── Verify OTP ──────────────────────────────────────────────────

    def verify_otp(self, phone, otp_code):
        """
        Verify an OTP code for the given phone number.

        Steps:
          1. Find the latest active (non-expired, non-verified) OTP
          2. Check if expired by time
          3. Increment attempt counter
          4. Verify hash (constant-time)
          5. Mark as verified on success

        Returns:
            OTP: The verified OTP record

        Raises:
            OTPInvalidError: If no active OTP found or code is wrong
            OTPExpiredError: If OTP has expired
            OTPMaxAttemptsError: If max attempts exceeded
        """
        # Find latest active OTP for this phone
        otp_record = OTP.objects.filter(
            phone=phone,
            is_expired=False,
            is_verified=False,
        ).order_by('-created_at').first()

        if not otp_record:
            raise OTPInvalidError(
                'No active OTP found. Please request a new one.'
            )

        # Check time-based expiry
        if timezone.now() >= otp_record.expires_at:
            otp_record.is_expired = True
            otp_record.save(update_fields=['is_expired'])
            raise OTPExpiredError(
                'OTP has expired. Please request a new one.'
            )

        # Check max attempts
        if otp_record.attempts >= self.max_attempts:
            otp_record.is_expired = True
            otp_record.save(update_fields=['is_expired'])
            raise OTPMaxAttemptsError(
                f'Maximum {self.max_attempts} verification attempts exceeded. '
                f'Please request a new OTP.'
            )

        # Verify the OTP (constant-time hash comparison)
        if not self._verify_hash(otp_code, otp_record.otp_hash):
            # Increment failed attempt
            otp_record.increment_attempt()
            remaining = self.max_attempts - otp_record.attempts
            logger.warning(
                'Invalid OTP attempt for %s (attempt %d/%d)',
                phone, otp_record.attempts, self.max_attempts,
            )
            raise OTPInvalidError(
                f'Invalid OTP. {remaining} attempt(s) remaining.'
            )

        # OTP is valid — mark as verified
        otp_record.is_verified = True
        otp_record.is_expired = True  # One-time use
        otp_record.save(update_fields=['is_verified', 'is_expired'])

        logger.info('OTP verified successfully for %s', phone)
        return otp_record

    # ── Cleanup ─────────────────────────────────────────────────────

    @staticmethod
    def cleanup_expired_otps(days_old=7):
        """
        Delete OTP records older than `days_old` days.
        Intended for periodic cleanup (management command / celery task).
        """
        cutoff = timezone.now() - timedelta(days=days_old)
        deleted_count, _ = OTP.objects.filter(created_at__lt=cutoff).delete()
        logger.info('Cleaned up %d expired OTP records', deleted_count)
        return deleted_count

    # ── SMS Sending (stub) ──────────────────────────────────────────

    @staticmethod
    def send_otp_sms(phone, otp_code):
        """
        Send OTP via SMS gateway.

        TODO: Integrate with production SMS provider:
          - Twilio
          - MSG91
          - AWS SNS
          - Firebase Phone Auth

        For development, the OTP is logged to console.
        """
        if settings.DEBUG:
            logger.info(
                '[DEV SMS] OTP for %s: %s (DO NOT USE IN PRODUCTION)',
                phone, otp_code,
            )
            print(f'\n[DEV OTP] OTP for {phone}: {otp_code}\n')
        else:
            # Production SMS integration goes here
            logger.info('Sending OTP SMS to %s via production gateway', phone)
            # Example: twilio_client.messages.create(
            #     body=f'Your MedConnect OTP is: {otp_code}. Valid for 5 minutes.',
            #     from_=settings.TWILIO_PHONE_NUMBER,
            #     to=str(phone),
            # )
            raise NotImplementedError(
                'Production SMS gateway not configured. '
                'Set up Twilio/MSG91/AWS SNS.'
            )
