"""
Custom DRF permissions for the businesses app.
"""

from rest_framework.permissions import BasePermission, IsAuthenticated

from accounts.models import User


class IsBusinessOwner(BasePermission):
    """
    Grants access only to the authenticated user who owns a specific business.

    Used on product management endpoints (/my-business/...).
    The business is identified via the user's `owned_business` reverse relation.
    """

    message = "You must be a business owner to perform this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return (
            request.user.role == User.Role.BUSINESS_OWNER
            and hasattr(request.user, "owned_business")
        )


class IsAdminOrReadOnly(BasePermission):
    """
    Admin users can write; anyone (including anonymous) can read.
    Used on category endpoints.
    """

    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request.user and request.user.is_staff
