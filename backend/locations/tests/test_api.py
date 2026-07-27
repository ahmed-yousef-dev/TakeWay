"""
API tests for the locations app.
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from locations.models import Location
from locations.tests.factories import GovernorateFactory, LocationFactory


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
class TestGovernorateList:
    url = "/api/v1/locations/governorates/"

    def test_returns_active_governorates(self, client):
        GovernorateFactory.create_batch(3)
        resp = client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 3

    def test_inactive_governorate_not_returned(self, client):
        GovernorateFactory(is_active=False)
        GovernorateFactory(is_active=True)
        resp = client.get(self.url)
        assert len(resp.data) == 1

    def test_no_authentication_required(self, client):
        resp = client.get(self.url)
        assert resp.status_code != status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestGovernorateDetail:
    def test_returns_governorate_with_locations(self, client):
        gov = GovernorateFactory()
        LocationFactory.create_batch(3, governorate=gov)
        resp = client.get(f"/api/v1/locations/governorates/{gov.pk}/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["locations"]) == 3

    def test_inactive_locations_excluded(self, client):
        gov = GovernorateFactory()
        LocationFactory(governorate=gov, is_active=True)
        LocationFactory(governorate=gov, is_active=False)
        resp = client.get(f"/api/v1/locations/governorates/{gov.pk}/")
        assert len(resp.data["locations"]) == 1


@pytest.mark.django_db
class TestLocationList:
    url = "/api/v1/locations/"

    def test_returns_active_locations(self, client):
        LocationFactory.create_batch(4)
        resp = client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 4

    def test_inactive_locations_not_returned(self, client):
        LocationFactory(is_active=True)
        LocationFactory(is_active=False)
        resp = client.get(self.url)
        assert len(resp.data) == 1

    def test_filter_by_governorate(self, client):
        gov1 = GovernorateFactory()
        gov2 = GovernorateFactory()
        LocationFactory.create_batch(2, governorate=gov1)
        LocationFactory.create_batch(3, governorate=gov2)
        resp = client.get(self.url, {"governorate": gov1.pk})
        assert len(resp.data) == 2

    def test_filter_by_type(self, client):
        LocationFactory(type=Location.LocationType.CITY)
        LocationFactory(type=Location.LocationType.VILLAGE)
        LocationFactory(type=Location.LocationType.VILLAGE)
        resp = client.get(self.url, {"type": "city"})
        assert len(resp.data) == 1

    def test_response_includes_delivery_fee(self, client):
        LocationFactory(delivery_fee="25.00")
        resp = client.get(self.url)
        assert "delivery_fee" in resp.data[0]
        assert resp.data[0]["delivery_fee"] == "25.00"


@pytest.mark.django_db
class TestLocationDetail:
    def test_returns_single_location(self, client):
        loc = LocationFactory()
        resp = client.get(f"/api/v1/locations/{loc.pk}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["id"] == loc.pk

    def test_includes_governorate_name(self, client):
        gov = GovernorateFactory(name="Qalyubia")
        loc = LocationFactory(governorate=gov)
        resp = client.get(f"/api/v1/locations/{loc.pk}/")
        assert resp.data["governorate_name"] == "Qalyubia"
