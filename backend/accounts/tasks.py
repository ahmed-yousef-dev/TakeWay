"""
Celery tasks for the accounts app.

Tasks here are kept thin — they delegate to service functions.
This keeps the business logic in services.py and testable without Celery.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,  # seconds
    name="accounts.tasks.send_otp_sms",
)
def send_otp_sms(self, phone: str, code: str) -> bool:
    """
    Async task: send an OTP SMS to the given phone number.

    Retries up to 3 times with a 30-second delay on failure.
    """
    from accounts.sms_backends import get_sms_backend

    message = f"Your TakeWay verification code is: {code}. Valid for 5 minutes. Do not share this code."

    try:
        backend = get_sms_backend()
        success = backend.send(phone, message)
        if not success:
            raise Exception(f"SMS backend returned False for {phone}")
        return True
    except Exception as exc:
        logger.error("Failed to send OTP to %s: %s", phone, exc)
        raise self.retry(exc=exc)
