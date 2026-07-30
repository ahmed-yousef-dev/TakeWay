from django.contrib import admin

from .models import Favorite, Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("user", "content_type", "object_id", "rating", "created_at")
    list_filter = ("content_type", "rating")
    search_fields = ("user__phone_number", "comment")
    readonly_fields = ("user", "content_type", "object_id", "rating", "comment", "created_at")
    ordering = ("-created_at",)


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "content_type", "object_id", "created_at")
    list_filter = ("content_type",)
    search_fields = ("user__phone_number",)
    readonly_fields = ("user", "content_type", "object_id", "created_at")
    ordering = ("-created_at",)
