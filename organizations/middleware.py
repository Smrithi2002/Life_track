"""
Organizations — Middleware
============================
Attaches `request.organization` to every incoming request.

Single-tenant behavior (current):
  • Fetches the first active Organization in the DB
  • Caches it in memory after first fetch

Multi-tenant behavior (future):
  • Read org slug from request header: X-Organization-Slug
  • Read org from subdomain: srisai.medconnect.app
  • Both approaches are stubbed here for future activation

Usage in views:
    def my_view(request):
        org = request.organization  # Organization instance or None
        if request.organization and request.organization.enable_lab:
            ...
"""

import logging
from django.core.cache import cache
from .models import Organization

logger = logging.getLogger(__name__)

# Cache key for single-tenant org
_ORG_CACHE_KEY = 'medconnect:default_organization'
_ORG_CACHE_TTL = 300  # 5 minutes


class OrganizationMiddleware:
    """
    Django middleware that attaches the current Organization to every request.

    Resolves organization in this priority order:
    1. X-Organization-Slug header (future multi-tenant)
    2. Authenticated user's organization FK (if set)
    3. First/default active organization (single-tenant fallback)
    4. None (if no organization exists yet — during initial setup)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organization = self._resolve_organization(request)
        response = self.get_response(request)
        return response

    def _resolve_organization(self, request):
        """Resolve the organization for this request."""

        # ── Priority 1: X-Organization-Slug header (multi-tenant ready) ──
        slug = request.headers.get('X-Organization-Slug')
        if slug:
            return self._get_by_slug(slug)

        # ── Priority 2: Authenticated user's organization ─────────────
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_org = getattr(request.user, 'organization', None)
            if user_org is not None:
                return user_org

        # ── Priority 3: Default (single-tenant) from cache ────────────
        return self._get_default()

    def _get_by_slug(self, slug: str):
        """Fetch org by slug (used for multi-tenant header routing)."""
        try:
            return Organization.objects.select_related().get(slug=slug, is_active=True)
        except Organization.DoesNotExist:
            logger.warning('OrganizationMiddleware: No active org found for slug "%s"', slug)
            return None

    def _get_default(self):
        """
        Get the default (only) organization for single-tenant deployments.
        Cached to avoid DB hit on every request.
        """
        # Try cache first
        cached = cache.get(_ORG_CACHE_KEY)
        if cached is not None:
            return cached

        # Fetch from DB
        try:
            org = Organization.objects.filter(is_active=True).order_by('created_at').first()
            if org:
                cache.set(_ORG_CACHE_KEY, org, _ORG_CACHE_TTL)
            return org
        except Exception as exc:
            # During migrations, Organization table may not exist yet
            logger.debug(
                'OrganizationMiddleware: Could not load organization (may be during setup): %s',
                exc,
            )
            return None


def invalidate_organization_cache():
    """
    Call this whenever an Organization is saved/updated,
    so the middleware picks up the new settings.
    Hook this into Organization's post_save signal.
    """
    cache.delete(_ORG_CACHE_KEY)
    logger.info('OrganizationMiddleware: Cache invalidated.')
