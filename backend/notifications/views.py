"""
Views for the notifications app.

  - DeviceTokenRegisterView  POST /api/v1/device-tokens/     — Register/refresh FCM token
  - NotificationListView     GET  /api/v1/notifications/     — List own notifications
  - NotificationMarkReadView POST /api/v1/notifications/mark-read/  — Mark all as read
"""

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.models import DeviceToken, Notification
from notifications.serializers import DeviceTokenRegisterSerializer, NotificationSerializer


class DeviceTokenRegisterView(APIView):
    """
    POST /api/v1/device-tokens/

    Register or refresh an FCM device token for the authenticated user.

    Uses update_or_create on the token field so re-registering the same
    device simply bumps updated_at — no duplicate tokens accumulate.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DeviceTokenRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data["token"]
        device_type = serializer.validated_data["device_type"]

        obj, created = DeviceToken.objects.update_or_create(
            token=token,
            defaults={"user": request.user, "device_type": device_type},
        )

        http_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response({"detail": "Device token registered."}, status=http_status)


class NotificationListView(generics.ListAPIView):
    """
    GET /api/v1/notifications/

    Returns the authenticated customer's notifications, newest first.
    Supports: ?is_read=false  to show only unread.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    filterset_fields = ["is_read", "type"]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by("-created_at")


class NotificationMarkAllReadView(APIView):
    """
    POST /api/v1/notifications/mark-read/

    Mark all of the authenticated customer's unread notifications as read.
    Returns the count of records updated.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated_count = Notification.objects.filter(
            user=request.user, is_read=False
        ).update(is_read=True)
        return Response({"marked_read": updated_count}, status=status.HTTP_200_OK)
