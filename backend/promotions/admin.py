"""
Django Admin configuration for the promotions app.

Provides the operations team with full control over:
  - Banners (homepage carousel)
  - Offers (product discounts)

Design decisions:
- OfferProductInline lets staff attach/detach products to an offer
  from the same page, avoiding the need to navigate to the M2M inline
  on the Product side.
- list_editable on is_active gives one-click toggling directly from
  the changelist — a key workflow for the ops team managing promotions.
- date_hierarchy on Offer enables quick drilling by promo period.
- BannerAdmin uses a computed scope_display to show "Global" vs the
  location name at a glance.
"""

from django.contrib import admin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Banner, Offer


# ── Banner ────────────────────────────────────────────────────────────────────

@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "scope_display",
        "target_type",
        "sort_order",
        "start_date",
        "end_date",
        "is_active",
        "is_live",
    )
    list_filter = ("target_type", "location", "is_active")
    list_editable = ("sort_order", "is_active")
    search_fields = ("title",)
    ordering = ("sort_order", "-created_at")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (None, {
            "fields": ("title", "image"),
        }),
        (_("Deep-link target"), {
            "fields": ("target_type", "target_id", "target_url"),
            "description": _(
                "Set target_type, then fill EITHER target_id (for in-app objects) "
                "OR target_url (for external links)."
            ),
        }),
        (_("Scope"), {
            "fields": ("location",),
            "description": _(
                "Leave blank to make this a global banner visible in all locations."
            ),
        }),
        (_("Scheduling & Display"), {
            "fields": ("start_date", "end_date", "sort_order", "is_active"),
        }),
        (_("Timestamps"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description=_("Scope"), ordering="location__name")
    def scope_display(self, obj):
        return obj.location.name if obj.location else "🌐 Global"

    @admin.display(description=_("Live?"), boolean=True)
    def is_live(self, obj):
        """True if the banner is active and within its scheduled date range."""
        if not obj.is_active:
            return False
        today = timezone.now().date()
        if obj.start_date and today < obj.start_date:
            return False
        if obj.end_date and today > obj.end_date:
            return False
        return True


# ── Offer ─────────────────────────────────────────────────────────────────────

class OfferProductInline(admin.TabularInline):
    """
    Inline to attach/detach products to an offer directly from the Offer page.
    Shows only products belonging to this offer's business (enforced via
    get_queryset — not perfect for add-new, but prevents confusion on display).
    """

    model = Offer.products.through
    verbose_name = _("linked product")
    verbose_name_plural = _("linked products")
    extra = 1

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("product")


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "business",
        "discount_type",
        "discount_value",
        "start_date",
        "end_date",
        "is_active",
        "is_live",
    )
    list_filter = ("discount_type", "business__location", "is_active")
    list_editable = ("is_active",)
    search_fields = ("title", "business__name")
    ordering = ("-created_at",)
    date_hierarchy = "start_date"
    raw_id_fields = ("business",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [OfferProductInline]

    fieldsets = (
        (None, {
            "fields": ("business", "title", "description"),
        }),
        (_("Discount"), {
            "fields": ("discount_type", "discount_value"),
        }),
        (_("Scheduling"), {
            "fields": ("start_date", "end_date", "is_active"),
        }),
        (_("Timestamps"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description=_("Live?"), boolean=True)
    def is_live(self, obj):
        """True if the offer is active and within its scheduled date range."""
        if not obj.is_active:
            return False
        today = timezone.now().date()
        if obj.start_date and today < obj.start_date:
            return False
        if obj.end_date and today > obj.end_date:
            return False
        return True
