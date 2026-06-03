"""
Organizations — Serializers
==============================
REST API serializers for Organization model and feature toggles.
"""

from rest_framework import serializers
from .models import Organization, SetupType
from .features import KNOWN_FEATURES, FeatureToggle


# ─────────────────────────────────────────────────────────────────────
#  FEATURE TOGGLE SERIALIZER
# ─────────────────────────────────────────────────────────────────────

class FeatureToggleSerializer(serializers.Serializer):
    """
    Serializes the feature map of an Organization.
    Used in GET /api/v1/organization/features/
    """
    enable_departments    = serializers.BooleanField()
    enable_lab            = serializers.BooleanField()
    enable_pharmacy       = serializers.BooleanField()
    enable_ipd            = serializers.BooleanField()
    enable_analytics      = serializers.BooleanField()
    enable_multi_doctor   = serializers.BooleanField()
    enable_online_booking = serializers.BooleanField()
    enable_telemedicine   = serializers.BooleanField()


class FeatureToggleUpdateSerializer(serializers.Serializer):
    """
    For PATCH /api/v1/organization/features/
    Allows toggling any single feature by name.
    """
    feature = serializers.ChoiceField(
        choices=list(KNOWN_FEATURES),
        help_text='The feature flag name to toggle.',
    )
    enabled = serializers.BooleanField(
        help_text='True to enable, False to disable.',
    )


# ─────────────────────────────────────────────────────────────────────
#  ORGANIZATION SERIALIZERS
# ─────────────────────────────────────────────────────────────────────

class OrganizationPublicSerializer(serializers.ModelSerializer):
    """
    Read-only serializer — safe for all authenticated users.
    Exposes org identity, setup_type, and feature flags.
    Used in: GET /api/v1/organization/
    """
    features = serializers.SerializerMethodField()
    setup_type_display = serializers.CharField(
        source='get_setup_type_display',
        read_only=True,
    )
    is_clinic   = serializers.SerializerMethodField()
    is_hospital = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            'id',
            'name',
            'short_name',
            'slug',
            'setup_type',
            'setup_type_display',
            'is_clinic',
            'is_hospital',
            'features',
            'phone',
            'email',
            'website',
            'city',
            'state',
            'country',
            'timezone',
            'currency',
            'default_consultation_fee',
            'max_daily_patients',
            'status',
            'logo',
            'created_at',
        ]
        read_only_fields = fields

    def get_features(self, obj):
        return FeatureToggle.get_all(obj)

    def get_is_clinic(self, obj):
        return obj.is_clinic()

    def get_is_hospital(self, obj):
        return obj.is_hospital()


class OrganizationAdminSerializer(serializers.ModelSerializer):
    """
    Full read/write serializer — Admin only.
    Used in: PUT/PATCH /api/v1/organization/
    """
    features = serializers.SerializerMethodField()
    setup_type_display = serializers.CharField(
        source='get_setup_type_display',
        read_only=True,
    )

    class Meta:
        model = Organization
        fields = [
            'id',
            'name',
            'short_name',
            'slug',
            'registration_number',
            'setup_type',
            'setup_type_display',
            # Feature toggles
            'enable_departments',
            'enable_lab',
            'enable_pharmacy',
            'enable_ipd',
            'enable_analytics',
            'enable_multi_doctor',
            'enable_online_booking',
            'enable_telemedicine',
            'features',
            # Contact
            'phone',
            'email',
            'website',
            'address_line_1',
            'address_line_2',
            'city',
            'state',
            'pincode',
            'country',
            # Operational
            'timezone',
            'currency',
            'default_consultation_fee',
            'max_daily_patients',
            'logo',
            'status',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'features']

    def get_features(self, obj):
        return FeatureToggle.get_all(obj)

    def validate_setup_type(self, value):
        """
        Warn if switching setup_type — flags will NOT auto-reset on update.
        Only auto-reset on initial creation.
        """
        instance = self.instance
        if instance and instance.setup_type != value:
            # Caller must explicitly set flags when changing setup_type via API
            pass
        return value

    def update(self, instance, validated_data):
        """Invalidate org cache after update."""
        from .middleware import invalidate_organization_cache
        result = super().update(instance, validated_data)
        invalidate_organization_cache()
        return result


class OrganizationMinimalSerializer(serializers.ModelSerializer):
    """
    Minimal read-only serializer — for embedding in user/appointment responses.
    """
    class Meta:
        model = Organization
        fields = ['id', 'name', 'short_name', 'setup_type', 'slug']
        read_only_fields = fields
