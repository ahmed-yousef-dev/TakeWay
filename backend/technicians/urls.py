from django.urls import path

from technicians.views import (
    TechnicianCategoryListView,
    TechnicianDetailView,
    TechnicianListView,
    TechnicianRequestListCreateView,
)

urlpatterns = [
    # ── Public: Technician categories ────────────────────────────────────────
    path(
        "technicians/categories/",
        TechnicianCategoryListView.as_view(),
        name="technician-category-list",
    ),
    # ── Public: Technicians ──────────────────────────────────────────────────
    path("technicians/", TechnicianListView.as_view(), name="technician-list"),
    path("technicians/<int:pk>/", TechnicianDetailView.as_view(), name="technician-detail"),
    # ── Customer: Requests ───────────────────────────────────────────────────
    path(
        "technician-requests/",
        TechnicianRequestListCreateView.as_view(),
        name="technician-request-list-create",
    ),
]
