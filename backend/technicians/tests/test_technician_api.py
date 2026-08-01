"""
API tests for the technicians app.

Covers:
  - Public: category list, technician list, technician detail
  - Auth: TechnicianRequest create (happy path, wrong address, unauthenticated)
  - Auth: TechnicianRequest list (scoped to customer)
  - Security: phone NEVER appears in any public response
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import UserFactory
from orders.models import DeliveryAddress
from technicians.models import TechnicianRequest
from technicians.tests.factories import TechnicianCategoryFactory, TechnicianFactory


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def customer():
    return UserFactory(name="Test Customer")


@pytest.fixture
def auth_client(customer):
    client = APIClient()
    client.force_authenticate(user=customer)
    return client, customer


@pytest.fixture
def technician():
    return TechnicianFactory(phone="01199999999")


@pytest.fixture
def customer_address(customer):
    return DeliveryAddress.objects.create(
        user=customer,
        address_details="123 Test Street",
    )


# ── Technician Category ───────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTechnicianCategoryList:
    url = "/api/v1/technicians/categories/"

    def test_returns_200_for_unauthenticated(self):
        resp = APIClient().get(self.url)
        assert resp.status_code == status.HTTP_200_OK

    def test_returns_all_active_categories(self):
        TechnicianCategoryFactory.create_batch(3)
        resp = APIClient().get(self.url)
        assert len(resp.data) == 3

    def test_response_fields(self):
        TechnicianCategoryFactory(name="Plumber", icon="wrench", sort_order=1)
        resp = APIClient().get(self.url)
        item = resp.data[0]
        assert "id" in item
        assert "name" in item
        assert "icon" in item
        assert "sort_order" in item


# ── Technician List ───────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTechnicianList:
    url = "/api/v1/technicians/"

    def test_returns_200_for_unauthenticated(self):
        resp = APIClient().get(self.url)
        assert resp.status_code == status.HTTP_200_OK

    def test_returns_technicians(self, technician):
        resp = APIClient().get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        # Results may be paginated — check count or results key
        data = resp.data
        results = data.get("results", data)
        assert len(results) >= 1

    def test_phone_never_in_response(self, technician):
        """CRITICAL: phone must never appear in any customer-facing list response."""
        resp = APIClient().get(self.url)
        data = resp.data
        results = data.get("results", data)
        for item in results:
            assert "phone" not in item, "phone field must never be exposed to customers!"

    def test_filter_by_category(self):
        cat_a = TechnicianCategoryFactory(name="Plumbing")
        cat_b = TechnicianCategoryFactory(name="Electrical")
        TechnicianFactory(category=cat_a)
        TechnicianFactory(category=cat_b)

        resp = APIClient().get(self.url, {"category": cat_a.pk})
        data = resp.data
        results = data.get("results", data)
        assert all(item["category"] == cat_a.pk for item in results)


# ── Technician Detail ─────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTechnicianDetail:
    def url(self, pk):
        return f"/api/v1/technicians/{pk}/"

    def test_returns_200_for_unauthenticated(self, technician):
        resp = APIClient().get(self.url(technician.pk))
        assert resp.status_code == status.HTTP_200_OK

    def test_returns_404_for_nonexistent(self):
        resp = APIClient().get(self.url(999999))
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_phone_never_in_detail_response(self, technician):
        """CRITICAL: phone must never appear in the technician detail response."""
        resp = APIClient().get(self.url(technician.pk))
        assert "phone" not in resp.data, "phone field must never be exposed to customers!"


# ── Technician Request: Create ────────────────────────────────────────────────


@pytest.mark.django_db
class TestTechnicianRequestCreate:
    url = "/api/v1/technician-requests/"

    def test_unauthenticated_returns_401(self, technician, customer_address):
        resp = APIClient().post(self.url, {
            "technician": technician.pk,
            "address": customer_address.pk,
        })
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authenticated_can_create_request(self, auth_client, technician, customer_address):
        client, customer = auth_client
        resp = client.post(self.url, {
            "technician": technician.pk,
            "address": customer_address.pk,
            "notes": "Please come in the morning.",
        })
        assert resp.status_code == status.HTTP_201_CREATED
        assert TechnicianRequest.objects.filter(customer=customer).count() == 1

    def test_customer_is_injected_not_provided(self, auth_client, technician, customer_address):
        """customer FK must be set server-side, never from client payload."""
        client, customer = auth_client
        other_user = UserFactory(name="Other User")
        resp = client.post(self.url, {
            "technician": technician.pk,
            "address": customer_address.pk,
            # Attempt to inject another user's ID — should be ignored
            "customer": other_user.pk,
        })
        assert resp.status_code == status.HTTP_201_CREATED
        req = TechnicianRequest.objects.get(pk=resp.data["id"])
        assert req.customer_id == customer.pk

    def test_default_status_is_pending(self, auth_client, technician, customer_address):
        client, customer = auth_client
        client.post(self.url, {
            "technician": technician.pk,
            "address": customer_address.pk,
        })
        req = TechnicianRequest.objects.get(customer=customer)
        assert req.status == TechnicianRequest.Status.PENDING

    def test_cannot_use_another_customers_address(self, auth_client, technician):
        """Address ownership validation must reject another user's address."""
        client, _ = auth_client
        other_user = UserFactory(name="Other User")
        other_address = DeliveryAddress.objects.create(
            user=other_user,
            address_details="Other Street",
        )
        resp = client.post(self.url, {
            "technician": technician.pk,
            "address": other_address.pk,
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ── Technician Request: List ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestTechnicianRequestList:
    url = "/api/v1/technician-requests/"

    def test_unauthenticated_returns_401(self):
        resp = APIClient().get(self.url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_customer_only_sees_own_requests(self, auth_client, technician, customer_address):
        client, customer = auth_client
        other_user = UserFactory(name="Other User")
        other_address = DeliveryAddress.objects.create(
            user=other_user, address_details="Other St"
        )

        # Create one request for our customer and one for another user
        TechnicianRequest.objects.create(
            customer=customer, technician=technician, address=customer_address
        )
        TechnicianRequest.objects.create(
            customer=other_user, technician=technician, address=other_address
        )

        resp = client.get(self.url)
        data = resp.data
        results = data.get("results", data)
        assert len(results) == 1
        # All results must belong to the authenticated customer
        for item in results:
            req = TechnicianRequest.objects.get(pk=item["id"])
            assert req.customer_id == customer.pk
