"""
Views for the locations app.

All endpoints are public (no authentication required) — anyone browsing
the app should be able to see available locations to select.
"""

from rest_framework import generics
from rest_framework.permissions import AllowAny

from locations.models import Governorate, Location
from locations.serializers import (
    GovernorateDetailSerializer,
    GovernorateSerializer,
    LocationSerializer,
)


class GovernorateListView(generics.ListAPIView):
    """
    GET /api/v1/locations/governorates/

    Returns all active governorates.
    """

    permission_classes = [AllowAny]
    serializer_class = GovernorateSerializer
    # SoftDeleteManager already filters is_active=True
    queryset = Governorate.objects.all()
    pagination_class = None  # Small list — no pagination needed


class GovernorateDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/locations/governorates/{id}/

    Returns a single governorate with its active locations nested.
    """

    permission_classes = [AllowAny]
    serializer_class = GovernorateDetailSerializer
    queryset = Governorate.objects.all()


class LocationListView(generics.ListAPIView):
    """
    GET /api/v1/locations/

    Returns all active locations.
    Supports filtering by ?governorate=<id> and ?type=city|village.
    """

    permission_classes = [AllowAny]
    serializer_class = LocationSerializer
    pagination_class = None  # Small list — no pagination needed
    filterset_fields = ["governorate", "type"]

    def get_queryset(self):
        return Location.objects.select_related("governorate").all()


class LocationDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/locations/{id}/

    Returns a single location's details (including delivery fee and minimum order).
    """

    permission_classes = [AllowAny]
    serializer_class = LocationSerializer

    def get_queryset(self):
        return Location.objects.select_related("governorate").all()
