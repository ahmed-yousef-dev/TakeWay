from django.urls import path

from .home_views import HomeAPIView, UnifiedSearchAPIView
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
    # Homepage & Search
    path("home/", HomeAPIView.as_view(), name="home"),
    path("search/", UnifiedSearchAPIView.as_view(), name="unified-search"),
]
