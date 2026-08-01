"""
Views for the rides app.

Customer (authenticated):
  - RideRequestListCreateView  GET  /api/v1/ride-requests/  — List own requests
                               POST /api/v1/ride-requests/  — Submit new request
"""

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from rides.models import RideRequest
from rides.serializers import RideRequestCreateSerializer, RideRequestListSerializer


class RideRequestListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/ride-requests/  — List the customer's own ride requests
    POST /api/v1/ride-requests/  — Submit a new ride request

    Only returns the authenticated customer's own requests.
    customer is injected automatically — never sent by the client.
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return RideRequestCreateSerializer
        return RideRequestListSerializer

    def get_queryset(self):
        return RideRequest.objects.filter(customer=self.request.user).order_by(
            "-created_at"
        )

    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)
