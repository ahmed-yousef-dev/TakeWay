"""
Django Admin configuration for the locations app.
"""

from django.contrib import admin

from locations.models import Governorate, Location


class LocationInline(admin.TabularInline):
    """Inline list of locations shown inside Governorate admin."""

    model = Location
    extra = 0
    fields = ("name", "type", "delivery_fee", "minimum_order_amount", "is_active")
    show_change_link = True


@admin.register(Governorate)
class GovernorateAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "location_count", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    inlines = [LocationInline]

    @admin.display(description="Locations")
    def location_count(self, obj):
        return obj.locations.count()


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "governorate",
        "type",
        "delivery_fee",
        "minimum_order_amount",
        "is_active",
    )
    list_filter = ("governorate", "type", "is_active")
    search_fields = ("name", "governorate__name")
    list_editable = ("delivery_fee", "minimum_order_amount", "is_active")
    ordering = ("governorate__name", "name")
