"""
MedConnect — Custom User Model
================================
Custom user model with:
  • Role-based access (Patient, Doctor, Nurse, Pharmacist, Reception, Admin)
  • Auto-generated User IDs (MC-PAT-2026-00001 format)
  • OTP-based authentication for patients
  • Username/Password authentication for staff & admin
  • Profile fields per SDD Section 7.1 (USERS entity)
"""

import uuid
from datetime import datetime
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
from phonenumber_field.modelfields import PhoneNumberField


# ─────────────────────────────────────────────────────────────────────
#  ENUMS / CHOICES  (SDD Section 7.3)
# ─────────────────────────────────────────────────────────────────────

class UserRole(models.TextChoices):
    """
    Maps to SDD enum: UserRole
    PATIENT | DOCTOR | NURSE | PHARMACIST | RECEPTION | ADMIN
    """
    PATIENT     = 'PATIENT',     'Patient'
    DOCTOR      = 'DOCTOR',      'Doctor'
    NURSE       = 'NURSE',       'Nurse'
    PHARMACIST  = 'PHARMACIST',  'Pharmacist'
    RECEPTION   = 'RECEPTION',   'Reception'
    ADMIN       = 'ADMIN',       'Admin'


class Gender(models.TextChoices):
    """
    Maps to SDD enum: Gender
    MALE | FEMALE | OTHER
    """
    MALE   = 'MALE',   'Male'
    FEMALE = 'FEMALE', 'Female'
    OTHER  = 'OTHER',  'Other'


class BloodGroup(models.TextChoices):
    """Blood group choices for health card / profile."""
    A_POSITIVE   = 'A+',  'A+'
    A_NEGATIVE   = 'A-',  'A-'
    B_POSITIVE   = 'B+',  'B+'
    B_NEGATIVE   = 'B-',  'B-'
    AB_POSITIVE  = 'AB+', 'AB+'
    AB_NEGATIVE  = 'AB-', 'AB-'
    O_POSITIVE   = 'O+',  'O+'
    O_NEGATIVE   = 'O-',  'O-'


# ─────────────────────────────────────────────────────────────────────
#  AUTO USER-ID GENERATION
# ─────────────────────────────────────────────────────────────────────

# Role-to-prefix mapping for auto-generated user IDs
ROLE_PREFIX_MAP = {
    'PATIENT':     'PAT',
    'DOCTOR':      'DOC',
    'NURSE':       'NUR',
    'PHARMACIST':  'PHR',
    'RECEPTION':   'REC',
    'ADMIN':       'ADM',
}


def generate_user_id(role):
    """
    Generate a unique User ID based on role and current year.
    Format:  MC-{ROLE_PREFIX}-{YEAR}-{SEQUENCE:05d}
    Example: MC-PAT-2026-00001, MC-DOC-2026-00015

    Per SDD Section 4.1 — Patient ID: MC-PAT-2026-00001
    """
    prefix = ROLE_PREFIX_MAP.get(role, 'USR')
    year = datetime.now().year

    # Find the last user_id with this prefix+year pattern
    pattern = f'MC-{prefix}-{year}-'
    last_user = User.objects.filter(
        user_id__startswith=pattern
    ).order_by('-user_id').first()

    if last_user and last_user.user_id:
        try:
            last_seq = int(last_user.user_id.split('-')[-1])
            next_seq = last_seq + 1
        except (ValueError, IndexError):
            next_seq = 1
    else:
        next_seq = 1

    return f'MC-{prefix}-{year}-{next_seq:05d}'


# ─────────────────────────────────────────────────────────────────────
#  CUSTOM USER MANAGER
# ─────────────────────────────────────────────────────────────────────

class UserManager(BaseUserManager):
    """
    Custom manager for the User model.

    All users authenticate via user_id + password.
    The user_id is auto-generated during registration.
    """

    def create_user(self, phone, role=UserRole.PATIENT, password=None, **extra_fields):
        """
        Create and return a user.
        All users login with auto-generated user_id + password.
        """
        if not phone:
            raise ValueError('Phone number is required for registration.')

        if not password:
            raise ValueError('Password is required for all users.')

        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)

        user = self.model(phone=phone, role=role, **extra_fields)

        # Auto-generate user_id if not provided
        if not user.user_id:
            user.user_id = generate_user_id(role)

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_staffuser(self, phone, password, role, **extra_fields):
        """
        Create and return a staff user (Doctor/Nurse/Pharmacist/Reception).
        Staff users require a password for web dashboard login.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', False)

        if not password:
            raise ValueError('Staff users must have a password.')

        return self.create_user(
            phone=phone,
            role=role,
            password=password,
            **extra_fields,
        )

    def create_superuser(self, phone, password, username=None, **extra_fields):
        """Create and return a superuser (Admin)."""
        if not username:
            raise ValueError("Admin must have a username")

        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        user = self.model(
            phone=phone,
            username=username,
            role=UserRole.ADMIN,
            **extra_fields,
        )

        # Auto-generate user_id
        user.user_id = generate_user_id(UserRole.ADMIN)

        user.set_password(password)
        user.save(using=self._db)
        return user


# ─────────────────────────────────────────────────────────────────────
#  CUSTOM USER MODEL  (SDD Section 7.1 — USERS entity)
# ─────────────────────────────────────────────────────────────────────

class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model for the MedConnect Digital Healthcare Platform.

    Authentication:
      - Patients:    Phone + OTP (passwordless)
      - Staff:       Username + Password (web dashboard)
      - Admin:       Username + Password (superuser)

    Auto-generated IDs:
      - MC-PAT-2026-00001 (Patient)
      - MC-DOC-2026-00001 (Doctor)
      - MC-NUR-2026-00001 (Nurse)
      - MC-PHR-2026-00001 (Pharmacist)
      - MC-REC-2026-00001 (Reception)
      - MC-ADM-2026-00001 (Admin)
    """

    # ── Primary Key ──────────────────────────────────────────────────
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Internal UUID primary key.',
    )

    # ── Auto-Generated User ID ───────────────────────────────────────
    user_id = models.CharField(
        max_length=25,
        unique=True,
        blank=True,
        db_index=True,
        help_text='Auto-generated user ID. Format: MC-PAT-2026-00001',
    )

    # ── Username (for staff/admin login) ─────────────────────────────
    username = models.CharField(
        max_length=150,
        unique=True,
        null=True,
        blank=True,
        help_text='Username for admin/staff dashboard login.',
    )

    # ── Authentication Fields ────────────────────────────────────────
    phone = PhoneNumberField(
        unique=True,
        help_text='Primary phone number for login & OTP verification. '
                  'Format: +919876543210',
    )

    email = models.EmailField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        help_text='Optional email address for notifications.',
    )

    # ── Role ─────────────────────────────────────────────────────────
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.PATIENT,
        db_index=True,
        help_text='User role determines RBAC permissions. '
                  'Ref: SDD Section 10.1 Permission Matrix.',
    )

    # ── Profile Information ──────────────────────────────────────────
    full_name = models.CharField(
        max_length=255,
        help_text='Full name of the user (First + Last).',
    )

    date_of_birth = models.DateField(
        blank=True,
        null=True,
        help_text='Date of birth for age calculation & patient records.',
    )

    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        blank=True,
        help_text='Gender: MALE | FEMALE | OTHER.',
    )

    blood_group = models.CharField(
        max_length=5,
        choices=BloodGroup.choices,
        blank=True,
        help_text='Blood group (displayed on Health Card).',
    )

    avatar = models.ImageField(
        upload_to='avatars/%Y/%m/',
        blank=True,
        null=True,
        help_text='Profile photo. Stored in S3/media in production.',
    )

    # ── Address ──────────────────────────────────────────────────────
    address_line_1 = models.CharField(
        max_length=255,
        blank=True,
        help_text='Street address line 1.',
    )

    address_line_2 = models.CharField(
        max_length=255,
        blank=True,
        help_text='Street address line 2 (apartment, suite, etc.).',
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        help_text='City name.',
    )

    state = models.CharField(
        max_length=100,
        blank=True,
        help_text='State / Province.',
    )

    pincode = models.CharField(
        max_length=10,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\d{5,10}$',
                message='Pincode must be between 5 to 10 digits.',
            )
        ],
        help_text='ZIP / Postal code.',
    )

    # ── Emergency Contact ────────────────────────────────────────────
    emergency_contact_name = models.CharField(
        max_length=255,
        blank=True,
        help_text='Name of emergency contact person.',
    )

    emergency_contact_phone = PhoneNumberField(
        blank=True,
        null=True,
        help_text='Emergency contact phone number.',
    )

    emergency_contact_relation = models.CharField(
        max_length=50,
        blank=True,
        help_text='Relationship with emergency contact (e.g., Spouse, Parent).',
    )

    # ── Medical Quick-Info ───────────────────────────────────────────
    known_allergies = models.TextField(
        blank=True,
        help_text='Comma-separated list of known allergies.',
    )

    existing_conditions = models.TextField(
        blank=True,
        help_text='Comma-separated list of pre-existing medical conditions.',
    )

    insurance_provider = models.CharField(
        max_length=255,
        blank=True,
        help_text='Name of insurance provider.',
    )

    insurance_policy_number = models.CharField(
        max_length=100,
        blank=True,
        help_text='Insurance policy number.',
    )

    # ── Status & Permissions ─────────────────────────────────────────
    is_active = models.BooleanField(
        default=True,
        help_text='Designates whether this user account is active. '
                  'Deactivate instead of deleting accounts.',
    )

    is_staff = models.BooleanField(
        default=False,
        help_text='Designates whether user can access the Django admin site.',
    )

    is_phone_verified = models.BooleanField(
        default=False,
        help_text='Set to True after successful OTP verification.',
    )

    is_email_verified = models.BooleanField(
        default=False,
        help_text='Set to True after email verification.',
    )

    is_profile_complete = models.BooleanField(
        default=False,
        help_text='True when user has completed all required profile fields. '
                  'Used in SDD API response: isProfileComplete.',
    )

    # ── FCM / Push Notification ──────────────────────────────────────
    fcm_token = models.CharField(
        max_length=512,
        blank=True,
        help_text='Firebase Cloud Messaging device token for push notifications.',
    )

    # ── Timestamps ───────────────────────────────────────────────────
    date_joined = models.DateTimeField(
        default=timezone.now,
        help_text='Timestamp of user registration.',
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text='Last profile update timestamp.',
    )

    last_login = models.DateTimeField(
        blank=True,
        null=True,
        help_text='Last successful login timestamp.',
    )

    # ── Manager ──────────────────────────────────────────────────────
    objects = UserManager()

    # ── Auth Configuration ───────────────────────────────────────────
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['phone', 'full_name']

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['phone'], name='idx_user_phone'),
            models.Index(fields=['email'], name='idx_user_email'),
            models.Index(fields=['role'], name='idx_user_role'),
            models.Index(fields=['user_id'], name='idx_user_user_id'),
            models.Index(fields=['is_active', 'role'], name='idx_user_active_role'),
        ]

    def __str__(self):
        return f'{self.user_id} — {self.full_name} ({self.get_role_display()})'

    def save(self, *args, **kwargs):
        """Override save to auto-generate user_id if not set."""
        if not self.user_id:
            self.user_id = generate_user_id(self.role)
        super().save(*args, **kwargs)

    # ── Computed Properties ──────────────────────────────────────────

    @property
    def age(self):
        """Calculate age from date_of_birth."""
        if self.date_of_birth:
            today = timezone.now().date()
            dob = self.date_of_birth
            return today.year - dob.year - (
                (today.month, today.day) < (dob.month, dob.day)
            )
        return None

    @property
    def is_patient(self):
        return self.role == UserRole.PATIENT

    @property
    def is_doctor(self):
        return self.role == UserRole.DOCTOR

    @property
    def is_nurse(self):
        return self.role == UserRole.NURSE

    @property
    def is_pharmacist(self):
        return self.role == UserRole.PHARMACIST

    @property
    def is_reception(self):
        return self.role == UserRole.RECEPTION

    @property
    def is_admin_user(self):
        return self.role == UserRole.ADMIN

    def get_full_address(self):
        """Return formatted full address string."""
        parts = filter(None, [
            self.address_line_1,
            self.address_line_2,
            self.city,
            self.state,
            self.pincode,
        ])
        return ', '.join(parts)

    def check_profile_completeness(self):
        """
        Check if patient has completed all required profile fields.
        Updates is_profile_complete flag.

        Required fields per SDD 4.1 Patient Registration Flow:
        Full Name, DOB, Gender, Blood Group, Address, Emergency Contact
        """
        required_fields_filled = all([
            self.full_name,
            self.date_of_birth,
            self.gender,
            self.blood_group,
            self.address_line_1,
            self.city,
            self.emergency_contact_name,
            self.emergency_contact_phone,
        ])
        if self.is_profile_complete != required_fields_filled:
            self.is_profile_complete = required_fields_filled
            self.save(update_fields=['is_profile_complete', 'updated_at'])
        return self.is_profile_complete


# ─────────────────────────────────────────────────────────────────────
#  OTP MODEL  (SDD Section 10.1 — OTP Security)
# ─────────────────────────────────────────────────────────────────────

class OTP(models.Model):
    """
    Stores OTP records for phone-based authentication.

    Security (per SDD Section 10.1):
      • 6-digit numeric OTP
      • SHA-256 hashed before storage (handled in service layer)
      • 5-minute expiry
      • Max 3 verification attempts
      • Rate limited: 1 per 60s, max 5 per hour
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    phone = PhoneNumberField(
        db_index=True,
        help_text='Phone number the OTP was sent to.',
    )

    otp_hash = models.CharField(
        max_length=128,
        help_text='SHA-256 hashed OTP value. Never store plain-text OTP.',
    )

    attempts = models.PositiveSmallIntegerField(
        default=0,
        help_text='Number of verification attempts (max 3).',
    )

    is_verified = models.BooleanField(
        default=False,
        help_text='Set to True when OTP is successfully verified.',
    )

    is_expired = models.BooleanField(
        default=False,
        help_text='Set to True when OTP expires or is invalidated.',
    )

    expires_at = models.DateTimeField(
        help_text='OTP expiration timestamp (5 minutes from creation).',
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Timestamp when OTP was generated.',
    )

    class Meta:
        db_table = 'otps'
        verbose_name = 'OTP'
        verbose_name_plural = 'OTPs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone', 'is_expired'], name='idx_otp_phone_active'),
        ]

    def __str__(self):
        return f'OTP for {self.phone} ({"Verified" if self.is_verified else "Pending"})'

    @property
    def is_still_valid(self):
        """Check if OTP is still valid (not expired, not used, attempts < 3)."""
        return (
            not self.is_expired
            and not self.is_verified
            and self.attempts < 3
            and timezone.now() < self.expires_at
        )

    def increment_attempt(self):
        """
        Record a failed verification attempt.
        Auto-expire after 3 failed attempts.
        """
        self.attempts += 1
        if self.attempts >= 3:
            self.is_expired = True
        self.save(update_fields=['attempts', 'is_expired'])
