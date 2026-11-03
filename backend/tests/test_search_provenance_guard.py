import json

import pytest

from app.ai.provider import SdkProvider
from app.core.config import Settings
from app.core.errors import DomainError
from tests.fakes import ScriptedModel, message_output


@pytest.mark.parametrize("extra", [{"citations": [{"sourceId": "invented", "title": "Bịa", "url": "https://example.org/", "start": 0, "end": 1}]},
    {"cards": [{"kind": "maps_search", "searchId": "00000000-0000-4000-8000-000000000000"}]}])
async def test_model_cannot_invent_source_authority(extra):
    payload = {"text": "x", "cards": [], **extra}
    async def progress():
        pass
    with pytest.raises(DomainError):
        await SdkProvider(Settings(_env_file=None)).run_reply(bot_id="hoatdong", history=[], tools=[],
            context={}, on_progress=progress, model_override=ScriptedModel([[message_output(json.dumps(payload))]]))


async def test_journal_renderer_cannot_bypass_source_authority():
    from tests.test_journal_ai import evidence_run
    run, source = evidence_run()
    payload = {"messages": [{"text": "Thử quán này", "cards": [{"kind": "maps_search", "searchId": "00000000-0000-4000-8000-000000000000"}]}], "source_entry_ids": [str(source.entry_id)]}
    async def progress():
        pass
    with pytest.raises(DomainError):
        await SdkProvider(Settings(_env_file=None, ai_multi_message_enabled=True)).run_reply(bot_id="nhatky", history=[{"role": "user", "content": "Chào"}], tools=[],
            context=run, on_progress=progress, model_override=ScriptedModel([[message_output(json.dumps(payload))]]))
