"""
Factory Boy factories for the accounts app.
"""

import factory
from django.utils import timezone

from accounts.models import OTP, User

# Default password used for all factory-created test users.
TEST_PASSWORD = "TestPass123"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    phone = factory.Sequence(lambda n: f"010{n:08d}")
    name = factory.Faker("name")
    role = User.Role.CUSTOMER
    location = None
    is_active = True
    # Provide a default usable password so factory users can log in.
    password = TEST_PASSWORD

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Use create_user so the manager hashes the password correctly."""
        manager = cls._get_manager(model_class)
        return manager.create_user(*args, **kwargs)


class BusinessOwnerFactory(UserFactory):
    role = User.Role.BUSINESS_OWNER


class AdminUserFactory(UserFactory):
    role = User.Role.ADMIN
    is_staff = True


class OTPFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OTP

    phone = factory.Sequence(lambda n: f"010{n:08d}")
    code = "123456"
    expires_at = factory.LazyFunction(
        lambda: timezone.now() + timezone.timedelta(minutes=5)
    )
    is_used = False
