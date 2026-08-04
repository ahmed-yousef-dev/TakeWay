"""
Django settings for takeway project.
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ── Security ─────────────────────────────────────────────────────────────────

# SECRET_KEY is required - it will raise an error if not set in .env
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is not set!")

DEBUG = os.getenv("DEBUG", "True") == "True"

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")


# ── Application definition ───────────────────────────────────────────────────

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "django_celery_beat",
    "django_celery_results",
    # Internal apps
    "common",
    "accounts",
    "locations",
    "businesses",
    "orders",
    "promotions",
    "technicians",
    "rides",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "takeway.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "takeway.wsgi.application"


# ── Custom User Model ─────────────────────────────────────────────────────────

AUTH_USER_MODEL = "accounts.User"


# ── Database ──────────────────────────────────────────────────────────────────

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "CONN_MAX_AGE": 600,  # Connection pooling (10 minutes)
        "OPTIONS": {
            "connect_timeout": 10,
        },
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ── Password validation ───────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ── Internationalization ──────────────────────────────────────────────────────

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Cairo"
USE_I18N = True
USE_TZ = True


# ── Static & Media files ──────────────────────────────────────────────────────

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Max upload size: 5 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5 MB


# ── Django REST Framework ─────────────────────────────────────────────────────



REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "10/minute",
        "user": "100/minute",
        # Custom scopes (applied per view)
        "otp_request": "5/hour",
        "otp_verify": "10/hour",
    },
}


# ── JWT Settings ──────────────────────────────────────────────────────────────

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}


# ── Celery ────────────────────────────────────────────────────────────────────

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "django-cache"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "True" if DEBUG else "False") == "True"
CELERY_TASK_EAGER_PROPAGATES = os.getenv("CELERY_TASK_EAGER_PROPAGATES", "True" if DEBUG else "False") == "True"


# ── Redis ─────────────────────────────────────────────────────────────────────

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/1")


# ── CORS ──────────────────────────────────────────────────────────────────────
# Disabled until a web frontend exists; mobile app does not use CORS.

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = []


# ── OTP Settings ─────────────────────────────────────────────────────────────

OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 5

# Toggle static mock OTP for dev/testing across all OTP flows
USE_MOCK_OTP = os.getenv("USE_MOCK_OTP", str(DEBUG)).lower() in ("true", "1", "t")
MOCK_OTP_CODE = os.getenv("MOCK_OTP_CODE", "123456")

# SMS backend: swap to a real provider in production
SMS_BACKEND = os.getenv("SMS_BACKEND", "accounts.sms_backends.ConsoleSMSBackend")

# Push notification backend: swap to FCMPushBackend in production
PUSH_NOTIFICATION_BACKEND = os.getenv(
    "PUSH_NOTIFICATION_BACKEND",
    "notifications.push_backends.ConsolePushBackend",
)


# ── API Documentation (drf-spectacular) ──────────────────────────────────────

SPECTACULAR_SETTINGS = {
    "TITLE": "TakeWay API",
    "DESCRIPTION": "All-in-One Village Super App — Backend API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# ── API Throttling Overrides ─────────────────────────────────────────────────

# 1. Master switch for ALL standard rate limits
ENABLE_API_THROTTLING = os.getenv("ENABLE_API_THROTTLING", "False" if DEBUG else "True") == "True"

# 2. Specific switch just for the strict exponential ones
ENABLE_EXPONENTIAL_THROTTLES = os.getenv("ENABLE_EXPONENTIAL_THROTTLES", "False" if DEBUG else "True") == "True"

# If global API throttling is disabled, clear the default DRF throttles
if not ENABLE_API_THROTTLING:
    REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []
