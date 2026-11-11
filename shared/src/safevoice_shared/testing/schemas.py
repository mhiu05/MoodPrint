"""Stable JSON schema export for the versioned shared contract surface."""

import inspect
from importlib import import_module
from typing import Any

from pydantic import TypeAdapter

from safevoice_shared.contracts.agent import ToolPolicy
from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.contracts.base import FrozenDTO
from safevoice_shared.contracts.streaming import STREAM_EVENT_ADAPTER

_MODULES = (
    "errors",
    "paging",
    "incidents",
    "evidence",
    "plans",
    "memory",
    "conversations",
    "context",
    "knowledge",
    "agent",
)


def contract_schemas() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name in _MODULES:
        module = import_module(f"safevoice_shared.contracts.{name}")
        models: dict[str, Any] = {}
        for symbol, candidate in inspect.getmembers(module, inspect.isclass):
            if candidate.__module__ == module.__name__ and issubclass(candidate, FrozenDTO):
                models[symbol] = candidate.model_json_schema(by_alias=True)
        result[f"{name}.json"] = models
    result["auth.json"] = {"AuthContext": TypeAdapter(AuthContext).json_schema()}
    result["agent.json"]["ToolPolicy"] = TypeAdapter(ToolPolicy).json_schema()
    result["streaming.json"] = STREAM_EVENT_ADAPTER.json_schema(by_alias=True)
    return result
