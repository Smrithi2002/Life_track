"""
MedConnect — Main URL Configuration
=====================================
All API endpoints are prefixed with /api/v1/

Admin Panel: /admin/
API Docs:    /api/v1/docs/ (Swagger UI)

App routing:
  /api/v1/auth/...           → accounts (auth, OTP, login)
  /api/v1/users/...          → accounts (profile, admin mgmt)
  /api/v1/healthcards/...    → healthcard
  /api/v1/departments/...    → appointments (departments)
  /api/v1/doctors/...        → appointments (doctor profiles)
  /api/v1/schedules/...      → appointments (doctor schedules)
  /api/v1/appointments/...   → appointments
  /api/v1/vitals/...         → appointments (vitals)
  /api/v1/medicines/...      → prescriptions
  /api/v1/prescriptions/...  → prescriptions
  /api/v1/pharmacy-orders/.. → prescriptions
  /api/v1/diagnoses/...      → medical_records
  /api/v1/medical-records/.. → medical_records
  /api/v1/lab-reports/...    → medical_records
  /api/v1/invoices/...       → billing
  /api/v1/payments/...       → billing
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


urlpatterns = [
    # Django Admin Panel
    path('admin/', admin.site.urls),

    # ─── MedConnect API v1 ───────────────────────────────────────────
    # Accounts (auth, users, admin management)
    path('api/v1/', include('accounts.urls')),

    # Health Card
    path('api/v1/', include('healthcard.urls')),

    # Appointments (departments, doctors, schedules, appointments, vitals)
    path('api/v1/', include('appointments.urls')),

    # Prescriptions (medicines, prescriptions, pharmacy orders)
    path('api/v1/', include('prescriptions.urls')),

    # Medical Records (diagnoses, records, lab reports)
    path('api/v1/', include('medical_records.urls')),

    # Billing (invoices, payments)
    path('api/v1/', include('billing.urls')),

    # Organizations (settings, feature toggles) — NEW
    path('api/v1/', include('organizations.urls')),

     # ... existing URLs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
