"""
Prescriptions App — Serializers
=================================
"""

from rest_framework import serializers
from .models import (
    Medicine, Prescription, PrescriptionItem,
    PharmacyOrder, PrescriptionStatus,
)


# ─────────────────────────────────────────────────────────────────────
#  MEDICINE
# ─────────────────────────────────────────────────────────────────────

class MedicineSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    is_low_stock     = serializers.BooleanField(read_only=True)
    is_expired       = serializers.BooleanField(read_only=True)

    class Meta:
        model = Medicine
        fields = [
            'id', 'name', 'generic_name', 'category', 'category_display',
            'manufacturer', 'strength', 'unit_price',
            'stock_quantity', 'reorder_level', 'expiry_date',
            'description', 'is_active', 'is_low_stock', 'is_expired',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class MedicineListSerializer(serializers.ModelSerializer):
    """Lightweight for dropdowns/search."""
    class Meta:
        model = Medicine
        fields = ['id', 'name', 'generic_name', 'strength', 'category', 'unit_price', 'stock_quantity']


# ─────────────────────────────────────────────────────────────────────
#  PRESCRIPTION ITEM
# ─────────────────────────────────────────────────────────────────────

class PrescriptionItemSerializer(serializers.ModelSerializer):
    medicine_name   = serializers.CharField(source='medicine.name', read_only=True)
    medicine_strength = serializers.CharField(source='medicine.strength', read_only=True)
    frequency_display = serializers.CharField(source='get_frequency_display', read_only=True)
    line_total      = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = PrescriptionItem
        fields = [
            'id', 'prescription', 'medicine', 'medicine_name', 'medicine_strength',
            'dosage', 'frequency', 'frequency_display',
            'duration_days', 'quantity', 'instructions',
            'is_dispensed', 'line_total',
        ]
        read_only_fields = ['id']


class PrescriptionItemCreateSerializer(serializers.ModelSerializer):
    """Nested within prescription creation."""
    class Meta:
        model = PrescriptionItem
        fields = [
            'medicine', 'dosage', 'frequency',
            'duration_days', 'quantity', 'instructions',
        ]


# ─────────────────────────────────────────────────────────────────────
#  PRESCRIPTION
# ─────────────────────────────────────────────────────────────────────

class PrescriptionSerializer(serializers.ModelSerializer):
    doctor_name     = serializers.CharField(source='doctor.full_name', read_only=True)
    patient_name    = serializers.CharField(source='patient.full_name', read_only=True)
    patient_user_id = serializers.CharField(source='patient.user_id', read_only=True)
    status_display  = serializers.CharField(source='get_status_display', read_only=True)
    items           = PrescriptionItemSerializer(many=True, read_only=True)
    item_count      = serializers.IntegerField(read_only=True)
    total_cost      = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Prescription
        fields = [
            'id', 'appointment', 'doctor', 'doctor_name',
            'patient', 'patient_name', 'patient_user_id',
            'status', 'status_display',
            'diagnosis_summary', 'notes',
            'items', 'item_count', 'total_cost',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PrescriptionCreateSerializer(serializers.ModelSerializer):
    """Create prescription with nested items."""
    items = PrescriptionItemCreateSerializer(many=True, write_only=True)

    class Meta:
        model = Prescription
        fields = [
            'appointment', 'patient', 'diagnosis_summary', 'notes', 'items',
        ]

    def validate(self, data):
        items = data.get('items', [])
        if not items:
            raise serializers.ValidationError({'items': 'At least one medicine is required.'})
        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        doctor = self.context['request'].user
        prescription = Prescription.objects.create(doctor=doctor, **validated_data)

        for item_data in items_data:
            PrescriptionItem.objects.create(prescription=prescription, **item_data)

        return prescription


# ─────────────────────────────────────────────────────────────────────
#  PHARMACY ORDER
# ─────────────────────────────────────────────────────────────────────

class PharmacyOrderSerializer(serializers.ModelSerializer):
    prescription_id     = serializers.UUIDField(source='prescription.id', read_only=True)
    patient_name        = serializers.CharField(
        source='prescription.patient.full_name', read_only=True,
    )
    doctor_name         = serializers.CharField(
        source='prescription.doctor.full_name', read_only=True,
    )
    dispensed_by_name   = serializers.CharField(
        source='dispensed_by.full_name', read_only=True,
    )
    status_display      = serializers.CharField(source='get_status_display', read_only=True)
    items               = serializers.SerializerMethodField()

    class Meta:
        model = PharmacyOrder
        fields = [
            'id', 'prescription', 'prescription_id',
            'patient_name', 'doctor_name',
            'dispensed_by', 'dispensed_by_name',
            'status', 'status_display',
            'total_amount', 'notes',
            'dispensed_at', 'created_at', 'updated_at',
            'items',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_items(self, obj):
        items = obj.prescription.items.select_related('medicine').all()
        return PrescriptionItemSerializer(items, many=True).data


class PharmacyOrderStatusSerializer(serializers.Serializer):
    """Update pharmacy order status."""
    status = serializers.ChoiceField(choices=PharmacyOrder.OrderStatus.choices)
    notes  = serializers.CharField(required=False, allow_blank=True, default='')
