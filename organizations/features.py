"""
Organizations — Feature Toggle System
========================================
Centralized feature checking utility.

Usage:
    from organizations.features import FeatureToggle

    # In a view:
    if FeatureToggle.is_enabled(request.organization, 'enable_lab'):
        ...

    # As a DRF permission class:
    class LabView(APIView):
        permission_classes = [IsAuthenticated, LabFeatureRequired]

    # As a decorator:
    @require_feature('enable_departments')
    def some_view(request): ...
"""

import functools
import logging
from django.conf import settings
from rest_framework.exceptions import PermissionDenied

logger = logging.getLogger(__name__)

# ── All known feature names ───────────────────────────────────────────
KNOWN_FEATURES = {
    'enable_departments',
    'enable_lab',
    'enable_pharmacy',
    'enable_ipd',
    'enable_analytics',
    'enable_multi_doctor',
    'enable_online_booking',
    'enable_telemedicine',
}


class FeatureToggle:
    """
    Centralized feature toggle checker.
    Works with an Organization instance or falls back to Django settings defaults.
    """

    @staticmethod
    def is_enabled(organization, feature: str) -> bool:
        """
        Check if a feature is enabled for the given organization.

        Args:
            organization: Organization model instance, or None (uses settings defaults)
            feature: Feature flag name (e.g., 'enable_lab')

        Returns:
            bool: True if feature is enabled
        """
        if feature not in KNOWN_FEATURES:
            logger.warning(
                'FeatureToggle: Unknown feature "%s" checked. '
                'Add it to organizations/features.py KNOWN_FEATURES.',
                feature,
            )
            return False

        # Primary: check the Organization model
        if organization is not None:
            return bool(getattr(organization, feature, False))

        # Fallback: check Django settings defaults
        org_defaults = getattr(settings, 'ORGANIZATION_DEFAULTS', {})
        return bool(org_defaults.get(feature, False))

    @staticmethod
    def require(organization, feature: str, raise_exception: bool = True) -> bool:
        """
        Assert that a feature is enabled. Raises PermissionDenied if not.

        Args:
            organization: Organization instance
            feature: Feature flag name
            raise_exception: If True, raises PermissionDenied when disabled

        Returns:
            bool: True if enabled, False if disabled (only when raise_exception=False)
        """
        if not FeatureToggle.is_enabled(organization, feature):
            if raise_exception:
                feature_label = feature.replace('enable_', '').replace('_', ' ').title()
                raise PermissionDenied(
                    detail={
                        'error': 'feature_disabled',
                        'message': (
                            f'The "{feature_label}" module is not enabled for your organization. '
                            f'Contact your administrator to enable it.'
                        ),
                        'feature': feature,
                    }
                )
            return False
        return True

    @staticmethod
    def get_all(organization) -> dict:
        """
        Get all feature flags as a dict for the given organization.

        Returns:
            dict: {feature_name: bool, ...}
        """
        if organization is not None:
            return organization.get_feature_map()

        # Fallback to settings defaults
        org_defaults = getattr(settings, 'ORGANIZATION_DEFAULTS', {})
        return {feature: org_defaults.get(feature, False) for feature in KNOWN_FEATURES}


# ── DRF Permission Classes ────────────────────────────────────────────

class FeatureRequired:
    """
    DRF Permission class factory for feature gating.

    Usage:
        class MyView(APIView):
            permission_classes = [IsAuthenticated, FeatureRequired('enable_lab')]

    This is a factory — call it with the feature name to get a permission class.
    """

    def __new__(cls, feature_name: str):
        """Return a new DRF BasePermission subclass for the given feature."""
        from rest_framework.permissions import BasePermission

        class _FeaturePermission(BasePermission):
            _feature = feature_name

            def has_permission(self, request, view):
                organization = getattr(request, 'organization', None)
                if not FeatureToggle.is_enabled(organization, self._feature):
                    self.message = {
                        'error': 'feature_disabled',
                        'feature': self._feature,
                        'message': (
                            f'The "{self._feature.replace("enable_", "").replace("_", " ").title()}" '
                            f'module is not enabled for your organization.'
                        ),
                    }
                    return False
                return True

        _FeaturePermission.__name__ = f'FeatureRequired_{feature_name}'
        _FeaturePermission.__doc__ = f'Requires {feature_name} to be enabled.'
        return _FeaturePermission


# ── View Decorator ────────────────────────────────────────────────────

def require_feature(feature_name: str):
    """
    Function decorator to gate a Django/DRF view by feature flag.

    Usage:
        @require_feature('enable_lab')
        def lab_order_view(request, *args, **kwargs):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request_or_self, *args, **kwargs):
            # Handle both function-based views and class-based view methods
            if hasattr(request_or_self, 'request'):
                # CBV method: first arg is `self`, second is `request`
                request = args[0] if args else None
            else:
                request = request_or_self

            organization = getattr(request, 'organization', None) if request else None
            FeatureToggle.require(organization, feature_name, raise_exception=True)
            return func(request_or_self, *args, **kwargs)

        return wrapper
    return decorator


# ── Pre-built Permission Classes (convenience imports) ────────────────
DepartmentsFeatureRequired = FeatureRequired('enable_departments')
LabFeatureRequired          = FeatureRequired('enable_lab')
PharmacyFeatureRequired     = FeatureRequired('enable_pharmacy')
IPDFeatureRequired          = FeatureRequired('enable_ipd')
AnalyticsFeatureRequired    = FeatureRequired('enable_analytics')
