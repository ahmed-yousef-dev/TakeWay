"""
Notifications domain models for TakeWay.

Models:
  - DeviceToken: stores FCM push tokens per user device
  - Notification: in-app notification record (all channels stored in DB)

Design decisions:
  - ALL notifications are stored in the DB regardless of push channel.
    This gives users an in-app notification center that works even if
    FCM delivery fails or the user had no internet at the time.
  - DeviceToken stores one FCM token per device (keyed by token string).
    A user can have multiple tokens (multiple devices). Duplicate tokens
    are upserted on registration — old entries are overwritten.
  - Notification.type is an enum so the mobile app can route to the
    correct screen without parsing free-text bodies.
  - data (JSONField) carries the deep-link payload (e.g. order_id, request_id)
    the mobile app needs to navigate to the relevant screen.
  - Push delivery itself is done via Celery task (notifications/tasks.py)
    using the abstracted PushNotificationBackend — so the DB record is
    always written synchronously, and delivery is best-effort async.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import TimestampMixin


class DeviceToken(TimestampMixin):
    """
    An FCM push token for a specific device owned by a user.

    A user may have multiple tokens (e.g. two phones).
    Token strings are unique in the DB — registering the same physical
    device again simply updates `updated_at` via upsert logic in the view.

    device_type is informational only (for analytics / debugging).
    """

    class DeviceType(models.TextChoices):
        ANDROID = "android", _("Android")
        IOS = "ios", _("iOS")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_tokens",
        verbose_name=_("user"),
    )
    token = models.TextField(
        _("FCM token"),
        unique=True,
        help_text=_("Firebase Cloud Messaging registration token for this device."),
    )
    device_type = models.CharField(
        _("device type"),
        max_length=10,
        choices=DeviceType.choices,
        default=DeviceType.ANDROID,
    )

    class Meta:
        verbose_name = _("device token")
        verbose_name_plural = _("device tokens")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} — {self.get_device_type_display()} token ({self.token[:20]}…)"


class Notification(TimestampMixin):
    """
    A single notification record for a user.

    Stored in DB regardless of push delivery status, providing a persistent
    in-app notification center that works offline and survives FCM failures.

    The `type` field tells the mobile app WHAT happened.
    The `data` JSONField tells it WHERE to navigate (e.g. {"order_id": 42}).
    """

    class NotificationType(models.TextChoices):
        ORDER_STATUS = "order_status", _("Order Status Update")
        TECHNICIAN_REQUEST = "technician_request", _("Technician Request Update")
        RIDE_REQUEST = "ride_request", _("Ride Request Update")
        PROMOTION = "promotion", _("Promotion / Offer")
        ANNOUNCEMENT = "announcement", _("General Announcement")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name=_("user"),
    )
    title = models.CharField(_("title"), max_length=255)
    body = models.TextField(_("body"))
    type = models.CharField(
        _("type"),
        max_length=30,
        choices=NotificationType.choices,
        db_index=True,
    )
    data = models.JSONField(
        _("data"),
        default=dict,
        blank=True,
        help_text=_(
            "Deep-link payload for the mobile app. "
            "e.g. {'order_id': 42} or {'technician_request_id': 7}."
        ),
    )
    is_read = models.BooleanField(_("is read"), default=False, db_index=True)

    class Meta:
        verbose_name = _("notification")
        verbose_name_plural = _("notifications")
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "is_read"],
                name="notification_user_read_idx",
            ),
        ]

    def __str__(self):
        read_label = "read" if self.is_read else "unread"
        return f"[{self.get_type_display()}] {self.title} → {self.user} ({read_label})"
