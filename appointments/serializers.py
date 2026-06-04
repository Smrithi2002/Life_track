"""
Appointments App — Serializers
================================
DRF serializers for Department, DoctorProfile, DoctorSchedule,
Appointment, and Vitals.
"""

from rest_framework import serializers
from .models import (
    Department, DoctorProfile, DoctorSchedule,
    Appointment, Vitals, AppointmentStatus,
)


# ─────────────────────────────────────────────────────────────────────
#  DEPARTMENT
# ─────────────────────────────────────────────────────────────────────

class DepartmentSerializer(serializers.ModelSerializer):
    doctor_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = [
            'id', 'name', 'description', 'icon', 'is_active',
            'doctor_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_doctor_count(self, obj):
        return obj.doctors.filter(is_available=True).count()


# ─────────────────────────────────────────────────────────────────────
#  DOCTOR PROFILE
# ─────────────────────────────────────────────────────────────────────

class DoctorProfileSerializer(serializers.ModelSerializer):
    full_name       = serializers.CharField(source='user.full_name', read_only=True)
    user_id         = serializers.CharField(source='user.user_id', read_only=True)
    phone           = serializers.CharField(source='user.phone', read_only=True)
    avatar          = serializers.ImageField(source='user.avatar', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = DoctorProfile
        fields = [
            'id', 'user', 'user_id', 'full_name', 'phone', 'avatar',
            'department', 'department_name', 'specialization',
            'qualification', 'experience_years', 'consultation_fee',
            'bio', 'rating', 'is_available', 'max_patients_per_slot',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'rating', 'created_at', 'updated_at']


class DoctorProfileCreateSerializer(serializers.ModelSerializer):
    """Used by Admin to create/update doctor profiles."""
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = DoctorProfile
        fields = [
            'user', 'department', 'specialization', 'qualification',
            'experience_years', 'consultation_fee', 'bio',
            'is_available', 'max_patients_per_slot',
        ]

    def validate_user(self, value):
        if value.role != 'DOCTOR':
            raise serializers.ValidationError('User must have DOCTOR role.')
        if DoctorProfile.objects.filter(user=value).exists():
            raise serializers.ValidationError('Doctor profile already exists for this user.')
        return value


class DoctorListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing doctors."""
    full_name       = serializers.CharField(source='user.full_name', read_only=True)
    user_id         = serializers.CharField(source='user.user_id', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = DoctorProfile
        fields = [
            'id', 'user_id', 'full_name', 'department_name',
            'specialization', 'consultation_fee', 'experience_years',
            'rating', 'is_available',
        ]


# ─────────────────────────────────────────────────────────────────────
#  DOCTOR SCHEDULE
# ─────────────────────────────────────────────────────────────────────

class DoctorScheduleSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source='doctor.user.full_name', read_only=True)
    day_name    = serializers.CharField(source='get_day_of_week_display', read_only=True)

    class Meta:
        model = DoctorSchedule
        fields = [
            'id', 'doctor', 'doctor_name', 'day_of_week', 'day_name',
            'start_time', 'end_time', 'slot_duration_min',
            'max_patients', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ─────────────────────────────────────────────────────────────────────
#  VITALS
# ─────────────────────────────────────────────────────────────────────

class VitalsSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.full_name', read_only=True)
    patient_name     = serializers.CharField(
        source='appointment.patient.full_name', read_only=True,
    )
    blood_pressure   = serializers.SerializerMethodField()

    class Meta:
        model = Vitals
        fields = [
            'id', 'appointment', 'recorded_by', 'recorded_by_name',
            'patient_name', 'blood_pressure',
            'blood_pressure_sys', 'blood_pressure_dia',
            'heart_rate', 'temperature', 'spo2', 'respiratory_rate',
            'weight', 'height', 'bmi', 'blood_glucose',
            'notes', 'recorded_at',
        ]
        read_only_fields = ['id', 'bmi', 'recorded_at']

    def get_blood_pressure(self, obj):
        if obj.blood_pressure_sys and obj.blood_pressure_dia:
            return f'{obj.blood_pressure_sys}/{obj.blood_pressure_dia}'
        return None


class VitalsCreateSerializer(serializers.ModelSerializer):
    """Used by Nurse to record vitals."""
    class Meta:
        model = Vitals
        fields = [
            'appointment', 'blood_pressure_sys', 'blood_pressure_dia',
            'heart_rate', 'temperature', 'spo2', 'respiratory_rate',
            'weight', 'height', 'blood_glucose', 'notes',
        ]

    def validate_appointment(self, value):
        if value.status == AppointmentStatus.CANCELLED:
            raise serializers.ValidationError('Cannot record vitals for a cancelled appointment.')
        if hasattr(value, 'vitals'):
            raise serializers.ValidationError('Vitals already recorded for this appointment.')
        return value


# ─────────────────────────────────────────────────────────────────────
#  APPOINTMENT
# ─────────────────────────────────────────────────────────────────────

class AppointmentSerializer(serializers.ModelSerializer):
    patient_name    = serializers.CharField(source='patient.full_name', read_only=True)
    patient_user_id = serializers.CharField(source='patient.user_id', read_only=True)
    doctor_name     = serializers.CharField(source='doctor.user.full_name', read_only=True)
    department_name = serializers.SerializerMethodField()
    status_display  = serializers.CharField(source='get_status_display', read_only=True)
    has_vitals      = serializers.SerializerMethodField()
    has_prescription = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            'id', 'patient', 'patient_name', 'patient_user_id',
            'doctor', 'doctor_name', 'department_name',
            'appointment_date', 'time_slot', 'appointment_type',
            'token_number', 'queue_position',
            'status', 'status_display', 'priority',
            'chief_complaint', 'notes',
            'checked_in_at', 'consultation_start', 'consultation_end',
            'cancelled_reason',
            'has_vitals', 'has_prescription',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'token_number', 'queue_position',
            'checked_in_at', 'consultation_start', 'consultation_end',
            'created_at', 'updated_at',
        ]

    def get_department_name(self, obj):
        if obj.doctor and obj.doctor.department:
            return obj.doctor.department.name
        return None

    def get_has_vitals(self, obj):
        return hasattr(obj, 'vitals')

    def get_has_prescription(self, obj):
        return obj.prescriptions.exists()


class AppointmentCreateSerializer(serializers.ModelSerializer):
    """Used by patient/reception to book an appointment (Standard form)."""
    class Meta:
        model = Appointment
        fields = [
            'patient', 'doctor', 'appointment_date', 'time_slot',
            'appointment_type', 'chief_complaint', 'notes',
        ]

    def validate(self, data):
        doctor = data['doctor']
        appt_date = data['appointment_date']
        time_slot = data['time_slot']

        # Check doctor availability
        if not doctor.is_available:
            raise serializers.ValidationError(
                'This doctor is not currently available.'
            )

        # Check for conflicting appointments
        existing = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appt_date,
            time_slot=time_slot,
        ).exclude(status=AppointmentStatus.CANCELLED).count()

        if existing >= doctor.max_patients_per_slot:
            raise serializers.ValidationError(
                'Selected time slot is fully booked. Please choose another.'
            )

        return data


class FlutterAppointmentCreateSerializer(serializers.Serializer):
    """Used by Flutter mobile app to book an appointment (BFF payload)."""
    doctor_id = serializers.UUIDField()
    department_id = serializers.CharField(required=False, allow_blank=True) # Ignored, but accepted
    appointment_date = serializers.DateField()
    appointment_time = serializers.TimeField()
    chief_complaint = serializers.CharField(required=False, allow_blank=True)

    def validate_doctor_id(self, value):
        from .models import DoctorProfile
        try:
            doctor = DoctorProfile.objects.get(id=value)
            if not doctor.is_available:
                raise serializers.ValidationError("This doctor is currently unavailable.")
            return doctor
        except DoctorProfile.DoesNotExist:
            raise serializers.ValidationError("Invalid doctor ID.")

    def validate(self, data):
        doctor = data['doctor_id']
        appt_date = data['appointment_date']
        time_slot = data['appointment_time']

        existing = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appt_date,
            time_slot=time_slot,
        ).exclude(status=AppointmentStatus.CANCELLED).count()

        if existing >= doctor.max_patients_per_slot:
            raise serializers.ValidationError("Selected time slot is fully booked. Please choose another.")
            
        return data


class AppointmentStatusUpdateSerializer(serializers.Serializer):
    """Used to transition appointment status."""
    status = serializers.ChoiceField(choices=AppointmentStatus.choices)
    reason = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_status(self, value):
        """Validate status transition is allowed."""
        appointment = self.context.get('appointment')
        if not appointment:
            return value

        current = appointment.status
        # Define allowed transitions
        allowed_transitions = {
            AppointmentStatus.BOOKED: [
                AppointmentStatus.CHECKED_IN,
                AppointmentStatus.CANCELLED,
                AppointmentStatus.NO_SHOW,
            ],
            AppointmentStatus.CHECKED_IN: [
                AppointmentStatus.VITALS_DONE,
                AppointmentStatus.WITH_DOCTOR,
                AppointmentStatus.CANCELLED,
            ],
            AppointmentStatus.VITALS_DONE: [
                AppointmentStatus.WITH_DOCTOR,
                AppointmentStatus.CANCELLED,
            ],
            AppointmentStatus.WITH_DOCTOR: [
                AppointmentStatus.CONSULTATION_DONE,
            ],
            AppointmentStatus.CONSULTATION_DONE: [
                AppointmentStatus.AT_PHARMACY,
                AppointmentStatus.COMPLETED,
            ],
            AppointmentStatus.AT_PHARMACY: [
                AppointmentStatus.DISPENSED,
            ],
            AppointmentStatus.DISPENSED: [
                AppointmentStatus.COMPLETED,
            ],
        }

        allowed = allowed_transitions.get(current, [])
        if value not in allowed:
            raise serializers.ValidationError(
                f'Cannot transition from {current} to {value}. '
                f'Allowed: {[s for s in allowed]}'
            )

        return value
