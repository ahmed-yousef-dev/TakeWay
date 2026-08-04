"""
URL routing for web views.
"""

from django.urls import path
from accounts.web_views import (
    WebAccountDeletionRequestView,
    WebAccountDeletionConfirmView,
    WebAccountDeletionSuccessView,
)

urlpatterns = [
    path("", WebAccountDeletionRequestView.as_view(), name="web-account-delete-request"),
    path("confirm/", WebAccountDeletionConfirmView.as_view(), name="web-account-delete-confirm"),
    path("success/", WebAccountDeletionSuccessView.as_view(), name="web-account-delete-success"),
]
