from django.urls import path, include
from rest_framework.routers import DefaultRouter

from orders.views import DeliveryAddressViewSet

router = DefaultRouter()
router.register("addresses", DeliveryAddressViewSet, basename="address")

urlpatterns = [
    path("", include(router.urls)),
]
