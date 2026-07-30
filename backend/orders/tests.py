import pytest
from decimal import Decimal

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
