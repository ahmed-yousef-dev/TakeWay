from django.urls import path, include
from rest_framework.routers import DefaultRouter

from orders.views import (
    AnythingRequestViewSet,
    CartItemViewSet,
    CartView,
    CheckoutView,
    DeliveryAddressViewSet,
    OrderViewSet,
)

router = DefaultRouter()
router.register("addresses", DeliveryAddressViewSet, basename="address")
router.register("cart/items", CartItemViewSet, basename="cart-item")
router.register("orders", OrderViewSet, basename="order")
router.register("anything-requests", AnythingRequestViewSet, basename="anything-request")

urlpatterns = [
    path("", include(router.urls)),
    path("cart/", CartView.as_view(), name="cart"),
    path("checkout/", CheckoutView.as_view(), name="checkout"),
]
