"""
Medical Records App — Models
===============================
Diagnosis, MedicalRecord (consultation notes/clinical findings)

Key design:
  • Diagnosis FK to Appointment (optional — allows standalone diagnoses)
  • Multiple diagnoses per appointment (ICD-10 coded)
  • MedicalRecord stores consultation narrative linked to appointment
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────
#  ENUMS
# ─────────────────────────────────────────────────────────────────────

class Severity(models.TextChoices):
    MILD     = 'MILD',     'Mild'
    MODERATE = 'MODERATE', 'Moderate'
    SEVERE   = 'SEVERE',   'Severe'
    CRITICAL = 'CRITICAL', 'Critical'


class ReportType(models.TextChoices):
    LAB       = 'LAB',       'Lab Test'
    IMAGING   = 'IMAGING',   'Imaging'
    PATHOLOGY = 'PATHOLOGY', 'Pathology'
    OTHER     = 'OTHER',     'Other'


class ReportStatus(models.TextChoices):
    ORDERED    = 'ORDERED',    'Ordered'
    PROCESSING = 'PROCESSING', 'Processing'
    READY      = 'READY',      'Ready'
    DELIVERED  = 'DELIVERED',  'Delivered'


# ─────────────────────────────────────────────────────────────────────
#  DIAGNOSIS
# ─────────────────────────────────────────────────────────────────────

class Diagnosis(models.Model):
    """
    ICD-10 coded diagnosis entry.
    SDD Section 7.1 — DIAGNOSIS entity.

    Multiple diagnoses per appointment are allowed.
    FK to appointment is optional (null/blank).
    """
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment     = models.ForeignKey(
        'appointments.Appointment',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='diagnoses',
    )
    doctor          = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='diagnoses_made',
        limit_choices_to={'role': 'DOCTOR'},
    )
    patient         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='patient_diagnoses',
        limit_choices_to={'role': 'PATIENT'},
    )
    icd_code        = models.CharField(
        max_length=20, blank=True,
        help_text='ICD-10 diagnosis code (e.g., J06.9)',
    )
    condition_name  = models.CharField(
        max_length=255,
        help_text='Diagnosis / Condition name',
    )
    severity        = models.CharField(
        max_length=10,
        choices=Severity.choices,
        default=Severity.MILD,
    )
    clinical_notes  = models.TextField(blank=True)
    follow_up_date  = models.DateField(
        null=True, blank=True,
        help_text='Recommended follow-up date.',
    )
    is_chronic      = models.BooleanField(
        default=False,
        help_text='Whether this is a chronic/ongoing condition.',
    )
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'diagnoses'
        ordering = ['-created_at']
        verbose_name = 'Diagnosis'
        verbose_name_plural = 'Diagnoses'
        indexes = [
            models.Index(fields=['patient', 'created_at'], name='idx_diag_patient_date'),
            models.Index(fields=['icd_code'], name='idx_diag_icd'),
        ]

    def __str__(self):
        return f'{self.condition_name} ({self.icd_code}) — {self.patient.full_name}'


# ─────────────────────────────────────────────────────────────────────
#  MEDICAL RECORD (Consultation Notes)
# ─────────────────────────────────────────────────────────────────────

class MedicalRecord(models.Model):
    """
    Comprehensive consultation record / clinical notes.
    Linked to an appointment (optional).
    """
    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment      = models.OneToOneField(
        'appointments.Appointment',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='medical_record',
    )
    doctor           = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='medical_records_created',
        limit_choices_to={'role': 'DOCTOR'},
    )
    patient          = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='patient_medical_records',
        limit_choices_to={'role': 'PATIENT'},
    )

    # Clinical content
    chief_complaint  = models.TextField(
        blank=True,
        help_text='Patient-reported primary complaint.',
    )
    history_of_present_illness = models.TextField(
        blank=True,
        help_text='HPI — detailed narrative of current illness.',
    )
    examination_findings = models.TextField(
        blank=True,
        help_text='Physical examination findings.',
    )
    clinical_notes   = models.TextField(
        blank=True,
        help_text='Doctor\'s overall clinical assessment.',
    )
    treatment_plan   = models.TextField(
        blank=True,
        help_text='Prescribed treatment approach.',
    )
    advice           = models.TextField(
        blank=True,
        help_text='General advice / lifestyle recommendations.',
    )
    follow_up_date   = models.DateField(null=True, blank=True)
    follow_up_notes  = models.TextField(blank=True)

    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'medical_records'
        ordering = ['-created_at']
        verbose_name = 'Medical Record'
        verbose_name_plural = 'Medical Records'
        indexes = [
            models.Index(fields=['patient', 'created_at'], name='idx_medrec_patient_date'),
        ]

    def __str__(self):
        return f'Record for {self.patient.full_name} by Dr. {self.doctor.full_name}'


# ─────────────────────────────────────────────────────────────────────
#  LAB / DIAGNOSTIC REPORT
# ─────────────────────────────────────────────────────────────────────

class LabReport(models.Model):
    """
    Lab / diagnostic report ordered by a doctor.
    SDD Section 7.1 — REPORT entity.
    """
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment     = models.ForeignKey(
        'appointments.Appointment',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='lab_reports',
    )
    patient         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='patient_reports',
        limit_choices_to={'role': 'PATIENT'},
    )
    ordered_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ordered_reports',
        limit_choices_to={'role': 'DOCTOR'},
    )
    report_type     = models.CharField(
        max_length=15,
        choices=ReportType.choices,
        default=ReportType.LAB,
    )
    title           = models.CharField(max_length=255)
    description     = models.TextField(blank=True)
    result_summary  = models.TextField(blank=True)
    file            = models.FileField(
        upload_to='reports/%Y/%m/',
        null=True, blank=True,
        help_text='Uploaded report file (PDF/image).',
    )
    status          = models.CharField(
        max_length=15,
        choices=ReportStatus.choices,
        default=ReportStatus.ORDERED,
        db_index=True,
    )
    completed_at    = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lab_reports'
        ordering = ['-created_at']
        verbose_name = 'Lab Report'
        verbose_name_plural = 'Lab Reports'

    def __str__(self):
        return f'{self.title} — {self.patient.full_name} ({self.status})'
