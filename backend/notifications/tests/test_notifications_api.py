"""
Tests for the notifications app.

Covers:
  - DeviceToken: register new token (201), refresh existing (200)
  - Notification: list own notifications, filter by is_read, unauthenticated
  - NotificationMarkAllRead: marks all unread as read
  - Celery task: send_push_to_user writes a DB record and calls the backend
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch

from accounts.tests.factories import UserFactory
from notifications.models import DeviceToken, Notification


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def customer():
    return UserFactory(name="Notif Customer")


@pytest.fixture
def auth_client(customer):
    client = APIClient()
    client.force_authenticate(user=customer)
    return client, customer


# ── Device Token Registration ─────────────────────────────────────────────────


@pytest.mark.django_db
class TestDeviceTokenRegister:
    url = "/api/v1/device-tokens/"

    def test_unauthenticated_returns_401(self):
        resp = APIClient().post(self.url, {"token": "abc123", "device_type": "android"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_new_token_returns_201(self, auth_client):
        client, _ = auth_client
        resp = client.post(self.url, {"token": "new-fcm-token-abc", "device_type": "android"})
        assert resp.status_code == status.HTTP_201_CREATED
        assert DeviceToken.objects.count() == 1

    def test_existing_token_returns_200_and_upserts(self, auth_client):
        """Re-registering the same token must update, not duplicate."""
        client, customer = auth_client
        DeviceToken.objects.create(user=customer, token="existing-token", device_type="android")
        resp = client.post(self.url, {"token": "existing-token", "device_type": "ios"})
        assert resp.status_code == status.HTTP_200_OK
        # Still only one token in DB
        assert DeviceToken.objects.filter(token="existing-token").count() == 1
        # Device type updated
        dt = DeviceToken.objects.get(token="existing-token")
        assert dt.device_type == "ios"

    def test_missing_token_returns_400(self, auth_client):
        client, _ = auth_client
        resp = client.post(self.url, {"device_type": "android"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ── Notification List ─────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestNotificationList:
    url = "/api/v1/notifications/"

    def test_unauthenticated_returns_401(self):
        resp = APIClient().get(self.url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_returns_own_notifications_only(self, auth_client):
        client, customer = auth_client
        other = UserFactory(name="Other User")

        Notification.objects.create(
            user=customer, title="Hello", body="msg",
            type=Notification.NotificationType.ANNOUNCEMENT
        )
        Notification.objects.create(
            user=other, title="Other", body="msg",
            type=Notification.NotificationType.ANNOUNCEMENT
        )

        resp = client.get(self.url)
        data = resp.data
        results = data.get("results", data)
        assert len(results) == 1
        assert results[0]["title"] == "Hello"

    def test_filter_by_is_read(self, auth_client):
        client, customer = auth_client
        Notification.objects.create(
            user=customer, title="Unread", body="msg",
            type=Notification.NotificationType.ANNOUNCEMENT, is_read=False
        )
        Notification.objects.create(
            user=customer, title="Read", body="msg",
            type=Notification.NotificationType.ANNOUNCEMENT, is_read=True
        )

        resp = client.get(self.url, {"is_read": "false"})
        data = resp.data
        results = data.get("results", data)
        assert all(not item["is_read"] for item in results)

    def test_response_includes_type_display(self, auth_client):
        client, customer = auth_client
        Notification.objects.create(
            user=customer, title="Test", body="msg",
            type=Notification.NotificationType.ORDER_STATUS
        )
        resp = client.get(self.url)
        data = resp.data
        results = data.get("results", data)
        assert "type_display" in results[0]


# ── Notification Mark All Read ────────────────────────────────────────────────


@pytest.mark.django_db
class TestNotificationMarkAllRead:
    url = "/api/v1/notifications/mark-read/"

    def test_unauthenticated_returns_401(self):
        resp = APIClient().post(self.url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_marks_all_unread_as_read(self, auth_client):
        client, customer = auth_client
        for _ in range(3):
            Notification.objects.create(
                user=customer, title="N", body="b",
                type=Notification.NotificationType.ANNOUNCEMENT, is_read=False
            )

        resp = client.post(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["marked_read"] == 3
        assert Notification.objects.filter(user=customer, is_read=False).count() == 0

    def test_does_not_affect_other_users_notifications(self, auth_client):
        client, customer = auth_client
        other = UserFactory(name="Other User")
        Notification.objects.create(
            user=other, title="N", body="b",
            type=Notification.NotificationType.ANNOUNCEMENT, is_read=False
        )

        resp = client.post(self.url)
        assert resp.status_code == status.HTTP_200_OK
        # Other user's notification must remain unread
        assert Notification.objects.filter(user=other, is_read=False).count() == 1


# ── Celery Task: send_push_to_user ────────────────────────────────────────────


@pytest.mark.django_db
class TestSendPushToUserTask:
    def test_creates_db_notification_record(self):
        """Notification must be persisted regardless of push backend result."""
        user = UserFactory()
        from notifications.tasks import send_push_to_user

        send_push_to_user(
            user_id=user.pk,
            title="Test Title",
            body="Test body",
            data={"type": Notification.NotificationType.ANNOUNCEMENT},
        )

        assert Notification.objects.filter(user=user, title="Test Title").exists()

    def test_no_tokens_returns_zero_counts(self):
        user = UserFactory()
        from notifications.tasks import send_push_to_user

        result = send_push_to_user(
            user_id=user.pk,
            title="Hi",
            body="body",
        )
        assert result["success"] == 0
        assert result["failure"] == 0
        assert result["tokens"] == 0

    def test_sends_to_all_user_device_tokens(self):
        user = UserFactory()
        DeviceToken.objects.create(user=user, token="token-1", device_type="android")
        DeviceToken.objects.create(user=user, token="token-2", device_type="ios")

        from notifications.tasks import send_push_to_user

        with patch(
            "notifications.push_backends.ConsolePushBackend.send_to_token",
            return_value=True,
        ) as mock_send:
            result = send_push_to_user(
                user_id=user.pk,
                title="Hello",
                body="World",
            )

        assert result["tokens"] == 2
        assert mock_send.call_count == 2
