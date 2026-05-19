"""Billing App — Views"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsAdmin, IsReceptionOrAdmin, IsAdminOrStaff
from accounts.utils import APIResponse
from .models import Invoice, Payment, PaymentStatus
from .serializers import (
    InvoiceSerializer, InvoiceCreateSerializer,
    PaymentSerializer, PaymentCreateSerializer,
)
from .services import BillingService
logger = logging.getLogger('billing')


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related('patient', 'appointment', 'created_by').prefetch_related('items', 'payments').all()
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return InvoiceCreateSerializer
        return InvoiceSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), IsReceptionOrAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == 'PATIENT':
            qs = qs.filter(patient=self.request.user)
        patient = self.request.query_params.get('patient')
        if patient:
            qs = qs.filter(patient_id=patient)
        payment_status = self.request.query_params.get('status')
        if payment_status:
            qs = qs.filter(payment_status=payment_status.upper())
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(qs, many=True)
        return APIResponse.success(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return APIResponse.success(data=InvoiceSerializer(instance, context={'request': request}).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save()
        return APIResponse.success(
            data=InvoiceSerializer(invoice, context={'request': request}).data,
            message=f'Invoice {invoice.invoice_number} created.',
            status_code=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='pay',
            permission_classes=[IsAuthenticated])
    def record_payment(self, request, pk=None):
        invoice = self.get_object()
        ser = PaymentCreateSerializer(data={**request.data, 'invoice': str(invoice.id)})
        ser.is_valid(raise_exception=True)
        payment = BillingService.record_payment(
            invoice=invoice,
            amount=ser.validated_data['amount'],
            payment_method=ser.validated_data['payment_method'],
            gateway_txn_id=ser.validated_data.get('gateway_txn_id', ''),
        )
        return APIResponse.success(
            data=PaymentSerializer(payment).data,
            message='Payment recorded.',
        )

    @action(detail=False, methods=['get'], url_path='my-invoices')
    def my_invoices(self, request):
        qs = Invoice.objects.filter(patient=request.user).order_by('-created_at')
        return APIResponse.success(data=InvoiceSerializer(qs, many=True, context={'request': request}).data)


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Payment.objects.select_related('invoice__patient').all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        return APIResponse.success(data=PaymentSerializer(qs, many=True).data)
