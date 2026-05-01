"""
Medical Records App — Serializers
====================================
"""

from rest_framework import serializers
from .models import Diagnosis, MedicalRecord, LabReport


# ─────────────────────────────────────────────────────────────────────
#  DIAGNOSIS
# ─────────────────────────────────────────────────────────────────────

class DiagnosisSerializer(serializers.ModelSerializer):
    doctor_name     = serializers.CharField(source='doctor.full_name', read_only=True)
    patient_name    = serializers.CharField(source='patient.full_name', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)

    class Meta:
        model = Diagnosis
        fields = [
            'id', 'appointment', 'doctor', 'doctor_name',
            'patient', 'patient_name',
            'icd_code', 'condition_name', 'severity', 'severity_display',
            'clinical_notes', 'follow_up_date', 'is_chronic',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DiagnosisCreateSerializer(serializers.ModelSerializer):
    """Used by Doctor to create diagnosis."""
    class Meta:
        model = Diagnosis
        fields = [
            'appointment', 'patient',
            'icd_code', 'condition_name', 'severity',
            'clinical_notes', 'follow_up_date', 'is_chronic',
        ]


# ─────────────────────────────────────────────────────────────────────
#  MEDICAL RECORD
# ─────────────────────────────────────────────────────────────────────

class MedicalRecordSerializer(serializers.ModelSerializer):
    doctor_name     = serializers.CharField(source='doctor.full_name', read_only=True)
    patient_name    = serializers.CharField(source='patient.full_name', read_only=True)
    diagnoses       = serializers.SerializerMethodField()

    class Meta:
        model = MedicalRecord
        fields = [
            'id', 'appointment', 'doctor', 'doctor_name',
            'patient', 'patient_name',
            'chief_complaint', 'history_of_present_illness',
            'examination_findings', 'clinical_notes',
            'treatment_plan', 'advice',
            'follow_up_date', 'follow_up_notes',
            'diagnoses',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_diagnoses(self, obj):
        if obj.appointment:
            diagnoses = obj.appointment.diagnoses.all()
            return DiagnosisSerializer(diagnoses, many=True).data
        return []


class MedicalRecordCreateSerializer(serializers.ModelSerializer):
    """Used by Doctor during consultation."""
    class Meta:
        model = MedicalRecord
        fields = [
            'appointment', 'patient',
            'chief_complaint', 'history_of_present_illness',
            'examination_findings', 'clinical_notes',
            'treatment_plan', 'advice',
            'follow_up_date', 'follow_up_notes',
        ]


# ─────────────────────────────────────────────────────────────────────
#  LAB REPORT
# ─────────────────────────────────────────────────────────────────────

class LabReportSerializer(serializers.ModelSerializer):
    patient_name     = serializers.CharField(source='patient.full_name', read_only=True)
    ordered_by_name  = serializers.CharField(source='ordered_by.full_name', read_only=True)
    type_display     = serializers.CharField(source='get_report_type_display', read_only=True)
    status_display   = serializers.CharField(source='get_status_display', read_only=True)
    file_url         = serializers.SerializerMethodField()

    class Meta:
        model = LabReport
        fields = [
            'id', 'appointment', 'patient', 'patient_name',
            'ordered_by', 'ordered_by_name',
            'report_type', 'type_display',
            'title', 'description', 'result_summary',
            'file', 'file_url',
            'status', 'status_display',
            'completed_at', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None


class LabReportCreateSerializer(serializers.ModelSerializer):
    """Used by Doctor to order lab tests."""
    class Meta:
        model = LabReport
        fields = [
            'appointment', 'patient', 'report_type',
            'title', 'description',
        ]
