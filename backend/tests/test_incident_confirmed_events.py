from uuid import UUID, uuid4

import pytest
from app.modules.incidents.service import IncidentService
from safevoice_shared.contracts.incidents import EventCreate


@pytest.mark.parametrize("provenance", ["user_entered", "ai_extracted"])
async def test_confirmed_entry_rejects_other_provenance_before_opening_transaction(provenance):
    service = IncidentService(None)
    data = EventCreate(id=uuid4(), description="Synthetic event", provenance=provenance)
    with pytest.raises(ValueError, match="user_confirmed"):
        await service.add_confirmed_event(None, uuid4(), data, proposal_id=uuid4())


@pytest.mark.parametrize("proposal_id", [None, UUID(int=0), "not-a-uuid"])
async def test_confirmed_entry_requires_non_nil_proposal_uuid(proposal_id):
    service = IncidentService(None)
    data = EventCreate(id=uuid4(), description="Synthetic event", provenance="user_confirmed")
    with pytest.raises(ValueError, match="proposal_id"):
        await service.add_confirmed_event(None, uuid4(), data, proposal_id=proposal_id)
