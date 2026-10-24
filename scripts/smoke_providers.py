"""One synthetic, opt-in provider request per invocation. Never prints provider content."""

import argparse
import asyncio
import io
import sys
import wave
from pathlib import Path

from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.ai.voyage import VoyageProvider  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.modules.voice.service import OpenAITranscriber  # noqa: E402


def synthetic_wav() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16_000)
        audio.writeframes(b"\0\0" * 16_000)
    return output.getvalue()


async def run(provider: str, settings: Settings) -> None:
    if provider == "openai":
        if not settings.openai_api_key.get_secret_value() or not settings.openai_model:
            raise ValueError("OpenAI key/model not configured")
        async with AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(), max_retries=0, timeout=15
        ) as client:
            await client.responses.create(
                model=settings.openai_model,
                input="Reply with the single word OK.",
                max_output_tokens=8,
                store=False,
            )
    elif provider == "voyage":
        if not settings.voyage_api_key.get_secret_value():
            raise ValueError("Voyage key not configured")
        await VoyageProvider(settings).embed("Synthetic test memory: I like reading.", "document")
    else:
        if not settings.openai_api_key.get_secret_value() or not settings.stt_model:
            raise ValueError("STT key/model not configured")
        await OpenAITranscriber(settings).transcribe(synthetic_wav())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("openai", "voyage", "stt"), required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--ack-billing", action="store_true")
    args = parser.parse_args()
    if not args.live or not args.ack_billing:
        parser.error("--live and --ack-billing are both required; each run makes one paid request")
    try:
        asyncio.run(run(args.provider, Settings()))
    except Exception as error:
        # Provider exceptions can carry URL or response details: print only the class.
        raise SystemExit(f"{args.provider}: FAIL ({type(error).__name__})") from None
    print(f"{args.provider}: PASS (one synthetic provider request; content not printed)")


if __name__ == "__main__":
    main()
