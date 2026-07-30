"""
Checkout service for TakeWay.

All business logic for converting a cart into an Order lives here.
Views call this service and handle HTTP concerns only.

Checkout flow
─────────────
1.  Validate the cart is non-empty.
2.  Resolve the customer's location from their user profile.
3.  Calculate the cart grand total (server-side, no client prices trusted).
4.  Validate the grand total meets the location's minimum_order_amount.
5.  Create the parent Order (status=pending, totals snapshotted).
6.  Split cart items by business → create one SubOrder per business.
7.  For each SubOrder, call OrderItem.create_snapshot() for each CartItem.
8.  Clear the cart.
9.  Return the created Order.

All steps run inside a single database transaction so any failure leaves
the database in a clean state.
"""

from decimal import Decimal

from django.db import transaction

from orders.models import Cart, CartItem, DeliveryAddress, Order, OrderItem, SubOrder


class CheckoutError(Exception):
    """
    Raised when checkout cannot proceed due to a business-rule violation.
    The message is safe to return directly in an API 400 response.
    """


def _calculate_cart_total(items) -> Decimal:
    """Return the grand total of the given CartItem queryset."""
    total = Decimal("0.00")
    for item in items:
        price = item.variant.selling_price if item.variant_id else item.product.selling_price
        total += price * item.quantity
    return total


def _group_items_by_business(items) -> dict:
    """Return a dict mapping business_id → list[CartItem]."""
    groups: dict[int, list] = {}
    for item in items:
        biz_id = item.product.business_id
        groups.setdefault(biz_id, []).append(item)
    return groups


@transaction.atomic
def checkout(user, delivery_address_id: int) -> Order:
    """
    Convert the user's active cart into a confirmed Order.

    Parameters
    ----------
    user : accounts.User
        The authenticated customer placing the order.
    delivery_address_id : int
        The PK of the DeliveryAddress to deliver to (must belong to user).

    Returns
    -------
    Order
        The newly created order (status=pending).

    Raises
    ------
    CheckoutError
        If the cart is empty, the address doesn't belong to the user,
        the user has no location set, or the total is below the minimum.
    """
    # ── 1. Load cart items ────────────────────────────────────────────────
    cart, _ = Cart.objects.get_or_create(user=user)
    items = list(
        CartItem.objects.filter(cart=cart).select_related(
            "product__business", "variant"
        )
    )

    if not items:
        raise CheckoutError("Your cart is empty.")

    # ── 2. Validate delivery address ownership ────────────────────────────
    try:
        delivery_address = DeliveryAddress.objects.get(pk=delivery_address_id, user=user)
    except DeliveryAddress.DoesNotExist:
        raise CheckoutError("Delivery address not found.")

    # ── 3. Resolve location & delivery fee ───────────────────────────────
    location = user.location
    if location is None:
        raise CheckoutError(
            "Your account has no location set. Please update your profile."
        )

    delivery_fee: Decimal = Decimal(str(location.delivery_fee))
    minimum_order: Decimal = Decimal(str(location.minimum_order_amount))

    # ── 4. Calculate totals ───────────────────────────────────────────────
    subtotal = _calculate_cart_total(items)

    if subtotal < minimum_order:
        raise CheckoutError(
            f"Minimum order for your location is {minimum_order} EGP "
            f"(your cart total is {subtotal} EGP)."
        )

    total_amount = subtotal + delivery_fee

    # ── 5. Create parent Order ────────────────────────────────────────────
    order = Order.objects.create(
        customer=user,
        delivery_address=delivery_address,
        status=Order.Status.PENDING,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        total_amount=total_amount,
    )

    # ── 6. Split items by business & create SubOrders + snapshots ─────────
    business_groups = _group_items_by_business(items)

    for business_id, group_items in business_groups.items():
        group_subtotal = _calculate_cart_total(group_items)
        business = group_items[0].product.business

        sub_order = SubOrder.objects.create(
            order=order,
            business=business,
            subtotal=group_subtotal,
        )

        snapshots = [
            OrderItem.create_snapshot(cart_item, sub_order)
            for cart_item in group_items
        ]
        OrderItem.objects.bulk_create(snapshots)

    # ── 7. Clear the cart ─────────────────────────────────────────────────
    cart.items.all().delete()

    return order
