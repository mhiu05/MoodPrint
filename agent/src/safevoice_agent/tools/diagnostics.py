"""Read-only diagnostic tool with no caller-controlled identity."""

from datetime import UTC, datetime

from agents import RunContextWrapper
from pydantic import BaseModel, ConfigDict
from safevoice_shared.contracts.agent import AgentToolContext


class ServerTime(BaseModel):
    model_config = ConfigDict(frozen=True)
    server_time: datetime


async def get_server_time(ctx: RunContextWrapper[AgentToolContext]) -> ServerTime:
    """Return the server's current time in UTC."""
    return ServerTime(server_time=datetime.now(UTC))
