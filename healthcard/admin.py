"""HealthCard App — Admin"""
from django.contrib import admin
from .models import HealthCard, CardScanLog


@admin.register(HealthCard)
class HealthCardAdmin(admin.ModelAdmin):
    list_display = ['card_number', 'patient', 'status', 'is_active', 'issued_date', 'expiry_date']
    list_filter = ['status', 'is_active']
    search_fields = ['card_number', 'patient__full_name', 'patient__user_id']
    raw_id_fields = ['patient', 'issued_by']


@admin.register(CardScanLog)
class CardScanLogAdmin(admin.ModelAdmin):
    list_display = ['card', 'scanned_by', 'department', 'purpose', 'ip_address', 'timestamp']
    list_filter = ['purpose', 'department']
    search_fields = ['card__card_number', 'scanned_by__full_name']
    raw_id_fields = ['card', 'scanned_by']
