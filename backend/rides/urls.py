from django.urls import path

from rides.views import RideRequestListCreateView

urlpatterns = [
    path(
        "ride-requests/",
        RideRequestListCreateView.as_view(),
        name="ride-request-list-create",
    ),
]
