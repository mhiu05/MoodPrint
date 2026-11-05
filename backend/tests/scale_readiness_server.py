"""Synthetic scale-provider contract, separate from fault fixtures with missing usage.

The inherited provider keeps its owner/memory isolation checks and buffered SSE behavior.
Usage below is a declared simulation profile, not a measurement of a real tokenizer/model.
"""

from openai.types.responses.response_usage import ResponseUsage


def known_usage():
    return ResponseUsage(input_tokens=8000, output_tokens=600, total_tokens=8600,
                         input_tokens_details={"cached_tokens": 0, "cache_write_tokens": 0},
                         output_tokens_details={"reasoning_tokens": 0})


def scale_model():
    # Import only after the runner validates the disposable target and denies egress.
    from tests.chat_load_server import LoadModel

    class KnownUsageLoadModel(LoadModel):
        async def stream_response(self, *args, **kwargs):
            import asyncio
            from contextlib import suppress

            from openai.types.responses import ResponseTextDeltaEvent

            source = super().stream_response(*args, **kwargs)
            pending = asyncio.create_task(anext(source))
            try:
                # Provider first-delta delay and completion delay are separate stages.
                await asyncio.sleep(0.5)
                yield ResponseTextDeltaEvent(content_index=0, delta="RAW-SYNTHETIC-CANARY",
                    item_id="load", logprobs=[], output_index=0, sequence_number=0,
                    type="response.output_text.delta")
                await pending  # Discard the old fixture's late first delta, not its response.
                async for event in source:
                    if event.type == "response.completed":
                        event.response.usage = known_usage()
                    yield event
            finally:
                if not pending.done():
                    pending.cancel()
                with suppress(asyncio.CancelledError):
                    await pending
                await source.aclose()

    return KnownUsageLoadModel()
