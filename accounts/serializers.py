"""
MedConnect — User Serializers
================================
DRF serializers for:
  • Djoser integration (user create, user detail, current user, set password)
  • Custom JWT token obtain pair (adds role + user_id claims)
  • Staff/Admin login (username + password via Djoser JWT)
  • Patient registration (phone + OTP flow)
  • Patient OTP send / verify
  • User profile read/update
  • Admin user management
  • Change password

Authentication Flows:
  1. Staff/Admin:  POST /auth/jwt/create/ → username + password → JWT tokens
  2. Patient:      POST /auth/patient/register/ → POST /auth/send-otp/ →
                   POST /auth/verify-otp/ → JWT tokens
"""

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User, OTP, UserRole, Gender, BloodGroup


# ═════════════════════════════════════════════════════════════════════
#  SIMPLEJWT — CUSTOM TOKEN SERIALIZER
# ═════════════════════════════════════════════════════════════════════

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT token serializer that adds role, user_id, and
    full_name as custom claims to the token.

    Used by: POST /auth/jwt/create/
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Custom claims embedded in token payload
        token['role'] = user.role
        token['user_id'] = str(user.user_id)
        token['full_name'] = user.full_name

        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        # Add user info to the response body (alongside tokens)
        data['user'] = {
            'id': str(self.user.id),
            'user_id': self.user.user_id,
            'username': self.user.username,
            'phone': str(self.user.phone),
            'email': self.user.email,
            'full_name': self.user.full_name,
            'role': self.user.role,
            'role_display': self.user.get_role_display(),
            'is_profile_complete': self.user.is_profile_complete,
            'is_phone_verified': self.user.is_phone_verified,
        }

        return data


# ═════════════════════════════════════════════════════════════════════
#  DJOSER SERIALIZERS
# ═════════════════════════════════════════════════════════════════════

class DjoserUserCreateSerializer(serializers.ModelSerializer):
    """
    Djoser user creation serializer.
    Used by: POST /auth/users/

    For staff/admin registration via Djoser's built-in endpoint.
    Patients should use POST /auth/patient/register/ instead.
    """
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
        help_text='Password (min 8 characters).',
    )
    re_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text='Confirm password.',
    )

    class Meta:
        model = User
        fields = [
            'phone', 'username', 'full_name', 'email',
            'role', 'password', 're_password',
            'gender', 'date_of_birth',
        ]
        extra_kwargs = {
            'phone': {'required': True},
            'full_name': {'required': True},
            'role': {
                'required': False,
                'default': UserRole.PATIENT,
                'help_text': 'PATIENT | DOCTOR | NURSE | PHARMACIST | RECEPTION | ADMIN',
            },
            'username': {'required': False},
            'email': {'required': False},
        }

    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError(
                'A user with this phone number already exists.'
            )
        return value

    def validate_email(self, value):
        if value and User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                'A user with this email already exists.'
            )
        return value

    def validate_username(self, value):
        if value and User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                'This username is already taken.'
            )
        return value

    def validate(self, attrs):
        password = attrs.get('password')
        re_password = attrs.get('re_password')

        if password != re_password:
            raise serializers.ValidationError({
                're_password': 'Passwords do not match.',
            })

        # Run Django password validators
        validate_password(password)

        return attrs

    def create(self, validated_data):
        validated_data.pop('re_password')
        password = validated_data.pop('password')
        role = validated_data.pop('role', UserRole.PATIENT)

        # Auto-generate username for non-admin staff if not provided
        if not validated_data.get('username') and role != UserRole.PATIENT:
            base_username = validated_data['full_name'].lower().replace(' ', '.')
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f'{base_username}{counter}'
                counter += 1
            validated_data['username'] = username

        if role == UserRole.PATIENT:
            return User.objects.create_user(
                phone=validated_data.pop('phone'),
                role=role,
                password=password,
                **validated_data,
            )
        else:
            return User.objects.create_staffuser(
                phone=validated_data.pop('phone'),
                password=password,
                role=role,
                **validated_data,
            )


class DjoserUserSerializer(serializers.ModelSerializer):
    """
    Djoser user detail serializer.
    Used for /auth/users/ list (admin only) and /auth/users/{id}/.
    """

    class Meta:
        model = User
        fields = [
            'id', 'user_id', 'username', 'phone', 'email',
            'full_name', 'role', 'gender', 'is_active',
            'is_profile_complete', 'date_joined',
        ]
        read_only_fields = [
            'id', 'user_id', 'role', 'is_active', 'date_joined',
        ]


class DjoserCurrentUserSerializer(serializers.ModelSerializer):
    """
    Djoser current user serializer.
    Used by: GET /auth/users/me/
    """
    age = serializers.SerializerMethodField()
    full_address = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            # Identity
            'id', 'user_id', 'username', 'phone', 'email', 'role',
            # Profile
            'full_name', 'date_of_birth', 'age', 'gender',
            'blood_group', 'avatar',
            # Address
            'address_line_1', 'address_line_2',
            'city', 'state', 'pincode', 'full_address',
            # Emergency
            'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relation',
            # Medical
            'known_allergies', 'existing_conditions',
            # Insurance
            'insurance_provider', 'insurance_policy_number',
            # Status
            'is_active', 'is_phone_verified', 'is_email_verified',
            'is_profile_complete',
            # Timestamps
            'date_joined', 'updated_at', 'last_login',
        ]
        read_only_fields = [
            'id', 'user_id', 'phone', 'role', 'is_active',
            'is_phone_verified', 'is_email_verified',
            'is_profile_complete', 'date_joined', 'updated_at',
            'last_login',
        ]

    def get_age(self, obj):
        return obj.age

    def get_full_address(self, obj):
        return obj.get_full_address()

    def update(self, instance, validated_data):
        user = super().update(instance, validated_data)
        user.check_profile_completeness()
        return user


class DjoserSetPasswordSerializer(serializers.Serializer):
    """
    Djoser set/change password serializer.
    Used by: POST /auth/users/set_password/
    """
    current_password = serializers.CharField(
        write_only=True,
        help_text='Current password.',
    )
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        help_text='New password (min 8 characters).',
    )
    re_new_password = serializers.CharField(
        write_only=True,
        help_text='Confirm new password.',
    )

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['re_new_password']:
            raise serializers.ValidationError({
                're_new_password': 'New passwords do not match.',
            })
        validate_password(attrs['new_password'])
        return attrs


# ═════════════════════════════════════════════════════════════════════
#  ROLE-SPECIFIC LOGIN SERIALIZERS (user_id + password)
# ═════════════════════════════════════════════════════════════════════

class LoginSerializer(serializers.Serializer):
    """
    Universal login for ALL roles.
    Login credential: user_id + password

    Example:
      { "user_id": "MC-PAT-2026-00001", "password": "mypassword" }
      { "user_id": "MC-DOC-2026-00001", "password": "staffpass" }
      { "user_id": "MC-ADM-2026-00001", "password": "adminpass" }
    """
    user_id = serializers.CharField(
        help_text='Your auto-generated User ID (e.g., MC-PAT-2026-00001).',
    )
    password = serializers.CharField(
        write_only=True,
        help_text='Your account password.',
    )

    def validate(self, attrs):
        user_id = attrs.get('user_id', '').strip()
        password = attrs.get('password')

        if not user_id or not password:
            raise serializers.ValidationError(
                'Both User ID and password are required.'
            )

        try:
            user = User.objects.get(user_id=user_id)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                'Invalid User ID. No account found.'
            )

        if not user.is_active:
            raise serializers.ValidationError(
                'This account has been deactivated. Contact administrator.'
            )

        if not user.check_password(password):
            raise serializers.ValidationError(
                'Invalid password. Please try again.'
            )

        attrs['user'] = user
        return attrs


class AdminLoginSerializer(LoginSerializer):
    """Admin login — validates user_id + password + admin role."""
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs['user'].role != UserRole.ADMIN:
            raise serializers.ValidationError(
                'This account does not have admin privileges.'
            )
        return attrs


class DoctorLoginSerializer(LoginSerializer):
    """Doctor login — validates user_id + password + doctor role."""
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs['user'].role != UserRole.DOCTOR:
            raise serializers.ValidationError(
                'This account is not registered as a Doctor.'
            )
        return attrs


class NurseLoginSerializer(LoginSerializer):
    """Nurse login — validates user_id + password + nurse role."""
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs['user'].role != UserRole.NURSE:
            raise serializers.ValidationError(
                'This account is not registered as a Nurse.'
            )
        return attrs


class PharmacistLoginSerializer(LoginSerializer):
    """Pharmacist login — validates user_id + password + pharmacist role."""
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs['user'].role != UserRole.PHARMACIST:
            raise serializers.ValidationError(
                'This account is not registered as a Pharmacist.'
            )
        return attrs


class ReceptionLoginSerializer(LoginSerializer):
    """Reception login — validates user_id + password + reception role."""
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs['user'].role != UserRole.RECEPTION:
            raise serializers.ValidationError(
                'This account is not registered as Reception staff.'
            )
        return attrs


class PatientLoginSerializer(LoginSerializer):
    """Patient login — validates user_id + password + patient role."""
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs['user'].role != UserRole.PATIENT:
            raise serializers.ValidationError(
                'This account is not registered as a Patient.'
            )
        return attrs


# ═════════════════════════════════════════════════════════════════════
#  PATIENT REGISTRATION SERIALIZER
# ═════════════════════════════════════════════════════════════════════

class PatientRegistrationSerializer(serializers.ModelSerializer):
    """
    Patient self-registration via phone number.

    Required: phone, full_name, password, confirm_password
    Optional: email, date_of_birth, gender, blood_group

    System auto-generates:
      - user_id (MC-PAT-2026-XXXXX)
      - UUID primary key

    After registration:
      Patient verifies phone via OTP → gets JWT tokens
    """
    
    is_elite_card = serializers.BooleanField(
        write_only=True,
        required=True,
        help_text='Set to True if purchasing Elite card, False for Base card.',
    )
    residential_address = serializers.CharField(
        source='address_line_1',
        required=True,
        help_text='Residential address.'
    )
    emergency_contact = serializers.CharField(
        source='emergency_contact_phone',
        required=True,
        help_text='Emergency contact phone number.'
    )

    class Meta:
        model = User
        fields = [
            'phone', 'full_name', 'email', 'avatar', 'id_proof',
            'is_elite_card', 'residential_address', 'emergency_contact',
            'date_of_birth', 'gender', 'blood_group',
        ]
        extra_kwargs = {
            'phone': {'required': True},
            'full_name': {'required': True},
            'email': {'required': False},
            'avatar': {'required': False},
            'id_proof': {'required': True},
            'date_of_birth': {'required': True},
            'gender': {'required': True},
            'blood_group': {'required': False},
        }

    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError(
                'A user with this phone number already exists.'
            )
        return value

    def validate_email(self, value):
        if value and User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                'A user with this email already exists.'
            )
        return value

    def create(self, validated_data):
        import secrets
        password = secrets.token_urlsafe(16)
        is_elite = validated_data.pop('is_elite_card', False)

        user = User.objects.create_user(
            phone=validated_data.pop('phone'),
            full_name=validated_data.pop('full_name'),
            email=validated_data.pop('email', None),
            role=UserRole.PATIENT,
            password=password,
            **validated_data,
        )
        
        # Auto-issue a Health Card based on registration selection
        from healthcard.models import HealthCard
        card = HealthCard.objects.create(
            patient=user,
            is_elite=is_elite,
        )
        # Generate the QR code for the newly issued card
        card.generate_qr_code()
        
        return user


# ═════════════════════════════════════════════════════════════════════
#  STAFF REGISTRATION SERIALIZER (Admin creates staff accounts)
# ═════════════════════════════════════════════════════════════════════

class StaffRegistrationSerializer(serializers.ModelSerializer):
    """
    Admin creates staff accounts.
    Creates: Doctor, Nurse, Pharmacist, Reception, Admin

    Required: phone, full_name, role, password, confirm_password
    Optional: email, username, gender, date_of_birth

    System auto-generates:
      - user_id (MC-DOC-2026-XXXXX, MC-NUR-2026-XXXXX, etc.)
      - username (if not provided, derived from full_name)
    """
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        help_text='Password for login.',
    )
    confirm_password = serializers.CharField(
        write_only=True,
        help_text='Confirm password.',
    )

    class Meta:
        model = User
        fields = [
            'phone', 'email', 'full_name', 'role',
            'username', 'password', 'confirm_password',
            'gender', 'date_of_birth',
        ]
        extra_kwargs = {
            'role': {
                'required': True,
                'help_text': 'Must be: DOCTOR, NURSE, PHARMACIST, RECEPTION, or ADMIN',
            },
            'username': {'required': False},
        }

    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError(
                'A user with this phone number already exists.'
            )
        return value

    def validate_username(self, value):
        if value and User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                'This username is already taken.'
            )
        return value

    def validate_role(self, value):
        if value == UserRole.PATIENT:
            raise serializers.ValidationError(
                'Use the patient registration endpoint for PATIENT role.'
            )
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match.',
            })
        validate_password(attrs['password'])
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')

        # Auto-generate username if not provided
        if not validated_data.get('username'):
            base_username = validated_data['full_name'].lower().replace(' ', '.')
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f'{base_username}{counter}'
                counter += 1
            validated_data['username'] = username

        return User.objects.create_staffuser(
            phone=validated_data.pop('phone'),
            password=password,
            role=validated_data.pop('role'),
            **validated_data,
        )


# ═════════════════════════════════════════════════════════════════════
#  PATIENT OTP SERIALIZERS
# ═════════════════════════════════════════════════════════════════════

class SendOTPSerializer(serializers.Serializer):
    """
    Request OTP for phone verification / patient login.
    Used by: POST /auth/send-otp/
    """
    phone = serializers.CharField(
        help_text='Phone number in E.164 format (e.g., +919876543210).',
    )

    def validate_phone(self, value):
        from accounts.utils import normalize_phone

        normalized = normalize_phone(value)
        if not normalized:
            raise serializers.ValidationError(
                'Invalid phone number format. Use format: +919876543210'
            )
        return normalized


class VerifyOTPSerializer(serializers.Serializer):
    """
    Verify OTP and get JWT tokens.
    Used by: POST /auth/verify-otp/
    """
    phone = serializers.CharField(
        help_text='Phone number the OTP was sent to.',
    )
    otp = serializers.CharField(
        min_length=6,
        max_length=6,
        help_text='6-digit OTP code.',
    )

    def validate_phone(self, value):
        from accounts.utils import normalize_phone

        normalized = normalize_phone(value)
        if not normalized:
            raise serializers.ValidationError(
                'Invalid phone number format.'
            )
        return normalized

    def validate_otp(self, value):
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError(
                'OTP must be exactly 6 digits.'
            )
        return value


# ═════════════════════════════════════════════════════════════════════
#  USER PROFILE SERIALIZER (GET/PUT /users/me)
# ═════════════════════════════════════════════════════════════════════

class UserProfileSerializer(serializers.ModelSerializer):
    """
    Read/update user profile.
    Includes computed fields: age, full_address.
    Shows the auto-generated user_id.
    """
    age = serializers.SerializerMethodField()
    full_address = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            # Identity
            'id', 'user_id', 'username', 'phone', 'email', 'role',
            # Profile
            'full_name', 'date_of_birth', 'age', 'gender',
            'blood_group', 'avatar',
            # Address
            'address_line_1', 'address_line_2',
            'city', 'state', 'pincode', 'full_address',
            # Emergency
            'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relation',
            # Medical
            'known_allergies', 'existing_conditions',
            # Insurance
            'insurance_provider', 'insurance_policy_number',
            # Status
            'is_active', 'is_phone_verified', 'is_email_verified',
            'is_profile_complete',
            # Timestamps
            'date_joined', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user_id', 'phone', 'role', 'is_active',
            'is_phone_verified', 'is_email_verified',
            'is_profile_complete', 'date_joined', 'updated_at',
        ]

    def get_age(self, obj):
        return obj.age

    def get_full_address(self, obj):
        return obj.get_full_address()

    def update(self, instance, validated_data):
        user = super().update(instance, validated_data)
        user.check_profile_completeness()
        return user


# ═════════════════════════════════════════════════════════════════════
#  USER LIST SERIALIZER (Admin views)
# ═════════════════════════════════════════════════════════════════════

class UserListSerializer(serializers.ModelSerializer):
    """Compact user listing for admin panels and search results."""

    class Meta:
        model = User
        fields = [
            'id', 'user_id', 'phone', 'full_name', 'role',
            'username', 'gender', 'is_active', 'is_profile_complete',
            'date_joined',
        ]


# ═════════════════════════════════════════════════════════════════════
#  ADMIN USER MANAGEMENT SERIALIZER
# ═════════════════════════════════════════════════════════════════════

class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """Admin can update any user's details including role & status."""

    class Meta:
        model = User
        fields = [
            'full_name', 'email', 'role', 'gender',
            'date_of_birth', 'blood_group',
            'address_line_1', 'address_line_2',
            'city', 'state', 'pincode',
            'is_active', 'is_phone_verified', 'is_email_verified',
        ]


# ═════════════════════════════════════════════════════════════════════
#  CHANGE PASSWORD SERIALIZER
# ═════════════════════════════════════════════════════════════════════

class ChangePasswordSerializer(serializers.Serializer):
    """Change password for any authenticated user."""
    old_password = serializers.CharField(
        write_only=True,
        help_text='Current password.',
    )
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        help_text='New password (min 8 characters).',
    )
    confirm_password = serializers.CharField(
        write_only=True,
        help_text='Confirm new password.',
    )

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'New passwords do not match.',
            })
        validate_password(attrs['new_password'])
        return attrs
