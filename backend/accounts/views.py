"""
Views for the accounts app.

All views are class-based and follow the thin-view pattern:
  - Serializer validates input
  - Service function handles business logic
  - View assembles and returns the response
"""

import logging

from django.utils.translation import gettext_lazy as _
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.serializers import (
    RequestOTPSerializer,
    UpdateUserSerializer,
    UserSerializer,
    VerifyOTPSerializer,
)
from accounts.services import generate_otp, get_tokens_for_user, verify_otp

logger = logging.getLogger(__name__)


class RequestOTPView(APIView):
    """
    POST /api/v1/auth/otp/request/

    Send an OTP to the provided phone number.
    Rate-limited to 5 requests per phone per hour.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_request"

    def post(self, request):
        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]

        generate_otp(phone)

        return Response(
            {"detail": _("OTP sent successfully.")},
            status=status.HTTP_200_OK,
        )


class VerifyOTPView(APIView):
    """
    POST /api/v1/auth/otp/verify/

    Verify the OTP code. Returns JWT tokens on success.
    On first login: name (and optionally location) must be provided.
    On subsequent logins: name/location are ignored if already set.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_verify"

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        code = serializer.validated_data["code"]
        name = serializer.validated_data.get("name", "")
        location = serializer.validated_data.get("location")

        try:
            user = verify_otp(phone, code)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # If this is a new user (no name yet), set profile data
        update_fields = []
        if not user.name and name:
            user.name = name.strip()
            update_fields.append("name")
        if location and not user.location_id:
            user.location = location
            update_fields.append("location")
        if update_fields:
            user.save(update_fields=update_fields)

        tokens = get_tokens_for_user(user)
        return Response(
            {
                "access": tokens["access"],
                "refresh": tokens["refresh"],
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class ProfileView(generics.RetrieveUpdateAPIView):
    """
    GET  /api/v1/auth/profile/  — Retrieve current user's profile
    PATCH /api/v1/auth/profile/ — Update name and/or location
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return UpdateUserSerializer
        return UserSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = True  # Always treat as PATCH
        return super().update(request, *args, **kwargs)
