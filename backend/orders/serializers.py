"""
Serializers for the orders app.

Includes:
- DeliveryAddressSerializer  — CRUD for saved addresses
- CartItemWriteSerializer     — Add / update a cart item (write)
- CartItemReadSerializer      — Read a single cart item (nested in cart response)
- CartBusinessGroupSerializer — Reads items grouped by business with subtotal
- CartSerializer              — Full cart response with per-business groups and grand total
- CheckoutSerializer          — Input validation for the checkout endpoint
- OrderItemSerializer         — Read representation of a snapshotted order item
- SubOrderSerializer          — Read representation of a sub-order (per business)
- OrderSerializer             — Full order response (detail)
- OrderListSerializer         — Lightweight order summary for the list endpoint
"""

from decimal import Decimal

from rest_framework import serializers

from businesses.models import Product, ProductVariant
from orders.models import (
    AnythingRequest,
    AnythingRequestImage,
    Cart,
    CartItem,
    DeliveryAddress,
    Order,
    OrderItem,
    SubOrder,
)


# ---------------------------------------------------------------------------
# DeliveryAddress
# ---------------------------------------------------------------------------

class DeliveryAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryAddress
        fields = [
            "id",
            "label",
            "address_details",
            "latitude",
            "longitude",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


# ---------------------------------------------------------------------------
# Cart — Write
# ---------------------------------------------------------------------------

class CartItemWriteSerializer(serializers.ModelSerializer):
    """
    Used when a customer adds or updates an item in their cart.

    Validation rules:
      - product must be active and available.
      - If the product has variants, a variant_id is required.
      - If the product has no variants, variant_id must NOT be provided.
      - The chosen variant (if any) must belong to the chosen product and be available.
      - quantity must be ≥ 1 (enforced by the model validator too, but we check here for
        a clean 400 error message).
    """

    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True, is_available=True),
        source="product",
    )
    variant_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.filter(is_available=True),
        source="variant",
        required=False,
        allow_null=True,
    )

    class Meta:
        model = CartItem
        fields = ["product_id", "variant_id", "quantity", "note"]

    def validate(self, attrs):
        product: Product = attrs["product"]
        variant: ProductVariant | None = attrs.get("variant")

        has_available_variants = product.variants.filter(is_available=True).exists()

        if has_available_variants and variant is None:
            raise serializers.ValidationError(
                {"variant_id": "This product requires a variant selection."}
            )

        if not has_available_variants and variant is not None:
            raise serializers.ValidationError(
                {"variant_id": "This product does not have variants."}
            )

        if variant is not None and variant.product_id != product.pk:
            raise serializers.ValidationError(
                {"variant_id": "The selected variant does not belong to this product."}
            )

        return attrs


# ---------------------------------------------------------------------------
# Cart — Read
# ---------------------------------------------------------------------------

class CartItemReadSerializer(serializers.ModelSerializer):
    """Flat read representation of a cart item, enriched with price info."""

    product_id = serializers.IntegerField(source="product.id")
    product_name = serializers.CharField(source="product.name")
    product_image = serializers.ImageField(source="product.image", read_only=True)
    variant_id = serializers.SerializerMethodField()
    variant_name = serializers.SerializerMethodField()
    unit_price = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product_id",
            "product_name",
            "product_image",
            "variant_id",
            "variant_name",
            "unit_price",
            "quantity",
            "line_total",
            "note",
        ]

    def get_variant_id(self, obj: CartItem):
        return obj.variant_id if obj.variant_id else None

    def get_variant_name(self, obj: CartItem):
        return obj.variant.name if obj.variant_id else None

    def get_unit_price(self, obj: CartItem) -> Decimal:
        offer = obj.product.get_best_active_offer()
        if obj.variant_id:
            base_price = obj.variant.selling_price
        else:
            base_price = obj.product.selling_price
        
        if offer:
            return offer.calculate_discounted_price(base_price)
        return base_price

    def get_line_total(self, obj: CartItem) -> Decimal:
        return self.get_unit_price(obj) * obj.quantity


class CartBusinessGroupSerializer(serializers.Serializer):
    """
    Read-only grouping of cart items belonging to the same business.
    Provides a per-business subtotal for UI display.
    """

    business_id = serializers.IntegerField()
    business_name = serializers.CharField()
    items = CartItemReadSerializer(many=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)


class CartSerializer(serializers.ModelSerializer):
    """
    Full cart response.

    Items are grouped by business and a grand total is included.
    The cart is created lazily (get_or_create) so this serializer
    is always read-only — mutations go through CartItemWriteSerializer.
    """

    groups = serializers.SerializerMethodField()
    grand_total = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ["id", "groups", "grand_total", "item_count"]

    def get_groups(self, cart: Cart):
        # Prefetch-friendly grouping — items already ordered by created_at
        items = list(
            cart.items.select_related(
                "product__business", "variant"
            ).prefetch_related(
                "product__offers", "product__business__offers", "product__business__offers__products"
            ).order_by("product__business_id", "created_at")
        )

        # Group items by business
        business_map: dict = {}
        for item in items:
            biz = item.product.business
            if biz.pk not in business_map:
                business_map[biz.pk] = {"business_id": biz.pk, "business_name": biz.name, "items": []}
            business_map[biz.pk]["items"].append(item)

        # Build group dicts with subtotals
        groups = []
        for group in business_map.values():
            item_serializer = CartItemReadSerializer(group["items"], many=True, context=self.context)
            subtotal = sum(
                (item["line_total"] for item in item_serializer.data),
                Decimal("0.00"),
            )
            groups.append(
                {
                    "business_id": group["business_id"],
                    "business_name": group["business_name"],
                    "items": item_serializer.data,
                    "subtotal": subtotal,
                }
            )
        return groups

    def get_grand_total(self, cart: Cart) -> Decimal:
        items = cart.items.select_related("variant", "product")
        total = Decimal("0.00")
        for item in items:
            price = item.variant.selling_price if item.variant_id else item.product.selling_price
            total += price * item.quantity
        return total

    def get_item_count(self, cart: Cart) -> int:
        return cart.items.count()


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------

class CheckoutSerializer(serializers.Serializer):
    """
    Input serializer for POST /api/v1/checkout/.

    Validates that the delivery_address_id references one of the
    authenticated user's saved addresses before the service layer runs.
    """

    delivery_address_id = serializers.IntegerField(
        help_text="PK of the DeliveryAddress to deliver to."
    )

    def validate_delivery_address_id(self, value):
        user = self.context["request"].user
        if not DeliveryAddress.objects.filter(pk=value, user=user).exists():
            raise serializers.ValidationError(
                "Delivery address not found or does not belong to you."
            )
        return value


# ---------------------------------------------------------------------------
# Order — Read
# ---------------------------------------------------------------------------

class OrderItemSerializer(serializers.ModelSerializer):
    """Read-only snapshot of a purchased item."""
    
    product_image = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product_name",
            "product_image",
            "variant_name",
            "unit_price",
            "quantity",
            "total_price",
            "note",
        ]

    def get_product_image(self, obj):
        if obj.product and obj.product.image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.product.image.url)
            return obj.product.image.url
        return None


class SubOrderSerializer(serializers.ModelSerializer):
    """Read-only sub-order grouped by business."""

    business_name = serializers.CharField(source="business.name")
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = SubOrder
        fields = ["id", "business_id", "business_name", "subtotal", "items"]


class OrderSerializer(serializers.ModelSerializer):
    """Full read-only order response returned after successful checkout."""

    sub_orders = SubOrderSerializer(many=True, read_only=True)
    delivery_address = DeliveryAddressSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "status",
            "status_display",
            "confirmed_eta",
            "delivery_address",
            "subtotal",
            "delivery_fee",
            "total_amount",
            "sub_orders",
            "created_at",
        ]
        read_only_fields = fields


class OrderListSerializer(serializers.ModelSerializer):
    """
    Lightweight order summary for the history list endpoint.

    Intentionally omits sub_orders / items to keep list responses fast.
    Clients can fetch the full detail with OrderSerializer when needed.
    """

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    address_label = serializers.CharField(
        source="delivery_address.label", read_only=True
    )
    address_details = serializers.CharField(
        source="delivery_address.address_details", read_only=True
    )
    business_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "status",
            "status_display",
            "confirmed_eta",
            "address_label",
            "address_details",
            "subtotal",
            "delivery_fee",
            "total_amount",
            "business_count",
            "created_at",
        ]
        read_only_fields = fields

    def get_business_count(self, obj: Order) -> int:
        return obj.sub_orders.count()


# ---------------------------------------------------------------------------
# AnythingRequest
# ---------------------------------------------------------------------------

class AnythingRequestImageSerializer(serializers.ModelSerializer):
    """Read-only representation of a single attached image."""

    class Meta:
        model = AnythingRequestImage
        fields = ["id", "image"]


class BaseAnythingRequestWriteSerializer(serializers.ModelSerializer):
    """
    Base write serializer for AnythingRequest, containing shared fields and creation logic.
    """
    delivery_address_id = serializers.PrimaryKeyRelatedField(
        queryset=DeliveryAddress.objects.all(),
        source="delivery_address",
        help_text="PK of one of your saved delivery addresses.",
    )
    images = serializers.ListField(
        child=serializers.ImageField(max_length=None, allow_empty_file=False),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text="Optional image uploads (multipart/form-data).",
    )

    def validate_delivery_address_id(self, value):
        """Ensure the address belongs to the requesting customer."""
        user = self.context["request"].user
        if value.user_id != user.pk:
            raise serializers.ValidationError(
                "Delivery address not found or does not belong to you."
            )
        return value

    def create(self, validated_data):
        images_data = validated_data.pop("images", [])
        anything_request = AnythingRequest.objects.create(**validated_data)
        for image_file in images_data:
            AnythingRequestImage.objects.create(
                anything_request=anything_request, image=image_file
            )
        return anything_request


class AnythingRequestTextWriteSerializer(BaseAnythingRequestWriteSerializer):
    """
    Write serializer for text-based AnythingRequests.
    Requires text, images are optional.
    """
    request_text = serializers.CharField(required=True, allow_blank=False)

    class Meta:
        model = AnythingRequest
        fields = ["delivery_address_id", "request_text", "images"]


class AnythingRequestImageWriteSerializer(BaseAnythingRequestWriteSerializer):
    """
    Write serializer for image-based AnythingRequests.
    Requires at least one image, text is optional.
    """
    
    class Meta:
        model = AnythingRequest
        fields = ["delivery_address_id", "request_text", "images"]

    def validate(self, attrs):
        images = attrs.get("images", [])
        if not images:
            raise serializers.ValidationError({"images": "At least one image is required."})
        return attrs


class AnythingRequestSerializer(serializers.ModelSerializer):
    """
    Read serializer for a customer's AnythingRequest.

    Returns full request details including attached images and the
    human-readable status label. ``admin_note`` is intentionally
    exposed so customers can read any quote/comment the admin adds.
    """

    images = AnythingRequestImageSerializer(many=True, read_only=True)
    delivery_address = DeliveryAddressSerializer(read_only=True)
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )

    class Meta:
        model = AnythingRequest
        fields = [
            "id",
            "status",
            "status_display",
            "request_text",
            "delivery_address",
            "admin_note",
            "images",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AnythingRequestListSerializer(serializers.ModelSerializer):
    """
    Lightweight list serializer — excludes images for fast listing.
    Clients fetch the full detail view for images.
    """

    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    address_label = serializers.CharField(
        source="delivery_address.label", read_only=True
    )
    image_count = serializers.SerializerMethodField()

    class Meta:
        model = AnythingRequest
        fields = [
            "id",
            "status",
            "status_display",
            "request_text",
            "address_label",
            "image_count",
            "created_at",
        ]
        read_only_fields = fields

    def get_image_count(self, obj: AnythingRequest) -> int:
        return obj.images.count()
