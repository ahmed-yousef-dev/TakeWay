import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.test import Client
from django.core.cache import cache

from accounts.models import User, OTP
from accounts.tests.factories import UserFactory
from orders.models import DeliveryAddress
from locations.models import Location

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def web_client():
    return Client()


def test_user_anonymize():
    """Verify that user.anonymize() scrambles PII and propagates to addresses."""
    user = UserFactory(name="John Doe", phone="01012345678")
    
    address = DeliveryAddress.objects.create(
        user=user,
        latitude=30.0,
        longitude=31.0,
        address_details="123 Main St, Apt 4"
    )
    
    user.anonymize()
    
    user.refresh_from_db()
    address.refresh_from_db()
    
    assert user.name == "Deleted User"
    assert user.phone == f"del_{user.id}"
    assert user.is_active is False
    assert user.location is None
    
    assert address.address_details == "Deleted Address"
    assert address.latitude is None
    assert address.longitude is None


def test_user_cannot_login_after_deletion(api_client):
    """Verify that a soft-deleted user cannot log in (get tokens)."""
    user = UserFactory(phone="01099999999")
    user.anonymize()
    url = reverse("v1:otp-request")
    response = api_client.post(url, {"phone": user.phone})
    # Since the number was changed to del_1, they can't even request OTP with their original phone
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_delete_account_api(api_client):
    """Verify the DELETE /api/v1/auth/profile/ endpoint soft deletes the user."""
    user = UserFactory()
    api_client.force_authenticate(user=user)
    url = reverse("v1:user-profile")
    response = api_client.delete(url)
    
    assert response.status_code == status.HTTP_204_NO_CONTENT
    
    user.refresh_from_db()
    assert user.is_active is False
    assert user.name == "Deleted User"
    assert user.phone == f"del_{user.id}"


def test_delete_account_web_flow(web_client):
    """Verify the out-of-app web deletion flow works end-to-end."""
    user = UserFactory(phone="01088888888")
    
    # 1. Request OTP
    request_url = reverse("web-account-delete-request")
    response = web_client.post(request_url, {"phone": "01088888888"})
    
    assert response.status_code == 302
    assert response.url == reverse("web-account-delete-confirm")
    
    otp = OTP.objects.get(phone="01088888888")
    
    # 2. Confirm OTP
    confirm_url = reverse("web-account-delete-confirm")
    response = web_client.post(confirm_url, {"code": otp.code})
    
    assert response.status_code == 302
    assert response.url == reverse("web-account-delete-success")
    
    user.refresh_from_db()
    assert user.is_active is False
    assert user.name == "Deleted User"
