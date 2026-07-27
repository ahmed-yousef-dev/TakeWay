"""
Django-filter FilterSets for the businesses app.
"""

import django_filters

from businesses.models import Business, Product


class BusinessFilter(django_filters.FilterSet):
    """
    Allows filtering the business list by location, category, and featured flag.
    All filters use the query parameter names directly.

    Example: /api/v1/businesses/?location=3&category=1&is_featured=true
    """

    class Meta:
        model = Business
        fields = {
            "location": ["exact"],
            "category": ["exact"],
            "is_featured": ["exact"],
        }


class ProductFilter(django_filters.FilterSet):
    """
    Allows filtering a business's products by category and availability.

    Example: /api/v1/businesses/5/products/?product_category=2&is_available=true
    """

    class Meta:
        model = Product
        fields = {
            "product_category": ["exact"],
            "is_available": ["exact"],
        }
