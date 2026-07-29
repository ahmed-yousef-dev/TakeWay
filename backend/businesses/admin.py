"""
Django Admin configuration for the businesses app.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from businesses.models import (
    Business,
    BusinessCategory,
    Product,
    ProductCategory,
    ProductVariant,
    WorkingHour,
)


@admin.register(BusinessCategory)
class BusinessCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "sort_order", "is_active", "business_count")
    list_editable = ("sort_order", "is_active")
    search_fields = ("name",)
    ordering = ("sort_order", "name")

    @admin.display(description="Businesses")
    def business_count(self, obj):
        return obj.businesses.count()


class WorkingHourInline(admin.TabularInline):
    model = WorkingHour
    extra = 0
    fields = ("day_of_week", "opening_time", "closing_time", "is_closed")


class ProductCategoryInline(admin.TabularInline):
    model = ProductCategory
    extra = 0
    fields = ("name", "sort_order", "is_active")
    show_change_link = True


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "category",
        "location",
        "owner",
        "avg_rating",
        "review_count",
        "is_featured",
        "is_active",
    )
    list_filter = ("category", "location__governorate", "is_featured", "is_active")
    search_fields = ("name", "owner__phone", "owner__name")
    list_editable = ("is_featured", "is_active")
    readonly_fields = ("avg_rating", "review_count", "created_at", "updated_at")
    raw_id_fields = ("owner",)
    inlines = [WorkingHourInline, ProductCategoryInline]

    fieldsets = (
        (None, {"fields": ("name", "description", "category", "location", "owner")}),
        (_("Media"), {"fields": ("logo", "cover_image")}),
        (_("Contact"), {"fields": ("phone", "address")}),
        (_("Status"), {"fields": ("is_featured", "is_active")}),
        (_("Stats"), {"fields": ("avg_rating", "review_count"), "classes": ("collapse",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ("name", "cost_price", "selling_price", "is_available")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "business",
        "product_category",
        "cost_price",
        "selling_price",
        "is_available",
        "is_active",
    )
    list_filter = ("business__location", "business__category", "is_available", "is_active")
    search_fields = ("name", "business__name")
    list_editable = ("is_available", "is_active")
    raw_id_fields = ("business",)
    inlines = [ProductVariantInline]


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "business", "sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "business__name")
    list_editable = ("sort_order", "is_active")
