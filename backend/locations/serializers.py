"""
Serializers for the locations app.
"""

from rest_framework import serializers

from locations.models import Governorate, Location


class LocationSerializer(serializers.ModelSerializer):
    """Lightweight location serializer — used in lists and nested contexts."""

    governorate_name = serializers.CharField(source="governorate.name", read_only=True)

    class Meta:
        model = Location
        fields = [
            "id",
            "name",
            "type",
            "governorate",
            "governorate_name",
            "delivery_fee",
            "minimum_order_amount",
        ]


class GovernorateSerializer(serializers.ModelSerializer):
    """Governorate list serializer (without nested locations)."""

    class Meta:
        model = Governorate
        fields = ["id", "name"]


class GovernorateDetailSerializer(serializers.ModelSerializer):
    """Governorate detail with nested list of its active locations."""

    locations = serializers.SerializerMethodField()

    class Meta:
        model = Governorate
        fields = ["id", "name", "locations"]

    def get_locations(self, obj):
        # Only return active locations (SoftDeleteManager filters is_active=True)
        locations = obj.locations.all()
        return LocationSerializer(locations, many=True).data
