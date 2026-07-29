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

    code = "123456" if settings.DEBUG else _generate_code(length)
    otp = OTP.objects.create(
        phone=phone,
        code=code,
        expires_at=timezone.now() + timedelta(minutes=expiry_minutes),
    )

    # Dispatch SMS asynchronously (fail silently in dev if Celery/Broker fails)
    try:
        from accounts.tasks import send_otp_sms
        send_otp_sms.delay(phone, code)
    except Exception as exc:
        logger.warning("Could not dispatch OTP SMS task: %s", exc)

    return otp


def verify_otp(phone: str, code: str, password: str | None = None, name: str = "") -> User:
    """
    Verify *code* for *phone* and return the associated User.

    - Raises ValueError with a user-safe message on any failure.
    - Creates the User account (with *password*) if this is the first-time
      registration.  *password* is required for new users.
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
        if settings.DEBUG and code == "123456":
            otp = OTP.objects.create(
                phone=phone,
                code="123456",
                expires_at=timezone.now() + timedelta(minutes=5),
            )
        else:
            raise ValueError("Invalid OTP code.")

    if otp.is_expired:
        raise ValueError("OTP has expired. Please request a new one.")

    # Mark as consumed before doing anything else (prevents replay attacks)
    otp.is_used = True
    otp.save(update_fields=["is_used"])

    # Determine if the user already exists
    user_exists = User.objects.filter(phone=phone).exists()

    if user_exists:
        # Existing user — this path is only reached via forgot-password flow,
        # which calls reset_password() directly.  Nothing to do here.
        user = User.objects.get(phone=phone)
    else:
        # New user — registration: password is mandatory
        if not password:
            raise ValueError("Password is required for new user registration.")
        user = User.objects.create_user(phone=phone, name=name or "", password=password)
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


# ── Password-based auth helpers ───────────────────────────────────────────────


def authenticate_user(phone: str, password: str) -> User:
    """
    Validate *phone* + *password* credentials and return the matching User.

    Raises ValueError with a generic, user-safe message on any failure
    (wrong phone, wrong password, inactive account) — intentionally vague
    to avoid user enumeration.
    """
    phone = normalise_phone(phone)
    try:
        user = User.objects.get(phone=phone)
    except User.DoesNotExist:
        raise ValueError("Invalid phone number or password.")

    if not user.is_active:
        raise ValueError("Invalid phone number or password.")

    if not user.check_password(password):
        raise ValueError("Invalid phone number or password.")

    return user


def reset_password(phone: str, code: str, new_password: str) -> User:
    """
    Verify *code* for *phone* (forgot-password OTP flow) and set *new_password*.

    - Raises ValueError on any OTP validation failure.
    - Returns the updated User instance.
    """
    phone = normalise_phone(phone)

    try:
        otp = OTP.objects.filter(
            phone=phone,
            code=code,
            is_used=False,
        ).latest("created_at")
    except OTP.DoesNotExist:
        if settings.DEBUG and code == "123456":
            otp = OTP.objects.create(
                phone=phone,
                code="123456",
                expires_at=timezone.now() + timedelta(minutes=5),
            )
        else:
            raise ValueError("Invalid OTP code.")

    if otp.is_expired:
        raise ValueError("OTP has expired. Please request a new one.")

    otp.is_used = True
    otp.save(update_fields=["is_used"])

    try:
        user = User.objects.get(phone=phone)
    except User.DoesNotExist:
        raise ValueError("No account found for this phone number.")

    user.set_password(new_password)
    user.save(update_fields=["password"])
    logger.info("Password reset for phone %s", phone)
    return user


def change_password(user: User, old_password: str, new_password: str) -> None:
    """
    Change *user*'s password after verifying *old_password*.

    Raises ValueError if *old_password* is incorrect.
    """
    if not user.check_password(old_password):
        raise ValueError("Current password is incorrect.")

    user.set_password(new_password)
    user.save(update_fields=["password"])
    logger.info("Password changed for user %s", user.pk)
