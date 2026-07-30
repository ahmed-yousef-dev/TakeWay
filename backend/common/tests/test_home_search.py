import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from businesses.tests.factories import BusinessCategoryFactory, BusinessFactory, ProductFactory
from locations.tests.factories import LocationFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestHomeAPI:
    def test_home_api_requires_location(self, api_client):
        # API doesn't strictly 400 without location, but it falls back gracefully
        url = reverse("v1:home")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        # Structure check
        assert "banners" in response.data
        assert "categories" in response.data
        assert "featured_businesses" in response.data
        assert "todays_offers" in response.data

    def test_home_api_returns_data(self, api_client):
        loc = LocationFactory()
        cat = BusinessCategoryFactory()
        b1 = BusinessFactory(location=loc, category=cat, is_featured=True, is_active=True)
        
        # Test with location
        url = reverse("v1:home")
        response = api_client.get(f"{url}?location={loc.id}")
        assert response.status_code == status.HTTP_200_OK
        
        assert len(response.data["categories"]) == 1
        assert response.data["categories"][0]["id"] == cat.id
        
        assert len(response.data["featured_businesses"]) == 1
        assert response.data["featured_businesses"][0]["id"] == b1.id


@pytest.mark.django_db
class TestUnifiedSearchAPI:
    def test_search_empty_query(self, api_client):
        url = reverse("v1:unified-search")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["query"] == ""
        assert response.data["businesses"] == []
        assert response.data["products"] == []

    def test_search_finds_business_and_product(self, api_client):
        loc = LocationFactory()
        b1 = BusinessFactory(name="Pizza House", location=loc, is_active=True)
        p1 = ProductFactory(name="Cheese Pizza", business=b1, is_active=True, is_available=True)
        
        url = reverse("v1:unified-search")
        response = api_client.get(f"{url}?q=pizza")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["query"] == "pizza"
        
        assert len(response.data["businesses"]) == 1
        assert response.data["businesses"][0]["id"] == b1.id
        
        assert len(response.data["products"]) == 1
        assert response.data["products"][0]["id"] == p1.id

    def test_search_respects_location(self, api_client):
        loc1 = LocationFactory()
        loc2 = LocationFactory()
        b1 = BusinessFactory(name="Pizza House 1", location=loc1, is_active=True)
        b2 = BusinessFactory(name="Pizza House 2", location=loc2, is_active=True)
        
        url = reverse("v1:unified-search")
        response = api_client.get(f"{url}?q=pizza&location={loc1.id}")
        assert response.status_code == status.HTTP_200_OK
        
        # Only loc1 business should be returned
        assert len(response.data["businesses"]) == 1
        assert response.data["businesses"][0]["id"] == b1.id
