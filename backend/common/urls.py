from django.urls import path

from .views import (
    FavoriteListView,
    FavoriteToggleView,
    ReviewCreateView,
    ReviewListView,
)

urlpatterns = [
    # Reviews
    path("reviews/", ReviewListView.as_view(), name="review-list"),
    path("reviews/create/", ReviewCreateView.as_view(), name="review-create"),
    # Favorites
    path("favorites/", FavoriteListView.as_view(), name="favorite-list"),
    path("favorites/toggle/", FavoriteToggleView.as_view(), name="favorite-toggle"),
]
