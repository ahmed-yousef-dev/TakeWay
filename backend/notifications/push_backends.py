"""
Push notification backend abstraction for TakeWay.

Mirrors the SMS backend pattern in accounts/sms_backends.py.

To add a real FCM provider, subclass BasePushBackend, implement send(),
then update settings.py:

    PUSH_NOTIFICATION_BACKEND = "notifications.push_backends.ConsolePushBackend"   # dev
    PUSH_NOTIFICATION_BACKEND = "notifications.push_backends.FCMPushBackend"        # prod (future)

The Celery tasks in notifications/tasks.py call get_push_backend() — so
swapping providers requires zero changes outside this file and settings.py.
"""

import logging

logger = logging.getLogger(__name__)


class BasePushBackend:
    """
    Abstract base class for push notification backends.

    All concrete backends must implement send_to_token() and, optionally,
    send_to_tokens() for batch delivery.
    """

    def send_to_token(self, token: str, title: str, body: str, data: dict | None = None) -> bool:
        """
        Send a push notification to a single FCM device token.

        Returns True on success, False on failure.
        Implementations should NOT raise exceptions — log and return False instead.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement send_to_token()."
        )

    def send_to_tokens(self, tokens: list[str], title: str, body: str, data: dict | None = None) -> dict:
        """
        Send a push notification to multiple device tokens.

        Default implementation calls send_to_token() in a loop.
        Override for batch API support (e.g. FCM multicast).

        Returns a dict: {"success": int, "failure": int}
        """
        results = {"success": 0, "failure": 0}
        for token in tokens:
            ok = self.send_to_token(token, title, body, data)
            if ok:
                results["success"] += 1
            else:
                results["failure"] += 1
        return results


class ConsolePushBackend(BasePushBackend):
    """
    Development backend: logs the notification instead of sending a real push.

    Use this in development and CI so no Firebase credentials are required.
    """

    def send_to_token(self, token: str, title: str, body: str, data: dict | None = None) -> bool:
        logger.info(
            "[PUSH → %s]: title=%r body=%r data=%r",
            token[:20] + "…",
            title,
            body,
            data or {},
        )
        print(
            f"\n[PUSH → {token[:20]}…]\n"
            f"  Title : {title}\n"
            f"  Body  : {body}\n"
            f"  Data  : {data or {}}\n"
        )
        return True


def get_push_backend() -> BasePushBackend:
    """
    Return an instance of the configured push notification backend.

    Loaded from settings.PUSH_NOTIFICATION_BACKEND.
    Raises ImportError / AttributeError if the path is invalid — fail fast.
    """
    from django.conf import settings
    from django.utils.module_loading import import_string

    backend_path = getattr(
        settings,
        "PUSH_NOTIFICATION_BACKEND",
        "notifications.push_backends.ConsolePushBackend",
    )
    backend_class = import_string(backend_path)
    return backend_class()
