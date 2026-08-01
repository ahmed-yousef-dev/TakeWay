"""
Ride booking models for TakeWay.

Design decisions:
  - Simplified, admin-mediated ride requests — NOT a full ride-hailing system.
  - Pickup and destination are stored as free-text strings (villages often lack
    formal addresses; users describe landmarks like "next to the big mosque").
  - Optional lat/lng fields on both ends allow precise GPS pins without
    requiring them — mirrors the pattern in orders.DeliveryAddress.
  - Flow: Customer submits → Admin coordinates with driver out-of-band
    → Admin updates status.
  - No driver accounts; no real-time tracking (Phase 1 scope).
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import TimestampMixin


class RideRequest(TimestampMixin):
    """
    A customer request for a ride (tuk-tuk or car).

    TakeWay acts as the middleman: the admin team coordinates with drivers
    out-of-band. The customer provides pickup and destination details as
    free text (with optional GPS coordinates for precision).

    Status flow:
        pending → approved → completed
            ↓
          rejected
    """

    class VehicleType(models.TextChoices):
        TUK_TUK = "tuk_tuk", _("Tuk-Tuk")
        CAR = "car", _("Car")

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")
        COMPLETED = "completed", _("Completed")

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ride_requests",
        verbose_name=_("customer"),
    )

    # ── Pickup ────────────────────────────────────────────────────────────────
    pickup_location = models.TextField(
        _("pickup location"),
        help_text=_("Free-text description, e.g. 'Next to the main mosque in Arab El-Raml'."),
    )
    pickup_lat = models.DecimalField(
        _("pickup latitude"),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text=_("Optional GPS latitude for precise pickup pinning."),
    )
    pickup_lng = models.DecimalField(
        _("pickup longitude"),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text=_("Optional GPS longitude for precise pickup pinning."),
    )

    # ── Destination ───────────────────────────────────────────────────────────
    destination = models.TextField(
        _("destination"),
        help_text=_("Free-text description of where the customer wants to go."),
    )
    destination_lat = models.DecimalField(
        _("destination latitude"),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text=_("Optional GPS latitude for precise destination pinning."),
    )
    destination_lng = models.DecimalField(
        _("destination longitude"),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text=_("Optional GPS longitude for precise destination pinning."),
    )

    # ── Request details ───────────────────────────────────────────────────────
    vehicle_type = models.CharField(
        _("vehicle type"),
        max_length=20,
        choices=VehicleType.choices,
        default=VehicleType.TUK_TUK,
    )
    notes = models.TextField(
        _("notes"),
        blank=True,
        help_text=_("Any additional context from the customer (e.g. number of passengers, luggage)."),
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
        help_text=_("Internal notes visible only to admin (e.g. driver name, ETA, reason for rejection)."),
    )

    class Meta:
        verbose_name = _("ride request")
        verbose_name_plural = _("ride requests")
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["customer", "status"],
                name="ridereq_customer_status_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Ride #{self.pk} — {self.customer} | "
            f"{self.get_vehicle_type_display()} | "
            f"[{self.get_status_display()}]"
        )
