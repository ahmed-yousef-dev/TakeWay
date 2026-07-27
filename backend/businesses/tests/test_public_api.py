"""
Tests for public business API endpoints (customer-facing).

Covers: categories, business list, business detail, product list, product detail.
Critical invariant: cost_price is NEVER present in any public response.
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from businesses.models import Product
from businesses.tests.factories import (
    BusinessCategoryFactory,
    BusinessFactory,
    ProductCategoryFactory,
    ProductFactory,
    ProductVariantFactory,
    WorkingHourFactory,
)
from locations.tests.factories import LocationFactory


@pytest.fixture
def client():
    return APIClient()


# ── Business categories ───────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBusinessCategoryList:
    url = "/api/v1/businesses/categories/"

    def test_returns_active_categories(self, client):
        BusinessCategoryFactory.create_batch(3)
        resp = client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 3

    def test_inactive_categories_excluded(self, client):
        BusinessCategoryFactory(is_active=True)
        BusinessCategoryFactory(is_active=False)
        resp = client.get(self.url)
        assert len(resp.data) == 1

    def test_ordered_by_sort_order(self, client):
        BusinessCategoryFactory(name="Z Category", sort_order=10)
        BusinessCategoryFactory(name="A Category", sort_order=1)
        resp = client.get(self.url)
        assert resp.data[0]["name"] == "A Category"

    def test_no_auth_required(self, client):
        resp = client.get(self.url)
        assert resp.status_code != status.HTTP_401_UNAUTHORIZED


# ── Business list ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBusinessList:
    url = "/api/v1/businesses/"

    def test_returns_active_businesses(self, client):
        BusinessFactory.create_batch(3)
        resp = client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 3

    def test_inactive_businesses_not_returned(self, client):
        BusinessFactory(is_active=True)
        BusinessFactory(is_active=False)
        resp = client.get(self.url)
        assert resp.data["count"] == 1

    def test_filter_by_location(self, client):
        loc1 = LocationFactory()
        loc2 = LocationFactory()
        BusinessFactory.create_batch(2, location=loc1)
        BusinessFactory.create_batch(3, location=loc2)
        resp = client.get(self.url, {"location": loc1.pk})
        assert resp.data["count"] == 2

    def test_filter_by_category(self, client):
        cat1 = BusinessCategoryFactory()
        cat2 = BusinessCategoryFactory()
        BusinessFactory(category=cat1)
        BusinessFactory(category=cat1)
        BusinessFactory(category=cat2)
        resp = client.get(self.url, {"category": cat1.pk})
        assert resp.data["count"] == 2

    def test_search_by_name(self, client):
        BusinessFactory(name="Ahmed Pharmacy")
        BusinessFactory(name="Nile Bakery")
        resp = client.get(self.url, {"search": "Pharmacy"})
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["name"] == "Ahmed Pharmacy"

    def test_cost_price_not_in_response(self, client):
        BusinessFactory()
        resp = client.get(self.url)
        for business in resp.data["results"]:
            assert "cost_price" not in business

    def test_response_includes_category_name(self, client):
        cat = BusinessCategoryFactory(name="Pharmacy")
        BusinessFactory(category=cat)
        resp = client.get(self.url)
        assert resp.data["results"][0]["category_name"] == "Pharmacy"


# ── Business detail ───────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBusinessDetail:
    def test_returns_business_with_working_hours(self, client):
        business = BusinessFactory()
        WorkingHourFactory(business=business, day_of_week=0)
        WorkingHourFactory(business=business, day_of_week=1)
        resp = client.get(f"/api/v1/businesses/{business.pk}/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["working_hours"]) == 2

    def test_inactive_business_returns_404(self, client):
        business = BusinessFactory(is_active=False)
        resp = client.get(f"/api/v1/businesses/{business.pk}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_cost_price_not_in_detail(self, client):
        business = BusinessFactory()
        resp = client.get(f"/api/v1/businesses/{business.pk}/")
        assert "cost_price" not in resp.data


# ── Business product list ─────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBusinessProductList:
    def test_returns_structured_categories_and_uncategorised(self, client):
        business = BusinessFactory()
        cat = ProductCategoryFactory(business=business)
        ProductFactory(business=business, product_category=cat)
        ProductFactory(business=business, product_category=None)  # uncategorised
        resp = client.get(f"/api/v1/businesses/{business.pk}/products/")
        assert resp.status_code == status.HTTP_200_OK
        assert "categories" in resp.data
        assert "uncategorised" in resp.data
        assert len(resp.data["uncategorised"]) == 1

    def test_inactive_products_excluded(self, client):
        business = BusinessFactory()
        ProductFactory(business=business, is_active=True)
        ProductFactory(business=business, is_active=False)
        resp = client.get(f"/api/v1/businesses/{business.pk}/products/")
        assert len(resp.data["uncategorised"]) == 1

    def test_cost_price_not_in_product_list(self, client):
        business = BusinessFactory()
        ProductFactory(business=business, cost_price="5.00", selling_price="10.00")
        resp = client.get(f"/api/v1/businesses/{business.pk}/products/")
        for product in resp.data["uncategorised"]:
            assert "cost_price" not in product


# ── Product detail ────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestProductDetail:
    def test_returns_product_with_variants(self, client):
        product = ProductFactory()
        ProductVariantFactory.create_batch(2, product=product)
        resp = client.get(f"/api/v1/products/{product.pk}/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["variants"]) == 2

    def test_cost_price_not_in_product_detail(self, client):
        product = ProductFactory(cost_price="5.00")
        resp = client.get(f"/api/v1/products/{product.pk}/")
        assert "cost_price" not in resp.data

    def test_cost_price_not_in_variants(self, client):
        product = ProductFactory()
        ProductVariantFactory(product=product, cost_price="5.00")
        resp = client.get(f"/api/v1/products/{product.pk}/")
        for variant in resp.data["variants"]:
            assert "cost_price" not in variant

    def test_inactive_product_returns_404(self, client):
        product = ProductFactory(is_active=False)
        resp = client.get(f"/api/v1/products/{product.pk}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND
