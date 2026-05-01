"""Medical Records App — Admin"""
from django.contrib import admin
from .models import Diagnosis, MedicalRecord, LabReport


@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
    list_display = ['condition_name', 'icd_code', 'patient', 'doctor', 'severity', 'created_at']
    list_filter = ['severity', 'is_chronic']
    search_fields = ['condition_name', 'icd_code', 'patient__full_name']
    raw_id_fields = ['doctor', 'patient', 'appointment']


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ['patient', 'doctor', 'appointment', 'created_at']
    search_fields = ['patient__full_name', 'doctor__full_name']
    raw_id_fields = ['doctor', 'patient', 'appointment']


@admin.register(LabReport)
class LabReportAdmin(admin.ModelAdmin):
    list_display = ['title', 'patient', 'ordered_by', 'report_type', 'status', 'created_at']
    list_filter = ['report_type', 'status']
    search_fields = ['title', 'patient__full_name']
    raw_id_fields = ['patient', 'ordered_by', 'appointment']
