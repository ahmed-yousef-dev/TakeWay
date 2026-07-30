"""
Homepage and Search API views for TakeWay.

Endpoints:
  GET /api/v1/home/?location=<id>   — Homepage sections aggregation
  GET /api/v1/search/?q=<term>&location=<id>  — Unified business + product search

Design decisions:
─────────────────────────────────────────────────────────────────────────────
Home endpoint:
  - Returns a single structured JSON response with named sections instead of
    requiring the mobile app to make 4–5 separate requests. This is the
    Backend-for-Frontend (BFF) pattern at a small scale.
  - `location` query param is expected. The app always knows the user's
    selected location, so returning data without location context would
    give meaningless global results.
  - Banners: location-scoped first; if none found, falls back to global
    (location=None) banners. This avoids an empty carousel for new locations.
  - Featured businesses: capped at 10 to keep payload lightweight.
  - Today's offers: active offers today, capped at 10.
  - Categories: full list — not location-scoped (categories are global).

Search endpoint:
  - A single ?q= param searches across both businesses (name, description)
    AND products (name, description).
  - Results are grouped by type so the mobile app can render separate
    sections ("Businesses" and "Products") in one response.
  - `location` scoping is applied to both businesses and products (via their
    parent business).
  - Pagination is intentionally skipped in favour of a cap (MAX_SEARCH_RESULTS
    per type) to keep the mobile UX snappy. Full pagination can be added
    when real traffic demands it.
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import date

from django.db.models import Q
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from businesses.models import Business, BusinessCategory, Product
from businesses.serializers import (
    BusinessCategorySerializer,
    BusinessListSerializer,
    ProductListSerializer,
)
from promotions.models import Banner, Offer
from promotions.serializers import BannerSerializer, OfferSerializer


MAX_SEARCH_RESULTS = 10  # Cap per result type for the search endpoint


# ── Date-range Q-object helpers ───────────────────────────────────────────────

def _start_date_ok(today):
    """Item's start_date is null (no restriction) OR has already started."""
    return Q(start_date__isnull=True) | Q(start_date__lte=today)


def _end_date_ok(today):
    """Item's end_date is null (no restriction) OR hasn't expired yet."""
    return Q(end_date__isnull=True) | Q(end_date__gte=today)


# ── Homepage ──────────────────────────────────────────────────────────────────

class HomeAPIView(APIView):
    """
    GET /api/v1/home/?location=<id>

    Returns structured homepage data in a single request.

    Response shape:
    {
      "banners": [...],
      "categories": [...],
      "featured_businesses": [...],
      "todays_offers": [...]
    }

    All sections are always present (as empty lists if no data exists).
    """

    permission_classes = [AllowAny]
    pagination_class = None

    def get(self, request):
        today = date.today()
        location_id = request.query_params.get("location")

        # ── Banners ───────────────────────────────────────────────────────────
        # Strategy: prefer location-scoped banners; fall back to global ones.
        active_banners = Banner.objects.filter(
            is_active=True,
        ).filter(_start_date_ok(today)).filter(_end_date_ok(today)).order_by("sort_order")

        if location_id:
            location_banners = active_banners.filter(location_id=location_id)
            banners = location_banners if location_banners.exists() else active_banners.filter(location__isnull=True)
        else:
            banners = active_banners.filter(location__isnull=True)

        # ── Categories ────────────────────────────────────────────────────────
        categories = BusinessCategory.objects.all().order_by("sort_order", "name")

        # ── Featured businesses ───────────────────────────────────────────────
        featured_qs = Business.objects.filter(is_active=True, is_featured=True).select_related("category", "location")
        if location_id:
            featured_qs = featured_qs.filter(location_id=location_id)
        featured_businesses = featured_qs[:10]

        # ── Today's offers ────────────────────────────────────────────────────
        offers_qs = Offer.objects.filter(
            is_active=True,
        ).filter(_start_date_ok(today)).filter(_end_date_ok(today)).select_related("business")
        if location_id:
            offers_qs = offers_qs.filter(business__location_id=location_id)
        todays_offers = offers_qs[:10]

        return Response({
            "banners": BannerSerializer(banners, many=True, context={"request": request}).data,
            "categories": BusinessCategorySerializer(categories, many=True, context={"request": request}).data,
            "featured_businesses": BusinessListSerializer(featured_businesses, many=True, context={"request": request}).data,
            "todays_offers": OfferSerializer(todays_offers, many=True, context={"request": request}).data,
        })


# ── Search ────────────────────────────────────────────────────────────────────

class UnifiedSearchAPIView(APIView):
    """
    GET /api/v1/search/?q=<term>&location=<id>

    Returns grouped search results across businesses and products.

    Response shape:
    {
      "query": "pizza",
      "businesses": [...],
      "products": [...]
    }

    Both sections are always present. An empty ?q returns empty lists (200 OK).
    """

    permission_classes = [AllowAny]
    pagination_class = None

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        location_id = request.query_params.get("location")

        if not query:
            return Response({"query": "", "businesses": [], "products": []})

        # ── Business search ───────────────────────────────────────────────────
        business_qs = Business.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query),
            is_active=True,
        ).select_related("category", "location")

        if location_id:
            business_qs = business_qs.filter(location_id=location_id)

        businesses = business_qs[:MAX_SEARCH_RESULTS]

        # ── Product search ────────────────────────────────────────────────────
        product_qs = Product.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query),
            is_active=True,
            is_available=True,
        ).select_related("business", "product_category")

        if location_id:
            product_qs = product_qs.filter(business__location_id=location_id)

        products = product_qs[:MAX_SEARCH_RESULTS]

        return Response({
            "query": query,
            "businesses": BusinessListSerializer(businesses, many=True, context={"request": request}).data,
            "products": ProductListSerializer(products, many=True, context={"request": request}).data,
        })
