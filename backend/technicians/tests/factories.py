"""
Factory Boy factories for the technicians app.
"""

import factory

from locations.tests.factories import LocationFactory
from technicians.models import Technician, TechnicianCategory, TechnicianRequest


class TechnicianCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TechnicianCategory

    name = factory.Sequence(lambda n: f"Category {n}")
    icon = "wrench"
    sort_order = factory.Sequence(lambda n: n)
    is_active = True


class TechnicianFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Technician

    name = factory.Sequence(lambda n: f"Technician {n}")
    category = factory.SubFactory(TechnicianCategoryFactory)
    location = factory.SubFactory(LocationFactory)
    phone = factory.Sequence(lambda n: f"011{n:08d}")
    bio = "Experienced professional."
    years_experience = 5
    avg_rating = "0.00"
    review_count = 0
    is_featured = False
    is_active = True


class TechnicianRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TechnicianRequest

    customer = factory.SubFactory("accounts.tests.factories.UserFactory")
    technician = factory.SubFactory(TechnicianFactory)
    notes = "Please come in the morning."
    status = TechnicianRequest.Status.PENDING
