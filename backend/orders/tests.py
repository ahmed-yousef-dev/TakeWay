import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from accounts.tests.factories import UserFactory
from businesses.tests.factories import ProductFactory, ProductVariantFactory
from orders.models import Cart, CartItem, Order, SubOrder, OrderItem, DeliveryAddress
from orders.services import CheckoutError, checkout as checkout_service
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


# ---------------------------------------------------------------------------
# Step 4: Cart Operations tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCartView:
    """GET /api/v1/cart/ — lazy creation, grouping, and totals."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.url = reverse("v1:cart")

    def test_empty_cart_is_created_lazily(self):
        """Fetching the cart when none exists should create it and return an empty cart."""
        assert not Cart.objects.filter(user=self.user).exists()
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert Cart.objects.filter(user=self.user).exists()
        assert response.data["groups"] == []
        assert Decimal(response.data["grand_total"]) == Decimal("0.00")
        assert response.data["item_count"] == 0

    def test_cart_groups_items_by_business(self):
        """Items from different businesses must appear in separate groups."""
        product_a = ProductFactory(selling_price=Decimal("10.00"))
        product_b = ProductFactory(selling_price=Decimal("20.00"))  # different business

        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=product_a, quantity=1)
        CartItem.objects.create(cart=cart, product=product_b, quantity=2)

        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["groups"]) == 2

    def test_grand_total_is_correct(self):
        """Grand total must equal sum of all line totals."""
        product = ProductFactory(selling_price=Decimal("10.00"))
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=product, quantity=3)

        response = self.client.get(self.url)
        assert Decimal(response.data["grand_total"]) == Decimal("30.00")

    def test_variant_price_used_in_total(self):
        """When a variant is attached, the variant selling_price must be used."""
        product = ProductFactory(selling_price=Decimal("10.00"))
        variant = ProductVariantFactory(product=product, selling_price=Decimal("25.00"))
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=product, variant=variant, quantity=2)

        response = self.client.get(self.url)
        assert Decimal(response.data["grand_total"]) == Decimal("50.00")

    def test_unauthenticated_request_is_rejected(self):
        anon_client = APIClient()
        response = anon_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestCartItemAdd:
    """POST /api/v1/cart/items/ — adding items."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.url = reverse("v1:cart-item-list")

    def test_add_base_product(self):
        """Adding a product without variants should create a cart item."""
        product = ProductFactory(selling_price=Decimal("15.00"))
        response = self.client.post(self.url, {"product_id": product.pk, "quantity": 2})
        assert response.status_code == status.HTTP_201_CREATED
        assert CartItem.objects.filter(product=product).count() == 1
        assert Decimal(response.data["grand_total"]) == Decimal("30.00")

    def test_adding_same_product_increments_quantity(self):
        """Adding the same product twice should accumulate quantity, not duplicate the row."""
        product = ProductFactory(selling_price=Decimal("10.00"))
        self.client.post(self.url, {"product_id": product.pk, "quantity": 1})
        self.client.post(self.url, {"product_id": product.pk, "quantity": 3})

        assert CartItem.objects.count() == 1
        assert CartItem.objects.first().quantity == 4

    def test_add_product_with_variant(self):
        """Adding a product+variant should use the variant price."""
        product = ProductFactory(selling_price=Decimal("10.00"))
        variant = ProductVariantFactory(product=product, selling_price=Decimal("18.00"))

        response = self.client.post(
            self.url,
            {"product_id": product.pk, "variant_id": variant.pk, "quantity": 1},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Decimal(response.data["grand_total"]) == Decimal("18.00")

    def test_variant_required_when_product_has_variants(self):
        """If the product has variants, omitting variant_id must return 400."""
        product = ProductFactory()
        ProductVariantFactory(product=product)

        response = self.client.post(self.url, {"product_id": product.pk, "quantity": 1})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_variant_rejected_for_product_without_variants(self):
        """If the product has no variants, passing a variant_id must return 400."""
        product_a = ProductFactory()
        product_b = ProductFactory()
        stray_variant = ProductVariantFactory(product=product_b)

        response = self.client.post(
            self.url,
            {"product_id": product_a.pk, "variant_id": stray_variant.pk, "quantity": 1},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_variant_from_different_product_is_rejected(self):
        """A variant that belongs to a different product must return 400."""
        product_a = ProductFactory()
        product_b = ProductFactory()
        # Add a variant to product_a so it "has variants"
        ProductVariantFactory(product=product_a)
        # Variant belongs to product_b
        variant_b = ProductVariantFactory(product=product_b)

        response = self.client.post(
            self.url,
            {"product_id": product_a.pk, "variant_id": variant_b.pk, "quantity": 1},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unavailable_product_rejected(self):
        """Products that are unavailable must not be addable to the cart."""
        product = ProductFactory(is_available=False)
        response = self.client.post(self.url, {"product_id": product.pk, "quantity": 1})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestCartItemUpdate:
    """PATCH /api/v1/cart/items/{id}/ — updating quantity/note."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.product = ProductFactory(selling_price=Decimal("10.00"))
        self.cart = Cart.objects.create(user=self.user)
        self.item = CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)

    def _url(self):
        return reverse("v1:cart-item-detail", args=[self.item.pk])

    def test_update_quantity(self):
        response = self.client.patch(self._url(), {"quantity": 5})
        assert response.status_code == status.HTTP_200_OK
        self.item.refresh_from_db()
        assert self.item.quantity == 5

    def test_update_note(self):
        response = self.client.patch(self._url(), {"note": "No onions"})
        assert response.status_code == status.HTTP_200_OK
        self.item.refresh_from_db()
        assert self.item.note == "No onions"

    def test_setting_quantity_to_zero_deletes_item(self):
        response = self.client.patch(self._url(), {"quantity": 0})
        assert response.status_code == status.HTTP_200_OK
        assert not CartItem.objects.filter(pk=self.item.pk).exists()

    def test_negative_quantity_rejected(self):
        response = self.client.patch(self._url(), {"quantity": -1})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_update_another_users_cart_item(self):
        other_user = UserFactory()
        other_client = APIClient()
        other_client.force_authenticate(user=other_user)

        response = other_client.patch(self._url(), {"quantity": 99})
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestCartItemRemove:
    """DELETE /api/v1/cart/items/{id}/ and /cart/items/clear/"""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.product = ProductFactory()
        self.cart = Cart.objects.create(user=self.user)
        self.item = CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)

    def test_remove_single_item(self):
        url = reverse("v1:cart-item-detail", args=[self.item.pk])
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_200_OK
        assert not CartItem.objects.filter(pk=self.item.pk).exists()

    def test_clear_cart(self):
        # Add a second item
        product2 = ProductFactory()
        CartItem.objects.create(cart=self.cart, product=product2, quantity=2)

        url = reverse("v1:cart-item-clear")
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_200_OK
        assert self.cart.items.count() == 0
        assert response.data["item_count"] == 0


# ---------------------------------------------------------------------------
# Step 5: Checkout Service Layer tests
# ---------------------------------------------------------------------------

def _make_user_with_location(delivery_fee="15.00", minimum_order_amount="0.00"):
    """Helper: creates a User with an attached Location."""
    location = LocationFactory(
        delivery_fee=delivery_fee,
        minimum_order_amount=minimum_order_amount,
    )
    user = UserFactory(location=location)
    return user, location


def _add_product_to_cart(user, price="50.00", quantity=1):
    """Helper: add one product to user's cart and return (cart, item, product)."""
    product = ProductFactory(selling_price=Decimal(price))
    cart, _ = Cart.objects.get_or_create(user=user)
    item = CartItem.objects.create(cart=cart, product=product, quantity=quantity)
    return cart, item, product


@pytest.mark.django_db
class TestCheckoutService:
    """Direct unit tests of the checkout() service function."""

    def test_checkout_creates_order_with_correct_totals(self):
        """Happy path: checkout produces an Order with snapshotted totals."""
        user, location = _make_user_with_location(delivery_fee="15.00", minimum_order_amount="0.00")
        _, _, product = _add_product_to_cart(user, price="40.00", quantity=2)
        address = DeliveryAddress.objects.create(user=user, address_details="123 Main")

        order = checkout_service(user=user, delivery_address_id=address.pk)

        assert order.pk is not None
        assert order.status == Order.Status.PENDING
        assert order.subtotal == Decimal("80.00")
        assert order.delivery_fee == Decimal("15.00")
        assert order.total_amount == Decimal("95.00")
        assert order.customer == user
        assert order.delivery_address == address

    def test_checkout_clears_cart_after_success(self):
        """Cart must be empty after a successful checkout."""
        user, _ = _make_user_with_location()
        cart, _, _ = _add_product_to_cart(user)
        address = DeliveryAddress.objects.create(user=user, address_details="Addr")

        checkout_service(user=user, delivery_address_id=address.pk)

        assert cart.items.count() == 0

    def test_checkout_splits_items_by_business(self):
        """Items from N businesses must produce N SubOrders."""
        user, _ = _make_user_with_location()
        address = DeliveryAddress.objects.create(user=user, address_details="Addr")

        cart = Cart.objects.create(user=user)
        # Two products from DIFFERENT businesses
        product_a = ProductFactory(selling_price=Decimal("20.00"))
        product_b = ProductFactory(selling_price=Decimal("30.00"))
        CartItem.objects.create(cart=cart, product=product_a, quantity=1)
        CartItem.objects.create(cart=cart, product=product_b, quantity=1)

        order = checkout_service(user=user, delivery_address_id=address.pk)

        assert order.sub_orders.count() == 2
        assert order.subtotal == Decimal("50.00")

    def test_checkout_creates_order_item_snapshots(self):
        """OrderItem snapshots must capture product name and price at checkout time."""
        user, _ = _make_user_with_location()
        address = DeliveryAddress.objects.create(user=user, address_details="Addr")
        product = ProductFactory(name="Falafel Sandwich", selling_price=Decimal("12.50"))
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(cart=cart, product=product, quantity=3)

        order = checkout_service(user=user, delivery_address_id=address.pk)

        snapshot = OrderItem.objects.get(sub_order__order=order)
        assert snapshot.product_name == "Falafel Sandwich"
        assert snapshot.unit_price == Decimal("12.50")
        assert snapshot.quantity == 3
        assert snapshot.total_price == Decimal("37.50")

    def test_checkout_raises_on_empty_cart(self):
        """Empty cart must raise CheckoutError."""
        user, _ = _make_user_with_location()
        address = DeliveryAddress.objects.create(user=user, address_details="Addr")

        with pytest.raises(CheckoutError, match="empty"):
            checkout_service(user=user, delivery_address_id=address.pk)

    def test_checkout_raises_below_minimum_order(self):
        """Cart total below location minimum must raise CheckoutError."""
        user, _ = _make_user_with_location(minimum_order_amount="100.00")
        _add_product_to_cart(user, price="20.00", quantity=1)
        address = DeliveryAddress.objects.create(user=user, address_details="Addr")

        with pytest.raises(CheckoutError, match="Minimum order"):
            checkout_service(user=user, delivery_address_id=address.pk)

    def test_checkout_raises_when_address_not_owned(self):
        """Address belonging to another user must raise CheckoutError."""
        user, _ = _make_user_with_location()
        other_user = UserFactory()
        _add_product_to_cart(user, price="50.00")
        other_address = DeliveryAddress.objects.create(user=other_user, address_details="Other")

        with pytest.raises(CheckoutError, match="not found"):
            checkout_service(user=user, delivery_address_id=other_address.pk)

    def test_checkout_raises_when_user_has_no_location(self):
        """User without a location set must raise CheckoutError."""
        user = UserFactory(location=None)
        _add_product_to_cart(user, price="50.00")
        address = DeliveryAddress.objects.create(user=user, address_details="Addr")

        with pytest.raises(CheckoutError, match="no location"):
            checkout_service(user=user, delivery_address_id=address.pk)

    def test_checkout_uses_variant_price_for_snapshot(self):
        """Variant price, not base product price, must be used in the snapshot."""
        user, _ = _make_user_with_location()
        address = DeliveryAddress.objects.create(user=user, address_details="Addr")
        product = ProductFactory(selling_price=Decimal("10.00"))
        variant = ProductVariantFactory(product=product, selling_price=Decimal("25.00"))
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(cart=cart, product=product, variant=variant, quantity=2)

        order = checkout_service(user=user, delivery_address_id=address.pk)

        snapshot = OrderItem.objects.get(sub_order__order=order)
        assert snapshot.unit_price == Decimal("25.00")
        assert snapshot.total_price == Decimal("50.00")
        assert order.subtotal == Decimal("50.00")


@pytest.mark.django_db
class TestCheckoutAPI:
    """Integration tests for POST /api/v1/checkout/."""

    def setup_method(self):
        self.client = APIClient()
        location = LocationFactory(delivery_fee="10.00", minimum_order_amount="0.00")
        self.user = UserFactory(location=location)
        self.client.force_authenticate(user=self.user)
        self.url = reverse("v1:checkout")

    def _setup_cart_and_address(self, price="30.00", quantity=1):
        product = ProductFactory(selling_price=Decimal(price))
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=product, quantity=quantity)
        address = DeliveryAddress.objects.create(user=self.user, address_details="My Home")
        return address

    def test_successful_checkout_returns_201_with_order(self):
        """Happy path via the API should return 201 with a full order payload."""
        address = self._setup_cart_and_address(price="50.00")
        response = self.client.post(self.url, {"delivery_address_id": address.pk})

        assert response.status_code == status.HTTP_201_CREATED
        assert "id" in response.data
        assert response.data["status"] == Order.Status.PENDING
        assert Decimal(response.data["delivery_fee"]) == Decimal("10.00")
        assert len(response.data["sub_orders"]) == 1

    def test_empty_cart_returns_400(self):
        address = DeliveryAddress.objects.create(user=self.user, address_details="Home")
        response = self.client.post(self.url, {"delivery_address_id": address.pk})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "empty" in response.data["detail"].lower()

    def test_wrong_address_returns_400(self):
        other_user = UserFactory()
        other_address = DeliveryAddress.objects.create(user=other_user, address_details="X")
        self._setup_cart_and_address()
        response = self.client.post(self.url, {"delivery_address_id": other_address.pk})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_returns_401(self):
        anon = APIClient()
        response = anon.post(self.url, {"delivery_address_id": 1})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_missing_address_id_returns_400(self):
        response = self.client.post(self.url, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
