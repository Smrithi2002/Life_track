"""
HealthCard Views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsAdmin, IsAdminOrStaff, IsReceptionOrAdmin
from accounts.utils import APIResponse
from accounts.models import User

from .models import HealthCard, CardScanLog
from .serializers import (
    HealthCardSerializer,
    HealthCardCreateSerializer,
    CardScanLogSerializer,
    PatientCardLookupSerializer,
)
from .services import HealthCardService


class HealthCardViewSet(viewsets.ModelViewSet):
    """
    CRUD for health cards + custom actions.

    list:   GET  /healthcards/                 Admin/Staff
    create: POST /healthcards/                 Reception/Admin → generate card
    retrieve: GET /healthcards/{id}/           Any staff
    update: PUT  /healthcards/{id}/            Admin
    destroy: DELETE /healthcards/{id}/         Admin

    Custom:
        POST /healthcards/generate/            Reception/Admin → issue with QR
        GET  /healthcards/my-card/             Patient → own active card
        POST /healthcards/{id}/deactivate/     Reception/Admin
        POST /healthcards/{id}/report-lost/    Reception/Admin
        GET  /healthcards/scan/?card=MC-PAT-…  Any staff → QR lookup + audit
    """
    queryset           = HealthCard.objects.select_related('patient', 'issued_by').all()
    serializer_class   = HealthCardSerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def get_serializer_class(self):
        if self.action == 'create':
            return HealthCardCreateSerializer
        return HealthCardSerializer

    # --- Reception / Admin: issue a new card ---
    @action(detail=False, methods=['post'], url_path='generate',
            permission_classes=[IsAuthenticated, IsReceptionOrAdmin])
    def generate(self, request):
        serializer = HealthCardCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        card = HealthCardService.issue_card(
            patient=serializer.validated_data['patient'],
            issued_by=request.user,
            expiry_date=serializer.validated_data.get('expiry_date'),
            notes=serializer.validated_data.get('notes', ''),
        )

        return APIResponse.success(
            data=HealthCardSerializer(card, context={'request': request}).data,
            message=f'Health card issued for {card.patient.full_name}.',
            status_code=status.HTTP_201_CREATED,
        )

    # --- Patient: view own active card ---
    @action(detail=False, methods=['get'], url_path='my-card',
            permission_classes=[IsAuthenticated])
    def my_card(self, request):
        if request.user.role != 'PATIENT':
            return APIResponse.error(
                message='Only patients can access this endpoint.',
                status_code=status.HTTP_403_FORBIDDEN,
            )
        card = HealthCard.objects.filter(
            patient=request.user, is_active=True
        ).first()
        if not card:
            return APIResponse.error(
                message='No active health card found.',
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return APIResponse.success(
            data=HealthCardSerializer(card, context={'request': request}).data,
        )

    # --- Staff QR scan: lookup + audit ---
    @action(detail=False, methods=['get'], url_path='scan',
            permission_classes=[IsAuthenticated, IsAdminOrStaff])
    def scan(self, request):
        card_number = request.query_params.get('card')
        if not card_number:
            return APIResponse.error(message='card query parameter is required.')

        card = HealthCardService.lookup_by_card_number(card_number)
        if not card:
            return APIResponse.error(
                message=f'No active card found for {card_number}.',
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Log the scan
        purpose    = request.query_params.get('purpose', 'GENERAL').upper()
        department = request.query_params.get('department', '')
        HealthCardService.log_scan(card, request.user, request, purpose, department)

        return APIResponse.success(
            data=PatientCardLookupSerializer(card, context={'request': request}).data,
            message=f'Patient found: {card.patient.full_name}',
        )

    # --- Deactivate card ---
    @action(detail=True, methods=['post'], url_path='deactivate',
            permission_classes=[IsAuthenticated, IsReceptionOrAdmin])
    def deactivate(self, request, pk=None):
        card = self.get_object()
        reason = request.data.get('reason', HealthCard.CardStatus.EXPIRED)
        card.deactivate(reason=reason)
        return APIResponse.success(message=f'Card {card.card_number} deactivated.')

    # --- Report lost ---
    @action(detail=False, methods=['post'], url_path='report-lost',
            permission_classes=[IsAuthenticated, IsReceptionOrAdmin])
    def report_lost(self, request):
        card_number = request.data.get('card_number')
        if not card_number:
            return APIResponse.error(message='card_number is required.')
        card = HealthCardService.report_lost(card_number, request.user)
        if not card:
            return APIResponse.error(
                message='No active card found.',
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return APIResponse.success(message=f'Card {card_number} marked as lost.')


class CardScanLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only audit log of card scans.
    GET /card-scan-logs/          Admin only
    GET /card-scan-logs/{id}/     Admin only
    """
    queryset           = CardScanLog.objects.select_related('card', 'scanned_by').all()
    serializer_class   = CardScanLogSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def list(self, request, *args, **kwargs):
        card_number = request.query_params.get('card')
        qs = self.get_queryset()
        if card_number:
            qs = qs.filter(card__card_number=card_number)
        serializer = self.get_serializer(qs, many=True)
        return APIResponse.success(data=serializer.data)
