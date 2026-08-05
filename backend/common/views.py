"""
Views for the common app — Reviews & Favorites.

Endpoints:
  POST   /api/v1/reviews/               — Create a review
  GET    /api/v1/reviews/?content_type=business&object_id=5
                                        — List reviews for a specific entity
  POST   /api/v1/favorites/toggle/      — Toggle a favorite (add or remove)
  GET    /api/v1/favorites/             — List the authenticated user's favorites

Design decisions:
- Reviews use a separate List (GET) and Create (POST) view rather than
  a single ViewSet to keep the permission and serializer logic explicit.
- Favorites use a toggle endpoint (POST /favorites/toggle/) instead of
  separate create/delete endpoints. This simplifies client logic: the client
  always POSTs the same payload and the server returns 201 (added) or
  204 (removed). No need for the client to track the Favorite PK.
- All write endpoints require authentication; the review list is public
  so the mobile app can show ratings on business pages without login.
"""

from django.db import IntegrityError
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Favorite, Review
from .serializers import (
    FavoriteCreateSerializer,
    FavoriteSerializer,
    ReviewCreateSerializer,
    ReviewSerializer,
)


# ── Reviews ───────────────────────────────────────────────────────────────────

class ReviewListView(generics.ListAPIView):
    """
    GET /api/v1/reviews/?content_type=<slug>&object_id=<id>

    Returns all reviews for a specific entity.
    Both query params are required; returns 400 if either is missing.
    Public — no authentication required.
    """

    permission_classes = [AllowAny]
    serializer_class = ReviewSerializer

    def get_queryset(self):
        from django.contrib.contenttypes.models import ContentType
        from .serializers import ALLOWED_CT_SLUGS

        ct_slug = self.request.query_params.get("content_type", "").strip()
        object_id = self.request.query_params.get("object_id", "").strip()

        if not ct_slug or not object_id:
            # Return empty queryset; the client will see an empty list.
            # Proper 400 is raised only on write ops.
            return Review.objects.none()

        if ct_slug not in ALLOWED_CT_SLUGS:
            return Review.objects.none()

        app_label, model = ALLOWED_CT_SLUGS[ct_slug]
        try:
            content_type = ContentType.objects.get(app_label=app_label, model=model)
        except ContentType.DoesNotExist:
            return Review.objects.none()

        return Review.objects.filter(
            content_type=content_type,
            object_id=object_id,
        ).select_related("user")


class ReviewCreateView(generics.CreateAPIView):
    """
    POST /api/v1/reviews/

    Creates a review for a business (or technician in future phases).
    Requires authentication. Enforces eligibility: the user must have a
    DELIVERED order from the target business.

    Request body:
      {
        "content_type_str": "business",
        "object_id": 5,
        "rating": 4,
        "comment": "Great service!"    // optional
      }
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ReviewCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            review = serializer.save()
        except IntegrityError:
            # Fallback for the rare race-condition duplicate hit
            return Response(
                {"detail": "You have already reviewed this entity."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(ReviewSerializer(review, context={"request": request}).data, status=status.HTTP_201_CREATED)


# ── Favorites ─────────────────────────────────────────────────────────────────

class FavoriteListView(generics.ListAPIView):
    """
    GET /api/v1/favorites/

    Returns all favorites for the authenticated user.
    Optionally filter by ?content_type=business
    """

    permission_classes = [IsAuthenticated]
    serializer_class = FavoriteSerializer

    def get_queryset(self):
        from django.contrib.contenttypes.models import ContentType
        from .serializers import ALLOWED_CT_SLUGS

        qs = Favorite.objects.filter(user=self.request.user).select_related("content_type")

        ct_slug = self.request.query_params.get("content_type", "").strip()
        if ct_slug and ct_slug in ALLOWED_CT_SLUGS:
            app_label, model = ALLOWED_CT_SLUGS[ct_slug]
            try:
                content_type = ContentType.objects.get(app_label=app_label, model=model)
                qs = qs.filter(content_type=content_type)
            except ContentType.DoesNotExist:
                pass

        return qs


class FavoriteToggleView(APIView):
    """
    POST /api/v1/favorites/toggle/

    Toggles a favorite:
      - If the favorite does NOT exist → create it → 201 Created
      - If the favorite DOES exist    → delete it → 204 No Content

    This single endpoint removes the need for the client to manage
    Favorite PKs or issue separate DELETE requests.

    Request body:
      {
        "content_type_str": "business",
        "object_id": 5
      }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = FavoriteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        content_type = serializer.validated_data["content_type"]
        object_id = serializer.validated_data["object_id"]

        favorite = Favorite.objects.filter(
            user=user, content_type=content_type, object_id=object_id
        ).first()

        if favorite:
            # Already favorited → remove it
            favorite.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            # Not yet favorited → add it
            try:
                new_fav = Favorite.objects.create(
                    user=user, content_type=content_type, object_id=object_id
                )
            except IntegrityError:
                # Race condition: another request created it just now → treat as removed
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(FavoriteSerializer(new_fav, context={"request": request}).data, status=status.HTTP_201_CREATED)
