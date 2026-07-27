"""
Factory Boy factories for the locations app.
"""

import factory

from locations.models import Governorate, Location


class GovernorateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Governorate

    name = factory.Sequence(lambda n: f"Governorate {n}")
    is_active = True


class LocationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Location

    name = factory.Sequence(lambda n: f"Village {n}")
    governorate = factory.SubFactory(GovernorateFactory)
    type = Location.LocationType.VILLAGE
    delivery_fee = "15.00"
    minimum_order_amount = "30.00"
    is_active = True
