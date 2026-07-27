"""
Views for the businesses app.

Split into two groups:
  1. Public views — browsable by all users (including unauthenticated)
  2. Owner views  — only accessible by authenticated business owners
"""

from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from businesses.filters import BusinessFilter, ProductFilter
from businesses.models import Business, BusinessCategory, Product, ProductCategory, ProductVariant
from businesses.permissions import IsBusinessOwner
from businesses.serializers import (
    BusinessCategorySerializer,
    BusinessDetailSerializer,
    BusinessListSerializer,
    ProductCategoryOwnerSerializer,
    ProductCategoryWithProductsSerializer,
    ProductDetailSerializer,
    ProductOwnerSerializer,
    ProductVariantOwnerSerializer,
)


# ── Public views ──────────────────────────────────────────────────────────────


class BusinessCategoryListView(generics.ListAPIView):
    """
    GET /api/v1/businesses/categories/

    Returns all active business categories, ordered by sort_order.
    """

    permission_classes = [AllowAny]
    serializer_class = BusinessCategorySerializer
    queryset = BusinessCategory.objects.all()
    pagination_class = None  # Small, stable list


class BusinessListView(generics.ListAPIView):
    """
    GET /api/v1/businesses/

    Returns businesses filtered by the user's selected location.
    Supports: ?location=<id>, ?category=<id>, ?is_featured=true, ?search=<term>
    """

    permission_classes = [AllowAny]
    serializer_class = BusinessListSerializer
    filterset_class = BusinessFilter
    search_fields = ["name", "description"]

    def get_queryset(self):
        return (
            Business.objects.select_related("category", "location")
            .all()
        )


class BusinessDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/businesses/{id}/

    Returns full business profile including working hours.
    """

    permission_classes = [AllowAny]
    serializer_class = BusinessDetailSerializer

    def get_queryset(self):
        return (
            Business.objects.select_related("category", "location")
            .prefetch_related("working_hours")
            .all()
        )


class BusinessProductListView(generics.ListAPIView):
    """
    GET /api/v1/businesses/{business_id}/products/

    Returns all products for a business, grouped by ProductCategory.
    Uncategorised products are returned in a separate group.
    Supports: ?product_category=<id>, ?is_available=true
    """

    permission_classes = [AllowAny]
    filterset_class = ProductFilter
    pagination_class = None  # Products within a business — usually a short list

    def get_serializer_class(self):
        return ProductCategoryWithProductsSerializer

    def get_business(self):
        try:
            return Business.objects.get(pk=self.kwargs["business_id"])
        except Business.DoesNotExist:
            raise NotFound("Business not found.")

    def get_queryset(self):
        business = self.get_business()
        return business.product_categories.filter(is_active=True).prefetch_related(
            "products"
        )

    def list(self, request, *args, **kwargs):
        """
        Return structured response:
        {
            "categories": [...],          // products grouped by category
            "uncategorised": [...]        // products with no category
        }
        """
        business = self.get_business()
        categories_qs = self.get_queryset()
        categories_data = ProductCategoryWithProductsSerializer(
            categories_qs, many=True, context={"request": request}
        ).data

        # Products not assigned to any category
        uncategorised_qs = business.products.filter(
            is_active=True, product_category__isnull=True
        )
        uncategorised_data = ProductDetailSerializer(
            uncategorised_qs, many=True, context={"request": request}
        ).data

        return Response({
            "categories": categories_data,
            "uncategorised": uncategorised_data,
        })


class ProductDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/products/{id}/

    Returns full product data including all variants.
    """

    permission_classes = [AllowAny]
    serializer_class = ProductDetailSerializer

    def get_queryset(self):
        return Product.objects.prefetch_related("variants").all()


# ── Owner views ───────────────────────────────────────────────────────────────

class OwnerBusinessView(generics.RetrieveAPIView):
    """
    GET /api/v1/my-business/

    Returns the authenticated business owner's business profile.
    """

    permission_classes = [IsBusinessOwner]
    serializer_class = BusinessDetailSerializer

    def get_object(self):
        return self.request.user.owned_business


class OwnerProductListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/my-business/products/  — List own products
    POST /api/v1/my-business/products/  — Create a new product
    """

    permission_classes = [IsBusinessOwner]
    serializer_class = ProductOwnerSerializer
    filterset_class = ProductFilter

    def get_queryset(self):
        business = self.request.user.owned_business
        return Product.all_objects.filter(business=business).prefetch_related("variants")

    def perform_create(self, serializer):
        serializer.save(business=self.request.user.owned_business)


class OwnerProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/v1/my-business/products/{id}/  — Read product
    PATCH  /api/v1/my-business/products/{id}/  — Update product
    DELETE /api/v1/my-business/products/{id}/  — Soft-delete product
    """

    permission_classes = [IsBusinessOwner]
    serializer_class = ProductOwnerSerializer

    def get_queryset(self):
        business = self.request.user.owned_business
        return Product.all_objects.filter(business=business).prefetch_related("variants")

    def destroy(self, request, *args, **kwargs):
        """Override to soft-delete instead of hard-delete."""
        product = self.get_object()
        product.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = True  # Always PATCH behaviour
        return super().update(request, *args, **kwargs)


class OwnerVariantListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/my-business/products/{product_id}/variants/
    POST /api/v1/my-business/products/{product_id}/variants/
    """

    permission_classes = [IsBusinessOwner]
    serializer_class = ProductVariantOwnerSerializer

    def get_product(self):
        try:
            business = self.request.user.owned_business
            return Product.all_objects.get(
                pk=self.kwargs["product_id"],
                business=business,
            )
        except Product.DoesNotExist:
            raise NotFound("Product not found.")

    def get_queryset(self):
        return self.get_product().variants.all()

    def perform_create(self, serializer):
        serializer.save(product=self.get_product())


class OwnerVariantDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    PATCH  /api/v1/my-business/products/{product_id}/variants/{pk}/
    DELETE /api/v1/my-business/products/{product_id}/variants/{pk}/
    """

    permission_classes = [IsBusinessOwner]
    serializer_class = ProductVariantOwnerSerializer

    def get_queryset(self):
        try:
            business = self.request.user.owned_business
            product = Product.all_objects.get(
                pk=self.kwargs["product_id"],
                business=business,
            )
            return product.variants.all()
        except Product.DoesNotExist:
            raise NotFound("Product not found.")

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return super().update(request, *args, **kwargs)


class OwnerProductCategoryListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/my-business/product-categories/
    POST /api/v1/my-business/product-categories/
    """

    permission_classes = [IsBusinessOwner]
    serializer_class = ProductCategoryOwnerSerializer

    def get_queryset(self):
        business = self.request.user.owned_business
        return ProductCategory.all_objects.filter(business=business)

    def perform_create(self, serializer):
        serializer.save(business=self.request.user.owned_business)


class OwnerProductCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    PATCH  /api/v1/my-business/product-categories/{pk}/
    DELETE /api/v1/my-business/product-categories/{pk}/
    """

    permission_classes = [IsBusinessOwner]
    serializer_class = ProductCategoryOwnerSerializer

    def get_queryset(self):
        business = self.request.user.owned_business
        return ProductCategory.all_objects.filter(business=business)

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        category.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return super().update(request, *args, **kwargs)
