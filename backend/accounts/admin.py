"""
Django Admin configuration for the accounts app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from accounts.models import OTP, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin for the phone-based User model.
    Extends Django's UserAdmin but replaces username/email fields with phone.
    """

    list_display = ("phone", "name", "role", "location", "is_active", "is_staff", "date_joined")
    list_filter = ("role", "is_active", "is_staff", "location__governorate")
    search_fields = ("phone", "name")
    ordering = ("-date_joined",)

    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        (_("Personal info"), {"fields": ("name", "location")}),
        (_("Role & Permissions"), {
            "fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
        }),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("phone", "name", "role", "password1", "password2"),
        }),
    )

    # Replace username with phone in list display
    readonly_fields = ("date_joined", "last_login")


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    """
    Read-only OTP admin for debugging purposes.
    OTPs should never be manually created or edited from the admin.
    """

    list_display = ("phone", "code", "created_at", "expires_at", "is_used")
    list_filter = ("is_used",)
    search_fields = ("phone",)
    ordering = ("-created_at",)
    readonly_fields = ("phone", "code", "expires_at", "is_used", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
