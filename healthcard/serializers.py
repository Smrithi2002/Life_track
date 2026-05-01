"""
HealthCard Serializers
"""
from rest_framework import serializers
from .models import HealthCard, CardScanLog
from accounts.serializers import UserListSerializer


class HealthCardSerializer(serializers.ModelSerializer):
    patient_name    = serializers.CharField(source='patient.full_name', read_only=True)
    patient_user_id = serializers.CharField(source='patient.user_id', read_only=True)
    issued_by_name  = serializers.CharField(source='issued_by.full_name', read_only=True)
    qr_code_url     = serializers.SerializerMethodField()

    class Meta:
        model = HealthCard
        fields = [
            'id', 'card_number', 'patient', 'patient_name', 'patient_user_id',
            'status', 'is_active', 'issued_by', 'issued_by_name',
            'issued_date', 'expiry_date', 'notes', 'qr_code_url',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'card_number', 'created_at', 'updated_at', 'qr_code_url']

    def get_qr_code_url(self, obj):
        request = self.context.get('request')
        if obj.qr_code_image and request:
            return request.build_absolute_uri(obj.qr_code_image.url)
        return None


class HealthCardCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = HealthCard
        fields = ['patient', 'expiry_date', 'notes']

    def validate_patient(self, value):
        if value.role != 'PATIENT':
            raise serializers.ValidationError('User must have PATIENT role.')
        return value


class CardScanLogSerializer(serializers.ModelSerializer):
    card_number     = serializers.CharField(source='card.card_number', read_only=True)
    patient_name    = serializers.CharField(source='card.patient.full_name', read_only=True)
    scanned_by_name = serializers.CharField(source='scanned_by.full_name', read_only=True)
    scanned_by_role = serializers.CharField(source='scanned_by.role', read_only=True)

    class Meta:
        model  = CardScanLog
        fields = [
            'id', 'card', 'card_number', 'patient_name',
            'scanned_by', 'scanned_by_name', 'scanned_by_role',
            'department', 'purpose', 'ip_address', 'device_info', 'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']


class PatientCardLookupSerializer(serializers.ModelSerializer):
    """
    Returned when a staff member scans a patient's QR code.
    Role-filtered data is added in the view/service layer.
    """
    patient_name    = serializers.CharField(source='patient.full_name')
    patient_user_id = serializers.CharField(source='patient.user_id')
    blood_group     = serializers.CharField(source='patient.blood_group')
    allergies       = serializers.CharField(source='patient.known_allergies')
    emergency_contact = serializers.SerializerMethodField()

    class Meta:
        model  = HealthCard
        fields = [
            'card_number', 'patient_name', 'patient_user_id',
            'blood_group', 'allergies', 'emergency_contact',
            'status', 'is_active',
        ]

    def get_emergency_contact(self, obj):
        p = obj.patient
        return {
            'name':     p.emergency_contact_name,
            'phone':    str(p.emergency_contact_phone) if p.emergency_contact_phone else None,
            'relation': p.emergency_contact_relation,
        }
