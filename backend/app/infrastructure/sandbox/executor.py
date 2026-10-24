"""Future sandbox boundary. No current bot has a code/file execution tool."""

from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID


@dataclass(frozen=True)
class SandboxLimits:
    cpu_cores: float = 0.5
    memory_bytes: int = 128 * 1024 * 1024
    process_count: int = 32
    timeout_seconds: int = 10
    temporary_disk_bytes: int = 16 * 1024 * 1024
    output_bytes: int = 16 * 1024
    network: Literal["none"] = "none"
    read_only_root: Literal[True] = True


@dataclass(frozen=True)
class ExecutionAuthorization:
    """Created only by a backend policy gate, never deserialized from model input."""

    actor_id: UUID
    run_id: UUID
    tool_name: str
    policy_version: str


@dataclass(frozen=True)
class SandboxRequest:
    code: str
    language: Literal["python"] = "python"


@dataclass(frozen=True)
class SandboxResult:
    status: Literal["unavailable", "completed", "timed_out", "failed"]
    stdout: str = ""
    stderr: str = ""
    error_code: str | None = None


class SandboxExecutor(Protocol):
    async def execute(
        self, request: SandboxRequest, authorization: ExecutionAuthorization
    ) -> SandboxResult: ...


class DisabledSandboxExecutor:
    async def execute(
        self, request: SandboxRequest, authorization: ExecutionAuthorization
    ) -> SandboxResult:
        return SandboxResult(status="unavailable", error_code="SANDBOX_UNAVAILABLE")


def create_executor(*, enabled: bool = False) -> SandboxExecutor:
    # A flag cannot authorize model-generated execution. A future Docker adapter
    # needs a reviewed use case, pinned image, backend allowlist, no host mounts or
    # secrets/socket, these resource limits, and cancellation/cleanup verification.
    return DisabledSandboxExecutor()
