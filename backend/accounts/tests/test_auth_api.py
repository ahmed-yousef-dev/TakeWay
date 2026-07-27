"""
API-level tests for auth endpoints.

Tests validate the HTTP contract: status codes, response shape, and headers.
Business logic details are already covered in test_models.py.
"""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import OTP, User
from accounts.tests.factories import OTPFactory, UserFactory


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

    def test_valid_otp_returns_tokens(self, client):
        OTPFactory(phone="01012345678", code="123456")
        resp = client.post(self.url, {
            "phone": "01012345678",
            "code": "123456",
            "name": "Ahmed Ali",
        })
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.data
        assert "refresh" in resp.data
        assert "user" in resp.data

    def test_first_login_creates_user_with_name(self, client):
        OTPFactory(phone="01011111111", code="111111")
        resp = client.post(self.url, {
            "phone": "01011111111",
            "code": "111111",
            "name": "New User",
        })
        assert resp.status_code == status.HTTP_200_OK
        user = User.objects.get(phone="01011111111")
        assert user.name == "New User"

    def test_wrong_code_returns_400(self, client):
        OTPFactory(phone="01012345678", code="123456")
        resp = client.post(self.url, {"phone": "01012345678", "code": "000000"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_expired_otp_returns_400(self, client):
        from django.utils import timezone
        OTPFactory(
            phone="01012345678",
            code="123456",
            expires_at=timezone.now() - timezone.timedelta(minutes=1),
        )
        resp = client.post(self.url, {"phone": "01012345678", "code": "123456"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_non_digit_code_returns_400(self, client):
        resp = client.post(self.url, {"phone": "01012345678", "code": "abcdef"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_code_too_short_returns_400(self, client):
        resp = client.post(self.url, {"phone": "01012345678", "code": "123"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_response_includes_user_data(self, client):
        OTPFactory(phone="01012345678", code="123456")
        resp = client.post(self.url, {
            "phone": "01012345678",
            "code": "123456",
            "name": "Ahmed",
        })
        assert resp.data["user"]["phone"] == "01012345678"
        assert "role" in resp.data["user"]


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
        resp = client.patch(self.url, {"phone": "01099999999"})
        user.refresh_from_db()
        assert user.phone == original_phone

    def test_role_is_read_only(self, auth_client):
        client, user = auth_client
        resp = client.patch(self.url, {"role": "admin"})
        user.refresh_from_db()
        assert user.role == User.Role.CUSTOMER


# ── POST /api/v1/auth/token/refresh/ ─────────────────────────────────────────


@pytest.mark.django_db
class TestTokenRefresh:
    url = "/api/v1/auth/token/refresh/"

    def test_valid_refresh_returns_new_access(self, client):
        # Get tokens first via OTP verification
        OTPFactory(phone="01012345678", code="123456")
        verify_resp = client.post("/api/v1/auth/otp/verify/", {
            "phone": "01012345678",
            "code": "123456",
            "name": "Test",
        })
        refresh_token = verify_resp.data["refresh"]

        resp = client.post(self.url, {"refresh": refresh_token})
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.data

    def test_invalid_refresh_returns_401(self, client):
        resp = client.post(self.url, {"refresh": "not-a-valid-token"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
