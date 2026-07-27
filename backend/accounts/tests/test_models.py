"""
Unit tests for accounts models and services.

Tests here validate business logic in isolation (no HTTP layer).
"""

import pytest
from django.utils import timezone

from accounts.models import OTP, User
from accounts.services import generate_otp, get_tokens_for_user, verify_otp
from accounts.tests.factories import OTPFactory, UserFactory
from accounts.validators import normalise_phone, validate_egyptian_phone
from django.core.exceptions import ValidationError


# ── Validator tests ───────────────────────────────────────────────────────────


class TestEgyptianPhoneValidator:
    def test_valid_vodafone(self):
        validate_egyptian_phone("01012345678")  # Should not raise

    def test_valid_etisalat(self):
        validate_egyptian_phone("01112345678")

    def test_valid_orange(self):
        validate_egyptian_phone("01212345678")

    def test_valid_we(self):
        validate_egyptian_phone("01512345678")

    def test_valid_international_format(self):
        validate_egyptian_phone("+201012345678")

    def test_invalid_prefix(self):
        with pytest.raises(ValidationError):
            validate_egyptian_phone("01312345678")  # 013 doesn't exist

    def test_invalid_landline(self):
        with pytest.raises(ValidationError):
            validate_egyptian_phone("0223456789")  # Cairo landline

    def test_too_short(self):
        with pytest.raises(ValidationError):
            validate_egyptian_phone("01012")

    def test_normalise_strips_country_code(self):
        assert normalise_phone("+201012345678") == "01012345678"

    def test_normalise_already_local(self):
        assert normalise_phone("01012345678") == "01012345678"


# ── OTP model tests ───────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestOTPModel:
    def test_is_expired_false_for_fresh_otp(self):
        otp = OTPFactory()
        assert otp.is_expired is False

    def test_is_expired_true_for_old_otp(self):
        otp = OTPFactory(
            expires_at=timezone.now() - timezone.timedelta(minutes=1)
        )
        assert otp.is_expired is True


# ── Service: generate_otp ─────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGenerateOTP:
    def test_creates_otp_record(self):
        otp = generate_otp("01012345678")
        assert OTP.objects.filter(phone="01012345678", is_used=False).exists()

    def test_code_is_six_digits(self):
        otp = generate_otp("01012345678")
        assert len(otp.code) == 6
        assert otp.code.isdigit()

    def test_previous_otps_invalidated(self):
        # Create an existing unused OTP
        OTPFactory(phone="01012345678", is_used=False)
        # Generate a new one
        generate_otp("01012345678")
        # Only the new OTP should be unused
        unused = OTP.objects.filter(phone="01012345678", is_used=False)
        assert unused.count() == 1

    def test_normalises_phone_with_country_code(self):
        otp = generate_otp("+201012345678")
        assert otp.phone == "01012345678"


# ── Service: verify_otp ───────────────────────────────────────────────────────


@pytest.mark.django_db
class TestVerifyOTP:
    def test_valid_otp_returns_user(self):
        OTPFactory(phone="01012345678", code="123456")
        user = verify_otp("01012345678", "123456")
        assert user is not None
        assert user.phone == "01012345678"

    def test_first_login_creates_user(self):
        OTPFactory(phone="01099999999", code="654321")
        assert not User.objects.filter(phone="01099999999").exists()
        user = verify_otp("01099999999", "654321")
        assert User.objects.filter(phone="01099999999").exists()

    def test_returning_user_not_duplicated(self):
        phone = "01011111111"
        UserFactory(phone=phone)
        OTPFactory(phone=phone, code="111111")
        verify_otp(phone, "111111")
        assert User.objects.filter(phone=phone).count() == 1

    def test_wrong_code_raises(self):
        OTPFactory(phone="01012345678", code="123456")
        with pytest.raises(ValueError, match="Invalid OTP"):
            verify_otp("01012345678", "000000")

    def test_expired_otp_raises(self):
        OTPFactory(
            phone="01012345678",
            code="123456",
            expires_at=timezone.now() - timezone.timedelta(minutes=1),
        )
        with pytest.raises(ValueError, match="expired"):
            verify_otp("01012345678", "123456")

    def test_used_otp_raises(self):
        OTPFactory(phone="01012345678", code="123456", is_used=True)
        with pytest.raises(ValueError, match="Invalid OTP"):
            verify_otp("01012345678", "123456")

    def test_otp_marked_used_after_verification(self):
        otp = OTPFactory(phone="01012345678", code="123456")
        verify_otp("01012345678", "123456")
        otp.refresh_from_db()
        assert otp.is_used is True


# ── User model tests ──────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUserModel:
    def test_customer_role_properties(self):
        user = UserFactory(role=User.Role.CUSTOMER)
        assert user.is_customer is True
        assert user.is_business_owner is False
        assert user.is_admin_staff is False

    def test_business_owner_role_properties(self):
        user = UserFactory(role=User.Role.BUSINESS_OWNER)
        assert user.is_business_owner is True
        assert user.is_customer is False

    def test_str_representation(self):
        user = UserFactory(name="Ahmed Ali", phone="01012345678")
        assert "Ahmed Ali" in str(user)
        assert "01012345678" in str(user)

    def test_customer_has_unusable_password(self):
        user = UserFactory()
        assert not user.has_usable_password()
