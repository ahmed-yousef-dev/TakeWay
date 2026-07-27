"""
Business domain models for TakeWay.

Hierarchy:
  BusinessCategory
    └── Business (belongs to one Location, one Category, has one Owner)
          ├── WorkingHour (7 rows per business)
          ├── ProductCategory (optional grouping within a business)
          └── Product
                └── ProductVariant (optional size/type variants)

Design decisions:
  - Single category per business (no M2M) for simplicity.
  - Products have cost_price + selling_price for flexible revenue model.
  - avg_rating and review_count are denormalized on Business for
    fast sorting/display without aggregation queries.
  - Soft delete via SoftDeleteMixin on all customer-facing models.
"""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import SoftDeleteMixin, TimestampMixin


class BusinessCategory(SoftDeleteMixin, TimestampMixin):
    """
    Top-level classification for businesses.

    Examples: Restaurant, Pharmacy, Bakery, Supermarket, Electronics.
    Managed by admin — not user-created.
    """

    name = models.CharField(_("name"), max_length=100, unique=True)
    icon = models.ImageField(
        _("icon"),
        upload_to="business_categories/icons/",
        null=True,
        blank=True,
    )
    sort_order = models.PositiveIntegerField(
        _("sort order"),
        default=0,
        help_text=_("Lower numbers appear first in the category list."),
    )

    class Meta:
        verbose_name = _("business category")
        verbose_name_plural = _("business categories")
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Business(SoftDeleteMixin, TimestampMixin):
    """
    A shop, restaurant, or any service provider in a location.

    Owned by a User with the business_owner role.
    Orders are NOT fulfilled by the business — TakeWay's team purchases
    items on behalf of customers.
    """

    name = models.CharField(_("name"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    category = models.ForeignKey(
        BusinessCategory,
        on_delete=models.PROTECT,
        related_name="businesses",
        verbose_name=_("category"),
    )
    location = models.ForeignKey(
        "locations.Location",
        on_delete=models.PROTECT,
        related_name="businesses",
        verbose_name=_("location"),
    )
    owner = models.OneToOneField(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_business",
        verbose_name=_("owner"),
        help_text=_("The business owner's app account. Created by admin during onboarding."),
    )
    logo = models.ImageField(
        _("logo"),
        upload_to="businesses/logos/",
        null=True,
        blank=True,
    )
    cover_image = models.ImageField(
        _("cover image"),
        upload_to="businesses/covers/",
        null=True,
        blank=True,
    )
    phone = models.CharField(
        _("phone"),
        max_length=15,
        blank=True,
        help_text=_("Business contact phone number (for display purposes)."),
    )
    address = models.TextField(
        _("address"),
        blank=True,
        help_text=_("Physical address / landmark description."),
    )
    # Denormalized rating fields — updated by a signal/service when reviews are added
    avg_rating = models.DecimalField(
        _("average rating"),
        max_digits=3,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )
    review_count = models.PositiveIntegerField(_("review count"), default=0)
    is_featured = models.BooleanField(
        _("is featured"),
        default=False,
        help_text=_("Featured businesses appear in the homepage featured section."),
    )

    class Meta:
        verbose_name = _("business")
        verbose_name_plural = _("businesses")
        ordering = ["-is_featured", "name"]
        indexes = [
            models.Index(fields=["location", "is_active"], name="business_location_active_idx"),
            models.Index(fields=["category", "is_active"], name="business_category_active_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.location.name})"


class WorkingHour(models.Model):
    """
    Operating hours for a business on a specific day of the week.

    7 rows per business (one per day). is_closed overrides the time fields.

    Note: Day 0 = Saturday (Egyptian week starts on Saturday).
    """

    class Day(models.IntegerChoices):
        SATURDAY = 0, _("Saturday")
        SUNDAY = 1, _("Sunday")
        MONDAY = 2, _("Monday")
        TUESDAY = 3, _("Tuesday")
        WEDNESDAY = 4, _("Wednesday")
        THURSDAY = 5, _("Thursday")
        FRIDAY = 6, _("Friday")

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="working_hours",
        verbose_name=_("business"),
    )
    day_of_week = models.IntegerField(_("day of week"), choices=Day.choices)
    opening_time = models.TimeField(_("opening time"), null=True, blank=True)
    closing_time = models.TimeField(_("closing time"), null=True, blank=True)
    is_closed = models.BooleanField(
        _("is closed"),
        default=False,
        help_text=_("If checked, this business is closed on this day."),
    )

    class Meta:
        verbose_name = _("working hour")
        verbose_name_plural = _("working hours")
        ordering = ["day_of_week"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "day_of_week"],
                name="unique_working_hour_per_day",
            )
        ]

    def __str__(self):
        day_name = self.Day(self.day_of_week).label
        if self.is_closed:
            return f"{self.business.name} — {day_name}: Closed"
        return f"{self.business.name} — {day_name}: {self.opening_time}–{self.closing_time}"


class ProductCategory(SoftDeleteMixin, TimestampMixin):
    """
    Optional grouping of products within a single business.

    Examples: "Appetizers", "Main Course", "Drinks" (for a restaurant),
    or "Dairy", "Vegetables" (for a supermarket).
    """

    name = models.CharField(_("name"), max_length=100)
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="product_categories",
        verbose_name=_("business"),
    )
    sort_order = models.PositiveIntegerField(_("sort order"), default=0)

    class Meta:
        verbose_name = _("product category")
        verbose_name_plural = _("product categories")
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "business"],
                name="unique_product_category_per_business",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.business.name})"


class Product(SoftDeleteMixin, TimestampMixin):
    """
    An item available for purchase from a business.

    - selling_price is what the customer pays (shown in the app).
    - cost_price is what the shop charges (admin/owner only — never exposed to customers).
    - is_available allows the business owner to temporarily hide an item.
    - If the product has ProductVariant rows, those override the base price.
    """

    name = models.CharField(_("name"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="products",
        verbose_name=_("business"),
    )
    product_category = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        verbose_name=_("product category"),
    )
    image = models.ImageField(
        _("image"),
        upload_to="products/",
        null=True,
        blank=True,
    )
    cost_price = models.DecimalField(
        _("cost price"),
        max_digits=10,
        decimal_places=2,
        help_text=_("What the shop charges. Never shown to customers."),
    )
    selling_price = models.DecimalField(
        _("selling price"),
        max_digits=10,
        decimal_places=2,
        help_text=_("What the customer pays."),
    )
    is_available = models.BooleanField(
        _("is available"),
        default=True,
        help_text=_("Uncheck to hide from customers when the item is out of stock."),
    )

    class Meta:
        verbose_name = _("product")
        verbose_name_plural = _("products")
        ordering = ["product_category__sort_order", "name"]
        indexes = [
            models.Index(
                fields=["business", "is_active", "is_available"],
                name="product_biz_active_avail_idx",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.business.name})"

    @property
    def has_variants(self):
        return self.variants.filter(is_available=True).exists()


class ProductVariant(models.Model):
    """
    An optional variant of a Product (e.g., size, type).

    When variants exist, customers choose one instead of the base product.
    Each variant has its own price pair.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
        verbose_name=_("product"),
    )
    name = models.CharField(
        _("name"),
        max_length=100,
        help_text=_("e.g. 'Small', 'Large', 'Sugar-free'"),
    )
    cost_price = models.DecimalField(_("cost price"), max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(_("selling price"), max_digits=10, decimal_places=2)
    is_available = models.BooleanField(_("is available"), default=True)

    class Meta:
        verbose_name = _("product variant")
        verbose_name_plural = _("product variants")
        ordering = ["selling_price"]

    def __str__(self):
        return f"{self.product.name} — {self.name}"
