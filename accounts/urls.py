"""
MedConnect — Accounts URL Configuration
==========================================
All auth & user management API endpoints.

═══════════════════════════════════════════════════════════════════════
 DJOSER BUILT-IN ENDPOINTS  (under /api/v1/auth/)
═══════════════════════════════════════════════════════════════════════
  POST   /auth/users/                — Registration (Djoser)
  GET    /auth/users/me/             — Get current user profile
  PUT    /auth/users/me/             — Update current user profile
  POST   /auth/jwt/create/           — Staff/Admin JWT login (username + password)
  POST   /auth/jwt/refresh/          — Refresh JWT access token
  POST   /auth/jwt/verify/           — Verify JWT token

═══════════════════════════════════════════════════════════════════════
 CUSTOM PATIENT OTP ENDPOINTS
═══════════════════════════════════════════════════════════════════════
  POST   /auth/patient/register/     — Patient self-registration
  POST   /auth/send-otp/             — Send OTP to phone number
  POST   /auth/verify-otp/           — Verify OTP → JWT tokens

═══════════════════════════════════════════════════════════════════════
 CUSTOM AUTH ENDPOINTS
═══════════════════════════════════════════════════════════════════════
  POST   /auth/logout/               — Blacklist refresh token
  POST   /auth/change-password/      — Change password
  POST   /auth/refresh-token/        — Custom refresh token endpoint

═══════════════════════════════════════════════════════════════════════
 ROLE-SPECIFIC LOGIN (user_id + password)
═══════════════════════════════════════════════════════════════════════
  POST   /auth/login/                — Universal login (any role)
  POST   /auth/admin/login/          — Admin login
  POST   /auth/doctor/login/         — Doctor login
  POST   /auth/nurse/login/          — Nurse login
  POST   /auth/pharmacist/login/     — Pharmacist login
  POST   /auth/reception/login/      — Reception login
  POST   /auth/patient/login/        — Patient login

═══════════════════════════════════════════════════════════════════════
 USER PROFILE
═══════════════════════════════════════════════════════════════════════
  GET/PUT /users/me/                 — Current user profile

═══════════════════════════════════════════════════════════════════════
 ADMIN USER MANAGEMENT
═══════════════════════════════════════════════════════════════════════
  GET    /admin/users/               — List all users
  GET    /admin/users/stats/         — User statistics
  GET    /admin/users/<id>/          — User detail
  PUT    /admin/users/<id>/          — Update user
  DELETE /admin/users/<id>/          — Deactivate user (soft delete)
  POST   /admin/users/<id>/reset-password/  — Reset user password
  POST   /auth/staff/register/       — Admin creates staff accounts
"""

from django.urls import path, include
from .views import (
    # Patient OTP
    SendOTPView,
    VerifyOTPView,
    # Login
    UniversalLoginView,
    AdminLoginView,
    DoctorLoginView,
    NurseLoginView,
    PharmacistLoginView,
    ReceptionLoginView,
    PatientLoginView,
    # Registration
    PatientRegistrationView,
    StaffRegistrationView,
    # Token management
    TokenRefreshView,
    LogoutView,
    # Profile
    UserProfileView,
    ChangePasswordView,
    # Admin management
    AdminUserListView,
    AdminUserDetailView,
    AdminUserStatsView,
    AdminResetPasswordView,
)


urlpatterns = [
    # ═════════════════════════════════════════════════════════════════
    #  DJOSER BUILT-IN ENDPOINTS
    # ═════════════════════════════════════════════════════════════════
    # Includes: /auth/users/, /auth/users/me/, /auth/jwt/create/,
    #           /auth/jwt/refresh/, /auth/jwt/verify/
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.jwt')),

    # ═════════════════════════════════════════════════════════════════
    #  PATIENT OTP ENDPOINTS
    # ═════════════════════════════════════════════════════════════════
    path('auth/patient/register/',  PatientRegistrationView.as_view(),  name='patient-register'),
    path('auth/send-otp/',          SendOTPView.as_view(),              name='send-otp'),
    path('auth/verify-otp/',        VerifyOTPView.as_view(),            name='verify-otp'),

    # ═════════════════════════════════════════════════════════════════
    #  CUSTOM AUTH ENDPOINTS
    # ═════════════════════════════════════════════════════════════════
    path('auth/logout/',            LogoutView.as_view(),               name='logout'),
    path('auth/change-password/',   ChangePasswordView.as_view(),       name='change-password'),
    path('auth/refresh-token/',     TokenRefreshView.as_view(),         name='token-refresh'),

    # ═════════════════════════════════════════════════════════════════
    #  STAFF REGISTRATION (Admin only)
    # ═════════════════════════════════════════════════════════════════
    path('auth/staff/register/',    StaffRegistrationView.as_view(),    name='staff-register'),

    # ═════════════════════════════════════════════════════════════════
    #  ROLE-SPECIFIC LOGIN (user_id + password)
    # ═════════════════════════════════════════════════════════════════
    path('auth/login/',             UniversalLoginView.as_view(),       name='universal-login'),
    path('auth/admin/login/',       AdminLoginView.as_view(),           name='admin-login'),
    path('auth/doctor/login/',      DoctorLoginView.as_view(),          name='doctor-login'),
    path('auth/nurse/login/',       NurseLoginView.as_view(),           name='nurse-login'),
    path('auth/pharmacist/login/',  PharmacistLoginView.as_view(),      name='pharmacist-login'),
    path('auth/reception/login/',   ReceptionLoginView.as_view(),       name='reception-login'),
    path('auth/patient/login/',     PatientLoginView.as_view(),         name='patient-login'),

    # ═════════════════════════════════════════════════════════════════
    #  USER PROFILE
    # ═════════════════════════════════════════════════════════════════
    path('users/me/', UserProfileView.as_view(), name='user-profile'),

    # ═════════════════════════════════════════════════════════════════
    #  ADMIN USER MANAGEMENT
    # ═════════════════════════════════════════════════════════════════
    path('admin/users/',            AdminUserListView.as_view(),        name='admin-user-list'),
    path('admin/users/stats/',      AdminUserStatsView.as_view(),       name='admin-user-stats'),
    path('admin/users/<str:user_id>/',           AdminUserDetailView.as_view(),     name='admin-user-detail'),
    path('admin/users/<str:user_id>/reset-password/', AdminResetPasswordView.as_view(), name='admin-reset-password'),
]
