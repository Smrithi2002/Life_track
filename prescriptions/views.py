"""
Prescriptions App — Views
===========================
ViewSets for Medicine, Prescription, and PharmacyOrder.
"""

import logging
from django.db import models
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import (
    IsAdmin, IsAdminOrStaff, IsDoctorOrAdmin,
    IsPharmacistOrAdmin, IsMedicalStaff,
)
from accounts.utils import APIResponse

from .models import (
    Medicine, Prescription, PrescriptionItem,
    PharmacyOrder, PrescriptionStatus,
)
from .serializers import (
    MedicineSerializer, MedicineListSerializer,
    PrescriptionSerializer, PrescriptionCreateSerializer,
    PrescriptionItemSerializer,
    PharmacyOrderSerializer, PharmacyOrderStatusSerializer,
)
from .services import (
    PrescriptionService,
    PrescriptionServiceError,
    InsufficientStockError,
)

logger = logging.getLogger('prescriptions')


# ─────────────────────────────────────────────────────────────────────
#  MEDICINE CATALOG
# ─────────────────────────────────────────────────────────────────────

class MedicineViewSet(viewsets.ModelViewSet):
    """
    Medicine catalog management.
    - List/Search: Any staff
    - Create/Update/Delete: Admin/Pharmacist
    """
    queryset = Medicine.objects.all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'generic_name', 'manufacturer']
    ordering_fields = ['name', 'unit_price', 'stock_quantity']

    def get_serializer_class(self):
        if self.action == 'list':
            return MedicineListSerializer
        return MedicineSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated(), IsAdminOrStaff()]
        return [IsAuthenticated(), IsPharmacistOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category.upper())
        if not self.request.query_params.get('include_inactive'):
            qs = qs.filter(is_active=True)
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
        serializer = MedicineSerializer(instance)
        return APIResponse.success(data=serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = MedicineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return APIResponse.success(
            data=serializer.data,
            message='Medicine added to catalog.',
            status_code=status.HTTP_201_CREATED,
        )

    # --- Low stock alert ---
    @action(detail=False, methods=['get'], url_path='low-stock',
            permission_classes=[IsAuthenticated, IsPharmacistOrAdmin])
    def low_stock(self, request):
        qs = Medicine.objects.filter(
            is_active=True,
            stock_quantity__lte=models.F('reorder_level'),
        )
        serializer = MedicineSerializer(qs, many=True)
        return APIResponse.success(data={
            'count': qs.count(),
            'medicines': serializer.data,
        })

    # --- Update stock ---
    @action(detail=True, methods=['post'], url_path='update-stock',
            permission_classes=[IsAuthenticated, IsPharmacistOrAdmin])
    def update_stock(self, request, pk=None):
        medicine = self.get_object()
        quantity = request.data.get('quantity')
        action_type = request.data.get('action', 'add')  # 'add' or 'set'

        if quantity is None:
            return APIResponse.error(message='quantity is required.')

        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            return APIResponse.error(message='quantity must be an integer.')

        if action_type == 'set':
            medicine.stock_quantity = max(0, quantity)
        else:
            medicine.stock_quantity = max(0, medicine.stock_quantity + quantity)

        medicine.save(update_fields=['stock_quantity', 'updated_at'])
        return APIResponse.success(
            data=MedicineSerializer(medicine).data,
            message=f'Stock updated. Current: {medicine.stock_quantity}',
        )


# ─────────────────────────────────────────────────────────────────────
#  PRESCRIPTION
# ─────────────────────────────────────────────────────────────────────

class PrescriptionViewSet(viewsets.ModelViewSet):
    """
    Prescription management.
    - Create: Doctor
    - View: Doctor, Patient (own), Medical staff
    - Send to pharmacy: Doctor/Admin
    """
    queryset = Prescription.objects.select_related(
        'doctor', 'patient', 'appointment',
    ).prefetch_related('items__medicine').all()
    serializer_class = PrescriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return PrescriptionCreateSerializer
        return PrescriptionSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), IsDoctorOrAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.role == 'PATIENT':
            qs = qs.filter(patient=user)
        elif user.role == 'DOCTOR':
            qs = qs.filter(doctor=user)
        elif user.role == 'PHARMACIST':
            qs = qs.filter(status__in=[
                PrescriptionStatus.AT_PHARMACY,
                PrescriptionStatus.PARTIALLY_DISPENSED,
            ])

        patient_filter = self.request.query_params.get('patient')
        if patient_filter:
            qs = qs.filter(patient_id=patient_filter)

        appointment_filter = self.request.query_params.get('appointment')
        if appointment_filter:
            qs = qs.filter(appointment_id=appointment_filter)

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
        prescription = serializer.save()

        return APIResponse.success(
            data=PrescriptionSerializer(prescription, context={'request': request}).data,
            message='Prescription created.',
            status_code=status.HTTP_201_CREATED,
        )

    # --- Send to Pharmacy ---
    @action(detail=True, methods=['post'], url_path='send-to-pharmacy',
            permission_classes=[IsAuthenticated, IsDoctorOrAdmin])
    def send_to_pharmacy(self, request, pk=None):
        prescription = self.get_object()
        try:
            order = PrescriptionService.send_to_pharmacy(prescription)
        except PrescriptionServiceError as e:
            return APIResponse.error(message=str(e))

        return APIResponse.success(
            data=PharmacyOrderSerializer(order, context={'request': request}).data,
            message='Prescription sent to pharmacy.',
        )

    # --- Patient's prescriptions ---
    @action(detail=False, methods=['get'], url_path='my-prescriptions')
    def my_prescriptions(self, request):
        qs = Prescription.objects.filter(
            patient=request.user,
        ).select_related('doctor', 'appointment').prefetch_related(
            'items__medicine',
        ).order_by('-created_at')

        serializer = PrescriptionSerializer(qs, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data)


# ─────────────────────────────────────────────────────────────────────
#  PHARMACY ORDER
# ─────────────────────────────────────────────────────────────────────

class PharmacyOrderViewSet(viewsets.ModelViewSet):
    """
    Pharmacy order / dispensing management.
    - List/View: Pharmacist, Admin
    - Dispense: Pharmacist, Admin
    """
    queryset = PharmacyOrder.objects.select_related(
        'prescription__patient', 'prescription__doctor', 'dispensed_by',
    ).all()
    serializer_class = PharmacyOrderSerializer
    permission_classes = [IsAuthenticated, IsPharmacistOrAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(qs, many=True)
        return APIResponse.success(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return APIResponse.success(data=serializer.data)

    # --- Dispense Order ---
    @action(detail=True, methods=['post'], url_path='dispense')
    def dispense(self, request, pk=None):
        order = self.get_object()
        dispensed_items = request.data.get('items')  # Optional: specific item IDs
        notes = request.data.get('notes', '')

        try:
            order = PrescriptionService.dispense_order(
                order=order,
                dispensed_by=request.user,
                dispensed_items=dispensed_items,
                notes=notes,
            )
        except InsufficientStockError as e:
            return APIResponse.error(
                message=str(e),
                status_code=status.HTTP_409_CONFLICT,
            )
        except PrescriptionServiceError as e:
            return APIResponse.error(message=str(e))

        return APIResponse.success(
            data=PharmacyOrderSerializer(order, context={'request': request}).data,
            message='Medicines dispensed.',
        )

    # --- Pharmacy Queue ---
    @action(detail=False, methods=['get'], url_path='queue')
    def pharmacy_queue(self, request):
        queue = PrescriptionService.get_pharmacy_queue()
        serializer = PharmacyOrderSerializer(queue, many=True, context={'request': request})
        return APIResponse.success(data={
            'queue_count': queue.count(),
            'orders': serializer.data,
        })
