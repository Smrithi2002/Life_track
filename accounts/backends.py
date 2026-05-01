"""
MedConnect — Custom Authentication Backend
=============================================
Supports login via:
  • Username (for staff/admin)
  • Phone number (for all users)
  • User ID (MC-PAT-2026-00001 format)
"""

from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from .models import User


class CustomAuthBackend(ModelBackend):
    """
    Multi-field authentication backend.
    Allows users to login with username, phone, or user_id.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        user = None

        # Try username first (most common for staff/admin)
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            pass

        # Try user_id (MC-PAT-2026-00001 format)
        if user is None:
            try:
                user = User.objects.get(user_id=username)
            except User.DoesNotExist:
                pass

        # Try phone number (may fail if input isn't a valid phone format)
        if user is None:
            try:
                user = User.objects.get(phone=username)
            except (User.DoesNotExist, Exception):
                pass

        # No user found
        if user is None:
            User().set_password(password)  # Timing attack mitigation
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None