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


# ---------------------------------------------------------------------------
# Step 6: Customer Order APIs tests
# ---------------------------------------------------------------------------

def _create_order_for_user(user, delivery_fee="10.00", minimum_order_amount="0.00"):
    """
    Helper: put one product in a cart, checkout, and return the Order.
    The user must have a location set.
    """
    product = ProductFactory(selling_price=Decimal("50.00"))
    cart, _ = Cart.objects.get_or_create(user=user)
    CartItem.objects.create(cart=cart, product=product, quantity=1)
    address = DeliveryAddress.objects.create(user=user, address_details="Test Addr")
    return checkout_service(user=user, delivery_address_id=address.pk)


@pytest.mark.django_db
class TestOrderListAPI:
    """GET /api/v1/orders/ — paginated order history."""

    def setup_method(self):
        self.client = APIClient()
        location = LocationFactory(delivery_fee="10.00", minimum_order_amount="0.00")
        self.user = UserFactory(location=location)
        self.client.force_authenticate(user=self.user)
        self.url = reverse("v1:order-list")

    def test_empty_history_returns_empty_list(self):
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_returns_only_customers_own_orders(self):
        """Orders from other users must never appear."""
        # Create order for self
        _create_order_for_user(self.user)

        # Create order for another user (different user + location)
        other_location = LocationFactory(delivery_fee="5.00", minimum_order_amount="0.00")
        other_user = UserFactory(location=other_location)
        _create_order_for_user(other_user)

        response = self.client.get(self.url)
        assert response.data["count"] == 1

    def test_multiple_orders_are_returned_newest_first(self):
        """Order history must be sorted newest-first."""
        _create_order_for_user(self.user)
        _create_order_for_user(self.user)

        response = self.client.get(self.url)
        assert response.data["count"] == 2
        ids = [o["id"] for o in response.data["results"]]
        assert ids == sorted(ids, reverse=True)

    def test_list_response_includes_summary_fields(self):
        """List items must include lightweight summary fields only (no sub_orders)."""
        _create_order_for_user(self.user)
        response = self.client.get(self.url)
        item = response.data["results"][0]
        assert "status" in item
        assert "total_amount" in item
        assert "business_count" in item
        # Full sub_orders detail must NOT be in the list response
        assert "sub_orders" not in item

    def test_unauthenticated_request_is_rejected(self):
        anon = APIClient()
        response = anon.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestOrderDetailAPI:
    """GET /api/v1/orders/{id}/ — full order detail."""

    def setup_method(self):
        self.client = APIClient()
        location = LocationFactory(delivery_fee="10.00", minimum_order_amount="0.00")
        self.user = UserFactory(location=location)
        self.client.force_authenticate(user=self.user)

    def test_returns_full_order_with_sub_orders(self):
        order = _create_order_for_user(self.user)
        url = reverse("v1:order-detail", args=[order.pk])
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == order.pk
        assert "sub_orders" in response.data
        assert len(response.data["sub_orders"]) == 1
        # Items must be nested inside sub_orders
        assert "items" in response.data["sub_orders"][0]

    def test_cannot_view_another_users_order(self):
        other_location = LocationFactory(delivery_fee="5.00", minimum_order_amount="0.00")
        other_user = UserFactory(location=other_location)
        other_order = _create_order_for_user(other_user)

        url = reverse("v1:order-detail", args=[other_order.pk])
        response = self.client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_nonexistent_order_returns_404(self):
        url = reverse("v1:order-detail", args=[99999])
        response = self.client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestOrderCancelAPI:
    """POST /api/v1/orders/{id}/cancel/ — cancellation rules."""

    def setup_method(self):
        self.client = APIClient()
        location = LocationFactory(delivery_fee="10.00", minimum_order_amount="0.00")
        self.user = UserFactory(location=location)
        self.client.force_authenticate(user=self.user)

    def _cancel_url(self, order):
        return reverse("v1:order-cancel", args=[order.pk])

    def test_cancel_pending_order_succeeds(self):
        """A pending order must be cancellable by the customer."""
        order = _create_order_for_user(self.user)
        assert order.status == Order.Status.PENDING

        response = self.client.post(self._cancel_url(order))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == Order.Status.CANCELLED

        order.refresh_from_db()
        assert order.status == Order.Status.CANCELLED

    def test_cancel_non_pending_order_returns_400(self):
        """Orders that are no longer pending must be rejected."""
        order = _create_order_for_user(self.user)
        order.status = Order.Status.ACCEPTED
        order.save()

        response = self.client.post(self._cancel_url(order))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "pending" in response.data["detail"].lower()

    def test_cancel_delivered_order_returns_400(self):
        order = _create_order_for_user(self.user)
        order.status = Order.Status.DELIVERED
        order.save()

        response = self.client.post(self._cancel_url(order))
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_cancel_another_users_order(self):
        other_location = LocationFactory(delivery_fee="5.00", minimum_order_amount="0.00")
        other_user = UserFactory(location=other_location)
        other_order = _create_order_for_user(other_user)

        response = self.client.post(self._cancel_url(other_order))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_cancel_returns_401(self):
        order = _create_order_for_user(self.user)
        anon = APIClient()
        response = anon.post(self._cancel_url(order))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# AnythingRequest API
# ---------------------------------------------------------------------------

import io
from django.core.files.uploadedfile import SimpleUploadedFile
from orders.models import AnythingRequest, AnythingRequestImage


def _make_fake_image(name="test.jpg"):
    """Return a minimal valid JPEG bytes object wrapped in a SimpleUploadedFile."""
    # Minimal JPEG header (SOI + EOI markers) — just enough to pass ImageField validation
    jpeg_bytes = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
        b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
        b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1e"
        b"\x1b\x1c \xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
        b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
        b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xf5\xd4\x00\x00\x00\xff\xd9"
    )
    return SimpleUploadedFile(name, jpeg_bytes, content_type="image/jpeg")


@pytest.mark.django_db
class TestAnythingRequestAPI:
    """
    Coverage for POST/GET /api/v1/anything-requests/ and the cancel action.
    """

    LIST_URL = "/api/v1/anything-requests/"

    @staticmethod
    def _detail_url(obj):
        return f"/api/v1/anything-requests/{obj.pk}/"

    @staticmethod
    def _cancel_url(obj):
        return f"/api/v1/anything-requests/{obj.pk}/cancel/"

    def setup_method(self):
        location = LocationFactory(minimum_order_amount=Decimal("20.00"))
        self.user = UserFactory(location=location)
        self.address = DeliveryAddress.objects.create(
            user=self.user, address_details="Village square"
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def test_create_text_only_request(self):
        """Customer can submit a text-only AnythingRequest."""
        payload = {
            "delivery_address_id": self.address.pk,
            "request_text": "I need a kilo of fresh dates.",
        }
        response = self.client.post(self.LIST_URL, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["request_text"] == payload["request_text"]
        assert data["status"] == AnythingRequest.Status.PENDING
        assert data["images"] == []
        assert AnythingRequest.objects.filter(customer=self.user).count() == 1

    def test_create_request_with_images(self, settings, tmp_path):
        """Customer can attach image files to an AnythingRequest."""
        settings.MEDIA_ROOT = str(tmp_path)

        img = _make_fake_image("item.jpg")
        payload = {
            "delivery_address_id": self.address.pk,
            "request_text": "Find me this item.",
            "images": [img],
        }
        response = self.client.post(self.LIST_URL, payload, format="multipart")

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert len(data["images"]) == 1
        assert AnythingRequestImage.objects.count() == 1

    def test_create_request_with_foreign_address_rejected(self):
        """Using another user's address must return 400."""
        other_user = UserFactory()
        other_address = DeliveryAddress.objects.create(
            user=other_user, address_details="Other place"
        )
        payload = {
            "delivery_address_id": other_address.pk,
            "request_text": "Sneak in with another's address.",
        }
        response = self.client.post(self.LIST_URL, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_request_missing_text_returns_400(self):
        """request_text is required."""
        payload = {"delivery_address_id": self.address.pk}
        response = self.client.post(self.LIST_URL, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_create_returns_401(self):
        payload = {
            "delivery_address_id": self.address.pk,
            "request_text": "Anything?",
        }
        anon = APIClient()
        response = anon.post(self.LIST_URL, payload, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def test_list_returns_only_own_requests(self):
        """Customers can only see their own requests."""
        AnythingRequest.objects.create(
            customer=self.user,
            delivery_address=self.address,
            request_text="My request",
        )
        other = UserFactory()
        other_addr = DeliveryAddress.objects.create(user=other, address_details="Elsewhere")
        AnythingRequest.objects.create(
            customer=other,
            delivery_address=other_addr,
            request_text="Not mine",
        )

        response = self.client.get(self.LIST_URL)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["results"]) == 1

    def test_list_newest_first(self):
        """Requests are ordered most recent first."""
        r1 = AnythingRequest.objects.create(
            customer=self.user,
            delivery_address=self.address,
            request_text="First",
        )
        r2 = AnythingRequest.objects.create(
            customer=self.user,
            delivery_address=self.address,
            request_text="Second",
        )
        response = self.client.get(self.LIST_URL)
        ids = [item["id"] for item in response.json()["results"]]
        assert ids == [r2.pk, r1.pk]

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------

    def test_retrieve_returns_full_detail_with_admin_note(self):
        """Detail endpoint exposes images and admin_note."""
        req = AnythingRequest.objects.create(
            customer=self.user,
            delivery_address=self.address,
            request_text="Need something special.",
            admin_note="We are looking into it.",
        )
        response = self.client.get(self._detail_url(req))
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["admin_note"] == "We are looking into it."
        assert "images" in data

    def test_cannot_retrieve_another_users_request(self):
        """Attempting to view another user's request returns 404."""
        other = UserFactory()
        other_addr = DeliveryAddress.objects.create(user=other, address_details="Elsewhere")
        other_req = AnythingRequest.objects.create(
            customer=other,
            delivery_address=other_addr,
            request_text="Not yours.",
        )
        response = self.client.get(self._detail_url(other_req))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def test_cancel_pending_request_soft_deletes(self):
        """Cancelling a pending request marks is_active=False."""
        req = AnythingRequest.objects.create(
            customer=self.user,
            delivery_address=self.address,
            request_text="Cancel me.",
        )
        response = self.client.post(self._cancel_url(req))
        assert response.status_code == status.HTTP_200_OK
        req.refresh_from_db()
        assert req.is_active is False

    def test_cancel_non_pending_request_returns_400(self):
        """Only pending requests can be cancelled."""
        req = AnythingRequest.objects.create(
            customer=self.user,
            delivery_address=self.address,
            request_text="Already quoted.",
            status=AnythingRequest.Status.QUOTED,
        )
        response = self.client.post(self._cancel_url(req))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "pending" in response.json()["detail"].lower()

    def test_cannot_cancel_another_users_request(self):
        """A customer cannot cancel someone else's request."""
        other = UserFactory()
        other_addr = DeliveryAddress.objects.create(user=other, address_details="Elsewhere")
        other_req = AnythingRequest.objects.create(
            customer=other,
            delivery_address=other_addr,
            request_text="Not yours.",
        )
        response = self.client.post(self._cancel_url(other_req))
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Step 9: Focused Verification Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSnapshotImmutability:
    """
    Verify that changing the catalog (price/name) after checkout does NOT
    alter existing OrderItem snapshots.
    """

    def test_price_change_does_not_affect_existing_snapshot(self):
        """Updating a product's selling_price must not change the snapshot's unit_price."""
        user, _ = _make_user_with_location()
        address = DeliveryAddress.objects.create(user=user, address_details="Home")
        product = ProductFactory(name="Kushari", selling_price=Decimal("15.00"))
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(cart=cart, product=product, quantity=2)

        order = checkout_service(user=user, delivery_address_id=address.pk)
        snapshot = OrderItem.objects.get(sub_order__order=order)

        # Change the price in the catalog
        product.selling_price = Decimal("99.99")
        product.save()

        snapshot.refresh_from_db()
        assert snapshot.unit_price == Decimal("15.00"), (
            "Snapshot unit_price must be frozen at checkout time."
        )
        assert snapshot.total_price == Decimal("30.00")

    def test_name_change_does_not_affect_existing_snapshot(self):
        """Renaming a product must not change the snapshot's product_name."""
        user, _ = _make_user_with_location()
        address = DeliveryAddress.objects.create(user=user, address_details="Home")
        product = ProductFactory(name="Original Name", selling_price=Decimal("10.00"))
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(cart=cart, product=product, quantity=1)

        order = checkout_service(user=user, delivery_address_id=address.pk)
        snapshot = OrderItem.objects.get(sub_order__order=order)

        product.name = "Completely Different Name"
        product.save()

        snapshot.refresh_from_db()
        assert snapshot.product_name == "Original Name"

    def test_variant_price_change_does_not_affect_snapshot(self):
        """Variant price changes must not bleed into existing snapshots."""
        user, _ = _make_user_with_location()
        address = DeliveryAddress.objects.create(user=user, address_details="Home")
        product = ProductFactory(selling_price=Decimal("10.00"))
        variant = ProductVariantFactory(product=product, selling_price=Decimal("20.00"))
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(cart=cart, product=product, variant=variant, quantity=3)

        order = checkout_service(user=user, delivery_address_id=address.pk)
        snapshot = OrderItem.objects.get(sub_order__order=order)

        variant.selling_price = Decimal("999.00")
        variant.save()

        snapshot.refresh_from_db()
        assert snapshot.unit_price == Decimal("20.00")
        assert snapshot.total_price == Decimal("60.00")


@pytest.mark.django_db
class TestCartMath:
    """
    Focused tests for cart totals — per-business subtotals and multi-variant scenarios.
    """

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(self.user)
        self.cart = Cart.objects.create(user=self.user)

    def test_per_business_subtotal_in_grouped_response(self):
        """Each business group in the cart response must carry the correct subtotal."""
        from businesses.tests.factories import BusinessFactory

        biz = BusinessFactory()
        p1 = ProductFactory(business=biz, selling_price=Decimal("10.00"))
        p2 = ProductFactory(business=biz, selling_price=Decimal("5.00"))
        CartItem.objects.create(cart=self.cart, product=p1, quantity=2)  # 20
        CartItem.objects.create(cart=self.cart, product=p2, quantity=4)  # 20

        response = self.client.get(reverse("v1:cart"))
        assert response.status_code == 200

        groups = response.data["groups"]
        biz_group = next(g for g in groups if g["business_id"] == biz.pk)
        assert Decimal(biz_group["subtotal"]) == Decimal("40.00")

    def test_grand_total_across_multiple_businesses(self):
        """Grand total must sum items from all businesses correctly."""
        p1 = ProductFactory(selling_price=Decimal("10.00"))
        p2 = ProductFactory(selling_price=Decimal("25.00"))  # different business
        CartItem.objects.create(cart=self.cart, product=p1, quantity=3)  # 30
        CartItem.objects.create(cart=self.cart, product=p2, quantity=2)  # 50

        response = self.client.get(reverse("v1:cart"))
        assert Decimal(response.data["grand_total"]) == Decimal("80.00")

    def test_item_count_reflects_line_items_not_quantity(self):
        """item_count must be the total number of line items, not total quantity."""
        p1 = ProductFactory()
        p2 = ProductFactory()
        CartItem.objects.create(cart=self.cart, product=p1, quantity=5)
        CartItem.objects.create(cart=self.cart, product=p2, quantity=10)

        response = self.client.get(reverse("v1:cart"))
        assert response.data["item_count"] == 2

    def test_mixed_base_and_variant_items_grand_total(self):
        """Cart with both base-product items and variant items must compute correctly."""
        product = ProductFactory(selling_price=Decimal("10.00"))
        variant = ProductVariantFactory(product=product, selling_price=Decimal("18.00"))
        other = ProductFactory(selling_price=Decimal("7.00"))

        CartItem.objects.create(cart=self.cart, product=product, variant=variant, quantity=2)  # 36
        CartItem.objects.create(cart=self.cart, product=other, quantity=3)  # 21

        response = self.client.get(reverse("v1:cart"))
        assert Decimal(response.data["grand_total"]) == Decimal("57.00")

    def test_note_is_preserved_when_quantity_is_accumulated(self):
        """When adding a duplicate item, the new note should overwrite the old one."""
        product = ProductFactory(selling_price=Decimal("10.00"))
        add_url = reverse("v1:cart-item-list")

        self.client.post(add_url, {"product_id": product.pk, "quantity": 1, "note": "no salt"})
        self.client.post(add_url, {"product_id": product.pk, "quantity": 2, "note": "extra hot"})

        item = CartItem.objects.get(product=product)
        assert item.quantity == 3
        assert item.note == "extra hot"


@pytest.mark.django_db
class TestDeliveryAddressCRUD:
    """
    Focused address CRUD coverage: delete, label choices, isolation,
    unauthenticated access, and GPS optional field handling.
    """

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(self.user)
        self.list_url = reverse("v1:address-list")

    def test_delete_address(self):
        """Customer can delete their own address."""
        address = DeliveryAddress.objects.create(
            user=self.user, address_details="To be deleted"
        )
        url = reverse("v1:address-detail", args=[address.pk])
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not DeliveryAddress.objects.filter(pk=address.pk).exists()

    def test_cannot_delete_another_users_address(self):
        """Attempting to delete another user's address must return 404."""
        other = UserFactory()
        other_address = DeliveryAddress.objects.create(
            user=other, address_details="Not yours"
        )
        url = reverse("v1:address-detail", args=[other_address.pk])
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_all_label_choices_are_accepted(self):
        """All three label choices (home, work, other) must be accepted by the API."""
        for label in ("home", "work", "other"):
            response = self.client.post(
                self.list_url,
                {"label": label, "address_details": f"Test {label}"},
            )
            assert response.status_code == status.HTTP_201_CREATED, f"Label '{label}' rejected"

    def test_invalid_label_is_rejected(self):
        """An unrecognised label must return 400."""
        response = self.client.post(
            self.list_url,
            {"label": "spaceship", "address_details": "Moon base"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_cannot_create_address(self):
        anon = APIClient()
        response = anon.post(
            self.list_url,
            {"label": "home", "address_details": "Anonymous home"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_address_with_gps_coordinates(self):
        """Addresses can be created with optional GPS coordinates."""
        payload = {
            "label": "work",
            "address_details": "Office building",
            "latitude": "30.044420",
            "longitude": "31.235712",
        }
        response = self.client.post(self.list_url, payload)
        assert response.status_code == status.HTTP_201_CREATED
        address = DeliveryAddress.objects.get(user=self.user, label="work")
        assert address.latitude is not None
        assert address.longitude is not None

    def test_address_without_gps_is_valid(self):
        """GPS coordinates are optional; omitting them must not fail."""
        response = self.client.post(
            self.list_url,
            {"label": "home", "address_details": "Village square"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        address = DeliveryAddress.objects.get(user=self.user)
        assert address.latitude is None
        assert address.longitude is None


@pytest.mark.django_db
class TestCheckoutAtomicity:
    """
    Verify that a failed checkout leaves no partial Order / SubOrder records.
    """

    def test_no_order_created_when_checkout_fails_min_order(self):
        """A CheckoutError must roll back the entire transaction."""
        user, _ = _make_user_with_location(minimum_order_amount="200.00")
        _add_product_to_cart(user, price="10.00", quantity=1)  # total=10, below minimum
        address = DeliveryAddress.objects.create(user=user, address_details="Addr")

        with pytest.raises(CheckoutError):
            checkout_service(user=user, delivery_address_id=address.pk)

        assert Order.objects.filter(customer=user).count() == 0
        assert SubOrder.objects.count() == 0
        assert OrderItem.objects.count() == 0

    def test_cart_is_not_cleared_when_checkout_fails(self):
        """Cart items must survive a failed checkout so the customer can retry."""
        user, _ = _make_user_with_location(minimum_order_amount="500.00")
        cart, _, _ = _add_product_to_cart(user, price="10.00", quantity=1)
        address = DeliveryAddress.objects.create(user=user, address_details="Addr")

        with pytest.raises(CheckoutError):
            checkout_service(user=user, delivery_address_id=address.pk)

        assert cart.items.count() == 1


@pytest.mark.django_db
class TestMultiBusinessGrouping:
    """
    Focused tests for multi-business grouping during checkout.
    Ensures each business gets exactly one SubOrder with the correct items and subtotals.
    """

    def test_each_business_gets_exactly_one_suborder(self):
        """Three products from two businesses must produce exactly two SubOrders."""
        from businesses.tests.factories import BusinessFactory

        user, _ = _make_user_with_location()
        address = DeliveryAddress.objects.create(user=user, address_details="Addr")

        biz_a = BusinessFactory()
        biz_b = BusinessFactory()
        pa1 = ProductFactory(business=biz_a, selling_price=Decimal("10.00"))
        pa2 = ProductFactory(business=biz_a, selling_price=Decimal("5.00"))
        pb1 = ProductFactory(business=biz_b, selling_price=Decimal("20.00"))

        cart = Cart.objects.create(user=user)
        CartItem.objects.create(cart=cart, product=pa1, quantity=1)
        CartItem.objects.create(cart=cart, product=pa2, quantity=2)
        CartItem.objects.create(cart=cart, product=pb1, quantity=1)

        order = checkout_service(user=user, delivery_address_id=address.pk)

        assert order.sub_orders.count() == 2

        so_a = order.sub_orders.get(business=biz_a)
        so_b = order.sub_orders.get(business=biz_b)

        assert so_a.items.count() == 2
        assert so_b.items.count() == 1
        assert so_a.subtotal == Decimal("20.00")   # 10*1 + 5*2
        assert so_b.subtotal == Decimal("20.00")   # 20*1
        assert order.subtotal == Decimal("40.00")

    def test_suborder_subtotals_sum_to_order_subtotal(self):
        """Sum of all SubOrder subtotals must exactly equal the parent Order subtotal."""
        user, _ = _make_user_with_location()
        address = DeliveryAddress.objects.create(user=user, address_details="Addr")

        cart = Cart.objects.create(user=user)
        for price in ("12.50", "7.00", "30.00"):
            product = ProductFactory(selling_price=Decimal(price))
            CartItem.objects.create(cart=cart, product=product, quantity=2)

        order = checkout_service(user=user, delivery_address_id=address.pk)

        sub_total_sum = sum(so.subtotal for so in order.sub_orders.all())
        assert sub_total_sum == order.subtotal


