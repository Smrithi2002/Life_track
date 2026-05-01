"""
Medical Records App — Service Layer
=======================================
Business logic for diagnoses, medical records, and lab reports.
"""

import logging
from django.db import transaction
from django.utils import timezone
from .models import Diagnosis, MedicalRecord, LabReport, ReportStatus

logger = logging.getLogger('medical_records')


class MedicalRecordService:
    """Core service for clinical documentation."""

    @staticmethod
    @transaction.atomic
    def create_consultation_record(doctor, patient, appointment=None,
                                    record_data=None, diagnoses_data=None):
        """
        Create medical record + diagnoses in one atomic operation.
        Called during doctor consultation completion.
        """
        record = MedicalRecord.objects.create(
            doctor=doctor,
            patient=patient,
            appointment=appointment,
            **(record_data or {}),
        )

        diagnoses = []
        if diagnoses_data:
            for diag_data in diagnoses_data:
                diagnosis = Diagnosis.objects.create(
                    doctor=doctor,
                    patient=patient,
                    appointment=appointment,
                    **diag_data,
                )
                diagnoses.append(diagnosis)

        logger.info(
            'Medical record created by Dr. %s for %s (%d diagnoses)',
            doctor.full_name, patient.full_name, len(diagnoses),
        )
        return record, diagnoses

    @staticmethod
    def get_patient_history(patient, limit=20):
        """
        Get complete medical history for a patient.
        Returns records with related diagnoses.
        """
        records = MedicalRecord.objects.filter(
            patient=patient,
        ).select_related(
            'doctor', 'appointment',
        ).order_by('-created_at')[:limit]

        diagnoses = Diagnosis.objects.filter(
            patient=patient,
        ).select_related('doctor').order_by('-created_at')[:limit]

        return {
            'records': records,
            'diagnoses': diagnoses,
        }

    @staticmethod
    @transaction.atomic
    def order_lab_test(doctor, patient, appointment=None,
                       title='', report_type='LAB', description=''):
        """Doctor orders a lab/diagnostic test."""
        report = LabReport.objects.create(
            patient=patient,
            ordered_by=doctor,
            appointment=appointment,
            report_type=report_type,
            title=title,
            description=description,
        )

        logger.info(
            'Lab test ordered: %s for %s by Dr. %s',
            title, patient.full_name, doctor.full_name,
        )
        return report

    @staticmethod
    @transaction.atomic
    def update_report_result(report, result_summary='', file=None):
        """Update lab report with results."""
        report.result_summary = result_summary
        report.status = ReportStatus.READY
        report.completed_at = timezone.now()

        update_fields = ['result_summary', 'status', 'completed_at', 'updated_at']

        if file:
            report.file = file
            update_fields.append('file')

        report.save(update_fields=update_fields)

        logger.info('Lab report completed: %s', report.title)
        return report
