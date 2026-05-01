"""
MedConnect — Custom Permissions
================================
Role-based permission classes for API access control.
Maps to SDD Section 10.1 — RBAC Permission Matrix.

Permission Matrix:
  ┌──────────────┬───────────────────────────────────────────────────────┐
  │ Role         │ Access Level                                         │
  ├──────────────┼───────────────────────────────────────────────────────┤
  │ ADMIN        │ Full access — all modules, user management           │
  │ DOCTOR       │ Medical modules — patients, prescriptions, records   │
  │ NURSE        │ Limited clinical — vitals, patient prep, triage      │
  │ PHARMACIST   │ Pharmacy — prescriptions, inventory, dispensing      │
  │ RECEPTION    │ Appointments, billing, patient registration          │
  │ PATIENT      │ Self-only — own records, appointments, prescriptions │
  └──────────────┴───────────────────────────────────────────────────────┘
"""

from rest_framework.permissions import BasePermission


# ═════════════════════════════════════════════════════════════════════
#  SINGLE-ROLE PERMISSIONS
# ═════════════════════════════════════════════════════════════════════

class IsAdmin(BasePermission):
    """Allow access only to Admin users. Full system access."""
    message = 'Admin access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'ADMIN'
        )


class IsDoctor(BasePermission):
    """Allow access only to Doctor users. Medical modules access."""
    message = 'Doctor access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'DOCTOR'
        )


class IsNurse(BasePermission):
    """Allow access only to Nurse users. Limited clinical access."""
    message = 'Nurse access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'NURSE'
        )


class IsPharmacist(BasePermission):
    """Allow access only to Pharmacist users. Pharmacy module access."""
    message = 'Pharmacist access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'PHARMACIST'
        )


class IsReception(BasePermission):
    """Allow access only to Reception users. Appointments/billing access."""
    message = 'Reception access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'RECEPTION'
        )


class IsPatient(BasePermission):
    """Allow access only to Patient users. Self-only access."""
    message = 'Patient access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'PATIENT'
        )


# ═════════════════════════════════════════════════════════════════════
#  COMPOSITE ROLE PERMISSIONS
# ═════════════════════════════════════════════════════════════════════

class IsAdminOrStaff(BasePermission):
    """Allow access to Admin, Doctor, Nurse, Pharmacist, or Reception."""
    STAFF_ROLES = {'ADMIN', 'DOCTOR', 'NURSE', 'PHARMACIST', 'RECEPTION'}
    message = 'Staff access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in self.STAFF_ROLES
        )


class IsMedicalStaff(BasePermission):
    """
    Allow access to medical professionals: Admin, Doctor, Nurse.
    Used for clinical data access.
    """
    MEDICAL_ROLES = {'ADMIN', 'DOCTOR', 'NURSE'}
    message = 'Medical staff access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in self.MEDICAL_ROLES
        )


class IsDoctorOrAdmin(BasePermission):
    """Allow access to Doctor or Admin users."""
    message = 'Doctor or Admin access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ('DOCTOR', 'ADMIN')
        )


class IsPharmacistOrAdmin(BasePermission):
    """Allow access to Pharmacist or Admin users."""
    message = 'Pharmacist or Admin access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ('PHARMACIST', 'ADMIN')
        )


class IsReceptionOrAdmin(BasePermission):
    """Allow access to Reception or Admin users. Appointments/billing."""
    message = 'Reception or Admin access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ('RECEPTION', 'ADMIN')
        )


# ═════════════════════════════════════════════════════════════════════
#  OBJECT-LEVEL PERMISSIONS
# ═════════════════════════════════════════════════════════════════════

class IsAdminOrSelf(BasePermission):
    """
    Admin can access any user's data.
    Non-admin users can only access their own data.
    """
    message = 'You can only access your own data.'

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'ADMIN':
            return True
        return obj.id == request.user.id


class IsOwnerOrAdmin(BasePermission):
    """
    Object must have a `user` or `patient` FK field.
    Admin can access any object; others only their own.
    """
    message = 'You can only access your own records.'

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'ADMIN':
            return True
        # Check common FK field names
        owner = getattr(obj, 'user', None) or getattr(obj, 'patient', None)
        if owner:
            return owner.id == request.user.id
        return False


class IsOwnerOrMedicalStaff(BasePermission):
    """
    Patient can view own records.
    Medical staff (Doctor, Nurse, Admin) can view any patient's records.
    """
    MEDICAL_ROLES = {'ADMIN', 'DOCTOR', 'NURSE'}
    message = 'Access denied. Only the patient or medical staff can view this.'

    def has_object_permission(self, request, view, obj):
        if request.user.role in self.MEDICAL_ROLES:
            return True
        owner = getattr(obj, 'user', None) or getattr(obj, 'patient', None)
        if owner:
            return owner.id == request.user.id
        return False


# ═════════════════════════════════════════════════════════════════════
#  DYNAMIC ROLE PERMISSION (Configurable)
# ═════════════════════════════════════════════════════════════════════

class HasRole(BasePermission):
    """
    Dynamic permission check — checks if user has any of the allowed roles.

    Usage in views:
        class MyView(APIView):
            permission_classes = [IsAuthenticated, HasRole]
            allowed_roles = ['ADMIN', 'DOCTOR', 'NURSE']
    """
    message = 'Your role does not have access to this resource.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        allowed_roles = getattr(view, 'allowed_roles', [])
        if not allowed_roles:
            return True  # No restriction defined

        return request.user.role in allowed_roles
