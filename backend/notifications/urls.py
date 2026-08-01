from django.urls import path

from notifications.views import (
    DeviceTokenRegisterView,
    NotificationListView,
    NotificationMarkAllReadView,
)

urlpatterns = [
    # FCM device token registration
    path(
        "device-tokens/",
        DeviceTokenRegisterView.as_view(),
        name="device-token-register",
    ),
    # In-app notification center
    path(
        "notifications/",
        NotificationListView.as_view(),
        name="notification-list",
    ),
    path(
        "notifications/mark-read/",
        NotificationMarkAllReadView.as_view(),
        name="notification-mark-read",
    ),
]
