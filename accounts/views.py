"""
MedConnect - Authentication & User Management Views
=====================================================
All API views for login, registration, OTP, profile, and admin.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Q, Count
from django.utils import timezone

from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, UserRole
from .serializers import (
    LoginSerializer,
    AdminLoginSerializer,
    DoctorLoginSerializer,
    NurseLoginSerializer,
    PharmacistLoginSerializer,
    ReceptionLoginSerializer,
    PatientLoginSerializer,
    PatientRegistrationSerializer,
    StaffRegistrationSerializer,
    SendOTPSerializer,
    VerifyOTPSerializer,
    UserProfileSerializer,
    UserListSerializer,
    AdminUserUpdateSerializer,
    ChangePasswordSerializer,
)
from .permissions import IsAdmin, IsAdminOrStaff, IsAdminOrSelf
from .services import (
    OTPService,
    OTPRateLimitError,
    OTPExpiredError,
    OTPMaxAttemptsError,
    OTPInvalidError,
)
from .utils import APIResponse, get_tokens_for_user, build_login_response

logger = logging.getLogger('accounts')


# =================================================================
#  PATIENT OTP ENDPOINTS
# =================================================================

class SendOTPView(APIView):
    """
    POST /api/v1/auth/send-otp/
    Send a 6-digit OTP to the given phone number.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data['phone']

        try:
            otp_service = OTPService()
            otp_record, otp_code = otp_service.generate_otp(phone)

            # Send OTP via SMS
            OTPService.send_otp_sms(phone, otp_code)

            response_data = {
                'phone': phone,
                'expires_in_seconds': settings.OTP_EXPIRY_MINUTES * 60,
                'max_attempts': settings.OTP_MAX_ATTEMPTS,
            }

            # Include OTP in response for development only
            if settings.DEBUG:
                response_data['dev_otp'] = otp_code

            return APIResponse.success(
                data=response_data,
                message='OTP sent successfully.',
            )

        except OTPRateLimitError as e:
            return APIResponse.error(
                message=str(e),
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except Exception as e:
            logger.exception('Failed to send OTP to %s', phone)
            return APIResponse.error(
                message='Failed to send OTP. Please try again later.',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class VerifyOTPView(APIView):
    """
    POST /api/v1/auth/verify-otp/
    Verify OTP and issue JWT tokens for the patient.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data['phone']
        otp_code = serializer.validated_data['otp']

        try:
            otp_service = OTPService()
            otp_record = otp_service.verify_otp(phone, otp_code)

            # OTP verified - check if user exists
            try:
                user = User.objects.get(phone=phone)
            except User.DoesNotExist:
                return APIResponse.success(
                    data={
                        'phone': phone,
                        'phone_verified': True,
                        'user_exists': False,
                    },
                    message='OTP verified. Please complete registration.',
                )

            if not user.is_active:
                return APIResponse.error(
                    message='Account deactivated. Contact administrator.',
                    status_code=status.HTTP_403_FORBIDDEN,
                )

            # Mark phone as verified
            if not user.is_phone_verified:
                user.is_phone_verified = True
                user.save(update_fields=['is_phone_verified'])

            # Issue JWT tokens
            login_data = build_login_response(user)

            return APIResponse.success(
                data=login_data,
                message='OTP verified. Login successful.',
            )

        except OTPInvalidError as e:
            return APIResponse.error(message=str(e))
        except OTPExpiredError as e:
            return APIResponse.error(message=str(e))
        except OTPMaxAttemptsError as e:
            return APIResponse.error(
                message=str(e),
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except Exception as e:
            logger.exception('OTP verification failed for %s', phone)
            return APIResponse.error(
                message='OTP verification failed. Please try again.',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =================================================================
#  LOGIN APIs - user_id + password
# =================================================================

class UniversalLoginView(APIView):
    """POST /api/v1/auth/login/ - Universal login for ALL roles."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        login_data = build_login_response(user)
        return APIResponse.success(
            data=login_data,
            message=f'{user.get_role_display()} login successful',
        )


class AdminLoginView(APIView):
    """POST /api/v1/auth/admin/login/"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        login_data = build_login_response(user)
        return APIResponse.success(data=login_data, message='Admin login successful')


class DoctorLoginView(APIView):
    """POST /api/v1/auth/doctor/login/"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DoctorLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        login_data = build_login_response(user)
        return APIResponse.success(data=login_data, message='Doctor login successful')


class NurseLoginView(APIView):
    """POST /api/v1/auth/nurse/login/"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = NurseLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        login_data = build_login_response(user)
        return APIResponse.success(data=login_data, message='Nurse login successful')


class PharmacistLoginView(APIView):
    """POST /api/v1/auth/pharmacist/login/"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PharmacistLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        login_data = build_login_response(user)
        return APIResponse.success(data=login_data, message='Pharmacist login successful')


class ReceptionLoginView(APIView):
    """POST /api/v1/auth/reception/login/"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ReceptionLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        login_data = build_login_response(user)
        return APIResponse.success(data=login_data, message='Reception login successful')


class PatientLoginView(APIView):
    """POST /api/v1/auth/patient/login/"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PatientLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        login_data = build_login_response(user)
        return APIResponse.success(data=login_data, message='Patient login successful')


# =================================================================
#  REGISTRATION APIs
# =================================================================

class PatientRegistrationView(APIView):
    """POST /api/v1/auth/patient/register/ - Patient self-registration."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PatientRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return APIResponse.success(
            data={
                'id': str(user.id),
                'user_id': user.user_id,
                'phone': str(user.phone),
                'full_name': user.full_name,
                'role': user.role,
                'role_display': user.get_role_display(),
                'login_info': {
                    'user_id': user.user_id,
                    'message': (
                        f'Registration successful! Your User ID is {user.user_id}. '
                        f'Please verify your phone number via OTP to login.'
                    ),
                },
            },
            message='Registration successful! Please verify your phone number.',
            status_code=status.HTTP_201_CREATED,
        )


class StaffRegistrationView(APIView):
    """POST /api/v1/auth/staff/register/ - Admin creates staff accounts."""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        serializer = StaffRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return APIResponse.success(
            data={
                'id': str(user.id),
                'user_id': user.user_id,
                'username': user.username,
                'phone': str(user.phone),
                'full_name': user.full_name,
                'role': user.role,
                'role_display': user.get_role_display(),
                'login_info': {
                    'user_id': user.user_id,
                    'message': (
                        f'Share this User ID ({user.user_id}) with the '
                        f'{user.get_role_display()}. They can also login '
                        f'with username: {user.username}'
                    ),
                },
            },
            message=f'{user.get_role_display()} account created successfully.',
            status_code=status.HTTP_201_CREATED,
        )


# =================================================================
#  PROFILE & TOKEN APIs
# =================================================================

class UserProfileView(APIView):
    """GET/PUT /api/v1/users/me/ - Current user profile."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return APIResponse.success(data=serializer.data)

    def put(self, request):
        serializer = UserProfileSerializer(
            request.user, data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return APIResponse.success(
            data=serializer.data,
            message='Profile updated successfully.',
        )


class ChangePasswordView(APIView):
    """POST /api/v1/auth/change-password/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return APIResponse.success(
            message=(
                f'Password changed successfully. Please login again with your '
                f'User ID ({user.user_id}) and new password.'
            ),
        )


class LogoutView(APIView):
    """POST /api/v1/auth/logout/ - Blacklist refresh token."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh_token')
        if not refresh_token:
            return APIResponse.error(
                message='Refresh token is required.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return APIResponse.success(message='Logged out successfully.')
        except Exception:
            return APIResponse.success(message='Logged out.')


class TokenRefreshView(APIView):
    """POST /api/v1/auth/refresh-token/ - Refresh access token."""
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get('refresh_token')
        if not refresh_token:
            return APIResponse.error(
                message='Refresh token is required.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            refresh = RefreshToken(refresh_token)
            return APIResponse.success(
                data={
                    'access_token': str(refresh.access_token),
                    'expires_in': int(
                        settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()
                    ),
                },
                message='Token refreshed successfully.',
            )
        except Exception:
            return APIResponse.error(
                message='Invalid or expired refresh token.',
                status_code=status.HTTP_401_UNAUTHORIZED,
            )


# =================================================================
#  ADMIN USER MANAGEMENT APIs
# =================================================================

class AdminUserListView(generics.ListAPIView):
    """GET /api/v1/admin/users/ - List all users (Admin only)."""
    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = UserListSerializer

    def get_queryset(self):
        queryset = User.objects.all()

        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role.upper())

        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(
                is_active=is_active.lower() in ('true', '1', 'yes')
            )

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) |
                Q(phone__icontains=search) |
                Q(user_id__icontains=search) |
                Q(username__icontains=search) |
                Q(email__icontains=search)
            )

        return queryset

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return APIResponse.success(data=response.data)


class AdminUserDetailView(APIView):
    """GET/PUT/DELETE /api/v1/admin/users/<user_id>/ (Admin only)."""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except (User.DoesNotExist, ValueError):
            try:
                return User.objects.get(user_id=user_id)
            except User.DoesNotExist:
                return None

    def get(self, request, user_id):
        user = self.get_user(user_id)
        if not user:
            return APIResponse.error(
                message='User not found.',
                status_code=status.HTTP_404_NOT_FOUND,
            )
        serializer = UserProfileSerializer(user)
        return APIResponse.success(data=serializer.data)

    def put(self, request, user_id):
        user = self.get_user(user_id)
        if not user:
            return APIResponse.error(
                message='User not found.',
                status_code=status.HTTP_404_NOT_FOUND,
            )

        serializer = AdminUserUpdateSerializer(
            user, data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return APIResponse.success(
            data=UserProfileSerializer(user).data,
            message='User updated successfully.',
        )

    def delete(self, request, user_id):
        user = self.get_user(user_id)
        if not user:
            return APIResponse.error(
                message='User not found.',
                status_code=status.HTTP_404_NOT_FOUND,
            )

        user.is_active = False
        user.save(update_fields=['is_active'])

        return APIResponse.success(
            message=f'User {user.user_id} has been deactivated.',
        )


class AdminUserStatsView(APIView):
    """GET /api/v1/admin/users/stats/ - User statistics (Admin only)."""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        total = User.objects.count()
        active = User.objects.filter(is_active=True).count()

        role_counts = dict(
            User.objects.values_list('role')
            .annotate(count=Count('id'))
            .values_list('role', 'count')
        )

        week_ago = timezone.now() - timedelta(days=7)
        recent = User.objects.filter(date_joined__gte=week_ago).count()

        return APIResponse.success(data={
            'total_users': total,
            'active_users': active,
            'inactive_users': total - active,
            'recent_registrations_7d': recent,
            'by_role': {
                'patients': role_counts.get('PATIENT', 0),
                'doctors': role_counts.get('DOCTOR', 0),
                'nurses': role_counts.get('NURSE', 0),
                'pharmacists': role_counts.get('PHARMACIST', 0),
                'reception': role_counts.get('RECEPTION', 0),
                'admins': role_counts.get('ADMIN', 0),
            },
        })


class AdminResetPasswordView(APIView):
    """POST /api/v1/admin/users/<user_id>/reset-password/ (Admin only)."""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except (User.DoesNotExist, ValueError):
            try:
                user = User.objects.get(user_id=user_id)
            except User.DoesNotExist:
                return APIResponse.error(
                    message='User not found.',
                    status_code=status.HTTP_404_NOT_FOUND,
                )

        new_password = request.data.get('new_password')
        if not new_password or len(new_password) < 8:
            return APIResponse.error(
                message='New password must be at least 8 characters.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()

        return APIResponse.success(
            message=(
                f'Password reset successfully for {user.user_id}. '
                f'User can now login with user_id: {user.user_id}'
            ),
        )
