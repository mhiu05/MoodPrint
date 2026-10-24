from uuid import uuid4

import pytest

from app.infrastructure.sandbox.executor import (
    ExecutionAuthorization,
    SandboxRequest,
    create_executor,
)


@pytest.mark.parametrize("enabled", [False, True])
async def test_configuration_cannot_enable_unreviewed_code_execution(tmp_path, enabled):
    marker = tmp_path / "must-not-exist.txt"
    executor = create_executor(enabled=enabled)
    result = await executor.execute(
        SandboxRequest(code=f"open({str(marker)!r}, 'w').write('executed')"),
        ExecutionAuthorization(uuid4(), uuid4(), "unregistered_tool", "unreviewed"),
    )
    assert result.status == "unavailable" and result.error_code == "SANDBOX_UNAVAILABLE"
    assert not marker.exists()
