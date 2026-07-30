"""
Promotions app models for TakeWay.

Models:
  Banner  — Homepage carousel banners, scoped to a Location or global.
  Offer   — Product discount promotions linked to a Business and its Products.

Design decisions:
  - Banner.location is nullable to support global (location-agnostic) banners
    that act as a fallback when no location-specific banner exists.
  - Banner.target_type is a CharField enum (not a ContentType FK) because the
    set of linkable target types is small, fixed, and known at design time.
    Using a full ContentType here would be over-engineering (YAGNI).
  - Offer.products is M2M to Products because a single promotional offer
    (e.g. "Weekend Sale") can apply to multiple items simultaneously.
  - Both models use TimestampMixin for audit trails and SoftDeleteMixin for
    safe deactivation by the ops team without data loss.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import SoftDeleteMixin, TimestampMixin


class Banner(SoftDeleteMixin, TimestampMixin):
    """
    Homepage carousel banner image.

    Banners are location-scoped (shown only in one village/city) OR global
    (location=None), which acts as a fallback for all locations that have no
    locally-scoped banners.

    target_type determines where the banner deep-links inside the app:
      - business    → opens a specific business profile
      - category    → opens a filtered business list by category
      - product     → opens a specific product detail
      - technician  → opens a technician profile
      - external    → opens a URL in a WebView
    """

    class TargetType(models.TextChoices):
        BUSINESS = "business", _("Business")
        CATEGORY = "category", _("Category")
        PRODUCT = "product", _("Product")
        TECHNICIAN = "technician", _("Technician")
        EXTERNAL = "external", _("External URL")

    # ── Content ──────────────────────────────────────────────────────────────

    title = models.CharField(
        _("title"),
        max_length=200,
        help_text=_("Displayed as alt-text / accessibility label."),
    )
    image = models.ImageField(
        _("image"),
        upload_to="promotions/banners/",
    )

    # ── Deep-link target ─────────────────────────────────────────────────────

    target_type = models.CharField(
        _("target type"),
        max_length=20,
        choices=TargetType.choices,
        default=TargetType.EXTERNAL,
    )
    # For business / category / product / technician targets:
    target_id = models.PositiveBigIntegerField(
        _("target ID"),
        null=True,
        blank=True,
        help_text=_("PK of the linked object (leave blank for external URL)."),
    )
    # For external_url targets:
    target_url = models.URLField(
        _("target URL"),
        blank=True,
        default="",
        help_text=_("External URL to open in a WebView (used when target_type=external)."),
    )

    # ── Scoping ───────────────────────────────────────────────────────────────

    location = models.ForeignKey(
        "locations.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="banners",
        help_text=_(
            "Which village/city this banner appears in. "
            "Leave blank to make it a global fallback for all locations."
        ),
    )

    # ── Scheduling & ordering ─────────────────────────────────────────────────

    start_date = models.DateField(
        _("start date"),
        null=True,
        blank=True,
        help_text=_("Banner is hidden before this date. Leave blank to show immediately."),
    )
    end_date = models.DateField(
        _("end date"),
        null=True,
        blank=True,
        help_text=_("Banner is hidden after this date. Leave blank to show indefinitely."),
    )
    sort_order = models.PositiveIntegerField(
        _("sort order"),
        default=0,
        help_text=_("Lower numbers appear first in the carousel."),
    )

    class Meta:
        verbose_name = _("banner")
        verbose_name_plural = _("banners")
        ordering = ["sort_order", "-created_at"]
        indexes = [
            # Primary query: active banners for a given location (or global)
            models.Index(fields=["location", "is_active"], name="banner_location_active_idx"),
        ]

    def __str__(self):
        scope = self.location.name if self.location else "Global"
        return f"[{scope}] {self.title}"


class Offer(SoftDeleteMixin, TimestampMixin):
    """
    A promotional discount linked to a business and one or more of its products.

    discount_type determines how discount_value is applied:
      - percentage  → e.g. 15% off the selling_price
      - fixed       → e.g. EGP 10 off the selling_price

    The actual discounted price is computed in the serializer / API layer,
    not stored on the model, to keep the source of truth in one place.
    """

    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", _("Percentage (%)")
        FIXED = "fixed", _("Fixed Amount")

    # ── Core details ──────────────────────────────────────────────────────────

    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="offers",
    )
    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True, default="")

    # ── Discount ──────────────────────────────────────────────────────────────

    discount_type = models.CharField(
        _("discount type"),
        max_length=20,
        choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE,
    )
    discount_value = models.DecimalField(
        _("discount value"),
        max_digits=8,
        decimal_places=2,
        help_text=_("Percentage (e.g. 15.00) or fixed amount (e.g. 10.00)."),
    )

    # ── Linked products ───────────────────────────────────────────────────────

    products = models.ManyToManyField(
        "businesses.Product",
        blank=True,
        related_name="offers",
        help_text=_("Which products this offer applies to. Leave empty to apply to all business products."),
    )

    # ── Scheduling ────────────────────────────────────────────────────────────

    start_date = models.DateField(
        _("start date"),
        null=True,
        blank=True,
        help_text=_("Offer is inactive before this date."),
    )
    end_date = models.DateField(
        _("end date"),
        null=True,
        blank=True,
        help_text=_("Offer is inactive after this date."),
    )

    class Meta:
        verbose_name = _("offer")
        verbose_name_plural = _("offers")
        ordering = ["-created_at"]
        indexes = [
            # Fast lookup of active offers per business
            models.Index(fields=["business", "is_active"], name="offer_business_active_idx"),
        ]

    def __str__(self):
        return f"{self.title} — {self.business.name} ({self.get_discount_type_display()})"
