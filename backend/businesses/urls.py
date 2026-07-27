from django.urls import path

from businesses.views import (
    BusinessCategoryListView,
    BusinessDetailView,
    BusinessListView,
    BusinessProductListView,
    OwnerBusinessView,
    OwnerProductCategoryDetailView,
    OwnerProductCategoryListCreateView,
    OwnerProductDetailView,
    OwnerProductListCreateView,
    OwnerVariantDetailView,
    OwnerVariantListCreateView,
    ProductDetailView,
)

urlpatterns = [
    # ── Public: Business categories ──────────────────────────────────────────
    path(
        "businesses/categories/",
        BusinessCategoryListView.as_view(),
        name="business-category-list",
    ),
    # ── Public: Businesses ───────────────────────────────────────────────────
    path("businesses/", BusinessListView.as_view(), name="business-list"),
    path("businesses/<int:pk>/", BusinessDetailView.as_view(), name="business-detail"),
    path(
        "businesses/<int:business_id>/products/",
        BusinessProductListView.as_view(),
        name="business-product-list",
    ),
    # ── Public: Products ─────────────────────────────────────────────────────
    path("products/<int:pk>/", ProductDetailView.as_view(), name="product-detail"),
    # ── Owner: My business ───────────────────────────────────────────────────
    path("my-business/", OwnerBusinessView.as_view(), name="owner-business"),
    path(
        "my-business/products/",
        OwnerProductListCreateView.as_view(),
        name="owner-product-list",
    ),
    path(
        "my-business/products/<int:pk>/",
        OwnerProductDetailView.as_view(),
        name="owner-product-detail",
    ),
    path(
        "my-business/products/<int:product_id>/variants/",
        OwnerVariantListCreateView.as_view(),
        name="owner-variant-list",
    ),
    path(
        "my-business/products/<int:product_id>/variants/<int:pk>/",
        OwnerVariantDetailView.as_view(),
        name="owner-variant-detail",
    ),
    path(
        "my-business/product-categories/",
        OwnerProductCategoryListCreateView.as_view(),
        name="owner-product-category-list",
    ),
    path(
        "my-business/product-categories/<int:pk>/",
        OwnerProductCategoryDetailView.as_view(),
        name="owner-product-category-detail",
    ),
]
