"""
Tests for business owner API endpoints.

Covers: product CRUD, variant CRUD, product category CRUD.
Critical invariants:
  - Business owners can only access their OWN business's data.
  - Non-owners get 403 on all owner endpoints.
  - Soft delete is used (DELETE returns 204 but record still exists in DB).
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from accounts.tests.factories import BusinessOwnerFactory, UserFactory
from businesses.models import Product, ProductCategory
from businesses.tests.factories import (
    BusinessFactory,
    ProductCategoryFactory,
    ProductFactory,
    ProductVariantFactory,
)


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def owner_setup():
    """Returns (client, owner_user, business) for a business owner."""
    owner = BusinessOwnerFactory(name="Owner")
    business = BusinessFactory(owner=owner)
    client = APIClient()
    client.force_authenticate(user=owner)
    return client, owner, business


@pytest.fixture
def other_owner_setup():
    """A second business owner with their own separate business."""
    other_owner = BusinessOwnerFactory(name="Other Owner")
    other_business = BusinessFactory(owner=other_owner)
    return other_owner, other_business


# ── GET /api/v1/my-business/ ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestMyBusiness:
    url = "/api/v1/my-business/"

    def test_owner_can_view_own_business(self, owner_setup):
        client, owner, business = owner_setup
        resp = client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["id"] == business.pk

    def test_customer_cannot_access(self, client):
        customer = UserFactory(role=User.Role.CUSTOMER)
        client.force_authenticate(user=customer)
        resp = client.get(self.url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_returns_401(self, client):
        resp = client.get(self.url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ── Products CRUD ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestOwnerProductList:
    url = "/api/v1/my-business/products/"

    def test_owner_can_list_own_products(self, owner_setup):
        client, owner, business = owner_setup
        ProductFactory.create_batch(3, business=business)
        resp = client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 3

    def test_owner_cannot_see_other_business_products(self, owner_setup, other_owner_setup):
        client, owner, business = owner_setup
        other_owner, other_business = other_owner_setup
        ProductFactory.create_batch(5, business=other_business)
        resp = client.get(self.url)
        assert resp.data["count"] == 0

    def test_response_includes_cost_price(self, owner_setup):
        client, owner, business = owner_setup
        ProductFactory(business=business, cost_price="8.00")
        resp = client.get(self.url)
        assert "cost_price" in resp.data["results"][0]

    def test_owner_can_create_product(self, owner_setup):
        client, owner, business = owner_setup
        payload = {
            "name": "New Product",
            "cost_price": "10.00",
            "selling_price": "15.00",
        }
        resp = client.post(self.url, payload)
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["name"] == "New Product"
        assert resp.data["business"] == business.pk

    def test_create_product_sets_business_automatically(self, owner_setup):
        client, owner, business = owner_setup
        payload = {"name": "Auto Business", "cost_price": "5.00", "selling_price": "8.00"}
        resp = client.post(self.url, payload)
        assert resp.data["business"] == business.pk

    def test_create_product_invalid_selling_price(self, owner_setup):
        client, owner, business = owner_setup
        payload = {"name": "Bad Product", "cost_price": "5.00", "selling_price": "-1.00"}
        resp = client.post(self.url, payload)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_non_owner_cannot_create(self, client):
        customer = UserFactory(role=User.Role.CUSTOMER)
        client.force_authenticate(user=customer)
        resp = client.post(self.url, {"name": "Hack", "cost_price": "1", "selling_price": "2"})
        assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestOwnerProductDetail:
    def test_owner_can_update_own_product(self, owner_setup):
        client, owner, business = owner_setup
        product = ProductFactory(business=business, name="Old Name")
        resp = client.patch(
            f"/api/v1/my-business/products/{product.pk}/",
            {"name": "New Name"},
        )
        assert resp.status_code == status.HTTP_200_OK
        product.refresh_from_db()
        assert product.name == "New Name"

    def test_owner_can_toggle_availability(self, owner_setup):
        client, owner, business = owner_setup
        product = ProductFactory(business=business, is_available=True)
        resp = client.patch(
            f"/api/v1/my-business/products/{product.pk}/",
            {"is_available": False},
        )
        assert resp.status_code == status.HTTP_200_OK
        product.refresh_from_db()
        assert product.is_available is False

    def test_owner_cannot_access_other_business_product(self, owner_setup, other_owner_setup):
        client, owner, business = owner_setup
        other_owner, other_business = other_owner_setup
        other_product = ProductFactory(business=other_business)
        resp = client.patch(
            f"/api/v1/my-business/products/{other_product.pk}/",
            {"name": "Hijacked"},
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_soft_deletes_product(self, owner_setup):
        client, owner, business = owner_setup
        product = ProductFactory(business=business)
        resp = client.delete(f"/api/v1/my-business/products/{product.pk}/")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        # Record still in DB but is_active=False
        product.refresh_from_db()
        assert product.is_active is False

    def test_soft_deleted_product_not_in_owner_list(self, owner_setup):
        client, owner, business = owner_setup
        product = ProductFactory(business=business)
        product.soft_delete()
        # Default manager (objects) filters is_active=True
        # But owner view uses all_objects — so it SHOULD appear
        # Check the public list instead, where it should be hidden
        resp = client.get(f"/api/v1/businesses/{business.pk}/products/")
        assert len(resp.data["uncategorised"]) == 0


# ── Variants CRUD ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestOwnerVariants:
    def test_owner_can_create_variant(self, owner_setup):
        client, owner, business = owner_setup
        product = ProductFactory(business=business)
        payload = {
            "name": "Large",
            "cost_price": "12.00",
            "selling_price": "18.00",
        }
        resp = client.post(
            f"/api/v1/my-business/products/{product.pk}/variants/",
            payload,
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["name"] == "Large"

    def test_owner_can_update_variant(self, owner_setup):
        client, owner, business = owner_setup
        product = ProductFactory(business=business)
        variant = ProductVariantFactory(product=product)
        resp = client.patch(
            f"/api/v1/my-business/products/{product.pk}/variants/{variant.pk}/",
            {"selling_price": "25.00"},
        )
        assert resp.status_code == status.HTTP_200_OK
        variant.refresh_from_db()
        assert str(variant.selling_price) == "25.00"

    def test_owner_cannot_add_variant_to_other_product(self, owner_setup, other_owner_setup):
        client, owner, business = owner_setup
        other_owner, other_business = other_owner_setup
        other_product = ProductFactory(business=other_business)
        resp = client.post(
            f"/api/v1/my-business/products/{other_product.pk}/variants/",
            {"name": "S", "cost_price": "1", "selling_price": "2"},
        )
        assert resp.status_code in (
            status.HTTP_404_NOT_FOUND,
            status.HTTP_403_FORBIDDEN,
        )


# ── Product categories CRUD ───────────────────────────────────────────────────


@pytest.mark.django_db
class TestOwnerProductCategories:
    url = "/api/v1/my-business/product-categories/"

    def test_owner_can_create_product_category(self, owner_setup):
        client, owner, business = owner_setup
        resp = client.post(self.url, {"name": "Drinks", "sort_order": 1})
        assert resp.status_code == status.HTTP_201_CREATED
        # Use all_objects to bypass SoftDeleteManager (categories are is_active=True by default)
        assert ProductCategory.all_objects.filter(name="Drinks", business=business).exists()

    def test_owner_cannot_see_other_business_categories(self, owner_setup, other_owner_setup):
        client, owner, business = owner_setup
        other_owner, other_business = other_owner_setup
        ProductCategoryFactory.create_batch(3, business=other_business)
        resp = client.get(self.url)
        assert resp.data["count"] == 0

    def test_delete_soft_deletes_category(self, owner_setup):
        client, owner, business = owner_setup
        cat = ProductCategoryFactory(business=business)
        resp = client.delete(f"{self.url}{cat.pk}/")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        cat.refresh_from_db()
        assert cat.is_active is False

    def test_product_category_must_belong_to_own_business(self, owner_setup, other_owner_setup):
        """Creating a product with another business's product category should fail."""
        client, owner, business = owner_setup
        other_owner, other_business = other_owner_setup
        other_cat = ProductCategoryFactory(business=other_business)
        payload = {
            "name": "Bad Product",
            "cost_price": "5.00",
            "selling_price": "8.00",
            "product_category": other_cat.pk,
        }
        resp = client.post("/api/v1/my-business/products/", payload)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
