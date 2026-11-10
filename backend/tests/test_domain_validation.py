"""Reject original replacement and prototype-only states at the HTTP boundary."""

from uuid import uuid4

import pytest
from pydantic import ValidationError


def test_original_and_contact_fields_cannot_be_added():
    from app.modules.contacts.schemas import ContactCreate
    from app.modules.evidence.schemas import EvidencePatch

    with pytest.raises(ValidationError):
        EvidencePatch(original_text="replacement")
    with pytest.raises(ValidationError):
        ContactCreate(id=uuid4(), label="Teacher", role="Teacher", email="x@example.test")


def test_support_demo_states_and_unselected_share_fields_rejected():
    from app.modules.sharing.schemas import ShareCreate
    from app.modules.support.schemas import DraftCreate

    with pytest.raises(ValidationError):
        DraftCreate(id=uuid4(), recipient_type="teacher", status="demo_submitted")
    with pytest.raises(ValidationError):
        ShareCreate(id=uuid4(), case_id=uuid4(), school_id=uuid4(), shared_fields=["ownerId"])
