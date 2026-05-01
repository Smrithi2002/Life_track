"""
Appointments App — URL Configuration
=======================================
All appointment-related API endpoints.

Department:
  GET/POST   /departments/
  GET/PUT/DEL /departments/{id}/

Doctor Profiles:
  GET         /doctors/                          List doctors
  GET         /doctors/{id}/                     Doctor detail
  GET         /doctors/{id}/slots/?date=...      Available slots
  POST        /doctors/                          Admin: create profile

Doctor Schedule:
  GET/POST    /schedules/
  GET/PUT/DEL /schedules/{id}/

Appointments:
  GET/POST    /appointments/
  GET/PUT     /appointments/{id}/
  POST        /appointments/{id}/check-in/       Nurse
  POST        /appointments/{id}/start/          Doctor
  POST        /appointments/{id}/complete/       Doctor
  POST        /appointments/{id}/cancel/         Patient/Staff
  POST        /appointments/{id}/update-status/  Staff
  GET         /appointments/my-appointments/     Patient
  GET         /appointments/doctor-queue/        Doctor
  GET         /appointments/today/               Staff

Vitals:
  GET/POST    /vitals/
  GET/PUT     /vitals/{id}/
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DepartmentViewSet,
    DoctorProfileViewSet,
    DoctorScheduleViewSet,
    AppointmentViewSet,
    VitalsViewSet,
)

router = DefaultRouter()
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'doctors', DoctorProfileViewSet, basename='doctor')
router.register(r'schedules', DoctorScheduleViewSet, basename='schedule')
router.register(r'appointments', AppointmentViewSet, basename='appointment')
router.register(r'vitals', VitalsViewSet, basename='vitals')

urlpatterns = router.urls
