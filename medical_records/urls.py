"""
Medical Records App — URL Configuration
"""

from rest_framework.routers import DefaultRouter
from .views import DiagnosisViewSet, MedicalRecordViewSet, LabReportViewSet

router = DefaultRouter()
router.register(r'diagnoses', DiagnosisViewSet, basename='diagnosis')
router.register(r'medical-records', MedicalRecordViewSet, basename='medical-record')
router.register(r'lab-reports', LabReportViewSet, basename='lab-report')

urlpatterns = router.urls
