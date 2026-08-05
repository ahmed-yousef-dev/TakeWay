from django.urls import path, include
from rest_framework.routers import DefaultRouter

from rides.views import RideRequestViewSet

router = DefaultRouter()
router.register(r"ride-requests", RideRequestViewSet, basename="ride-request")

urlpatterns = [
    path("", include(router.urls)),
]
