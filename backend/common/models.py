"""
Abstract base models shared across all apps.

Every domain model in TakeWay should inherit from one or more of these
mixins to get consistent timestamp tracking and soft-delete behaviour.
"""

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
