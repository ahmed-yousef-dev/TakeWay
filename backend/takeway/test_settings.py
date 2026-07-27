"""
Test-only Django settings.

Inherits from the main settings but overrides the database to use
SQLite in-memory for fast, isolated test runs without PostgreSQL.
"""

from takeway.settings import *  # noqa: F401, F403

# ── Override database for tests ───────────────────────────────────────────────

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# ── Speed up password hashing in tests ────────────────────────────────────────

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# ── Celery: run tasks synchronously (no broker needed) ────────────────────────

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
