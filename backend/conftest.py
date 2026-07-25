import pytest
from django.db import connections
from django.db.utils import ConnectionHandler

@pytest.fixture(scope="session", autouse=True)
def _configure_test_settings(django_test_environment):
    from django.conf import settings
    settings.DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
    settings.REST_FRAMEWORK = {
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        )
    }
    connections["default"] = ConnectionHandler(settings.DATABASES)["default"]
