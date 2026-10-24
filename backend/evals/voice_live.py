"""Two finite real API calls: synthetic Vietnamese speech, then application STT adapter."""

import argparse
import asyncio
import io
import json
import logging
import time
import wave
from pathlib import Path

from openai import AsyncOpenAI

from app.core.config import Settings
from app.modules.voice.service import OpenAITranscriber, validate_audio

SYNTHETIC_TEXT = "Hôm nay mình muốn đi dạo mười phút rồi vẽ một bức tranh màu nước."


async def run(model: str, output: Path):
    if await asyncio.to_thread(output.exists):
        raise ValueError("Refusing to overwrite voice evidence")
    settings = Settings()
    report = {"synthetic": True, "stt_model": model, "tts_model": "gpt-4o-mini-tts",
              "tts_requests": 0, "stt_requests": 0, "source_text": SYNTHETIC_TEXT,
              "application_stt_adapter": True, "audio_persisted": False,
              "default_stt_enabled": settings.stt_enabled, "retries": 0}
    start = time.perf_counter()
    try:
        async with AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value(), max_retries=0, timeout=30) as client:
            report["tts_requests"] = 1
            audio = await client.audio.speech.create(model="gpt-4o-mini-tts", voice="coral",
                                                     input=SYNTHETIC_TEXT, response_format="pcm")
            pcm = audio.content
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            wav.writeframes(pcm)
        data = buffer.getvalue()
        report["duration_seconds"] = validate_audio(data)
        report["audio_bytes"] = len(data)
        transcriber = OpenAITranscriber(settings.model_copy(update={"stt_model": model}))
        report["stt_requests"] = 1
        text = await transcriber.transcribe(data)
        report.update(transcript=text, status="PASS" if "màu nước" in text.lower() and "mười phút" in text.lower() else "REVIEW")
    except Exception as error:
        report.update(status="FAILED", error_type=type(error).__name__, http_status=getattr(error, "status_code", None))
    report["latency_seconds"] = round(time.perf_counter() - start, 3)
    await asyncio.to_thread(output.write_text, json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", required=True, action="store_true")
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    asyncio.run(run(args.model, args.output))


if __name__ == "__main__":
    main()
