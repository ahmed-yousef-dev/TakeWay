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

    def validate_phone(self, value: str) -> str:
        validate_egyptian_phone(value)
        return normalise_phone(value)


class VerifyOTPSerializer(serializers.Serializer):
    """
    Validates phone + OTP code.

    On first-time registration (user doesn't exist yet), name and location
    are required. On subsequent logins they are ignored.
    """

    phone = serializers.CharField(max_length=15)
    code = serializers.CharField(max_length=6, min_length=6)
    # Registration fields — only required for new users
    name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    # read_only=True is a placeholder; __init__ replaces it with a proper queryset.
    location = serializers.PrimaryKeyRelatedField(
        read_only=True,
        required=False,
        allow_null=True,
    )

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
