"""
Serializers for the accounts app.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from accounts.models import User
from accounts.validators import normalise_phone, validate_egyptian_phone


# ── Auth serializers ──────────────────────────────────────────────────────────


class RequestOTPSerializer(serializers.Serializer):
    """Validates the phone number for OTP request."""

    phone = serializers.CharField(max_length=15)
    intent = serializers.ChoiceField(
        choices=["register", "login", "reset_password", "delete_account"]
    )

    def validate_phone(self, value: str) -> str:
        validate_egyptian_phone(value)
        return normalise_phone(value)

    def validate(self, attrs):
        phone = attrs.get("phone")
        intent = attrs.get("intent")
        
        user_exists = User.objects.filter(phone=phone).exists()
        
        if intent == "register":
            if user_exists:
                raise serializers.ValidationError({"phone": _("An account is already registered with this phone number.")})
        else:
            if not user_exists:
                raise serializers.ValidationError({"phone": _("No account is registered with this phone number.")})
                
        return attrs


class VerifyOTPSerializer(serializers.Serializer):
    """
    Validates phone + OTP code for new-user registration.

    name and location are required for new users; password and
    password_confirm are always required (set during registration).
    """

    phone = serializers.CharField(max_length=15)
    code = serializers.CharField(max_length=6, min_length=6)
    # Registration fields
    name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    # read_only=True is a placeholder; __init__ replaces it with a proper queryset.
    location = serializers.PrimaryKeyRelatedField(
        read_only=True,
        required=False,
        allow_null=True,
    )
    # Password fields — required for registration
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Defer import to avoid circular import at module load time.
        from locations.models import Location
        self.fields["location"] = serializers.PrimaryKeyRelatedField(
            queryset=Location.objects.all(),
            required=False,
            allow_null=True,
        )

    def validate_phone(self, value: str) -> str:
        validate_egyptian_phone(value)
        return normalise_phone(value)

    def validate_code(self, value: str) -> str:
        if not value.isdigit():
            raise serializers.ValidationError(_("OTP code must contain only digits."))
        return value

    def validate(self, attrs):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError

        password = attrs.get("password")
        password_confirm = attrs.get("password_confirm")

        if password != password_confirm:
            raise serializers.ValidationError(
                {"password_confirm": _("Passwords do not match.")}
            )

        try:
            validate_password(password)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})

        return attrs


class LoginSerializer(serializers.Serializer):
    """Validates phone + password for login."""

    phone = serializers.CharField(max_length=15)
    password = serializers.CharField(write_only=True)

    def validate_phone(self, value: str) -> str:
        validate_egyptian_phone(value)
        return normalise_phone(value)


class ForgotPasswordSerializer(serializers.Serializer):
    """Validates the OTP-based password reset payload."""

    phone = serializers.CharField(max_length=15)
    code = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate_phone(self, value: str) -> str:
        validate_egyptian_phone(value)
        return normalise_phone(value)

    def validate_code(self, value: str) -> str:
        if not value.isdigit():
            raise serializers.ValidationError(_("OTP code must contain only digits."))
        return value

    def validate(self, attrs):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError

        new_password = attrs.get("new_password")
        new_password_confirm = attrs.get("new_password_confirm")

        if new_password != new_password_confirm:
            raise serializers.ValidationError(
                {"new_password_confirm": _("Passwords do not match.")}
            )

        try:
            validate_password(new_password)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})

        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """Validates the authenticated change-password payload."""

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError

        new_password = attrs.get("new_password")
        new_password_confirm = attrs.get("new_password_confirm")

        if new_password != new_password_confirm:
            raise serializers.ValidationError(
                {"new_password_confirm": _("Passwords do not match.")}
            )

        try:
            validate_password(new_password)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})

        return attrs


# ── User profile serializers ──────────────────────────────────────────────────


class UserSerializer(serializers.ModelSerializer):
    """Read-only serializer for the current user's profile."""

    location_name = serializers.CharField(
        source="location.name", read_only=True, default=None
    )

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "name",
            "role",
            "location",
            "location_name",
            "date_joined",
        ]
        read_only_fields = ["id", "phone", "role", "date_joined"]


class UpdateUserSerializer(serializers.ModelSerializer):
    """Allows users to update their name and selected location."""

    class Meta:
        model = User
        fields = ["name", "location"]

    def validate_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError(_("Name cannot be blank."))
        return value.strip()


class DeleteAccountSerializer(serializers.Serializer):
    """Validates the OTP code for account deletion."""

    code = serializers.CharField(max_length=6, min_length=6)

    def validate_code(self, value: str) -> str:
        if not value.isdigit():
            raise serializers.ValidationError(_("OTP code must contain only digits."))
        return value

