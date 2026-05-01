"""
Prescriptions App — Admin Configuration
"""

from django.contrib import admin
from .models import Medicine, Prescription, PrescriptionItem, PharmacyOrder


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'generic_name', 'category', 'strength',
        'unit_price', 'stock_quantity', 'reorder_level',
        'expiry_date', 'is_active',
    ]
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'generic_name', 'manufacturer']
    list_editable = ['stock_quantity', 'unit_price', 'is_active']


class PrescriptionItemInline(admin.TabularInline):
    model = PrescriptionItem
    extra = 1
    raw_id_fields = ['medicine']


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'doctor', 'patient', 'appointment',
        'status', 'created_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = [
        'doctor__full_name', 'patient__full_name',
        'patient__user_id',
    ]
    raw_id_fields = ['doctor', 'patient', 'appointment']
    inlines = [PrescriptionItemInline]


@admin.register(PharmacyOrder)
class PharmacyOrderAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'prescription', 'dispensed_by',
        'status', 'total_amount', 'dispensed_at',
    ]
    list_filter = ['status']
    raw_id_fields = ['prescription', 'dispensed_by']
