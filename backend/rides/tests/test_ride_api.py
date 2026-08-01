"""
API tests for the rides app.

Covers:
  - Auth: RideRequest create (happy path, unauthenticated)
  - Auth: RideRequest list (scoped to customer)
  - Default status is pending
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import UserFactory
from rides.models import RideRequest


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def customer():
    return UserFactory(name="Ride Customer")


@pytest.fixture
def auth_client(customer):
    client = APIClient()
    client.force_authenticate(user=customer)
    return client, customer


VALID_PAYLOAD = {
    "pickup_location": "Village Square",
    "destination": "City Hospital",
    "vehicle_type": RideRequest.VehicleType.CAR,
}


# ── RideRequest: Create ───────────────────────────────────────────────────────


@pytest.mark.django_db
class TestRideRequestCreate:
    url = "/api/v1/ride-requests/"

    def test_unauthenticated_returns_401(self):
        resp = APIClient().post(self.url, VALID_PAYLOAD)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authenticated_can_create_request(self, auth_client):
        client, customer = auth_client
        resp = client.post(self.url, VALID_PAYLOAD)
        assert resp.status_code == status.HTTP_201_CREATED
        assert RideRequest.objects.filter(customer=customer).count() == 1

    def test_default_status_is_pending(self, auth_client):
        client, customer = auth_client
        client.post(self.url, VALID_PAYLOAD)
        req = RideRequest.objects.get(customer=customer)
        assert req.status == RideRequest.Status.PENDING

    def test_customer_is_injected_not_provided(self, auth_client):
        """customer FK must be set server-side, never from client payload."""
        client, customer = auth_client
        other_user = UserFactory(name="Other User")
        payload = {**VALID_PAYLOAD, "customer": other_user.pk}
        resp = client.post(self.url, payload)
        assert resp.status_code == status.HTTP_201_CREATED
        req = RideRequest.objects.get(pk=resp.data["id"])
        assert req.customer_id == customer.pk

    def test_optional_gps_fields_accepted(self, auth_client):
        client, _ = auth_client
        payload = {
            **VALID_PAYLOAD,
            "pickup_lat": "30.060000",
            "pickup_lng": "31.239000",
            "destination_lat": "30.080000",
            "destination_lng": "31.250000",
        }
        resp = client.post(self.url, payload)
        assert resp.status_code == status.HTTP_201_CREATED

    def test_missing_required_fields_returns_400(self, auth_client):
        client, _ = auth_client
        resp = client.post(self.url, {"pickup_location": "Square"})
        # destination and vehicle_type are required
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ── RideRequest: List ─────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestRideRequestList:
    url = "/api/v1/ride-requests/"

    def test_unauthenticated_returns_401(self):
        resp = APIClient().get(self.url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_customer_only_sees_own_requests(self, auth_client):
        client, customer = auth_client
        other_user = UserFactory(name="Other User")

        RideRequest.objects.create(customer=customer, **VALID_PAYLOAD)
        RideRequest.objects.create(customer=other_user, **VALID_PAYLOAD)

        resp = client.get(self.url)
        data = resp.data
        results = data.get("results", data)
        assert len(results) == 1
        req = RideRequest.objects.get(pk=results[0]["id"])
        assert req.customer_id == customer.pk

    def test_response_includes_display_fields(self, auth_client):
        client, customer = auth_client
        RideRequest.objects.create(customer=customer, **VALID_PAYLOAD)
        resp = client.get(self.url)
        data = resp.data
        results = data.get("results", data)
        item = results[0]
        assert "status_display" in item
        assert "vehicle_type_display" in item
