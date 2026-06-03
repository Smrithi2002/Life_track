"""
Organizations App — Models
===========================
Organization (clinic/hospital configuration), including:
  • SetupType enum: CLINIC | HOSPITAL
  • Feature toggles: departments, lab, pharmacy, IPD, analytics
  • Multi-tenant ready: all major entities can FK to Organization

Design goals:
  • Clinic mode = minimal, fast, no departments required
  • Hospital mode = full feature set (departments, lab, IPD, etc.)
  • One model to rule them all — no separate "ClinicSettings" vs "HospitalSettings"
"""

import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
from phonenumber_field.modelfields import PhoneNumberField


# ─────────────────────────────────────────────────────────────────────
#  ENUMS / CHOICES
# ─────────────────────────────────────────────────────────────────────

class SetupType(models.TextChoices):
    """
    Determines the operational mode of the organization.
    CLINIC  → lightweight, single-doctor or small multi-doctor setup
    HOSPITAL → full-featured: departments, lab, IPD, radiology, etc.
    """
    CLINIC   = 'CLINIC',   'Clinic'
    HOSPITAL = 'HOSPITAL', 'Hospital'


class OrganizationStatus(models.TextChoices):
    ACTIVE    = 'ACTIVE',    'Active'
    SUSPENDED = 'SUSPENDED', 'Suspended'
    TRIAL     = 'TRIAL',     'Trial'


# ─────────────────────────────────────────────────────────────────────
#  ORGANIZATION MODEL
# ─────────────────────────────────────────────────────────────────────

class Organization(models.Model):
    """
    Central configuration model for a clinic or hospital deployment.

    Feature flags govern which modules are visible/accessible.
    Switching setup_type from CLINIC → HOSPITAL auto-enables hospital flags.

    For single-tenant deployments:
      • One Organization record is created at setup
      • All users/entities belong to this single org

    For future multi-tenant:
      • Multiple Organization records
      • All users/entities filtered by org FK
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # ── Identity ─────────────────────────────────────────────────────
    name = models.CharField(
        max_length=255,
        help_text='Full legal name of the organization. E.g., "Sri Sai Clinic"',
    )

    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text='URL-friendly identifier. E.g., "sri-sai-clinic"',
    )

    short_name = models.CharField(
        max_length=50,
        blank=True,
        help_text='Short name for display. E.g., "SSC"',
    )

    registration_number = models.CharField(
        max_length=100,
        blank=True,
        help_text='Medical council / government registration number.',
    )

    # ── Setup Type ───────────────────────────────────────────────────
    setup_type = models.CharField(
        max_length=10,
        choices=SetupType.choices,
        default=SetupType.CLINIC,
        db_index=True,
        help_text=(
            'CLINIC: lightweight mode (no departments required). '
            'HOSPITAL: full-featured with departments, lab, IPD.'
        ),
    )

    # ── Feature Toggles ──────────────────────────────────────────────
    # These can be individually overridden regardless of setup_type.

    enable_departments = models.BooleanField(
        default=False,
        help_text=(
            'Enable department-based routing. '
            'CLINIC=False (doctors work independently). '
            'HOSPITAL=True (doctors assigned to departments).'
        ),
    )

    enable_lab = models.BooleanField(
        default=False,
        help_text='Enable lab test ordering and result management.',
    )

    enable_pharmacy = models.BooleanField(
        default=True,
        help_text='Enable pharmacy module (medicine dispensing, stock management).',
    )

    enable_ipd = models.BooleanField(
        default=False,
        help_text='Enable In-Patient Department (IPD) module: ward management, bed allocation.',
    )

    enable_analytics = models.BooleanField(
        default=False,
        help_text='Enable analytics dashboard: revenue reports, patient trends, doctor performance.',
    )

    enable_multi_doctor = models.BooleanField(
        default=True,
        help_text='Allow multiple doctors. Set False for solo-practitioner clinics.',
    )

    enable_online_booking = models.BooleanField(
        default=True,
        help_text='Allow patients to book appointments online via patient app.',
    )

    enable_telemedicine = models.BooleanField(
        default=False,
        help_text='Enable telemedicine/video consultation module.',
    )

    # ── Contact & Address ────────────────────────────────────────────
    phone = PhoneNumberField(
        blank=True,
        help_text='Primary contact number.',
    )

    email = models.EmailField(
        blank=True,
        help_text='Primary contact email.',
    )

    website = models.URLField(
        blank=True,
        help_text='Organization website URL.',
    )

    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city           = models.CharField(max_length=100, blank=True)
    state          = models.CharField(max_length=100, blank=True)
    pincode        = models.CharField(
        max_length=10,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\d{5,10}$',
                message='Pincode must be 5–10 digits.',
            )
        ],
    )
    country = models.CharField(max_length=100, default='India')

    # ── Branding ─────────────────────────────────────────────────────
    logo = models.ImageField(
        upload_to='org_logos/%Y/',
        blank=True,
        null=True,
        help_text='Organization logo image.',
    )

    # ── Operational Settings ─────────────────────────────────────────
    timezone = models.CharField(
        max_length=50,
        default='Asia/Kolkata',
        help_text='Organization timezone for scheduling.',
    )

    currency = models.CharField(
        max_length=5,
        default='INR',
        help_text='Currency code for billing. E.g., INR, USD.',
    )

    default_consultation_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Default consultation fee when doctor fee is not set.',
    )

    max_daily_patients = models.PositiveIntegerField(
        default=100,
        help_text='Maximum patients per day (for capacity planning).',
    )

    # ── Status ───────────────────────────────────────────────────────
    status = models.CharField(
        max_length=15,
        choices=OrganizationStatus.choices,
        default=OrganizationStatus.ACTIVE,
        db_index=True,
    )

    is_active = models.BooleanField(
        default=True,
        help_text='Master switch. Deactivating blocks all access.',
    )

    # ── Timestamps ───────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organizations'
        verbose_name = 'Organization'
        verbose_name_plural = 'Organizations'
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug'], name='idx_org_slug'),
            models.Index(fields=['setup_type', 'is_active'], name='idx_org_type_active'),
        ]

    def __str__(self):
        return f'{self.name} ({self.get_setup_type_display()})'

    # ── Feature Helpers ──────────────────────────────────────────────

    def is_clinic(self) -> bool:
        return self.setup_type == SetupType.CLINIC

    def is_hospital(self) -> bool:
        return self.setup_type == SetupType.HOSPITAL

    def get_feature_map(self) -> dict:
        """
        Returns all feature toggles as a dict.
        Used by FeatureToggle utility and API responses.
        """
        return {
            'enable_departments':    self.enable_departments,
            'enable_lab':            self.enable_lab,
            'enable_pharmacy':       self.enable_pharmacy,
            'enable_ipd':            self.enable_ipd,
            'enable_analytics':      self.enable_analytics,
            'enable_multi_doctor':   self.enable_multi_doctor,
            'enable_online_booking': self.enable_online_booking,
            'enable_telemedicine':   self.enable_telemedicine,
        }

    def apply_hospital_defaults(self):
        """
        Auto-enable standard hospital features when switching to HOSPITAL mode.
        Can be called after setting setup_type = HOSPITAL.
        """
        self.enable_departments = True
        self.enable_lab         = True
        self.enable_pharmacy    = True
        self.enable_ipd         = True
        self.enable_analytics   = True

    def apply_clinic_defaults(self):
        """
        Reset to clinic-mode defaults.
        Called when switching back to CLINIC mode.
        """
        self.enable_departments = False
        self.enable_lab         = False
        self.enable_pharmacy    = True   # Pharmacy stays on for clinics too
        self.enable_ipd         = False
        self.enable_analytics   = False

    def save(self, *args, **kwargs):
        """
        Override save: if setup_type changes, auto-apply defaults
        only on the first save (is_clinic/hospital switching).
        For explicit overrides, callers should set flags directly.
        """
        if self._state.adding:
            # New organization — apply defaults based on setup_type
            if self.setup_type == SetupType.HOSPITAL:
                self.apply_hospital_defaults()
            else:
                self.apply_clinic_defaults()
                self.enable_pharmacy = True  # Always keep pharmacy on
        super().save(*args, **kwargs)
