"""
Serializers for the notifications app.
"""

from rest_framework import serializers

from notifications.models import DeviceToken, Notification


class DeviceTokenRegisterSerializer(serializers.ModelSerializer):
    """
    Used when a customer registers or refreshes their FCM device token.
    user is injected by the view.

    If the token already exists (same device re-registering), the view
    will upsert (update_or_create) — the serializer just validates the input.
    """

    class Meta:
        model = DeviceToken
        fields = ["token", "device_type"]


class NotificationSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for the in-app notification center.
    """

    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "body",
            "type",
            "type_display",
            "data",
            "is_read",
            "created_at",
        ]
        read_only_fields = fields
