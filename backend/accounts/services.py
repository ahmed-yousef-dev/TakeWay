"""
Business logic for account management.

Views stay thin — all logic lives here and is independently testable.
"""

import logging
import random
import string
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from accounts.models import OTP, User
from accounts.validators import normalise_phone

logger = logging.getLogger(__name__)

# ── OTP helpers ───────────────────────────────────────────────────────────────


def _generate_code(length: int = 6) -> str:
    """Generate a numeric OTP code of the given length."""
    return "".join(random.choices(string.digits, k=length))


def generate_otp(phone: str) -> OTP:
    """
    Generate a new OTP for *phone* and trigger async SMS delivery.

    - Invalidates (marks used) any existing unused OTPs for the same phone
      so that only the latest code is valid.
    - Returns the newly created OTP instance.
    """
    phone = normalise_phone(phone)
    length = getattr(settings, "OTP_LENGTH", 6)
    expiry_minutes = getattr(settings, "OTP_EXPIRY_MINUTES", 5)

    # Invalidate previous unused OTPs for this phone
    OTP.objects.filter(phone=phone, is_used=False).update(is_used=True)

    code = _generate_code(length)
    otp = OTP.objects.create(
        phone=phone,
        code=code,
        expires_at=timezone.now() + timedelta(minutes=expiry_minutes),
    )

    # Dispatch SMS asynchronously
    from accounts.tasks import send_otp_sms
    send_otp_sms.delay(phone, code)

    return otp


def verify_otp(phone: str, code: str) -> User:
    """
    Verify *code* for *phone* and return the associated User.

    - Raises ValueError with a user-safe message on any failure.
    - Creates the User account if this is the first-time login.
    - Marks the OTP as used on success.
    """
    phone = normalise_phone(phone)

    try:
        otp = OTP.objects.filter(
            phone=phone,
            code=code,
            is_used=False,
        ).latest("created_at")
    except OTP.DoesNotExist:
        raise ValueError("Invalid OTP code.")

    if otp.is_expired:
        raise ValueError("OTP has expired. Please request a new one.")

    # Mark as consumed before doing anything else (prevents replay attacks)
    otp.is_used = True
    otp.save(update_fields=["is_used"])

    # Get or create the user account
    user, created = User.objects.get_or_create(
        phone=phone,
        defaults={"name": ""},  # name will be set during registration step
    )

    if created:
        logger.info("New user created for phone %s", phone)

    return user


def get_tokens_for_user(user: User) -> dict:
    """
    Generate and return JWT access + refresh tokens for *user*.

    Uses djangorestframework-simplejwt's RefreshToken.
    """
    from rest_framework_simplejwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }
