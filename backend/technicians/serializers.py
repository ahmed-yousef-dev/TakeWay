"""
Serializers for the technicians app.

Two sets:
  1. Public — customer-facing: NEVER expose technician phone number.
  2. Customer request — authenticated customer submitting a TechnicianRequest.
"""

from rest_framework import serializers

from technicians.models import Technician, TechnicianCategory, TechnicianRequest


# ── Public (customer-facing) serializers ──────────────────────────────────────


class TechnicianCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TechnicianCategory
        fields = ["id", "name", "icon", "sort_order"]


class TechnicianListSerializer(serializers.ModelSerializer):
    """
    Compact technician card for list views.
    Phone is intentionally excluded — never shown to customers.
    """

    category_name = serializers.CharField(source="category.name", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = Technician
        fields = [
            "id",
            "name",
            "category",
            "category_name",
            "location",
            "location_name",
            "photo",
            "bio",
            "years_experience",
            "avg_rating",
            "review_count",
            "is_featured",
        ]


class TechnicianDetailSerializer(serializers.ModelSerializer):
    """
    Full technician profile.
    Phone is intentionally excluded — never shown to customers.
    """

    category_name = serializers.CharField(source="category.name", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = Technician
        fields = [
            "id",
            "name",
            "category",
            "category_name",
            "location",
            "location_name",
            "photo",
            "bio",
            "years_experience",
            "avg_rating",
            "review_count",
            "is_featured",
        ]


# ── Customer Request serializers ──────────────────────────────────────────────


class TechnicianRequestCreateSerializer(serializers.ModelSerializer):
    """
    Used when a customer submits a new TechnicianRequest.
    customer is injected by the view — not provided by the client.
    """

    class Meta:
        model = TechnicianRequest
        fields = ["id", "technician", "address", "notes"]
        read_only_fields = ["id"]

    def validate_address(self, address):
        """Ensure the delivery address belongs to the requesting customer."""
        request = self.context.get("request")
        if request and address.user_id != request.user.id:
            raise serializers.ValidationError(
                "This address does not belong to you."
            )
        return address


class TechnicianRequestListSerializer(serializers.ModelSerializer):
    """
    Used to list a customer's own technician requests.
    Includes technician name and status display for the mobile app.
    """

    technician_name = serializers.CharField(source="technician.name", read_only=True)
    technician_photo = serializers.ImageField(source="technician.photo", read_only=True)
    category_name = serializers.CharField(source="technician.category.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = TechnicianRequest
        fields = [
            "id",
            "technician",
            "technician_name",
            "technician_photo",
            "category_name",
            "address",
            "notes",
            "status",
            "status_display",
            "created_at",
        ]
