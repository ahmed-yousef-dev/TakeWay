"""
Views for the rides app.

Customer (authenticated):
  - RideRequestListCreateView  GET  /api/v1/ride-requests/  — List own requests
                               POST /api/v1/ride-requests/  — Submit new request
"""

from rest_framework import generics, viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from rides.models import RideRequest
from rides.serializers import RideRequestCreateSerializer, RideRequestListSerializer


class RideRequestViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET  /api/v1/ride-requests/  — List the customer's own ride requests
    POST /api/v1/ride-requests/  — Submit a new ride request
    POST /api/v1/ride-requests/{id}/cancel/ — Cancel a pending ride request

    Only returns the authenticated customer's own requests.
    customer is injected automatically — never sent by the client.
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return RideRequestCreateSerializer
        return RideRequestListSerializer

    def get_queryset(self):
        return RideRequest.objects.filter(customer=self.request.user).order_by(
            "-created_at"
        )

    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        ride_request = self.get_object()

        if ride_request.status != RideRequest.Status.PENDING:
            return Response(
                {"detail": "Only pending ride requests can be cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ride_request.status = RideRequest.Status.CANCELLED
        ride_request.save(update_fields=["status"])

        return Response({"detail": "Ride request cancelled successfully."})
