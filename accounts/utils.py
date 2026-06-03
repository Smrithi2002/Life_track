"""
MedConnect — Utility Functions
================================
Shared utilities:
  • Standardized API response builder
  • Custom DRF exception handler
  • JWT token generation helper
  • Phone number normalization
"""

import logging

from django.conf import settings
from django.utils import timezone

from rest_framework import status
from rest_framework.exceptions import (
    ValidationError,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    NotFound,
    Throttled,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler

from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger('accounts')


# ─────────────────────────────────────────────────────────────────────
#  STANDARDIZED API RESPONSE
# ─────────────────────────────────────────────────────────────────────

class APIResponse:
    """
    Standardized API response builder.

    Usage:
        return APIResponse.success(data={...}, message='Done', status_code=200)
        return APIResponse.error(message='Not found', status_code=404)
    """

    @staticmethod
    def success(data=None, message='Success', status_code=status.HTTP_200_OK):
        payload = {
            'success': True,
            'message': message,
            'timestamp': timezone.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
        }
        if data is not None:
            payload['data'] = data
        return Response(payload, status=status_code)

    @staticmethod
    def error(message='An error occurred', errors=None,
              status_code=status.HTTP_400_BAD_REQUEST):
        payload = {
            'success': False,
            'message': message,
            'timestamp': timezone.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
        }
        if errors is not None:
            payload['errors'] = errors
        return Response(payload, status=status_code)


# ─────────────────────────────────────────────────────────────────────
#  CUSTOM DRF EXCEPTION HANDLER
# ─────────────────────────────────────────────────────────────────────

def custom_exception_handler(exc, context):
    """
    Custom exception handler that wraps all DRF errors in the
    standard { success, message, errors, timestamp } format.
    """
    # Call DRF's default exception handler first
    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exception — log and return 500
        logger.exception('Unhandled exception in %s', context.get('view'))
        return APIResponse.error(
            message='Internal server error. Please try again later.',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Map specific exception types to user-friendly messages
    if isinstance(exc, ValidationError):
        errors = response.data
        # Flatten if it's a list at validate() level
        if isinstance(errors, list):
            message = errors[0] if errors else 'Validation error.'
            errors = None
        elif isinstance(errors, dict):
            # Try to extract first meaningful error
            first_key = next(iter(errors), None)
            if first_key == 'non_field_errors':
                msgs = errors[first_key]
                message = msgs[0] if isinstance(msgs, list) else str(msgs)
            else:
                message = 'Validation error. Check the errors field for details.'
        else:
            message = str(errors)

        return APIResponse.error(
            message=message,
            errors=errors,
            status_code=response.status_code,
        )

    elif isinstance(exc, AuthenticationFailed):
        # Extract the actual error message (e.g., from SimpleJWT)
        err_msg = str(exc.detail) if hasattr(exc, 'detail') else 'Authentication failed.'
        if err_msg.lower() == 'authentication credentials were not provided.':
            err_msg = 'Authentication failed. Invalid or expired token.'
            
        return APIResponse.error(
            message=err_msg,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    elif isinstance(exc, NotAuthenticated):
        return APIResponse.error(
            message='Authentication required. Please provide a valid token.',
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    elif isinstance(exc, PermissionDenied):
        return APIResponse.error(
            message='You do not have permission to perform this action.',
            status_code=status.HTTP_403_FORBIDDEN,
        )

    elif isinstance(exc, NotFound):
        return APIResponse.error(
            message='The requested resource was not found.',
            status_code=status.HTTP_404_NOT_FOUND,
        )

    elif isinstance(exc, Throttled):
        wait = exc.wait
        if wait:
            message = f'Request limit exceeded. Please retry after {int(wait)} seconds.'
        else:
            message = 'Request limit exceeded. Please try again later.'
        return APIResponse.error(
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # Generic fallback
    return APIResponse.error(
        message=str(exc.detail) if hasattr(exc, 'detail') else 'An error occurred.',
        status_code=response.status_code,
    )


# ─────────────────────────────────────────────────────────────────────
#  JWT TOKEN HELPER
# ─────────────────────────────────────────────────────────────────────

def get_tokens_for_user(user):
    """
    Generate JWT access + refresh token pair for a user.
    Includes custom claims: role, user_id, full_name.
    """
    refresh = RefreshToken.for_user(user)

    # Add custom claims
    refresh['role'] = user.role
    refresh['user_id'] = str(user.user_id)
    refresh['full_name'] = user.full_name

    return {
        'access_token': str(refresh.access_token),
        'refresh_token': str(refresh),
        'expires_in': int(
            settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()
        ),
    }


def build_user_data(user):
    """Build standardized user data dict for API responses."""
    return {
        'id': str(user.id),
        'user_id': user.user_id,
        'username': user.username,
        'phone': str(user.phone),
        'email': user.email,
        'full_name': user.full_name,
        'role': user.role,
        'role_display': user.get_role_display(),
        'gender': user.gender,
        'is_profile_complete': user.is_profile_complete,
        'is_phone_verified': user.is_phone_verified,
        'date_joined': user.date_joined.strftime('%Y-%m-%dT%H:%M:%SZ'),
    }


def build_login_response(user, message='Login successful'):
    """Build standardized login response with user data + tokens."""
    tokens = get_tokens_for_user(user)

    # Update last login
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])

    return {
        'user': build_user_data(user),
        'tokens': tokens,
    }


# ─────────────────────────────────────────────────────────────────────
#  PHONE NUMBER HELPERS
# ─────────────────────────────────────────────────────────────────────

def normalize_phone(phone_str):
    """
    Normalize phone number to E.164 format.
    Returns the normalized string or None if invalid.
    """
    import phonenumbers

    try:
        parsed = phonenumbers.parse(phone_str, settings.PHONENUMBER_DEFAULT_REGION)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164,
            )
    except phonenumbers.NumberParseException:
        pass
    return None
