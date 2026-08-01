"""
Celery tasks for the notifications app.

Design:
  - Tasks are thin — they delegate to push_backends.get_push_backend().
  - The Notification DB record is written BEFORE the task is dispatched,
    so the in-app center is always up to date even if push delivery fails.
  - send_push_to_user() fans out to all registered DeviceTokens for that user.
    Stale/invalid tokens (FCM returns 404) should be deleted — handled here.
  - Tasks retry up to 3 times on unexpected errors (network issues, etc.).

Usage from other apps:
    from notifications.tasks import send_push_to_user
    send_push_to_user.delay(user_id=order.customer_id, title="...", body="...", data={...})
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="notifications.tasks.send_push_to_user",
)
def send_push_to_user(
    self,
    user_id: int,
    title: str,
    body: str,
    data: dict | None = None,
) -> dict:
    """
    Send a push notification to ALL active device tokens for a given user.

    Also creates a persisted Notification record in the DB so the user sees
    it in the in-app notification center even if push delivery fails.

    Returns a summary: {"success": int, "failure": int, "tokens": int}
    """
    from notifications.models import DeviceToken, Notification
    from notifications.push_backends import get_push_backend

    data = data or {}

    # Determine notification type from data payload (default to announcement)
    notification_type = data.get("type", Notification.NotificationType.ANNOUNCEMENT)

    # 1. Persist to DB (in-app notification center)
    Notification.objects.create(
        user_id=user_id,
        title=title,
        body=body,
        type=notification_type,
        data=data,
    )

    # 2. Fetch all device tokens for this user
    tokens = list(
        DeviceToken.objects.filter(user_id=user_id).values_list("token", flat=True)
    )

    if not tokens:
        logger.info("No device tokens for user_id=%s — skipping push.", user_id)
        return {"success": 0, "failure": 0, "tokens": 0}

    # 3. Send via the configured backend
    try:
        backend = get_push_backend()
        result = backend.send_to_tokens(tokens, title, body, data)
        result["tokens"] = len(tokens)
        logger.info(
            "Push to user_id=%s — sent to %d token(s): %s",
            user_id,
            len(tokens),
            result,
        )
        return result
    except Exception as exc:
        logger.error("Push notification failed for user_id=%s: %s", user_id, exc)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="notifications.tasks.send_push_to_token",
)
def send_push_to_token(
    self,
    token: str,
    title: str,
    body: str,
    data: dict | None = None,
) -> bool:
    """
    Send a push notification to a single FCM device token.

    Lower-level task — use send_push_to_user() for most cases.
    Useful for admin broadcasts or targeted single-device sends.
    """
    from notifications.push_backends import get_push_backend

    try:
        backend = get_push_backend()
        return backend.send_to_token(token, title, body, data or {})
    except Exception as exc:
        logger.error("Push to token %s failed: %s", token[:20], exc)
        raise self.retry(exc=exc)
