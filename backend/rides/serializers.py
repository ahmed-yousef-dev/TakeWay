"""
Serializers for the rides app.
"""

from rest_framework import serializers

from rides.models import RideRequest


class RideRequestCreateSerializer(serializers.ModelSerializer):
    """
    Used when a customer submits a new RideRequest.
    customer is injected by the view — not provided by the client.
    """

    class Meta:
        model = RideRequest
        fields = [
            "id",
            "pickup_location",
            "pickup_lat",
            "pickup_lng",
            "destination",
            "destination_lat",
            "destination_lng",
            "vehicle_type",
            "notes",
        ]
        read_only_fields = ["id"]


class RideRequestListSerializer(serializers.ModelSerializer):
    """
    Used to list a customer's own ride requests.
    Includes human-readable display fields for the mobile app.
    """

    vehicle_type_display = serializers.CharField(
        source="get_vehicle_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = RideRequest
        fields = [
            "id",
            "pickup_location",
            "pickup_lat",
            "pickup_lng",
            "destination",
            "destination_lat",
            "destination_lng",
            "vehicle_type",
            "vehicle_type_display",
            "notes",
            "status",
            "status_display",
            "created_at",
        ]
