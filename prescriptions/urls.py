"""
Prescriptions App — URL Configuration
========================================
Medicine:
  GET/POST   /medicines/                    List/Create
  GET/PUT/DEL /medicines/{id}/              Detail
  GET         /medicines/low-stock/         Low stock alert
  POST        /medicines/{id}/update-stock/ Stock management

Prescriptions:
  GET/POST    /prescriptions/               List/Create
  GET         /prescriptions/{id}/          Detail
  POST        /prescriptions/{id}/send-to-pharmacy/
  GET         /prescriptions/my-prescriptions/  Patient's own

Pharmacy Orders:
  GET         /pharmacy-orders/             List
  GET         /pharmacy-orders/{id}/        Detail
  POST        /pharmacy-orders/{id}/dispense/   Dispense
  GET         /pharmacy-orders/queue/       Active queue
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MedicineViewSet,
    PrescriptionViewSet,
    PharmacyOrderViewSet,
)

router = DefaultRouter()
router.register(r'medicines', MedicineViewSet, basename='medicine')
router.register(r'prescriptions', PrescriptionViewSet, basename='prescription')
router.register(r'pharmacy-orders', PharmacyOrderViewSet, basename='pharmacy-order')

urlpatterns = router.urls
