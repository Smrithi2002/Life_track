"""
Organizations — Django Admin
==============================
Admin interface for Organization management.
Grouped sections for identity, feature toggles, and operational settings.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Organization
from .middleware import invalidate_organization_cache


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'setup_type',
        'status',
        'is_active',
        'feature_summary',
        'city',
        'created_at',
    ]
    list_filter  = ['setup_type', 'status', 'is_active', 'enable_lab', 'enable_pharmacy', 'enable_ipd']
    search_fields = ['name', 'slug', 'city', 'registration_number']
    readonly_fields = ['id', 'created_at', 'updated_at']
    prepopulated_fields = {'slug': ('name',)}

    fieldsets = (
        ('🏥 Identity', {
            'fields': ('id', 'name', 'short_name', 'slug', 'registration_number', 'logo'),
        }),
        ('⚙️ Setup & Mode', {
            'fields': ('setup_type', 'status', 'is_active'),
            'description': (
                'CLINIC mode: lightweight, no departments required. '
                'HOSPITAL mode: full features. Changing setup_type does NOT '
                'auto-reset feature flags — use the "switch-mode" API or '
                'apply_clinic_defaults()/apply_hospital_defaults() manually.'
            ),
        }),
        ('🔌 Feature Toggles', {
            'fields': (
                'enable_departments',
                'enable_lab',
                'enable_pharmacy',
                'enable_ipd',
                'enable_analytics',
                'enable_multi_doctor',
                'enable_online_booking',
                'enable_telemedicine',
            ),
        }),
        ('📞 Contact Information', {
            'fields': ('phone', 'email', 'website'),
            'classes': ('collapse',),
        }),
        ('📍 Address', {
            'fields': (
                'address_line_1',
                'address_line_2',
                'city',
                'state',
                'pincode',
                'country',
            ),
            'classes': ('collapse',),
        }),
        ('💰 Operational Settings', {
            'fields': (
                'timezone',
                'currency',
                'default_consultation_fee',
                'max_daily_patients',
            ),
            'classes': ('collapse',),
        }),
        ('🕐 Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def feature_summary(self, obj):
        """Show enabled features as colored badges."""
        features = []
        if obj.enable_pharmacy:
            features.append('<span style="color:green">💊 Pharmacy</span>')
        if obj.enable_departments:
            features.append('<span style="color:blue">🏢 Depts</span>')
        if obj.enable_lab:
            features.append('<span style="color:purple">🧪 Lab</span>')
        if obj.enable_ipd:
            features.append('<span style="color:orange">🛏️ IPD</span>')
        if obj.enable_analytics:
            features.append('<span style="color:teal">📊 Analytics</span>')
        return format_html(' '.join(features)) if features else '—'

    feature_summary.short_description = 'Enabled Features'

    def save_model(self, request, obj, form, change):
        """Invalidate cache when org is saved from admin."""
        super().save_model(request, obj, form, change)
        invalidate_organization_cache()
