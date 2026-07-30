from django.urls import path, include
from rest_framework.routers import DefaultRouter

from orders.views import CartItemViewSet, CartView, DeliveryAddressViewSet

router = DefaultRouter()
router.register("addresses", DeliveryAddressViewSet, basename="address")
router.register("cart/items", CartItemViewSet, basename="cart-item")

urlpatterns = [
    path("", include(router.urls)),
    path("cart/", CartView.as_view(), name="cart"),
]
