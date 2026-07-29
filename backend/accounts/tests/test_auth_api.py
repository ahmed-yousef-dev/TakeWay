"""
API-level tests for auth endpoints.

Tests validate the HTTP contract: status codes, response shape, and headers.
Business logic details are already covered in test_models.py.
"""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.core.cache import cache

from accounts.models import OTP, User
from accounts.tests.factories import TEST_PASSWORD, OTPFactory, UserFactory


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def auth_client(client):
    """APIClient authenticated as a regular customer."""
    user = UserFactory(name="Test User")
    client.force_authenticate(user=user)
    return client, user


# ── POST /api/v1/auth/otp/request/ ───────────────────────────────────────────


@pytest.mark.django_db
class TestRequestOTP:
    url = "/api/v1/auth/otp/request/"

    def test_valid_phone_returns_200(self, client):
        resp = client.post(self.url, {"phone": "01012345678"})
        assert resp.status_code == status.HTTP_200_OK
        assert "detail" in resp.data

    def test_otp_record_created(self, client):
        client.post(self.url, {"phone": "01012345678"})
        assert OTP.objects.filter(phone="01012345678", is_used=False).exists()

    def test_invalid_phone_returns_400(self, client):
        resp = client.post(self.url, {"phone": "not-a-phone"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_phone_returns_400(self, client):
        resp = client.post(self.url, {})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ── POST /api/v1/auth/otp/verify/ ────────────────────────────────────────────


@pytest.mark.django_db
class TestVerifyOTP:
    url = "/api/v1/auth/otp/verify/"

    # Shared valid payload used by most tests
    VALID_PASSWORD = "ValidPass123!"

    def _payload(self, phone="01012345678", code="123456", **extra):
        return {
            "phone": phone,
            "code": code,
            "name": "Ahmed Ali",
            "password": self.VALID_PASSWORD,
            "password_confirm": self.VALID_PASSWORD,
            **extra,
        }

    def test_valid_otp_returns_tokens(self, client):
        OTPFactory(phone="01012345678", code="123456")
        resp = client.post(self.url, self._payload())
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.data
        assert "refresh" in resp.data
        assert "user" in resp.data

    def test_registration_creates_user_with_name_and_password(self, client):
        OTPFactory(phone="01011111111", code="111111")
        resp = client.post(self.url, self._payload(phone="01011111111", code="111111", name="New User"))
        assert resp.status_code == status.HTTP_200_OK
        user = User.objects.get(phone="01011111111")
        assert user.name == "New User"
        assert user.check_password(self.VALID_PASSWORD)

    def test_wrong_code_returns_400(self, client):
        OTPFactory(phone="01012345678", code="123456")
        resp = client.post(self.url, self._payload(code="000000"))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_expired_otp_returns_400(self, client):
        from django.utils import timezone
        OTPFactory(
            phone="01012345678",
            code="123456",
            expires_at=timezone.now() - timezone.timedelta(minutes=1),
        )
        resp = client.post(self.url, self._payload())
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_non_digit_code_returns_400(self, client):
        resp = client.post(self.url, self._payload(code="abcdef"))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_code_too_short_returns_400(self, client):
        resp = client.post(self.url, self._payload(code="123"))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_password_mismatch_returns_400(self, client):
        OTPFactory(phone="01012345678", code="123456")
        payload = self._payload()
        payload["password_confirm"] = "DifferentPass99!"
        resp = client.post(self.url, payload)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_weak_password_returns_400(self, client):
        OTPFactory(phone="01012345678", code="123456")
        resp = client.post(self.url, self._payload(password="12345678", password_confirm="12345678"))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_password_returns_400(self, client):
        OTPFactory(phone="01012345678", code="123456")
        resp = client.post(self.url, {
            "phone": "01012345678",
            "code": "123456",
            "name": "Ahmed",
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_response_includes_user_data(self, client):
        OTPFactory(phone="01012345678", code="123456")
        resp = client.post(self.url, self._payload())
        assert resp.data["user"]["phone"] == "01012345678"
        assert "role" in resp.data["user"]


# ── POST /api/v1/auth/login/ ─────────────────────────────────────────────────


@pytest.mark.django_db
class TestLogin:
    url = "/api/v1/auth/login/"

    def test_valid_credentials_returns_tokens(self, client):
        user = UserFactory(phone="01012345678")
        resp = client.post(self.url, {"phone": "01012345678", "password": TEST_PASSWORD})
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.data
        assert "refresh" in resp.data
        assert "user" in resp.data

    def test_response_includes_user_data(self, client):
        UserFactory(phone="01012345678", name="Login User")
        resp = client.post(self.url, {"phone": "01012345678", "password": TEST_PASSWORD})
        assert resp.data["user"]["phone"] == "01012345678"
        assert resp.data["user"]["name"] == "Login User"

    def test_wrong_password_returns_401(self, client):
        UserFactory(phone="01012345678")
        resp = client.post(self.url, {"phone": "01012345678", "password": "WrongPass99!"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_nonexistent_phone_returns_401(self, client):
        resp = client.post(self.url, {"phone": "01099999999", "password": TEST_PASSWORD})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_missing_phone_returns_400(self, client):
        resp = client.post(self.url, {"password": TEST_PASSWORD})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_password_returns_400(self, client):
        resp = client.post(self.url, {"phone": "01012345678"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_inactive_user_returns_401(self, client):
        UserFactory(phone="01012345678", is_active=False)
        resp = client.post(self.url, {"phone": "01012345678", "password": TEST_PASSWORD})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ── POST /api/v1/auth/password/reset/ ────────────────────────────────────────


@pytest.mark.django_db
class TestForgotPassword:
    url = "/api/v1/auth/password/reset/"
    NEW_PASSWORD = "NewValidPass99!"

    def _payload(self, phone="01012345678", code="123456", **extra):
        return {
            "phone": phone,
            "code": code,
            "new_password": self.NEW_PASSWORD,
            "new_password_confirm": self.NEW_PASSWORD,
            **extra,
        }

    def test_valid_reset_returns_tokens(self, client):
        UserFactory(phone="01012345678")
        OTPFactory(phone="01012345678", code="123456")
        resp = client.post(self.url, self._payload())
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.data
        assert "refresh" in resp.data

    def test_password_is_actually_changed(self, client):
        user = UserFactory(phone="01012345678")
        OTPFactory(phone="01012345678", code="123456")
        client.post(self.url, self._payload())
        user.refresh_from_db()
        assert user.check_password(self.NEW_PASSWORD)
        assert not user.check_password(TEST_PASSWORD)

    def test_expired_otp_returns_400(self, client):
        from django.utils import timezone
        UserFactory(phone="01012345678")
        OTPFactory(
            phone="01012345678",
            code="123456",
            expires_at=timezone.now() - timezone.timedelta(minutes=1),
        )
        resp = client.post(self.url, self._payload())
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_wrong_code_returns_400(self, client):
        UserFactory(phone="01012345678")
        OTPFactory(phone="01012345678", code="123456")
        resp = client.post(self.url, self._payload(code="000000"))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_password_mismatch_returns_400(self, client):
        UserFactory(phone="01012345678")
        OTPFactory(phone="01012345678", code="123456")
        payload = self._payload()
        payload["new_password_confirm"] = "DoesNotMatch99!"
        resp = client.post(self.url, payload)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_weak_password_returns_400(self, client):
        UserFactory(phone="01012345678")
        OTPFactory(phone="01012345678", code="123456")
        resp = client.post(self.url, self._payload(new_password="12345678", new_password_confirm="12345678"))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_no_account_for_phone_returns_400(self, client):
        OTPFactory(phone="01099988877", code="123456")
        resp = client.post(self.url, self._payload(phone="01099988877"))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ── POST /api/v1/auth/password/change/ ───────────────────────────────────────


@pytest.mark.django_db
class TestChangePassword:
    url = "/api/v1/auth/password/change/"
    NEW_PASSWORD = "NewValidPass99!"

    def _payload(self, **extra):
        return {
            "old_password": TEST_PASSWORD,
            "new_password": self.NEW_PASSWORD,
            "new_password_confirm": self.NEW_PASSWORD,
            **extra,
        }

    def test_valid_change_returns_200(self, auth_client):
        client, user = auth_client
        resp = client.post(self.url, self._payload())
        assert resp.status_code == status.HTTP_200_OK
        assert "detail" in resp.data

    def test_password_is_actually_changed(self, auth_client):
        client, user = auth_client
        client.post(self.url, self._payload())
        user.refresh_from_db()
        assert user.check_password(self.NEW_PASSWORD)
        assert not user.check_password(TEST_PASSWORD)

    def test_wrong_old_password_returns_400(self, auth_client):
        client, _ = auth_client
        resp = client.post(self.url, self._payload(old_password="WrongOldPass!"))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_password_mismatch_returns_400(self, auth_client):
        client, _ = auth_client
        payload = self._payload()
        payload["new_password_confirm"] = "DoesNotMatch99!"
        resp = client.post(self.url, payload)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_weak_new_password_returns_400(self, auth_client):
        client, _ = auth_client
        resp = client.post(self.url, self._payload(new_password="12345678", new_password_confirm="12345678"))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_returns_401(self, client):
        resp = client.post(self.url, self._payload())
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ── GET/PATCH /api/v1/auth/profile/ ──────────────────────────────────────────


@pytest.mark.django_db
class TestProfile:
    url = "/api/v1/auth/profile/"

    def test_unauthenticated_returns_401(self, client):
        resp = client.get(self.url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authenticated_returns_profile(self, auth_client):
        client, user = auth_client
        resp = client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["phone"] == user.phone
        assert resp.data["name"] == user.name

    def test_patch_updates_name(self, auth_client):
        client, user = auth_client
        resp = client.patch(self.url, {"name": "Updated Name"})
        assert resp.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.name == "Updated Name"

    def test_phone_is_read_only(self, auth_client):
        client, user = auth_client
        original_phone = user.phone
        client.patch(self.url, {"phone": "01099999999"})
        user.refresh_from_db()
        assert user.phone == original_phone

    def test_role_is_read_only(self, auth_client):
        client, user = auth_client
        client.patch(self.url, {"role": "admin"})
        user.refresh_from_db()
        assert user.role == User.Role.CUSTOMER


# ── POST /api/v1/auth/token/refresh/ ─────────────────────────────────────────


@pytest.mark.django_db
class TestTokenRefresh:
    url = "/api/v1/auth/token/refresh/"

    def test_valid_refresh_returns_new_access(self, client):
        # Get tokens via registration (OTP verify)
        OTPFactory(phone="01012345678", code="123456")
        verify_resp = client.post("/api/v1/auth/otp/verify/", {
            "phone": "01012345678",
            "code": "123456",
            "name": "Test",
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
        })
        refresh_token = verify_resp.data["refresh"]

        resp = client.post(self.url, {"refresh": refresh_token})
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.data

    def test_valid_refresh_after_login(self, client):
        # Also verify the refresh token from login works
        UserFactory(phone="01012345678")
        login_resp = client.post("/api/v1/auth/login/", {
            "phone": "01012345678",
            "password": TEST_PASSWORD,
        })
        refresh_token = login_resp.data["refresh"]

        resp = client.post(self.url, {"refresh": refresh_token})
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.data

    def test_invalid_refresh_returns_401(self, client):
        resp = client.post(self.url, {"refresh": "not-a-valid-token"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
