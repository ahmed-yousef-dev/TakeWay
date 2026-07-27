from django.urls import path

from locations.views import (
    GovernorateDetailView,
    GovernorateListView,
    LocationDetailView,
    LocationListView,
)

urlpatterns = [
    path("governorates/", GovernorateListView.as_view(), name="governorate-list"),
    path("governorates/<int:pk>/", GovernorateDetailView.as_view(), name="governorate-detail"),
    path("", LocationListView.as_view(), name="location-list"),
    path("<int:pk>/", LocationDetailView.as_view(), name="location-detail"),
]
