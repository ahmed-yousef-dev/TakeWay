"""
Factory Boy factories for the businesses app.
"""

import factory

from accounts.tests.factories import BusinessOwnerFactory, UserFactory
from businesses.models import (
    Business,
    BusinessCategory,
    Product,
    ProductCategory,
    ProductVariant,
    WorkingHour,
)
from locations.tests.factories import LocationFactory


class BusinessCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BusinessCategory

    name = factory.Sequence(lambda n: f"Category {n}")
    sort_order = factory.Sequence(lambda n: n)
    is_active = True


class BusinessFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Business

    name = factory.Sequence(lambda n: f"Business {n}")
    description = factory.Faker("sentence")
    category = factory.SubFactory(BusinessCategoryFactory)
    location = factory.SubFactory(LocationFactory)
    owner = factory.SubFactory(BusinessOwnerFactory)
    avg_rating = "4.50"
    review_count = 10
    is_featured = False
    is_active = True


class WorkingHourFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WorkingHour

    business = factory.SubFactory(BusinessFactory)
    day_of_week = WorkingHour.Day.SATURDAY
    opening_time = "09:00:00"
    closing_time = "22:00:00"
    is_closed = False


class ProductCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductCategory

    name = factory.Sequence(lambda n: f"Product Category {n}")
    business = factory.SubFactory(BusinessFactory)
    sort_order = factory.Sequence(lambda n: n)
    is_active = True


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    name = factory.Sequence(lambda n: f"Product {n}")
    description = factory.Faker("sentence")
    business = factory.SubFactory(BusinessFactory)
    product_category = None
    cost_price = "10.00"
    selling_price = "15.00"
    is_available = True
    is_active = True


class ProductVariantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductVariant

    product = factory.SubFactory(ProductFactory)
    name = factory.Sequence(lambda n: f"Variant {n}")
    cost_price = "12.00"
    selling_price = "18.00"
    is_available = True
