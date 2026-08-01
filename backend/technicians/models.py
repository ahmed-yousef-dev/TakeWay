"""
Technician domain models for TakeWay.

Hierarchy:
  TechnicianCategory
    └── Technician (belongs to one Location, one Category)
          └── TechnicianRequest (customer → admin-mediated service request)

Design decisions:
  - Technicians are data entries managed by admin. They do NOT have accounts.
  - Requests are admin-mediated: admin contacts the technician out-of-band,
    then updates the status.
  - avg_rating and review_count are denormalized on Technician (same pattern
    as Business) — updated by a signal when a Review is added via the generic
    Review model in common.
  - Phone number is stored but intentionally NEVER exposed in customer-facing
    API serializers (protects the middleman model).
  - SoftDeleteMixin used on Technician and TechnicianCategory so deactivated
    entries disappear from customer listings without data loss.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import SoftDeleteMixin, TimestampMixin


class TechnicianCategory(SoftDeleteMixin, TimestampMixin):
    """
    Top-level classification for technicians.

    Examples: Electrician, Plumber, Painter, Carpenter, AC Technician.
    Managed by admin — not user-created.
    """

    name = models.CharField(_("name"), max_length=100, unique=True)
    icon = models.ImageField(
        _("icon"),
        upload_to="technician_categories/icons/",
        null=True,
        blank=True,
    )
    sort_order = models.PositiveIntegerField(
        _("sort order"),
        default=0,
        help_text=_("Lower numbers appear first in the category list."),
    )

    class Meta:
        verbose_name = _("technician category")
        verbose_name_plural = _("technician categories")
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Technician(SoftDeleteMixin, TimestampMixin):
    """
    A service technician listed on the platform.

    Technicians are managed by admin — they never log in or have accounts.
    Customers browse the list and submit a TechnicianRequest. TakeWay's
    admin team then contacts the technician out-of-band to arrange the visit.

    Privacy note: the `phone` field must NEVER be included in any
    customer-facing serializer. It is for internal/admin use only.
    """

    name = models.CharField(_("name"), max_length=200)
    category = models.ForeignKey(
        TechnicianCategory,
        on_delete=models.PROTECT,
        related_name="technicians",
        verbose_name=_("category"),
    )
    location = models.ForeignKey(
        "locations.Location",
        on_delete=models.PROTECT,
        related_name="technicians",
        verbose_name=_("location"),
    )
    photo = models.ImageField(
        _("photo"),
        upload_to="technicians/photos/",
        null=True,
        blank=True,
    )
    phone = models.CharField(
        _("phone"),
        max_length=20,
        blank=True,
        help_text=_("Internal use only — NEVER expose this to customers."),
    )
    bio = models.TextField(
        _("bio / description"),
        blank=True,
        help_text=_("Short description of the technician's expertise and experience."),
    )
    years_experience = models.PositiveSmallIntegerField(
        _("years of experience"),
        default=0,
    )
    # Denormalized rating fields — updated by a signal/service when Reviews are added.
    # The Review model in common uses ContentType, so Technician is automatically
    # review-able without any changes to this model.
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
        help_text=_("Featured technicians may appear in the homepage popular section."),
    )

    class Meta:
        verbose_name = _("technician")
        verbose_name_plural = _("technicians")
        ordering = ["-is_featured", "name"]
        indexes = [
            models.Index(
                fields=["location", "is_active"],
                name="technician_location_active_idx",
            ),
            models.Index(
                fields=["category", "is_active"],
                name="technician_category_active_idx",
            ),
        ]

    def __str__(self):
        return f"{self.name} — {self.category.name} ({self.location.name})"


class TechnicianRequest(TimestampMixin):
    """
    A customer's request for a technician's services.

    Flow:
        Customer submits request
        → Admin sees it (status: pending)
        → Admin contacts technician out-of-band
        → Admin approves/rejects and updates status
        → On completion, customer can leave a Review on the Technician

    The `address` FK links to the customer's saved DeliveryAddress so the
    admin knows exactly where to send the technician. `notes` provides
    any extra context the customer wants to share.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")
        COMPLETED = "completed", _("Completed")

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="technician_requests",
        verbose_name=_("customer"),
    )
    technician = models.ForeignKey(
        Technician,
        on_delete=models.PROTECT,
        related_name="requests",
        verbose_name=_("technician"),
    )
    address = models.ForeignKey(
        "orders.DeliveryAddress",
        on_delete=models.PROTECT,
        related_name="technician_requests",
        verbose_name=_("service address"),
        help_text=_("The customer's address where the technician should visit."),
    )
    notes = models.TextField(
        _("notes"),
        blank=True,
        help_text=_("Customer's description of the problem or additional context."),
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    admin_notes = models.TextField(
        _("admin notes"),
        blank=True,
        help_text=_("Internal notes visible only to admin (e.g. technician feedback, scheduling info)."),
    )

    class Meta:
        verbose_name = _("technician request")
        verbose_name_plural = _("technician requests")
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["customer", "status"],
                name="techreq_customer_status_idx",
            ),
            models.Index(
                fields=["technician", "status"],
                name="techreq_technician_status_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Request #{self.pk} — {self.customer} → {self.technician.name} "
            f"[{self.get_status_display()}]"
        )
