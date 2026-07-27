"""
SMS backend abstraction for TakeWay.

To add a new provider, subclass BaseSMSBackend and implement send().
Then set SMS_BACKEND in settings.py to the dotted path of your class.

Example:
    SMS_BACKEND = "accounts.sms_backends.ConsoleSMSBackend"          # dev
    SMS_BACKEND = "accounts.sms_backends.VonageSMSBackend"           # prod
"""

import logging

logger = logging.getLogger(__name__)


class BaseSMSBackend:
    """
    Abstract base class for SMS backends.

    All concrete backends must implement send().
    """

    def send(self, phone: str, message: str) -> bool:
        """
        Send *message* to *phone*.

        Returns True on success, False on failure.
        Implementations should not raise exceptions — log and return False instead.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement send()."
        )


class ConsoleSMSBackend(BaseSMSBackend):
    """
    Development backend: logs the message instead of sending an SMS.

    Use this in development and CI so no real SMS messages are sent
    and no API keys are required.
    """

    def send(self, phone: str, message: str) -> bool:
        logger.info("[SMS → %s]: %s", phone, message)
        print(f"\n[SMS → {phone}]: {message}\n")  # Also print for easy debugging
        return True


def get_sms_backend() -> BaseSMSBackend:
    """
    Return an instance of the configured SMS backend.

    Loaded from settings.SMS_BACKEND. Raises ImportError/AttributeError
    if the path is invalid — fail fast at startup.
    """
    from django.conf import settings
    from django.utils.module_loading import import_string

    backend_path = getattr(settings, "SMS_BACKEND", "accounts.sms_backends.ConsoleSMSBackend")
    backend_class = import_string(backend_path)
    return backend_class()
