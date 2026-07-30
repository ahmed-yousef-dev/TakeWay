"""
Django Admin configuration for the orders app.

Covers all Phase 1B commerce models:
  - DeliveryAddress
  - Cart / CartItem  (read-only inspection view)
  - Order / SubOrder / OrderItem  (with inline drill-down and status management)
  - AnythingRequest / AnythingRequestImage  (with admin-mediated lifecycle)
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from orders.models import (
    AnythingRequest,
    AnythingRequestImage,
    Cart,
    CartItem,
    DeliveryAddress,
    Order,
    OrderItem,
    SubOrder,
)


# ---------------------------------------------------------------------------
# DeliveryAddress
# ---------------------------------------------------------------------------

@admin.register(DeliveryAddress)
class DeliveryAddressAdmin(admin.ModelAdmin):
    """
    Saved delivery addresses for customers.
    Admins need this to cross-reference orders and anything-requests.
    """

    list_display = ("id", "user", "label", "address_details", "has_gps", "is_active", "created_at")
    list_filter = ("label", "is_active")
    search_fields = ("user__phone", "user__name", "address_details")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("user",)
    ordering = ("-created_at",)

    @admin.display(description="GPS", boolean=True)
    def has_gps(self, obj):
        return obj.latitude is not None and obj.longitude is not None


# ---------------------------------------------------------------------------
# Cart (read-only inspection)
# ---------------------------------------------------------------------------

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    fields = ("product", "variant", "quantity", "note", "created_at")
    readonly_fields = ("created_at",)
    raw_id_fields = ("product", "variant")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """
    Read-only cart inspection. Useful for debugging customer issues.
    Mutations happen through the API only.
    """

    list_display = ("id", "user", "item_count", "created_at", "updated_at")
    search_fields = ("user__phone", "user__name")
    readonly_fields = ("user", "created_at", "updated_at")
    inlines = [CartItemInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Items")
    def item_count(self, obj):
        return obj.items.count()


# ---------------------------------------------------------------------------
# Order → SubOrder → OrderItem  (nested inlines)
# ---------------------------------------------------------------------------

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = (
        "product_name",
        "variant_name",
        "unit_price",
        "quantity",
        "total_price",
        "note",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SubOrder)
class SubOrderAdmin(admin.ModelAdmin):
    """
    Individual sub-orders grouped by business.
    Accessible from the Order change page via inline; also registered
    standalone so staff can filter/search sub-orders directly.
    """

    list_display = ("id", "order", "business", "subtotal", "item_count", "created_at")
    list_filter = ("business",)
    search_fields = ("order__id", "business__name", "order__customer__phone")
    readonly_fields = ("order", "business", "subtotal", "created_at")
    raw_id_fields = ()
    inlines = [OrderItemInline]

    def has_add_permission(self, request):
        return False

    @admin.display(description="Items")
    def item_count(self, obj):
        return obj.items.count()


class SubOrderInline(admin.StackedInline):
    model = SubOrder
    extra = 0
    fields = ("business", "subtotal")
    readonly_fields = ("business", "subtotal")
    show_change_link = True  # lets admin drill into SubOrderAdmin

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """
    Parent order admin.

    Key operational actions:
      - Filter by status to manage the fulfilment queue.
      - Use list_editable status to bulk-update orders.
      - Drill into sub-orders via inline links.
    """

    list_display = (
        "id",
        "customer",
        "status_badge",
        "subtotal",
        "delivery_fee",
        "total_amount",
        "business_count",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("id", "customer__phone", "customer__name")
    readonly_fields = (
        "customer",
        "delivery_address",
        "subtotal",
        "delivery_fee",
        "total_amount",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)
    inlines = [SubOrderInline]

    fieldsets = (
        (None, {
            "fields": ("customer", "delivery_address", "status"),
        }),
        (_("Totals"), {
            "fields": ("subtotal", "delivery_fee", "total_amount"),
        }),
        (_("Timestamps"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def has_add_permission(self, request):
        """Orders are created only via the checkout API.\u00a0No manual creation."""
        return False

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colours = {
            Order.Status.PENDING:   "#f59e0b",   # amber
            Order.Status.ACCEPTED:  "#3b82f6",   # blue
            Order.Status.ON_WAY:    "#8b5cf6",   # violet
            Order.Status.DELIVERED: "#22c55e",   # green
            Order.Status.CANCELLED: "#ef4444",   # red
        }
        colour = colours.get(obj.status, "#6b7280")
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            colour,
            obj.get_status_display(),
        )

    @admin.display(description="Businesses")
    def business_count(self, obj):
        return obj.sub_orders.count()


# ---------------------------------------------------------------------------
# AnythingRequest
# ---------------------------------------------------------------------------

class AnythingRequestImageInline(admin.TabularInline):
    model = AnythingRequestImage
    extra = 0
    fields = ("image", "image_preview")
    readonly_fields = ("image_preview",)

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Preview")
    def image_preview(self, obj):
        if obj.pk and obj.image:
            return format_html(
                '<img src="{}" style="max-height:80px;border-radius:4px;" />',
                obj.image.url,
            )
        return "—"


@admin.register(AnythingRequest)
class AnythingRequestAdmin(admin.ModelAdmin):
    """
    Admin-mediated "Order Anything" feature.

    Operational lifecycle:
      1. Customer submits → status = pending.
      2. Admin reviews images + text, calls customer to confirm price.
      3. Admin sets status to quoted / accepted / rejected.
      4. On acceptance, admin may manually convert to a regular Order and
         link it by setting the order field (future Phase 1B+ enhancement).

    ``admin_note`` is the internal scratchpad between staff members and is
    surfaced to the customer on the detail API (quotes, clarifications).
    """

    list_display = (
        "id",
        "customer",
        "status_badge",
        "short_text",
        "delivery_address",
        "image_count",
        "is_active",
        "created_at",
    )
    list_filter = ("status", "is_active", "created_at")
    search_fields = ("customer__phone", "customer__name", "request_text")
    readonly_fields = ("customer", "delivery_address", "created_at", "updated_at")
    raw_id_fields = ()
    ordering = ("-created_at",)
    inlines = [AnythingRequestImageInline]

    fieldsets = (
        (None, {
            "fields": ("customer", "delivery_address", "request_text"),
        }),
        (_("Lifecycle"), {
            "fields": ("status", "is_active"),
        }),
        (_("Admin Notes"), {
            "fields": ("admin_note",),
            "description": _(
                "Use this field to record quotes, prices, or any internal notes. "
                "This note is visible to the customer via the mobile app."
            ),
        }),
        (_("Timestamps"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colours = {
            AnythingRequest.Status.PENDING:  "#f59e0b",
            AnythingRequest.Status.QUOTED:   "#3b82f6",
            AnythingRequest.Status.ACCEPTED: "#22c55e",
            AnythingRequest.Status.REJECTED: "#ef4444",
            AnythingRequest.Status.ORDERED:  "#8b5cf6",
        }
        colour = colours.get(obj.status, "#6b7280")
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            colour,
            obj.get_status_display(),
        )

    @admin.display(description="Request")
    def short_text(self, obj):
        text = obj.request_text
        return text[:60] + "…" if len(text) > 60 else text

    @admin.display(description="Images")
    def image_count(self, obj):
        return obj.images.count()
