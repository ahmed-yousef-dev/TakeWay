"""
Serializers for the businesses app.

Two sets of serializers exist:
  1. Public serializers — used by customers browsing the app.
     NEVER expose cost_price.
  2. Owner serializers — used by business owners managing their products.
     Include cost_price and allow writes.
"""

from rest_framework import serializers

from businesses.models import (
    Business,
    BusinessCategory,
    Product,
    ProductCategory,
    ProductVariant,
    WorkingHour,
)


# ── Public (customer-facing) serializers ──────────────────────────────────────


class BusinessCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessCategory
        fields = ["id", "name", "icon", "sort_order"]


class WorkingHourSerializer(serializers.ModelSerializer):
    day_name = serializers.CharField(source="get_day_of_week_display", read_only=True)

    class Meta:
        model = WorkingHour
        fields = ["day_of_week", "day_name", "opening_time", "closing_time", "is_closed"]


class ProductVariantPublicSerializer(serializers.ModelSerializer):
    """Variant data for customers — selling_price only, no cost_price."""

    discounted_price = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = ["id", "name", "selling_price", "discounted_price", "is_available"]

    def get_discounted_price(self, obj):
        offer = obj.product.get_best_active_offer()
        if offer:
            return offer.calculate_discounted_price(obj.selling_price)
        return None


class ProductListSerializer(serializers.ModelSerializer):
    """
    Lightweight product serializer for list views.
    Excludes variants (too much data) — detail endpoint includes them.
    """

    discounted_price = serializers.SerializerMethodField()
    active_offer_title = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "image",
            "selling_price",
            "discounted_price",
            "active_offer_title",
            "is_available",
            "has_variants",
            "product_category",
        ]

    def get_discounted_price(self, obj):
        offer = obj.get_best_active_offer()
        if offer:
            return offer.calculate_discounted_price(obj.selling_price)
        return None

    def get_active_offer_title(self, obj):
        offer = obj.get_best_active_offer()
        return offer.title if offer else None


class ProductDetailSerializer(serializers.ModelSerializer):
    """Full product data including all available variants."""

    variants = ProductVariantPublicSerializer(many=True, read_only=True)
    discounted_price = serializers.SerializerMethodField()
    active_offer_title = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "image",
            "selling_price",
            "discounted_price",
            "active_offer_title",
            "is_available",
            "variants",
            "product_category",
        ]

    def get_discounted_price(self, obj):
        offer = obj.get_best_active_offer()
        if offer:
            return offer.calculate_discounted_price(obj.selling_price)
        return None

    def get_active_offer_title(self, obj):
        offer = obj.get_best_active_offer()
        return offer.title if offer else None


class ProductCategoryWithProductsSerializer(serializers.ModelSerializer):
    """Product category with its products nested — used in business product listing."""

    products = serializers.SerializerMethodField()

    class Meta:
        model = ProductCategory
        fields = ["id", "name", "sort_order", "products"]

    def get_products(self, obj):
        # Only return active, available products within this category
        # Using .all() preserves the Prefetch done in the view, avoiding N+1
        products = [p for p in obj.products.all() if p.is_active]
        return ProductListSerializer(products, many=True, context=self.context).data


class BusinessListSerializer(serializers.ModelSerializer):
    """
    Compact business card for list views (category browser, search results).
    Does NOT include working hours or product data.
    """

    category_name = serializers.CharField(source="category.name", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = Business
        fields = [
            "id",
            "name",
            "category",
            "category_name",
            "location",
            "location_name",
            "logo",
            "cover_image",
            "avg_rating",
            "review_count",
            "is_featured",
            "typical_delivery_time",
        ]


class BusinessDetailSerializer(serializers.ModelSerializer):
    """
    Full business profile including working hours.
    Used by the business detail screen.
    """

    category_name = serializers.CharField(source="category.name", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)
    working_hours = WorkingHourSerializer(many=True, read_only=True)

    class Meta:
        model = Business
        fields = [
            "id",
            "name",
            "description",
            "category",
            "category_name",
            "location",
            "location_name",
            "logo",
            "cover_image",
            "phone",
            "address",
            "avg_rating",
            "review_count",
            "is_featured",
            "typical_delivery_time",
            "working_hours",
        ]


# ── Owner (business-owner-facing) serializers ─────────────────────────────────


class ProductVariantOwnerSerializer(serializers.ModelSerializer):
    """Full variant data for business owners — includes cost_price."""

    class Meta:
        model = ProductVariant
        fields = ["id", "name", "cost_price", "selling_price", "is_available"]


class ProductOwnerSerializer(serializers.ModelSerializer):
    """
    Full product data for business owners — includes cost_price.
    Used for both reading and writing product data.
    """

    variants = ProductVariantOwnerSerializer(many=True, read_only=True)
    business = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "business",
            "product_category",
            "image",
            "cost_price",
            "selling_price",
            "is_available",
            "is_active",
            "variants",
        ]
        read_only_fields = ["id", "business"]

    def validate_product_category(self, value):
        """Ensure the product category belongs to the owner's business."""
        if value is None:
            return value
        request = self.context.get("request")
        if request and hasattr(request.user, "owned_business"):
            if value.business_id != request.user.owned_business.id:
                raise serializers.ValidationError(
                    "This product category does not belong to your business."
                )
        return value

    def validate_selling_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Selling price must be greater than zero.")
        return value

    def validate_cost_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Cost price cannot be negative.")
        return value


class ProductCategoryOwnerSerializer(serializers.ModelSerializer):
    """Product category CRUD for business owners."""

    class Meta:
        model = ProductCategory
        fields = ["id", "name", "sort_order", "is_active"]
        read_only_fields = ["id"]
