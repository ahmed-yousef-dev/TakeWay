"""
Abstract base models shared across all apps.

Includes:
- TimestampMixin: created_at / updated_at
- SoftDeleteMixin: is_active soft-delete with custom manager
- Review: generic, ContentType-based customer review model
- Favorite: generic, ContentType-based customer favorite model
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class SoftDeleteManager(models.Manager):
    """Default manager: returns only active (non-soft-deleted) records."""

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class TimestampMixin(models.Model):
    """
    Adds created_at and updated_at to any model.
    Both fields are managed automatically by Django.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    """
    Adds is_active soft-delete behaviour.

    - The default manager (objects) only returns active records.
    - Use all_objects to bypass the filter (e.g. in admin or migrations).
    - Call .soft_delete() instead of .delete() for soft deletion.
    """

    is_active = models.BooleanField(default=True, db_index=True)

    objects = SoftDeleteManager()       # Filtered: active only
    all_objects = models.Manager()      # Unfiltered: all records

    def soft_delete(self):
        """Mark this record as inactive without removing it from the DB."""
        self.is_active = False
        # Only update the two fields we changed — avoids race conditions
        update_fields = ["is_active"]
        if hasattr(self, "updated_at"):
            update_fields.append("updated_at")
        self.save(update_fields=update_fields)

    class Meta:
        abstract = True


# ── Concrete generic models ───────────────────────────────────────────────────

class Review(models.Model):
    """
    A generic, ContentType-based review that can be attached to any model
    (Business, Technician, etc.) without modifying those models.

    Design decisions:
    - ContentType + object_id gives full flexibility to review any entity.
    - rating is validated 1-5 at the model layer (DB check constraint added
      by Django's MinValueValidator / MaxValueValidator via form/serializer
      validation; the validators themselves live on the field).
    - One review per user per reviewed object is enforced by the unique_together
      constraint, preventing spam and duplicate ratings.
    - comment is optional — a star rating alone is a valid review.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="The type of the reviewed object (e.g. Business, Technician).",
    )
    object_id = models.PositiveBigIntegerField(
        help_text="The primary key of the reviewed object.",
    )
    content_object = GenericForeignKey("content_type", "object_id")

    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 (worst) to 5 (best).",
    )
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Review"
        verbose_name_plural = "Reviews"
        # One review per user per entity (business, technician, …)
        unique_together = [("user", "content_type", "object_id")]
        indexes = [
            # Fast lookup of all reviews for a given object
            models.Index(fields=["content_type", "object_id"], name="review_ct_obj_idx"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Review by {self.user} on {self.content_type.model}#{self.object_id} "
            f"— {self.rating}★"
        )


class Favorite(models.Model):
    """
    A generic, ContentType-based favorite that can be attached to any model
    (Business, Technician, etc.).

    Design decisions:
    - Same ContentType pattern as Review for maximum extensibility.
    - Unique constraint on (user, content_type, object_id) prevents duplicate
      favorites and allows safe toggle logic: try to create → catch IntegrityError.
    - No soft-delete here — favorites are simply created or deleted (hard delete).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="The type of the favorited object (e.g. Business, Technician).",
    )
    object_id = models.PositiveBigIntegerField(
        help_text="The primary key of the favorited object.",
    )
    content_object = GenericForeignKey("content_type", "object_id")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Favorite"
        verbose_name_plural = "Favorites"
        # Prevents a user from favoriting the same entity twice
        unique_together = [("user", "content_type", "object_id")]
        indexes = [
            # Fast lookup of all favorites for a given object
            models.Index(fields=["content_type", "object_id"], name="favorite_ct_obj_idx"),
            # Fast lookup of all favorites for a given user
            models.Index(fields=["user", "content_type"], name="favorite_user_ct_idx"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Favorite by {self.user}: {self.content_type.model}#{self.object_id}"
