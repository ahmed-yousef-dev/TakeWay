"""
Serializers for the promotions app (Banner & Offer) — public, read-only.

These are used by the Homepage and potentially future promotions-listing
endpoints. Kept separate from the admin-side serializers to maintain a
clean public/internal boundary (same philosophy as businesses/serializers.py).
"""

from rest_framework import serializers

from .models import Banner, Offer


class BannerSerializer(serializers.ModelSerializer):
    """Compact banner representation for the homepage carousel."""

    class Meta:
        model = Banner
        fields = [
            "id",
            "title",
            "subtitle",
            "tag",
            "image",
            "target_type",
            "target_id",
            "target_url",
            "sort_order",
        ]


class OfferSerializer(serializers.ModelSerializer):
    """Compact offer representation for homepage 'Today's Offers' section."""

    business_name = serializers.CharField(source="business.name", read_only=True)
    business_logo = serializers.ImageField(source="business.logo", read_only=True)

    class Meta:
        model = Offer
        fields = [
            "id",
            "title",
            "description",
            "business",
            "business_name",
            "business_logo",
            "discount_type",
            "discount_value",
        ]
