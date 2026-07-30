from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Cart, CartItem, DeliveryAddress
from orders.serializers import (
    CartItemWriteSerializer,
    CartSerializer,
    CheckoutSerializer,
    DeliveryAddressSerializer,
    OrderSerializer,
)
from orders.services import CheckoutError, checkout as checkout_service


class DeliveryAddressViewSet(viewsets.ModelViewSet):
    """
    CRUD for customer delivery addresses.
    Customers can only manage their own addresses.
    """
    serializer_class = DeliveryAddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only return the logged-in user's active addresses
        return DeliveryAddress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Automatically assign the logged-in user as the owner
        serializer.save(user=self.request.user)


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------

class CartView(APIView):
    """
    GET /api/v1/cart/

    Returns the authenticated customer's cart, with items grouped by business
    and server-side line totals and grand total calculated.

    The cart is created lazily on first access (get_or_create).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)


class CartItemViewSet(viewsets.GenericViewSet):
    """
    /api/v1/cart/items/

    Endpoints:
      POST   /cart/items/         — Add a product to the cart (or update qty if already there)
      PATCH  /cart/items/{id}/    — Update quantity / note of an existing cart item
      DELETE /cart/items/{id}/    — Remove an item from the cart
      DELETE /cart/items/clear/   — Empty the entire cart
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CartItemWriteSerializer

    def get_queryset(self):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        return CartItem.objects.filter(cart=cart).select_related("product", "variant")

    # POST /cart/items/
    def create(self, request):
        """
        Add a product to the cart.

        - If the exact (product, variant) combination already exists in the cart,
          the quantity is incremented by the requested amount rather than creating
          a duplicate row. This keeps totals accurate without extra client logic.
        """
        serializer = CartItemWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart, _ = Cart.objects.get_or_create(user=request.user)

        product = serializer.validated_data["product"]
        variant = serializer.validated_data.get("variant")
        quantity = serializer.validated_data["quantity"]
        note = serializer.validated_data.get("note", "")

        existing = CartItem.objects.filter(cart=cart, product=product, variant=variant).first()

        if existing:
            existing.quantity += quantity
            if note:
                existing.note = note
            existing.save()
            cart_item = existing
            created = False
        else:
            cart_item = CartItem.objects.create(
                cart=cart,
                product=product,
                variant=variant,
                quantity=quantity,
                note=note,
            )
            created = True

        cart_serializer = CartSerializer(cart)
        http_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(cart_serializer.data, status=http_status)

    # PATCH /cart/items/{id}/
    def partial_update(self, request, pk=None):
        """
        Update the quantity or note of a cart item.

        Setting quantity to 0 is equivalent to DELETE.
        """
        cart_item = self.get_object()

        quantity = request.data.get("quantity")
        note = request.data.get("note")

        if quantity is not None:
            try:
                quantity = int(quantity)
            except (TypeError, ValueError):
                return Response(
                    {"quantity": "Must be a positive integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if quantity == 0:
                cart_item.delete()
                cart, _ = Cart.objects.get_or_create(user=request.user)
                return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)
            if quantity < 0:
                return Response(
                    {"quantity": "Must be ≥ 0."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            cart_item.quantity = quantity

        if note is not None:
            cart_item.note = note

        cart_item.save()
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return Response(CartSerializer(cart).data)

    # DELETE /cart/items/{id}/
    def destroy(self, request, pk=None):
        """Remove a single item from the cart."""
        cart_item = self.get_object()
        cart_item.delete()
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)

    # DELETE /cart/items/clear/
    @action(detail=False, methods=["delete"], url_path="clear")
    def clear(self, request):
        """Remove ALL items from the customer's cart."""
        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart.items.all().delete()
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------

class CheckoutView(APIView):
    """
    POST /api/v1/checkout/

    Convert the authenticated customer's cart into an Order.

    Request body
    ────────────
    {
        "delivery_address_id": <int>
    }

    Success response (201 Created)
    ──────────────────────────────
    Full OrderSerializer payload.

    Error responses
    ───────────────
    400 — cart empty, min-order not met, address not found, no location set.
    401 — unauthenticated.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        try:
            order = checkout_service(
                user=request.user,
                delivery_address_id=serializer.validated_data["delivery_address_id"],
            )
        except CheckoutError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)
