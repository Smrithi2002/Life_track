"""
Medical Records App — Views
==============================
ViewSets for Diagnosis, MedicalRecord, and LabReport.
"""

import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsDoctorOrAdmin, IsAdminOrStaff
from accounts.utils import APIResponse

from .models import Diagnosis, MedicalRecord, LabReport
from .serializers import (
    DiagnosisSerializer, DiagnosisCreateSerializer,
    MedicalRecordSerializer, MedicalRecordCreateSerializer,
    LabReportSerializer, LabReportCreateSerializer,
)
from .services import MedicalRecordService

logger = logging.getLogger('medical_records')


class DiagnosisViewSet(viewsets.ModelViewSet):
    queryset = Diagnosis.objects.select_related('doctor', 'patient', 'appointment').all()
    serializer_class = DiagnosisSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return DiagnosisCreateSerializer
        return DiagnosisSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update']:
            return [IsAuthenticated(), IsDoctorOrAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == 'PATIENT':
            qs = qs.filter(patient=user)
        elif user.role == 'DOCTOR':
            qs = qs.filter(doctor=user)
        patient = self.request.query_params.get('patient')
        if patient:
            qs = qs.filter(patient_id=patient)
        appointment = self.request.query_params.get('appointment')
        if appointment:
            qs = qs.filter(appointment_id=appointment)
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        return APIResponse.success(data=DiagnosisSerializer(qs, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        return APIResponse.success(data=DiagnosisSerializer(self.get_object()).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        diagnosis = serializer.save(doctor=request.user)
        return APIResponse.success(
            data=DiagnosisSerializer(diagnosis).data,
            message='Diagnosis recorded.',
            status_code=status.HTTP_201_CREATED,
        )


class MedicalRecordViewSet(viewsets.ModelViewSet):
    queryset = MedicalRecord.objects.select_related('doctor', 'patient', 'appointment').all()
    serializer_class = MedicalRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return MedicalRecordCreateSerializer
        return MedicalRecordSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update']:
            return [IsAuthenticated(), IsDoctorOrAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == 'PATIENT':
            qs = qs.filter(patient=user)
        elif user.role == 'DOCTOR':
            qs = qs.filter(doctor=user)
        patient = self.request.query_params.get('patient')
        if patient:
            qs = qs.filter(patient_id=patient)
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        return APIResponse.success(
            data=MedicalRecordSerializer(qs, many=True, context={'request': request}).data,
        )

    def retrieve(self, request, *args, **kwargs):
        return APIResponse.success(
            data=MedicalRecordSerializer(self.get_object(), context={'request': request}).data,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = serializer.save(doctor=request.user)
        return APIResponse.success(
            data=MedicalRecordSerializer(record, context={'request': request}).data,
            message='Medical record created.',
            status_code=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'], url_path='patient-history')
    def patient_history(self, request):
        patient_id = request.query_params.get('patient')
        if not patient_id and request.user.role == 'PATIENT':
            patient_id = request.user.id
        if not patient_id:
            return APIResponse.error(message='patient query parameter required.')

        from accounts.models import User
        try:
            patient = User.objects.get(id=patient_id, role='PATIENT')
        except User.DoesNotExist:
            return APIResponse.error(message='Patient not found.', status_code=status.HTTP_404_NOT_FOUND)

        history = MedicalRecordService.get_patient_history(patient)
        return APIResponse.success(data={
            'patient': patient.full_name,
            'records': MedicalRecordSerializer(history['records'], many=True, context={'request': request}).data,
            'diagnoses': DiagnosisSerializer(history['diagnoses'], many=True).data,
        })


class LabReportViewSet(viewsets.ModelViewSet):
    queryset = LabReport.objects.select_related('patient', 'ordered_by', 'appointment').all()
    serializer_class = LabReportSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return LabReportCreateSerializer
        return LabReportSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), IsDoctorOrAdmin()]
        if self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), IsAdminOrStaff()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == 'PATIENT':
            qs = qs.filter(patient=user)
        elif user.role == 'DOCTOR':
            qs = qs.filter(ordered_by=user)
        patient = self.request.query_params.get('patient')
        if patient:
            qs = qs.filter(patient_id=patient)
        report_status = self.request.query_params.get('status')
        if report_status:
            qs = qs.filter(status=report_status.upper())
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        return APIResponse.success(data=LabReportSerializer(qs, many=True, context={'request': request}).data)

    def retrieve(self, request, *args, **kwargs):
        return APIResponse.success(data=LabReportSerializer(self.get_object(), context={'request': request}).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = serializer.save(ordered_by=request.user)
        return APIResponse.success(
            data=LabReportSerializer(report, context={'request': request}).data,
            message='Lab test ordered.',
            status_code=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='upload-result',
            permission_classes=[IsAuthenticated, IsAdminOrStaff])
    def upload_result(self, request, pk=None):
        report = self.get_object()
        result_summary = request.data.get('result_summary', '')
        file = request.FILES.get('file')
        report = MedicalRecordService.update_report_result(report, result_summary=result_summary, file=file)
        return APIResponse.success(
            data=LabReportSerializer(report, context={'request': request}).data,
            message='Lab report results updated.',
        )
