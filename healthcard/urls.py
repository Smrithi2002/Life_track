"""HealthCard App — URL Configuration"""
from rest_framework.routers import DefaultRouter
from .views import HealthCardViewSet, CardScanLogViewSet

router = DefaultRouter()
router.register(r'healthcards', HealthCardViewSet, basename='healthcard')
router.register(r'card-scan-logs', CardScanLogViewSet, basename='card-scan-log')

urlpatterns = router.urls
