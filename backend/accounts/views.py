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
from rest_framework_simplejwt.views import TokenRefreshView  # noqa: F401 — re-exported via urls

from accounts.serializers import (
    ChangePasswordSerializer,
    DeleteAccountSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    RequestOTPSerializer,
    UpdateUserSerializer,
    UserSerializer,
    VerifyOTPSerializer,
)
from accounts.services import (
    authenticate_user,
    change_password,
    delete_account,
    generate_otp,
    get_tokens_for_user,
    reset_password,
    verify_deletion_otp,
    verify_otp,
)

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

    Verify the OTP code and create the user account (registration).
    Returns JWT tokens + user data on success.

    Required fields: phone, code, password, password_confirm
    Optional fields: name, location (for profile setup)
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
        password = serializer.validated_data["password"]

        try:
            user = verify_otp(phone, code, password=password, name=name)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Set location if provided and not already set
        if location and not user.location_id:
            user.location = location
            user.save(update_fields=["location"])

        tokens = get_tokens_for_user(user)
        return Response(
            {
                "access": tokens["access"],
                "refresh": tokens["refresh"],
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class LoginView(APIView):
    """
    POST /api/v1/auth/login/

    Authenticate with phone + password and return JWT tokens.
    Rate-limited to prevent brute-force attacks.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_verify"  # reuse the same bucket as OTP verify

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        password = serializer.validated_data["password"]

        try:
            user = authenticate_user(phone, password)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        tokens = get_tokens_for_user(user)
        return Response(
            {
                "access": tokens["access"],
                "refresh": tokens["refresh"],
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class ForgotPasswordView(APIView):
    """
    POST /api/v1/auth/password/reset/

    OTP-based password reset (forgot password flow).
    Accepts: phone, code, new_password, new_password_confirm
    Returns JWT tokens so the user is logged in immediately after reset.
    Rate-limited.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_verify"

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        code = serializer.validated_data["code"]
        new_password = serializer.validated_data["new_password"]

        try:
            user = reset_password(phone, code, new_password)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tokens = get_tokens_for_user(user)
        return Response(
            {
                "access": tokens["access"],
                "refresh": tokens["refresh"],
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class ChangePasswordView(APIView):
    """
    POST /api/v1/auth/password/change/

    Change password for the currently authenticated user.
    Accepts: old_password, new_password, new_password_confirm
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_password = serializer.validated_data["old_password"]
        new_password = serializer.validated_data["new_password"]

        try:
            change_password(request.user, old_password, new_password)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": _("Password changed successfully.")},
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

    def delete(self, request, *args, **kwargs):
        serializer = DeleteAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"]

        try:
            verify_deletion_otp(request.user.phone, code)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        delete_account(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
