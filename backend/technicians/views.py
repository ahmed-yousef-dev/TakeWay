"""
Views for the technicians app.

Public:
  - TechnicianCategoryListView   GET /api/v1/technicians/categories/
  - TechnicianListView           GET /api/v1/technicians/
  - TechnicianDetailView         GET /api/v1/technicians/{id}/

Customer (authenticated):
  - TechnicianRequestCreateView  POST /api/v1/technician-requests/
  - TechnicianRequestListView    GET  /api/v1/technician-requests/
"""

from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated

from technicians.models import Technician, TechnicianCategory, TechnicianRequest
from technicians.serializers import (
    TechnicianCategorySerializer,
    TechnicianDetailSerializer,
    TechnicianListSerializer,
    TechnicianRequestCreateSerializer,
    TechnicianRequestListSerializer,
)


# ── Public views ──────────────────────────────────────────────────────────────


class TechnicianCategoryListView(generics.ListAPIView):
    """
    GET /api/v1/technicians/categories/

    Returns all active technician categories, ordered by sort_order.
    """

    permission_classes = [AllowAny]
    serializer_class = TechnicianCategorySerializer
    queryset = TechnicianCategory.objects.all()
    pagination_class = None  # Small, stable list


class TechnicianListView(generics.ListAPIView):
    """
    GET /api/v1/technicians/

    Returns all active technicians.
    Supports: ?location=<id>, ?category=<id>, ?search=<name>, ?is_featured=true
    """

    permission_classes = [AllowAny]
    serializer_class = TechnicianListSerializer
    search_fields = ["name", "bio"]
    filterset_fields = ["location", "category", "is_featured"]

    def get_queryset(self):
        return (
            Technician.objects.select_related("category", "location")
            .all()
        )


class TechnicianDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/technicians/{id}/

    Returns full technician profile. Phone is never included.
    """

    permission_classes = [AllowAny]
    serializer_class = TechnicianDetailSerializer

    def get_queryset(self):
        return Technician.objects.select_related("category", "location").all()


# ── Customer (authenticated) views ────────────────────────────────────────────


class TechnicianRequestListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/technician-requests/  — List the customer's own requests
    POST /api/v1/technician-requests/  — Submit a new request

    Only returns the authenticated customer's own requests — never another
    customer's data.
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TechnicianRequestCreateSerializer
        return TechnicianRequestListSerializer

    def get_queryset(self):
        return (
            TechnicianRequest.objects.filter(customer=self.request.user)
            .select_related("technician", "technician__category", "address")
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)
