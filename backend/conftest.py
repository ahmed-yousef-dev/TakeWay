"""
Shared test fixtures for TakeWay.

Database and Celery configuration is handled via takeway/test_settings.py
(pointed to by pytest.ini). This file only contains reusable fixtures.
"""

import pytest


@pytest.fixture
def api_client():
    """Return an unauthenticated DRF APIClient."""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def auth_api_client():
    """Return an APIClient authenticated as a regular customer."""
    from rest_framework.test import APIClient
    from accounts.tests.factories import UserFactory

    user = UserFactory(name="Test Customer")
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user
