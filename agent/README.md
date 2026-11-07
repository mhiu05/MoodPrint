# MoodPrint agent runtime

The `moodprint_agent` package uses the official `openai-agents[sqlalchemy]==0.24.*`
SDK. Phase 0 exposes one Companion and the read-only `get_server_time` tool.
Live model requests use `moodprint_shared.config.OPENAI_MODEL`; no key is needed
for deterministic tests using the SDK's `ScriptedModel`.

`CompanionRuntime` accepts an injected `AsyncOpenAI` client from the backend.
All runs use `store=False`, disabled tracing, and disabled sensitive trace data.
Only the versioned shared event contract crosses the SSE boundary; raw tool
arguments, tool output, and reasoning events stay inside the SDK.

The backend owns authentication, conversation ownership, persistence, and the
background task that drains a run when a client disconnects. It must check the
owner, expiry, and one-time decision before passing an opaque, server-stored
approval checkpoint to `resume_after_approval`. Never accept checkpoint state
from a client. Runtime checkpoints omit context and restore a fresh authenticated
context, budget counters, and monotonically increasing event sequence numbers.

`make_session` is called only after the conversation service checks ownership.
It maps SDK tables to `agent_store`, preserves Unicode, disables table creation,
and limits loaded history. The compaction wrapper is available with an always-off
Phase 0 policy and explicit input mode. Approved memories enter dynamic instructions,
so they are not copied into replay history. See the [S-02 spike](../docs/implementation/spikes/S-02.md)
and [S-03 spike](../docs/implementation/spikes/S-03.md) for actual evidence.

```powershell
.venv/Scripts/python.exe -m pytest agent/tests -q
.venv/Scripts/python.exe -m pytest agent/tests/integration -m integration -q
.venv/Scripts/python.exe -m pyright agent/src
```

Integration tests require a loopback `TEST_DATABASE_URL` from the process or the
synthetic local `.local/test.env`. No test reads the owner's root `.env`.
Only synthetic data is supported at this stage; production readiness requires
the remaining gates in architecture decision document 00, section 6.
