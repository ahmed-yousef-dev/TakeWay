"""
Django Admin configuration for the technicians app.

Key operational flows:
  - TechnicianCategory: manage icons and sort order.
  - Technician: manage the catalogue — photo, bio, featured flag.
    Phone is VISIBLE to admins (needed to dispatch technician) but is
    read-only in the list to avoid accidental bulk edits.
  - TechnicianRequest: the core mediation queue.
    Admins review the customer's address and notes, then call the technician
    and set status to approved/rejected. admin_notes is the internal scratchpad.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from technicians.models import Technician, TechnicianCategory, TechnicianRequest


@admin.register(TechnicianCategory)
class TechnicianCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "icon", "sort_order", "is_active", "technician_count")
    list_editable = ("sort_order", "is_active")
    search_fields = ("name",)
    ordering = ("sort_order", "name")

    @admin.display(description="Technicians")
    def technician_count(self, obj):
        return obj.technicians.count()


@admin.register(Technician)
class TechnicianAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "category",
        "location",
        "years_experience",
        "avg_rating",
        "review_count",
        "is_featured",
        "is_active",
    )
    list_filter = ("category", "location__governorate", "is_featured", "is_active")
    search_fields = ("name", "phone", "bio")
    list_editable = ("is_featured", "is_active")
    readonly_fields = ("avg_rating", "review_count", "created_at", "updated_at")

    fieldsets = (
        (None, {
            "fields": ("name", "category", "location", "photo"),
        }),
        (_("Profile"), {
            "fields": ("bio", "years_experience"),
        }),
        # Phone is visible to admins — they need it to dispatch the technician.
        # NEVER expose this in customer-facing serializers.
        (_("Contact (Admin Only)"), {
            "fields": ("phone",),
            "description": _(
                "⚠️ This phone number is NEVER shown to customers. "
                "Admins use it to coordinate with the technician directly."
            ),
        }),
        (_("Status"), {
            "fields": ("is_featured", "is_active"),
        }),
        (_("Stats (auto-calculated)"), {
            "fields": ("avg_rating", "review_count"),
            "classes": ("collapse",),
        }),
        (_("Timestamps"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(TechnicianRequest)
class TechnicianRequestAdmin(admin.ModelAdmin):
    """
    Core mediation queue for the operations team.

    Lifecycle:
      1. Customer submits → status = pending.
      2. Admin reviews address + notes, calls the technician to arrange.
      3. Admin sets status to approved or rejected.
      4. admin_notes records outcome / internal details.
    """

    list_display = (
        "id",
        "customer",
        "technician",
        "status_badge",
        "address",
        "created_at",
    )
    list_filter = ("status", "technician__category", "created_at")
    search_fields = (
        "customer__phone",
        "customer__name",
        "technician__name",
        "notes",
    )
    readonly_fields = ("customer", "technician", "address", "notes", "created_at", "updated_at")
    ordering = ("-created_at",)

    fieldsets = (
        (_("Request"), {
            "fields": ("customer", "technician", "address", "notes"),
        }),
        (_("Lifecycle"), {
            "fields": ("status",),
        }),
        (_("Admin Notes"), {
            "fields": ("admin_notes",),
            "description": _(
                "Use this field to record the outcome of your call with the technician, "
                "scheduling details, or any internal notes."
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

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colours = {
            TechnicianRequest.Status.PENDING:   "#f59e0b",
            TechnicianRequest.Status.APPROVED:  "#22c55e",
            TechnicianRequest.Status.REJECTED:  "#ef4444",
            TechnicianRequest.Status.COMPLETED: "#3b82f6",
        }
        colour = colours.get(obj.status, "#6b7280")
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            colour,
            obj.get_status_display(),
        )
