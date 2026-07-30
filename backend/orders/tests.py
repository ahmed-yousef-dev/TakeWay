import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from accounts.tests.factories import UserFactory
from businesses.tests.factories import ProductFactory, ProductVariantFactory
from orders.models import Cart, CartItem, Order, SubOrder, OrderItem, DeliveryAddress
from locations.tests.factories import LocationFactory


@pytest.mark.django_db
class TestOrderItemSnapshot:
    def test_create_snapshot_from_base_product(self):
        """Test snapshot correctly copies base product details when no variant is selected."""
        user = UserFactory()
        product = ProductFactory(name="Test Base Product", selling_price=Decimal("15.50"))
        
        cart = Cart.objects.create(user=user)
        cart_item = CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=2,
            note="Extra spicy"
        )
        
        location = LocationFactory()
        delivery_address = DeliveryAddress.objects.create(user=user, address_details="123 Main St")
        order = Order.objects.create(customer=user, delivery_address=delivery_address)
        sub_order = SubOrder.objects.create(order=order, business=product.business)
        
        snapshot = OrderItem.create_snapshot(cart_item, sub_order)
        snapshot.save()
        
        assert snapshot.product_name == "Test Base Product"
        assert snapshot.variant_name == ""
        assert snapshot.unit_price == Decimal("15.50")
        assert snapshot.quantity == 2
        assert snapshot.total_price == Decimal("31.00")
        assert snapshot.note == "Extra spicy"
        
    def test_create_snapshot_from_product_variant(self):
        """Test snapshot correctly copies variant details when a variant is selected."""
        user = UserFactory()
        product = ProductFactory(name="Test Product")
        variant = ProductVariantFactory(product=product, name="Large Size", selling_price=Decimal("20.00"))
        
        cart = Cart.objects.create(user=user)
        cart_item = CartItem.objects.create(
            cart=cart,
            product=product,
            variant=variant,
            quantity=3,
        )
        
        delivery_address = DeliveryAddress.objects.create(user=user, address_details="123 Main St")
        order = Order.objects.create(customer=user, delivery_address=delivery_address)
        sub_order = SubOrder.objects.create(order=order, business=product.business)
        
        snapshot = OrderItem.create_snapshot(cart_item, sub_order)
        snapshot.save()
        
        assert snapshot.product_name == "Test Product"
        assert snapshot.variant_name == "Large Size"
        assert snapshot.unit_price == Decimal("20.00")
        assert snapshot.quantity == 3
        assert snapshot.total_price == Decimal("60.00")

@pytest.mark.django_db
class TestDeliveryAddressAPI:
    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.url = reverse("v1:address-list")

    def test_create_address(self):
        """User can create a delivery address."""
        payload = {
            "label": "home",
            "address_details": "123 Test St",
            "latitude": "30.044420",
            "longitude": "31.235712",
        }
        response = self.client.post(self.url, payload)
        assert response.status_code == status.HTTP_201_CREATED
        assert DeliveryAddress.objects.filter(user=self.user).count() == 1
        
        address = DeliveryAddress.objects.get()
        assert address.address_details == "123 Test St"
        assert address.user == self.user

    def test_list_addresses(self):
        """User only sees their own addresses."""
        DeliveryAddress.objects.create(user=self.user, address_details="My Home")
        
        other_user = UserFactory()
        DeliveryAddress.objects.create(user=other_user, address_details="Other Home")
        
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["address_details"] == "My Home"

    def test_update_address(self):
        """User can update their address."""
        address = DeliveryAddress.objects.create(user=self.user, address_details="Old St")
        url = reverse("v1:address-detail", args=[address.id])
        
        response = self.client.patch(url, {"address_details": "New St"})
        assert response.status_code == status.HTTP_200_OK
        address.refresh_from_db()
        assert address.address_details == "New St"
