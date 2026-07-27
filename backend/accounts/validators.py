"""
Egyptian phone number validator for the accounts app.

Accepts formats:
  - 01XXXXXXXXX  (11 digits, starting with 010, 011, 012, or 015)
  - +201XXXXXXXXX (international format)

Normalises all valid inputs to the local 01XXXXXXXXX format before saving.
"""

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# Egyptian mobile networks:
#   010 → Vodafone Egypt
#   011 → Etisalat Egypt
#   012 → Mobinil (Orange Egypt)
#   015 → WE (Telecom Egypt)
_EGYPTIAN_PHONE_RE = re.compile(r"^(?:\+?20)?0?(1[0-2|5]\d{8})$")


def validate_egyptian_phone(value: str) -> None:
    """
    Raise ValidationError if *value* is not a valid Egyptian mobile number.
    """
    if not _EGYPTIAN_PHONE_RE.match(value):
        raise ValidationError(
            _("Enter a valid Egyptian mobile number (e.g. 01012345678)."),
            code="invalid_phone",
        )


def normalise_phone(value: str) -> str:
    """
    Normalise a valid Egyptian phone number to the 01XXXXXXXXX format.

    Strips the country code (+20 or 20) if present.
    Raises ValueError for invalid input — call validate_egyptian_phone first.
    """
    match = _EGYPTIAN_PHONE_RE.match(value)
    if not match:
        raise ValueError(f"Cannot normalise invalid phone number: {value!r}")
    return "0" + match.group(1)
