"""
Custom User model and OTP model for TakeWay.

Design decisions:
- Phone number is the primary identifier (not email or username).
- Passwords are only set for superusers (Django Admin access).
  Regular customers authenticate exclusively via OTP.
- The User model has a FK to locations.Location so we can scope content
  to the user's selected village/city.
- OTP stores phone directly (not a FK to User) because an OTP can be
  created before the user account exists (first-time registration).
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from common.models import TimestampMixin
from accounts.validators import validate_egyptian_phone


class UserManager(BaseUserManager):
    """Custom manager for the phone-based User model."""

    def create_user(self, phone: str, name: str, password=None, **extra_fields):
        if not phone:
            raise ValueError(_("Phone number is required."))
        if not name:
            raise ValueError(_("Name is required."))

        user = self.model(phone=phone, name=name, **extra_fields)
        # Customers do not have usable passwords — OTP auth only.
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone: str, name: str, password: str, **extra_fields):
        if not password:
            raise ValueError(_("Superusers must have a password."))
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        return self.create_user(phone, name, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, TimestampMixin):
    """
    TakeWay's custom User model.

    Replaces Django's default User. Phone number is the login identifier.
    """

    class Role(models.TextChoices):
        CUSTOMER = "customer", _("Customer")
        BUSINESS_OWNER = "business_owner", _("Business Owner")
        ADMIN = "admin", _("Admin")

    phone = models.CharField(
        _("phone number"),
        max_length=15,
        unique=True,
        validators=[validate_egyptian_phone],
        help_text=_("Egyptian mobile number, e.g. 01012345678"),
    )
    name = models.CharField(_("name"), max_length=150)
    role = models.CharField(
        _("role"),
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
    )

    # FK to Location — set at registration, can be changed later.
    # Nullable so we can create the user before the location app is fully
    # migrated (circular FK safety), and to handle admin users with no location.
    location = models.ForeignKey(
        "locations.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        verbose_name=_("location"),
    )

    # Django Admin access flags
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Allows access to the Django Admin site."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_("Uncheck to deactivate this account instead of deleting it."),
    )
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["-date_joined"]

    def __str__(self):
        return f"{self.name} ({self.phone})"

    @property
    def is_customer(self):
        return self.role == self.Role.CUSTOMER

    @property
    def is_business_owner(self):
        return self.role == self.Role.BUSINESS_OWNER

    @property
    def is_admin_staff(self):
        return self.role == self.Role.ADMIN or self.is_superuser


class OTP(models.Model):
    """
    One-Time Password for phone-based authentication.

    Lifecycle:
      1. Created when a user requests an OTP.
      2. Sent (async) to the user's phone via the configured SMS backend.
      3. Verified when the user submits the code.
      4. Marked as used after successful verification.
      5. Expired OTPs are rejected. Cleanup can be done periodically.
    """

    phone = models.CharField(
        _("phone number"),
        max_length=15,
        db_index=True,
        help_text=_("The phone number this OTP was sent to."),
    )
    code = models.CharField(_("code"), max_length=6)
    expires_at = models.DateTimeField(_("expires at"))
    is_used = models.BooleanField(_("is used"), default=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("OTP")
        verbose_name_plural = _("OTPs")
        ordering = ["-created_at"]
        indexes = [
            # Composite index for the most common lookup: phone + is_used + expires_at
            models.Index(fields=["phone", "is_used", "expires_at"], name="otp_phone_used_exp_idx"),
        ]

    def __str__(self):
        return f"OTP for {self.phone} (used={self.is_used})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
