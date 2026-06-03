"""
Organizations — Views
=======================
REST API views for Organization settings and feature toggles.

Endpoints:
  GET  /api/v1/organization/          → Current org info (all authenticated users)
  PUT  /api/v1/organization/          → Update org settings (Admin only)
  PATCH /api/v1/organization/         → Partial update (Admin only)
  GET  /api/v1/organization/features/ → All feature toggles with status
  PATCH /api/v1/organization/features/→ Toggle a single feature (Admin only)
  POST /api/v1/organization/switch-mode/ → Switch CLINIC ↔ HOSPITAL (Admin only)
"""

import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Organization, SetupType
from .serializers import (
    OrganizationPublicSerializer,
    OrganizationAdminSerializer,
    FeatureToggleSerializer,
    FeatureToggleUpdateSerializer,
)
from .features import FeatureToggle, KNOWN_FEATURES
from .middleware import invalidate_organization_cache

logger = logging.getLogger(__name__)


def _is_admin(user):
    """Check if user is an admin."""
    return user.is_authenticated and (user.is_staff or getattr(user, 'role', None) == 'ADMIN')


# ─────────────────────────────────────────────────────────────────────
#  ORGANIZATION DETAIL + UPDATE
# ─────────────────────────────────────────────────────────────────────

class OrganizationView(APIView):
    """
    GET  → Returns current organization info (role-based serializer)
    PUT  → Full update (Admin only)
    PATCH → Partial update (Admin only)
    """
    permission_classes = [IsAuthenticated]

    def _get_organization(self, request):
        """Get org from request or DB fallback."""
        org = getattr(request, 'organization', None)
        if org is None:
            org = Organization.objects.filter(is_active=True).order_by('created_at').first()
        return org

    def get(self, request):
        org = self._get_organization(request)
        if org is None:
            return Response(
                {
                    'error': 'no_organization',
                    'message': 'No organization has been configured yet. '
                               'Run: python manage.py create_default_organization',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Admin gets full details; others get public view
        if _is_admin(request.user):
            serializer = OrganizationAdminSerializer(org, context={'request': request})
        else:
            serializer = OrganizationPublicSerializer(org, context={'request': request})

        return Response(serializer.data)

    def patch(self, request):
        return self._update(request, partial=True)

    def put(self, request):
        return self._update(request, partial=False)

    def _update(self, request, partial=False):
        if not _is_admin(request.user):
            return Response(
                {'error': 'permission_denied', 'message': 'Only admins can update organization settings.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        org = self._get_organization(request)
        if org is None:
            return Response(
                {'error': 'no_organization', 'message': 'No organization found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OrganizationAdminSerializer(
            org,
            data=request.data,
            partial=partial,
            context={'request': request},
        )
        if serializer.is_valid():
            org = serializer.save()
            logger.info(
                'Organization updated by %s: %s',
                request.user.user_id,
                list(request.data.keys()),
            )
            return Response(OrganizationAdminSerializer(org).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────────
#  FEATURE TOGGLES
# ─────────────────────────────────────────────────────────────────────

class FeatureListView(APIView):
    """
    GET  /api/v1/organization/features/
    Returns all feature toggles with their current status.
    Available to all authenticated users.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = getattr(request, 'organization', None)
        features = FeatureToggle.get_all(org)

        # Enrich with metadata
        feature_details = []
        feature_meta = {
            'enable_departments':    {'label': 'Departments', 'description': 'Department-based doctor routing and filtering.', 'module': 'core'},
            'enable_lab':            {'label': 'Lab Management', 'description': 'Lab test ordering, sample tracking, and result management.', 'module': 'hospital'},
            'enable_pharmacy':       {'label': 'Pharmacy', 'description': 'Medicine dispensing and inventory management.', 'module': 'core'},
            'enable_ipd':            {'label': 'In-Patient Department (IPD)', 'description': 'Ward management, bed allocation, and inpatient care.', 'module': 'hospital'},
            'enable_analytics':      {'label': 'Analytics & Reports', 'description': 'Revenue reports, patient trends, and doctor performance dashboards.', 'module': 'enterprise'},
            'enable_multi_doctor':   {'label': 'Multi-Doctor', 'description': 'Support for multiple doctors in the same organization.', 'module': 'core'},
            'enable_online_booking': {'label': 'Online Booking', 'description': 'Patient app appointment booking.', 'module': 'core'},
            'enable_telemedicine':   {'label': 'Telemedicine', 'description': 'Video consultation and remote care.', 'module': 'enterprise'},
        }

        for feature_name, is_enabled in features.items():
            meta = feature_meta.get(feature_name, {})
            feature_details.append({
                'feature':     feature_name,
                'label':       meta.get('label', feature_name),
                'description': meta.get('description', ''),
                'module':      meta.get('module', 'core'),
                'enabled':     is_enabled,
            })

        return Response({
            'organization': org.name if org else 'Default',
            'setup_type':   org.setup_type if org else 'CLINIC',
            'features':     feature_details,
        })


class FeatureToggleView(APIView):
    """
    PATCH /api/v1/organization/features/
    Toggle a specific feature on or off.
    Admin only.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        if not _is_admin(request.user):
            return Response(
                {'error': 'permission_denied', 'message': 'Only admins can toggle features.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = FeatureToggleUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        feature  = serializer.validated_data['feature']
        enabled  = serializer.validated_data['enabled']

        org = getattr(request, 'organization', None)
        if org is None:
            org = Organization.objects.filter(is_active=True).order_by('created_at').first()

        if org is None:
            return Response(
                {'error': 'no_organization', 'message': 'No organization found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        setattr(org, feature, enabled)
        org.save(update_fields=[feature, 'updated_at'])
        invalidate_organization_cache()

        logger.info(
            'Feature "%s" set to %s by admin %s',
            feature, enabled, request.user.user_id,
        )

        return Response({
            'success': True,
            'feature': feature,
            'enabled': enabled,
            'message': f'Feature "{feature}" has been {"enabled" if enabled else "disabled"}.',
        })


# ─────────────────────────────────────────────────────────────────────
#  MODE SWITCHER
# ─────────────────────────────────────────────────────────────────────

class OrganizationModeSwitchView(APIView):
    """
    POST /api/v1/organization/switch-mode/
    Switch between CLINIC and HOSPITAL modes.
    Admin only. Applies default feature flags for the new mode.

    Body: {"setup_type": "HOSPITAL", "apply_defaults": true}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _is_admin(request.user):
            return Response(
                {'error': 'permission_denied', 'message': 'Only admins can switch organization mode.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        new_type = request.data.get('setup_type')
        apply_defaults = request.data.get('apply_defaults', True)

        if new_type not in [SetupType.CLINIC, SetupType.HOSPITAL]:
            return Response(
                {'error': 'invalid_setup_type', 'message': f'setup_type must be CLINIC or HOSPITAL. Got: {new_type}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        org = getattr(request, 'organization', None)
        if org is None:
            org = Organization.objects.filter(is_active=True).order_by('created_at').first()

        if org is None:
            return Response({'error': 'no_organization'}, status=status.HTTP_404_NOT_FOUND)

        old_type = org.setup_type
        org.setup_type = new_type

        if apply_defaults:
            if new_type == SetupType.HOSPITAL:
                org.apply_hospital_defaults()
            else:
                org.apply_clinic_defaults()

        org.save()
        invalidate_organization_cache()

        logger.info(
            'Organization mode switched %s → %s by admin %s (apply_defaults=%s)',
            old_type, new_type, request.user.user_id, apply_defaults,
        )

        return Response({
            'success':      True,
            'old_mode':     old_type,
            'new_mode':     new_type,
            'apply_defaults': apply_defaults,
            'features':     FeatureToggle.get_all(org),
            'message': (
                f'Organization switched from {old_type} to {new_type} mode. '
                + ('Default features applied.' if apply_defaults else 'Features unchanged.')
            ),
        })
