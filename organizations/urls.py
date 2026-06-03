"""
Organizations — URL Configuration
====================================
All routes prefixed with /api/v1/organization/
"""

from django.urls import path
from .views import (
    OrganizationView,
    FeatureListView,
    FeatureToggleView,
    OrganizationModeSwitchView,
)

urlpatterns = [
    # GET        → Current org details (all authenticated users)
    # PUT/PATCH  → Update org settings (Admin only)
    path('organization/', OrganizationView.as_view(), name='organization-detail'),

    # GET   → List all feature toggles with status (all authenticated)
    # PATCH → Toggle a specific feature (Admin only)
    path('organization/features/', FeatureListView.as_view(), name='organization-features'),
    path('organization/features/toggle/', FeatureToggleView.as_view(), name='organization-feature-toggle'),

    # POST → Switch CLINIC ↔ HOSPITAL mode (Admin only)
    path('organization/switch-mode/', OrganizationModeSwitchView.as_view(), name='organization-switch-mode'),
]
