from rest_framework.throttling import BaseThrottle
from accounts.services import check_rate_limit
from accounts.validators import normalise_phone
from django.core.exceptions import ValidationError

class BaseExponentialThrottle(BaseThrottle):
    max_attempts = 3
    base_timeout = 300
    cache_prefix = "throttle"

    def allow_request(self, request, view):
        phone = request.data.get("phone")
        if not phone:
            return True
            
        try:
            phone = normalise_phone(phone)
        except (ValidationError, ValueError):
            pass

        throttle_key = f"{self.cache_prefix}_{phone}"
        allowed, wait_seconds = check_rate_limit(
            throttle_key, 
            max_attempts=self.max_attempts, 
            base_timeout=self.base_timeout
        )
        
        self.wait_seconds = wait_seconds
        return allowed

    def wait(self):
        return getattr(self, "wait_seconds", None)


class ExponentialOTPRequestThrottle(BaseExponentialThrottle):
    max_attempts = 3
    base_timeout = 300
    cache_prefix = "api_otp_request"


class ExponentialOTPVerifyThrottle(BaseExponentialThrottle):
    max_attempts = 5
    base_timeout = 300
    cache_prefix = "api_otp_verify"


class ExponentialLoginThrottle(BaseExponentialThrottle):
    max_attempts = 5
    base_timeout = 300
    cache_prefix = "api_login"
