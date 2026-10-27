"""Public request/response contracts for the guest trial (camelCase, extra forbidden)."""

from typing import Literal

from pydantic import Field, field_validator

from app.contracts import DTO, EligibilityInput, GuestQuota

__all__ = ["GuestInput", "GuestQuota", "PublicExperience"]


class GuestInput(DTO):
    """Explicit trial entry: the existing age attestation, a one-shot CAPTCHA and the disclosure."""

    eligibility: EligibilityInput
    # Verified upstream by the provider; never persisted, logged or echoed.
    captcha_token: str = Field(min_length=1, max_length=4096, repr=False)
    disclosure_version: Literal["guest-v1"]

    @field_validator("eligibility")
    @classmethod
    def first_declaration(cls, value: EligibilityInput) -> EligibilityInput:
        # A new anonymous identity has no earlier declaration to supersede.
        if value.expected_version != 0:
            raise ValueError("A guest age declaration starts at version 0")
        return value


class PublicExperience(DTO):
    """Identity-free landing readiness. Publishes capability, never secrets, budget or quota."""

    guest_available: bool
    guest_unavailable_reason: Literal["disabled", "configuration_missing", "temporarily_unavailable"] | None
    feedback_available: bool
    product_tour_available: bool
    captcha_site_key: str | None
