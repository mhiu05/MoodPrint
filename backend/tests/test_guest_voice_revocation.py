"""Personal consent switches no longer gate transcription."""

from uuid import uuid4

import pytest

from tests.guest_helpers import add_guest, enable_paid_fixture
from tests.test_guest_paid_dispatch import CountingTranscriber, wav

pytestmark = pytest.mark.postgres


async def speaker(clients, kind):
    app, actors = clients
    enable_paid_fixture(app)
    client = (await add_guest(app, consents=True)).client if kind == "guest" else actors[0][0]
    app.state.transcriber = CountingTranscriber()
    return client, app.state.transcriber


@pytest.mark.parametrize("kind", ["guest", "registered"])
async def test_permitted_voice_dispatch_calls_provider_once(clients, kind):
    client, provider = await speaker(clients, kind)
    response = await client.post(
        "/api/v1/voice/transcriptions",
        content=wav(),
        headers={"Content-Type": "audio/wav", "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 200, response.text
    assert provider.calls == 1
