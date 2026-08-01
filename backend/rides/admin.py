"""
Django Admin configuration for the rides app.

Key operational flow:
  - RideRequest: the mediation queue for ride bookings.
    Admin reviews pickup/destination, calls the appropriate vehicle/driver,
    then updates status to approved or rejected. admin_notes records the outcome.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from rides.models import RideRequest


@admin.register(RideRequest)
class RideRequestAdmin(admin.ModelAdmin):
    """
    Mediation queue for ride requests.

    Lifecycle:
      1. Customer submits → status = pending.
      2. Admin reviews pickup + destination, arranges a vehicle.
      3. Admin sets status to approved or rejected.
      4. admin_notes records driver details, ETA, or rejection reason.
    """

    list_display = (
        "id",
        "customer",
        "vehicle_type_display",
        "pickup_location",
        "destination",
        "status_badge",
        "has_gps",
        "created_at",
    )
    list_filter = ("status", "vehicle_type", "created_at")
    search_fields = ("customer__phone", "customer__name", "pickup_location", "destination")
    readonly_fields = (
        "customer",
        "pickup_location",
        "pickup_lat",
        "pickup_lng",
        "destination",
        "destination_lat",
        "destination_lng",
        "vehicle_type",
        "notes",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)

    fieldsets = (
        (_("Request"), {
            "fields": (
                "customer",
                "vehicle_type",
                "notes",
            ),
        }),
        (_("Pickup"), {
            "fields": ("pickup_location", "pickup_lat", "pickup_lng"),
        }),
        (_("Destination"), {
            "fields": ("destination", "destination_lat", "destination_lng"),
        }),
        (_("Lifecycle"), {
            "fields": ("status",),
        }),
        (_("Admin Notes"), {
            "fields": ("admin_notes",),
            "description": _(
                "Record driver name, vehicle plate, ETA, or rejection reason here."
            ),
        }),
        (_("Timestamps"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def has_add_permission(self, request):
        """Requests are created by customers via the API only."""
        return False

    @admin.display(description="Vehicle", ordering="vehicle_type")
    def vehicle_type_display(self, obj):
        return obj.get_vehicle_type_display()

    @admin.display(description="GPS", boolean=True)
    def has_gps(self, obj):
        return obj.pickup_lat is not None and obj.destination_lat is not None

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colours = {
            RideRequest.Status.PENDING:   "#f59e0b",
            RideRequest.Status.APPROVED:  "#22c55e",
            RideRequest.Status.REJECTED:  "#ef4444",
            RideRequest.Status.COMPLETED: "#3b82f6",
        }
        colour = colours.get(obj.status, "#6b7280")
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            colour,
            obj.get_status_display(),
        )
