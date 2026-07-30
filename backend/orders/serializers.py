"""
Serializers for the orders app.

Includes:
- DeliveryAddressSerializer  — CRUD for saved addresses
- CartItemWriteSerializer     — Add / update a cart item (write)
- CartItemReadSerializer      — Read a single cart item (nested in cart response)
- CartBusinessGroupSerializer — Reads items grouped by business with subtotal
- CartSerializer              — Full cart response with per-business groups and grand total
"""

from decimal import Decimal

from rest_framework import serializers

from businesses.models import Product, ProductVariant
from orders.models import Cart, CartItem, DeliveryAddress


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
        if obj.variant_id:
            return obj.variant.selling_price
        return obj.product.selling_price

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
            item_serializer = CartItemReadSerializer(group["items"], many=True)
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
