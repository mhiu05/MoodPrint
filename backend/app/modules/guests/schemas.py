"""Public request/response contracts for the guest trial (camelCase, extra forbidden)."""

from typing import Literal

from pydantic import Field, StrictBool, field_validator

from app.contracts import DTO, GuestQuota, VersionInput

__all__ = ["GuestEligibility", "GuestInput", "GuestQuota", "PublicExperience"]


class GuestEligibility(VersionInput):
    """The adult attestation, parsed leniently so under-18 and a missing confirmation
    answer GUEST_INELIGIBLE (before any provider call) instead of a generic validation error."""

    birth_year: int = Field(ge=1900, le=9999, strict=True)
    confirmed_minimum_age: StrictBool
    confirmed_adult_age: StrictBool = False
    policy_version: Literal["self-declared-age-v2-18plus"]


class GuestInput(DTO):
    """Explicit trial entry: the age attestation, a one-shot CAPTCHA and the disclosure version."""

    eligibility: GuestEligibility
    # Verified upstream by the provider; never persisted, logged or echoed.
    captcha_token: str = Field(min_length=1, max_length=4096, repr=False)
    disclosure_version: Literal["guest-v2"]

    @field_validator("eligibility")
    @classmethod
    def first_declaration(cls, value: GuestEligibility) -> GuestEligibility:
        # A new anonymous identity has no earlier declaration to supersede.
        if value.expected_version != 0:
            raise ValueError("A guest age declaration starts at version 0")
        return value


class PublicExperience(DTO):
    """Identity-free landing readiness. Publishes capability, never secrets, budget or quota."""

    guest_available: bool
    guest_unavailable_reason: (
        Literal["disabled", "configuration_missing", "temporarily_unavailable"] | None
    )
    feedback_available: bool
    product_tour_available: bool
    captcha_site_key: str | None
