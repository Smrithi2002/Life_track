"""
Appointments App — Views
==========================
ViewSets for Department, DoctorProfile, DoctorSchedule,
Appointment, and Vitals.
"""

import logging
from datetime import date

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import (
    IsAdmin, IsAdminOrStaff, IsMedicalStaff,
    IsReceptionOrAdmin, IsDoctorOrAdmin, IsPatient,
)
from accounts.utils import APIResponse
from organizations.features import DepartmentsFeatureRequired, FeatureToggle

from .models import (
    Department, DoctorProfile, DoctorSchedule,
    Appointment, Vitals, AppointmentStatus,
)
from .serializers import (
    DepartmentSerializer,
    DoctorProfileSerializer, DoctorProfileCreateSerializer, DoctorListSerializer,
    DoctorScheduleSerializer,
    AppointmentSerializer, AppointmentCreateSerializer,
    FlutterAppointmentCreateSerializer,
    AppointmentStatusUpdateSerializer,
    VitalsSerializer, VitalsCreateSerializer,
)
from .services import (
    AppointmentService,
    AppointmentServiceError,
    SlotUnavailableError,
    InvalidTransitionError,
)

logger = logging.getLogger('appointments')


# ─────────────────────────────────────────────────────────────────────
#  DEPARTMENT
# ─────────────────────────────────────────────────────────────────────

class DepartmentViewSet(viewsets.ModelViewSet):
    """
    CRUD for hospital departments.
    - List/Retrieve: Any authenticated user
    - Create/Update/Delete: Admin only
    """
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']

    def get_permissions(self):
        perms = [IsAuthenticated(), DepartmentsFeatureRequired()]
        if self.action not in ['list', 'retrieve']:
            perms.append(IsAdmin())
        return perms

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        if not request.query_params.get('include_inactive'):
            qs = qs.filter(is_active=True)
        serializer = self.get_serializer(qs, many=True)
        return APIResponse.success(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return APIResponse.success(data=serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return APIResponse.success(
            data=serializer.data,
            message='Department created successfully.',
            status_code=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────────────────────────────────
#  DOCTOR PROFILE
# ─────────────────────────────────────────────────────────────────────

class DoctorProfileViewSet(viewsets.ModelViewSet):
    """
    Doctor profiles — public listing with search/filter.
    - List/Retrieve: Any authenticated user
    - Create/Update/Delete: Admin only
    """
    queryset = DoctorProfile.objects.select_related('user', 'department').all()
    filter_backends = [filters.SearchFilter]
    search_fields = ['user__full_name', 'specialization', 'department__name']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return DoctorProfileCreateSerializer
        if self.action == 'list':
            return DoctorListSerializer
        return DoctorProfileSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        
        organization = getattr(self.request, 'organization', None)
        if FeatureToggle.is_enabled(organization, 'enable_departments'):
            dept = self.request.query_params.get('department')
            if dept:
                qs = qs.filter(department_id=dept)
                
        available = self.request.query_params.get('available')
        if available is not None:
            qs = qs.filter(is_available=available.lower() in ('true', '1'))
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(qs, many=True)
        return APIResponse.success(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = DoctorProfileSerializer(instance, context={'request': request})
        return APIResponse.success(data=serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        return APIResponse.success(
            data=DoctorProfileSerializer(profile, context={'request': request}).data,
            message='Doctor profile created.',
            status_code=status.HTTP_201_CREATED,
        )

    # --- Available slots for a doctor ---
    @action(detail=True, methods=['get'], url_path='slots')
    def available_slots(self, request, pk=None):
        """GET /doctors/{id}/slots/?date=2026-04-29"""
        doctor = self.get_object()
        date_str = request.query_params.get('date')
        if not date_str:
            target_date = date.today()
        else:
            try:
                target_date = date.fromisoformat(date_str)
            except ValueError:
                return APIResponse.error(message='Invalid date format. Use YYYY-MM-DD.')

        slots = AppointmentService.get_available_slots(doctor, target_date)
        return APIResponse.success(data={
            'doctor': doctor.user.full_name,
            'date': str(target_date),
            'slots': slots,
        })


# ─────────────────────────────────────────────────────────────────────
#  DOCTOR SCHEDULE
# ─────────────────────────────────────────────────────────────────────

class DoctorScheduleViewSet(viewsets.ModelViewSet):
    """
    Doctor weekly schedule management.
    - Doctors can manage their own schedule
    - Admin can manage any schedule
    """
    queryset = DoctorSchedule.objects.select_related('doctor__user').all()
    serializer_class = DoctorScheduleSerializer
    permission_classes = [IsAuthenticated, IsDoctorOrAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        doctor_id = self.request.query_params.get('doctor')
        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)
        elif self.request.user.role == 'DOCTOR':
            qs = qs.filter(doctor__user=self.request.user)
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(qs, many=True)
        return APIResponse.success(data=serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return APIResponse.success(
            data=serializer.data,
            message='Schedule created.',
            status_code=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────────────────────────────────
#  APPOINTMENT
# ─────────────────────────────────────────────────────────────────────

class AppointmentViewSet(viewsets.ModelViewSet):
    """
    Appointment CRUD + status transition actions.

    list:     GET    /appointments/                 (filtered by role)
    create:   POST   /appointments/                 (Patient/Reception)
    retrieve: GET    /appointments/{id}/
    update:   PUT    /appointments/{id}/
    
    Custom actions:
      POST /appointments/{id}/check-in/         Nurse
      POST /appointments/{id}/start/            Doctor
      POST /appointments/{id}/complete/         Doctor
      POST /appointments/{id}/cancel/           Patient/Reception/Admin
      POST /appointments/{id}/update-status/    Staff
      GET  /appointments/my-appointments/       Patient
      GET  /appointments/doctor-queue/          Doctor
      GET  /appointments/today/                 Staff
    """
    queryset = Appointment.objects.select_related(
        'patient', 'doctor__user', 'doctor__department',
    ).all()
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            # Use the BFF Flutter payload format
            return FlutterAppointmentCreateSerializer
        return AppointmentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Role-based filtering
        if user.role == 'PATIENT':
            qs = qs.filter(patient=user)
        elif user.role == 'DOCTOR':
            qs = qs.filter(doctor__user=user)

        # Query params
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter.upper())

        date_filter = self.request.query_params.get('date')
        if date_filter:
            try:
                qs = qs.filter(appointment_date=date.fromisoformat(date_filter))
            except ValueError:
                pass

        doctor_filter = self.request.query_params.get('doctor')
        if doctor_filter:
            qs = qs.filter(doctor_id=doctor_filter)

        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return APIResponse.success(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return APIResponse.success(data=serializer.data)

    def create(self, request, *args, **kwargs):
        # Only patients should book via this mobile endpoint
        if request.user.role != 'PATIENT':
            return APIResponse.error(message="Only patients can book appointments via this endpoint.")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            appointment = AppointmentService.book_appointment(
                patient=request.user,
                doctor=data['doctor_id'],
                appointment_date=data['appointment_date'],
                time_slot=data['appointment_time'],
                appointment_type='BOOKED',
                chief_complaint=data.get('chief_complaint', ''),
                notes='',
            )
        except SlotUnavailableError as e:
            return APIResponse.error(
                message=str(e),
                status_code=status.HTTP_409_CONFLICT,
            )

        # Build custom Flutter BFF response
        custom_response = {
            "id": str(appointment.id),
            "doctor": {
                "id": str(appointment.doctor.id),
                "name": f"Dr. {appointment.doctor.user.full_name}",
                "specialization": appointment.doctor.specialization or "General",
                "experience_years": appointment.doctor.experience_years
            },
            "department": {
                "id": str(appointment.doctor.department.id) if appointment.doctor.department else "",
                "name": appointment.doctor.department.name if appointment.doctor.department else "General"
            },
            "appointment_date": str(appointment.appointment_date),
            "appointment_time": str(appointment.time_slot)[:5], # format HH:MM
            "duration_minutes": 15, # Hardcoded default or fetch from schedule
            "chief_complaint": appointment.chief_complaint,
            "status": "pending" if appointment.status == AppointmentStatus.BOOKED else appointment.status.lower(),
            "created_at": appointment.created_at.isoformat()
        }

        return APIResponse.success(
            data={"appointment": custom_response},
            message='Appointment created successfully',
            status_code=status.HTTP_201_CREATED,
        )

    # --- Check In (Nurse) ---
    @action(detail=True, methods=['post'], url_path='check-in',
            permission_classes=[IsAuthenticated, IsMedicalStaff])
    def check_in(self, request, pk=None):
        appointment = self.get_object()
        try:
            appointment = AppointmentService.check_in(appointment)
        except InvalidTransitionError as e:
            return APIResponse.error(message=str(e))
        return APIResponse.success(
            data=AppointmentSerializer(appointment, context={'request': request}).data,
            message=f'Patient {appointment.patient.full_name} checked in.',
        )

    # --- Start Consultation (Doctor) ---
    @action(detail=True, methods=['post'], url_path='start',
            permission_classes=[IsAuthenticated, IsDoctorOrAdmin])
    def start_consultation(self, request, pk=None):
        appointment = self.get_object()
        try:
            appointment = AppointmentService.start_consultation(appointment)
        except InvalidTransitionError as e:
            return APIResponse.error(message=str(e))
        return APIResponse.success(
            data=AppointmentSerializer(appointment, context={'request': request}).data,
            message='Consultation started.',
        )

    # --- Complete Consultation (Doctor) ---
    @action(detail=True, methods=['post'], url_path='complete',
            permission_classes=[IsAuthenticated, IsDoctorOrAdmin])
    def complete_consultation(self, request, pk=None):
        appointment = self.get_object()
        try:
            appointment = AppointmentService.complete_consultation(appointment)
        except InvalidTransitionError as e:
            return APIResponse.error(message=str(e))
        return APIResponse.success(
            data=AppointmentSerializer(appointment, context={'request': request}).data,
            message='Consultation completed.',
        )

    # --- Cancel Appointment ---
    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        appointment = self.get_object()
        reason = request.data.get('reason', '')
        try:
            appointment = AppointmentService.cancel_appointment(appointment, reason)
        except InvalidTransitionError as e:
            return APIResponse.error(message=str(e))
        return APIResponse.success(
            message=f'Appointment {appointment.token_number} cancelled.',
        )

    # --- Generic Status Update (Staff) ---
    @action(detail=True, methods=['post'], url_path='update-status',
            permission_classes=[IsAuthenticated, IsAdminOrStaff])
    def update_status(self, request, pk=None):
        appointment = self.get_object()
        serializer = AppointmentStatusUpdateSerializer(
            data=request.data,
            context={'appointment': appointment},
        )
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data['status']
        reason = serializer.validated_data.get('reason', '')

        appointment = AppointmentService.update_status(appointment, new_status, reason)
        return APIResponse.success(
            data=AppointmentSerializer(appointment, context={'request': request}).data,
            message=f'Status updated to {appointment.get_status_display()}.',
        )

    # --- Patient's own appointments ---
    @action(detail=False, methods=['get'], url_path='my-appointments')
    def my_appointments(self, request):
        qs = Appointment.objects.filter(
            patient=request.user,
        ).select_related('doctor__user', 'doctor__department').order_by('-appointment_date')

        upcoming_qs = qs.filter(
            appointment_date__gte=date.today(),
        ).exclude(status__in=[AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED])

        past_qs = qs.filter(
            status__in=[AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED],
        ) | qs.filter(appointment_date__lt=date.today())

        def format_appointment(appt):
            return {
                "id": str(appt.id),
                "doctor_name": f"Dr. {appt.doctor.user.full_name}",
                "specialization": appt.doctor.specialization or "General",
                "appointment_date": str(appt.appointment_date),
                "appointment_time": str(appt.time_slot)[:5],
                "duration_minutes": 15,
                "status": "pending" if appt.status == AppointmentStatus.BOOKED else appt.status.lower()
            }

        return APIResponse.success(data={
            'upcoming': [format_appointment(a) for a in upcoming_qs.distinct()[:10]],
            'history': [format_appointment(a) for a in past_qs.distinct()[:20]],
        })

    # --- Doctor Queue ---
    @action(detail=False, methods=['get'], url_path='doctor-queue',
            permission_classes=[IsAuthenticated, IsDoctorOrAdmin])
    def doctor_queue(self, request):
        doctor_id = request.query_params.get('doctor')
        if doctor_id:
            try:
                doctor = DoctorProfile.objects.get(id=doctor_id)
            except DoctorProfile.DoesNotExist:
                return APIResponse.error(message='Doctor not found.', status_code=status.HTTP_404_NOT_FOUND)
        elif request.user.role == 'DOCTOR':
            try:
                doctor = request.user.doctor_profile
            except DoctorProfile.DoesNotExist:
                return APIResponse.error(message='Doctor profile not found.', status_code=status.HTTP_404_NOT_FOUND)
        else:
            return APIResponse.error(message='doctor query parameter required.')

        queue = AppointmentService.get_doctor_queue(doctor)
        return APIResponse.success(data={
            'doctor': doctor.user.full_name,
            'date': str(date.today()),
            'queue_count': queue.count(),
            'queue': AppointmentSerializer(queue, many=True, context={'request': request}).data,
        })

    # --- Today's appointments (Staff) ---
    @action(detail=False, methods=['get'], url_path='today',
            permission_classes=[IsAuthenticated, IsAdminOrStaff])
    def today(self, request):
        today_date = date.today()
        qs = Appointment.objects.filter(
            appointment_date=today_date,
        ).select_related('patient', 'doctor__user')

        doctor_id = request.query_params.get('doctor')
        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)
        elif request.user.role == 'DOCTOR':
            qs = qs.filter(doctor__user=request.user)

        qs = qs.exclude(status=AppointmentStatus.CANCELLED).order_by('time_slot')

        return APIResponse.success(data={
            'date': str(today_date),
            'total': qs.count(),
            'appointments': AppointmentSerializer(qs, many=True, context={'request': request}).data,
        })


# ─────────────────────────────────────────────────────────────────────
#  VITALS
# ─────────────────────────────────────────────────────────────────────

class VitalsViewSet(viewsets.ModelViewSet):
    """
    Vitals recording and viewing.
    - Create: Nurse/Doctor/Admin
    - View: Medical staff or patient (own records)
    """
    queryset = Vitals.objects.select_related(
        'appointment__patient', 'appointment__doctor__user', 'recorded_by',
    ).all()
    serializer_class = VitalsSerializer

    def get_serializer_class(self):
        if self.action == 'create':
            return VitalsCreateSerializer
        return VitalsSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update']:
            return [IsAuthenticated(), IsMedicalStaff()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.role == 'PATIENT':
            qs = qs.filter(appointment__patient=user)
        elif user.role == 'DOCTOR':
            qs = qs.filter(appointment__doctor__user=user)

        appointment_id = self.request.query_params.get('appointment')
        if appointment_id:
            qs = qs.filter(appointment_id=appointment_id)

        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(qs, many=True)
        return APIResponse.success(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return APIResponse.success(data=serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        appointment = serializer.validated_data['appointment']
        vitals_data = {k: v for k, v in serializer.validated_data.items() if k != 'appointment'}

        try:
            vitals = AppointmentService.record_vitals(
                appointment=appointment,
                recorded_by=request.user,
                vitals_data=vitals_data,
            )
        except InvalidTransitionError as e:
            return APIResponse.error(message=str(e))

        return APIResponse.success(
            data=VitalsSerializer(vitals, context={'request': request}).data,
            message='Vitals recorded successfully.',
            status_code=status.HTTP_201_CREATED,
        )
