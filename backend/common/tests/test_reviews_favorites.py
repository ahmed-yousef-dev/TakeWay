import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from businesses.models import Business
from common.models import Favorite, Review
from orders.models import Order, SubOrder

from accounts.tests.factories import UserFactory
from businesses.tests.factories import BusinessFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def business():
    return BusinessFactory()


@pytest.mark.django_db
class TestFavoritesAPI:
    def test_toggle_favorite_adds_and_removes(self, auth_client, user, business):
        url = reverse("v1:favorite-toggle")
        payload = {"content_type_str": "business", "object_id": business.id}

        # Toggle ON
        response = auth_client.post(url, payload)
        assert response.status_code == status.HTTP_201_CREATED
        assert Favorite.objects.filter(user=user, object_id=business.id).exists()

        # Toggle OFF
        response = auth_client.post(url, payload)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Favorite.objects.filter(user=user, object_id=business.id).exists()

    def test_toggle_invalid_content_type(self, auth_client, business):
        url = reverse("v1:favorite-toggle")
        payload = {"content_type_str": "invalid_slug", "object_id": business.id}
        response = auth_client.post(url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_favorites(self, auth_client, user, business):
        # Create a favorite manually
        auth_client.post(reverse("v1:favorite-toggle"), {"content_type_str": "business", "object_id": business.id})
        
        response = auth_client.get(reverse("v1:favorite-list"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["object_id"] == business.id
        assert response.data["results"][0]["content_type_str"] == "business"


@pytest.mark.django_db
class TestReviewsAPI:
    def test_review_creation_rejected_without_completed_order(self, auth_client, business):
        url = reverse("v1:review-create")
        payload = {
            "content_type_str": "business",
            "object_id": business.id,
            "rating": 5,
            "comment": "Awesome!"
        }
        response = auth_client.post(url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "You can only review a business after a delivered order from it." in str(response.data)
        assert Review.objects.count() == 0

    def test_review_creation_accepted_with_completed_order(self, auth_client, user, business):
        # Create a delivered order for this business
        from orders.models import DeliveryAddress
        address = DeliveryAddress.objects.create(
            user=user,
            label="Home",
            address_details="123 Test St"
        )
        
        order = Order.objects.create(
            customer=user,
            delivery_address=address,
            status=Order.Status.DELIVERED,
        )
        SubOrder.objects.create(order=order, business=business)

        url = reverse("v1:review-create")
        payload = {
            "content_type_str": "business",
            "object_id": business.id,
            "rating": 4,
            "comment": "Great!"
        }
        response = auth_client.post(url, payload)
        assert response.status_code == status.HTTP_201_CREATED
        assert Review.objects.count() == 1
        review = Review.objects.first()
        assert review.rating == 4
        assert review.comment == "Great!"

    def test_duplicate_review_rejected(self, auth_client, user, business):
        from orders.models import DeliveryAddress
        address = DeliveryAddress.objects.create(
            user=user,
            label="Home",
            address_details="123 Test St"
        )
        order = Order.objects.create(customer=user, delivery_address=address, status=Order.Status.DELIVERED)
        SubOrder.objects.create(order=order, business=business)

        url = reverse("v1:review-create")
        payload = {"content_type_str": "business", "object_id": business.id, "rating": 4}
        
        # First review
        auth_client.post(url, payload)
        
        # Second review
        response = auth_client.post(url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "You have already reviewed this business." in str(response.data)

