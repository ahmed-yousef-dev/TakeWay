"""
Location models for TakeWay.

Two-level hierarchy: Governorate → Location (City or Village).

All content in the app (businesses, technicians, etc.) is scoped to
a Location, allowing complete isolation between different areas.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import SoftDeleteMixin, TimestampMixin


class Governorate(SoftDeleteMixin, TimestampMixin):
    """
    Top-level geographic unit (e.g., Qalyubia, Menofia).

    Active governorates are shown to users when they select their location.
    """

    name = models.CharField(_("name"), max_length=100, unique=True)

    class Meta:
        verbose_name = _("governorate")
        verbose_name_plural = _("governorates")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Location(SoftDeleteMixin, TimestampMixin):
    """
    A specific city or village within a governorate.

    Each Location has its own delivery fee and minimum order amount,
    reflecting the actual logistics cost to serve that area.
    """

    class LocationType(models.TextChoices):
        CITY = "city", _("City")
        VILLAGE = "village", _("Village")

    name = models.CharField(_("name"), max_length=100)
    governorate = models.ForeignKey(
        Governorate,
        on_delete=models.PROTECT,  # Can't delete a governorate that has locations
        related_name="locations",
        verbose_name=_("governorate"),
    )
    type = models.CharField(
        _("type"),
        max_length=10,
        choices=LocationType.choices,
        default=LocationType.VILLAGE,
    )
    delivery_fee = models.DecimalField(
        _("delivery fee"),
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text=_("Flat delivery fee charged for orders delivered to this location (EGP)."),
    )
    minimum_order_amount = models.DecimalField(
        _("minimum order amount"),
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text=_("Minimum order value required for delivery to this location (EGP)."),
    )

    class Meta:
        verbose_name = _("location")
        verbose_name_plural = _("locations")
        ordering = ["governorate__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "governorate"],
                name="unique_location_per_governorate",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.governorate.name})"
