"""
Serializers for the common app (Review & Favorite).

Design decisions:
- `content_type_str` is accepted as a human-readable string on write
  (e.g. "business", "technician") and resolved to a ContentType PK
  internally. This hides Django internals from the mobile client.
- On read, `content_type_str` + `object_id` are returned so the client
  knows what entity was reviewed / favorited.
- Review eligibility (completed order) is enforced in ReviewCreateSerializer
  .validate() rather than the view, keeping validation logic close to the data.
"""

from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from orders.models import Order, SubOrder
from .models import Favorite, Review


# Allowed content-type slugs the client can submit.
# Extend this dict as new reviewable/favoriteable entities are added.
ALLOWED_CT_SLUGS = {
    "business": ("businesses", "business"),
    "technician": ("technicians", "technician"),  # future
}


def resolve_content_type(slug: str) -> ContentType:
    """
    Convert a client-supplied slug (e.g. 'business') to a ContentType instance.
    Raises ValidationError if the slug is unknown.
    """
    if slug not in ALLOWED_CT_SLUGS:
        raise serializers.ValidationError(
            f"Invalid content_type '{slug}'. "
            f"Allowed values: {', '.join(ALLOWED_CT_SLUGS.keys())}."
        )
    app_label, model = ALLOWED_CT_SLUGS[slug]
    try:
        return ContentType.objects.get(app_label=app_label, model=model)
    except ContentType.DoesNotExist:
        raise serializers.ValidationError(
            f"Content type '{slug}' is not yet available in this environment."
        )


# ── Review serializers ────────────────────────────────────────────────────────

class ReviewSerializer(serializers.ModelSerializer):
    """Read-only representation of a Review (used in list/retrieve)."""

    content_type_str = serializers.SerializerMethodField()
    user_name = serializers.CharField(source="user.name", read_only=True)

    class Meta:
        model = Review
        fields = [
            "id",
            "user_name",
            "content_type_str",
            "object_id",
            "rating",
            "comment",
            "created_at",
        ]

    def get_content_type_str(self, obj) -> str:
        return obj.content_type.model


class ReviewCreateSerializer(serializers.ModelSerializer):
    """
    Write serializer for creating a Review.

    Validates:
    1. content_type is a valid, allowed slug.
    2. The target object actually exists.
    3. The authenticated user has a DELIVERED Order that includes the target
       business (eligibility rule). For Phase 1 this only applies to Business
       reviews; the same pattern will extend to Technicians in Phase 1C.
    4. The user has not already reviewed this object (DB unique_together is a
       safety net but we surface a clear error here).
    """

    content_type_str = serializers.ChoiceField(
        choices=list(ALLOWED_CT_SLUGS.keys()),
        write_only=True,
        help_text="Entity type to review: 'business' or 'technician'.",
    )

    class Meta:
        model = Review
        fields = ["content_type_str", "object_id", "rating", "comment"]

    def validate(self, attrs):
        user = self.context["request"].user
        slug = attrs.pop("content_type_str")
        content_type = resolve_content_type(slug)
        object_id = attrs["object_id"]

        # ── 1. Target object must exist ───────────────────────────────────────
        model_class = content_type.model_class()
        if not model_class.objects.filter(pk=object_id).exists():
            raise serializers.ValidationError(
                {"object_id": f"No {slug} with id={object_id} found."}
            )

        # ── 2. Duplicate review check ─────────────────────────────────────────
        if Review.objects.filter(
            user=user, content_type=content_type, object_id=object_id
        ).exists():
            raise serializers.ValidationError(
                f"You have already reviewed this {slug}."
            )

        # ── 3. Eligibility: must have a DELIVERED order for this business ─────
        #    Currently enforced only for 'business'. When Technician reviews
        #    are enabled (Phase 1C), extend this block.
        if slug == "business":
            has_completed_order = SubOrder.objects.filter(
                order__customer=user,
                order__status=Order.Status.DELIVERED,
                business_id=object_id,
            ).exists()
            if not has_completed_order:
                raise serializers.ValidationError(
                    "You can only review a business after a delivered order from it."
                )

        attrs["content_type"] = content_type
        attrs["user"] = user
        return attrs

    def create(self, validated_data):
        return Review.objects.create(**validated_data)


# ── Favorite serializers ──────────────────────────────────────────────────────

class FavoriteSerializer(serializers.ModelSerializer):
    """Read-only representation of a Favorite."""

    content_type_str = serializers.SerializerMethodField()

    class Meta:
        model = Favorite
        fields = ["id", "content_type_str", "object_id", "created_at"]

    def get_content_type_str(self, obj) -> str:
        return obj.content_type.model


class FavoriteCreateSerializer(serializers.Serializer):
    """
    Write serializer for toggling a Favorite (create or delete).

    Uses a plain Serializer (not ModelSerializer) because the toggle
    endpoint may return either a created Favorite or a 204 No Content.
    """

    content_type_str = serializers.ChoiceField(
        choices=list(ALLOWED_CT_SLUGS.keys()),
        help_text="Entity type to favorite: 'business' or 'technician'.",
    )
    object_id = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        slug = attrs["content_type_str"]
        content_type = resolve_content_type(slug)
        object_id = attrs["object_id"]

        # Target object must exist
        model_class = content_type.model_class()
        if not model_class.objects.filter(pk=object_id).exists():
            raise serializers.ValidationError(
                {"object_id": f"No {slug} with id={object_id} found."}
            )

        attrs["content_type"] = content_type
        return attrs
