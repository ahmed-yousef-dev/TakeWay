from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Cart, CartItem, DeliveryAddress, Order, AnythingRequest
from orders.serializers import (
    AnythingRequestListSerializer,
    AnythingRequestSerializer,
    AnythingRequestTextWriteSerializer,
    AnythingRequestImageWriteSerializer,
    CartItemWriteSerializer,
    CartSerializer,
    CheckoutSerializer,
    DeliveryAddressSerializer,
    OrderListSerializer,
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
        serializer = CartSerializer(cart, context={"request": request})
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

        cart_serializer = CartSerializer(cart, context={"request": request})
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
                # Get cart and ensure everything is prefetched for fast discount calculations
                cart = Cart.objects.prefetch_related(
                    "items__product", 
                    "items__variant", 
                    "items__product__business",
                    "items__product__offers",
                    "items__product__business__offers",
                    "items__product__business__offers__products",
                ).get(user=request.user)
                return Response(CartSerializer(cart, context={"request": request}).data, status=status.HTTP_200_OK)
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
        return Response(CartSerializer(cart, context={"request": request}).data)

    # DELETE /cart/items/{id}/
    def destroy(self, request, pk=None):
        """Remove a single item from the cart."""
        cart_item = self.get_object()
        cart_item.delete()
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return Response(CartSerializer(cart, context={"request": request}).data, status=status.HTTP_200_OK)

    # DELETE /cart/items/clear/
    @action(detail=False, methods=["delete"], url_path="clear")
    def clear(self, request):
        """Remove ALL items from the customer's cart."""
        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart.items.all().delete()
        return Response(CartSerializer(cart, context={"request": request}).data, status=status.HTTP_200_OK)


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

        return Response(OrderSerializer(order, context={"request": request}).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Customer Order History & Detail
# ---------------------------------------------------------------------------

class OrderViewSet(viewsets.GenericViewSet):
    """
    /api/v1/orders/

    Read-only order history and detail for the authenticated customer.
    The only mutation allowed is cancellation (status=pending only).

    Endpoints:
      GET    /orders/         — Paginated list of the customer's orders (newest first)
      GET    /orders/{id}/    — Full order detail with all sub-orders and item snapshots
      POST   /orders/{id}/cancel/  — Cancel a pending order
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Customers can only see their own, non-deleted orders.
        Uses select_related / prefetch_related to minimise query count.
        """
        return (
            Order.objects.filter(customer=self.request.user, is_active=True)
            .select_related("delivery_address")
            .prefetch_related("sub_orders__items", "sub_orders__business")
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        """Use the lightweight list serializer for list, full detail for retrieve."""
        if self.action == "list":
            return OrderListSerializer
        return OrderSerializer

    # GET /orders/
    def list(self, request):
        """Paginated order history, most recent first."""
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    # GET /orders/{id}/
    def retrieve(self, request, pk=None):
        """Full order detail including all sub-orders and item snapshots."""
        order = self.get_object()
        return Response(self.get_serializer(order).data)

    # POST /orders/{id}/cancel/
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """
        Cancel a pending order.

        Only orders in status=pending may be cancelled by the customer.
        Any other status returns 400 with a clear error message.
        """
        order = self.get_object()

        if order.status != Order.Status.PENDING:
            return Response(
                {
                    "detail": (
                        "Only pending orders can be cancelled. "
                        f"This order is currently '{order.get_status_display()}'."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status"])
        return Response(OrderSerializer(order, context={"request": request}).data)


# ---------------------------------------------------------------------------
# AnythingRequest
# ---------------------------------------------------------------------------

class AnythingRequestViewSet(viewsets.GenericViewSet):
    """
    /api/v1/anything-requests/

    Endpoints:
      POST   /anything-requests/         — Submit a new request (text + optional images)
      GET    /anything-requests/         — List all requests by the authenticated customer
      GET    /anything-requests/{id}/    — Full request detail (with images and admin note)
      POST   /anything-requests/{id}/cancel/  — Cancel a pending request

    Image upload requires ``multipart/form-data``.
    All status/admin fields are read-only from the customer perspective.
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return only the authenticated customer's active requests."""
        return (
            AnythingRequest.objects.filter(
                customer=self.request.user, is_active=True
            )
            .select_related("delivery_address")
            .prefetch_related("images")
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "text":
            return AnythingRequestTextWriteSerializer
        if self.action == "image":
            return AnythingRequestImageWriteSerializer
        if self.action == "list":
            return AnythingRequestListSerializer
        return AnythingRequestSerializer

    @action(detail=False, methods=["post"], url_path="text")
    def text(self, request):
        """
        Submit a new text-based AnythingRequest.
        """
        serializer = AnythingRequestTextWriteSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        anything_request = serializer.save(customer=request.user)
        return Response(
            AnythingRequestSerializer(anything_request, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="image")
    def image(self, request):
        """
        Submit a new image-based AnythingRequest.
        """
        serializer = AnythingRequestImageWriteSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        anything_request = serializer.save(customer=request.user)
        return Response(
            AnythingRequestSerializer(anything_request, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    # GET /anything-requests/
    def list(self, request):
        """Paginated list of the customer's requests (most recent first)."""
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = AnythingRequestListSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        serializer = AnythingRequestListSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)

    # GET /anything-requests/{id}/
    def retrieve(self, request, pk=None):
        """Full request detail including images and admin note."""
        instance = self.get_object()
        return Response(
            AnythingRequestSerializer(instance, context={"request": request}).data
        )

    # POST /anything-requests/{id}/cancel/
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """
        Cancel an AnythingRequest.

        Only requests in ``pending`` status can be cancelled by the customer.
        """
        instance = self.get_object()

        if instance.status != AnythingRequest.Status.PENDING:
            return Response(
                {
                    "detail": (
                        "Only pending requests can be cancelled. "
                        f"This request is currently '{instance.get_status_display()}'."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance.status = AnythingRequest.Status.CANCELLED
        instance.save(update_fields=["status"])
        return Response(
            AnythingRequestSerializer(instance, context={"request": request}).data
        )
