"""
Appointments App — Admin Configuration
"""

from django.contrib import admin
from .models import Department, DoctorProfile, DoctorSchedule, Appointment, Vitals


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'specialization', 'department',
        'consultation_fee', 'experience_years', 'is_available',
    ]
    list_filter = ['department', 'is_available']
    search_fields = ['user__full_name', 'specialization']
    raw_id_fields = ['user', 'department']


@admin.register(DoctorSchedule)
class DoctorScheduleAdmin(admin.ModelAdmin):
    list_display = [
        'doctor', 'day_of_week', 'start_time', 'end_time',
        'slot_duration_min', 'max_patients', 'is_active',
    ]
    list_filter = ['day_of_week', 'is_active']
    raw_id_fields = ['doctor']


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = [
        'token_number', 'patient', 'doctor',
        'appointment_date', 'time_slot', 'status',
        'appointment_type', 'priority',
    ]
    list_filter = ['status', 'appointment_type', 'priority', 'appointment_date']
    search_fields = [
        'token_number', 'patient__full_name', 'patient__user_id',
        'doctor__user__full_name',
    ]
    raw_id_fields = ['patient', 'doctor']
    date_hierarchy = 'appointment_date'


@admin.register(Vitals)
class VitalsAdmin(admin.ModelAdmin):
    list_display = [
        'appointment', 'blood_pressure_sys', 'blood_pressure_dia',
        'heart_rate', 'temperature', 'spo2', 'weight', 'recorded_at',
    ]
    list_filter = ['recorded_at']
    raw_id_fields = ['appointment', 'recorded_by']
