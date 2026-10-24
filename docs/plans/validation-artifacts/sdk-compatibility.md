# Python Agents SDK compatibility — 2026-10-23

Verified locally with Python **3.12.13**, `openai-agents` **0.24.0**, `openai`
**3.37.0**, Pydantic **2.14.1**, and the committed dependency selections in
`backend/uv.lock`. Import resolves to
`backend/.venv/Lib/site-packages/agents/__init__.py`; the existing root `agents/`
directory does not shadow the SDK.

## Implementation and checks

The shared [SdkProvider](../../../backend/app/ai/provider.py) constructs an SDK
`Agent` for the requested bot with separate Mây/Gương/Nhịp/Rủ Rê/Cầu Nối
instructions and the caller's allowlisted function tools. It uses the SDK's
`Runner.run_streamed()`, consumes the iterator to completion, and returns only
the validated `AiOutput`. Raw deltas and tool outputs are never passed to the
progress callback. The callback receives no arguments and can revalidate live
authorization before each model request.

| Concern | Verified behavior |
| --- | --- |
| Structured output | `Agent(output_type=AiOutput)` rejects empty/oversized text and unknown cards; the application schema rejects forged receipt fields. |
| Model budget | `max_turns=3`, a model-start hook capped at three, and retries disabled. Repeated empty structured responses produce SDK `MaxTurnsExceeded` after exactly three model calls. |
| Tool budget | A tool-start hook prevents the third invocation before execution. Domain tool authorization remains in the caller's gateway. Two tool calls followed by a final answer use exactly three model calls. |
| Deadlines | Whole-run `asyncio.timeout(30)` plus `ModelSettings(timeout=30)` and client timeout 30 seconds. A bounded test watchdog distinguishes the application deadline from the test's own cancellation. |
| Cancellation | Caller cancellation invokes `RunResultStreaming.cancel()`, drains SDK events for cleanup, and re-raises `CancelledError`. A blocked model observes cancellation. |
| Tracing | `set_tracing_disabled(True)` before execution and `RunConfig(tracing_disabled=True, trace_include_sensitive_data=False)`; fake models observe `ModelTracing.DISABLED`. Canary input/raw deltas are absent from captured logs. |
| Provider persistence | An actual `OpenAIResponsesModel` request through a local HTTP mock contains `store: false`; the adapter supplies no provider conversation ID or previous response ID. |
| Parallel tools | `ModelSettings(parallel_tool_calls=False)` reaches the outbound request when a tool is supplied. The SDK intentionally omits this field for an empty tool list. |
| Retries | `AsyncOpenAI(max_retries=0)` and `ModelRetrySettings(max_retries=0)`; a mocked 503 produces one outbound attempt. |
| Client lifecycle | Each configured live run owns and closes an `AsyncOpenAI` client. Missing configuration fails explicitly with `AI_UNAVAILABLE`; no fallback response is generated. |
| Test injection | `model_override` is a Python-only argument. `tests.fakes.make_test_model` returns an actual SDK `Model` subclass; no fake-model constructor exists in production code. |

The output guardrail rejects common unsupported first-person or sentence-leading
claims that data was saved, published, or an invitation sent. Current model tools
only propose changes, so they cannot supply a durable success receipt. This is a
narrow rule, not a complete semantic classifier; any future durable tool requires
receipt-aware validation before expanding these claims.

Two installed-version details were checked against source and executable tests:

- The Responses adapter omits `parallel_tool_calls` without tools. It transmits
  `false` with tools; no unsupported provider argument was added.
- The SDK wraps non-SDK exceptions from tool hooks in `UserError`. The provider
  restores an underlying `DomainError` after cancelling/draining the run.

## Reproduction

From `backend/`:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_sdk_adapter.py -q
.venv/Scripts/ruff.exe check app/ai/provider.py tests/fakes.py tests/test_sdk_adapter.py
.venv/Scripts/ruff.exe format --check app/ai/provider.py tests/fakes.py tests/test_sdk_adapter.py
.venv/Scripts/python.exe -m mypy app/ai/provider.py tests/fakes.py tests/test_sdk_adapter.py
```

Observed result: **18 passed in 3.20 seconds**, exit code 0; Ruff checks and
format checks pass; mypy reports no issues in all three files. Tests execute the
real SDK loop with synthetic models or local HTTP transports; no model API,
tracing exporter, credentials, or remote database was contacted. A configured
live model canary still requires the user's model/API settings and privacy gate.

## Primary references

The official [Agents SDK guide](https://developers.openai.com/api/docs/guides/agents/sdk)
links the Python runtime and its responsibilities. The SDK
[streaming guide](https://openai.github.io/openai-agents-python/streaming/)
describes consuming the complete event iterator and cancellation. The
[running agents guide](https://openai.github.io/openai-agents-python/running_agents/)
describes structured output and maximum turns. Installed SDK source and the
outbound transport tests above determine compatibility for the pinned version.
