"""Single-call multimodal reader: image in, ``EvidenceReading`` out.

Deliberately not an agent: no session, no tools, no handoffs, no stored response (``store=False``),
no tracing. Instructions are fixed text; the image is untrusted data and any instruction inside it
is content to be quoted (see the pinned ``evidence_reader_v1`` prompt).
"""

import asyncio
import hashlib
from dataclasses import dataclass
from typing import Any, cast

from moodprint_shared.config import AppConfig
from openai import AsyncOpenAI, OpenAIError

from moodprint_agent.companion import EVIDENCE_READER_VERSION, load_prompt
from moodprint_agent.evidence.image import PreparedImage
from moodprint_agent.evidence.models import EvidenceReading

READER_OUTPUT_TOKENS = 2_500


class ReadFailed(Exception):
    """The reading did not complete; ``code`` is shown to the user, never the provider text."""

    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class ReaderOutput:
    reading: EvidenceReading
    usage: dict[str, int]
    version: str


def reader_version() -> str:
    digest = hashlib.sha256(load_prompt(EVIDENCE_READER_VERSION).encode("utf-8")).hexdigest()
    return f"{EVIDENCE_READER_VERSION}@{digest[:8]}"


class EvidenceReader:
    def __init__(self, client: AsyncOpenAI, cfg: AppConfig) -> None:
        self._client = client
        self._cfg = cfg

    async def read(self, image: PreparedImage) -> ReaderOutput:
        cfg = self._cfg
        try:
            async with asyncio.timeout(cfg.agent.analysis_timeout_s):
                response = await self._client.responses.parse(
                    model=cfg.agent.vision_model,
                    instructions=load_prompt(EVIDENCE_READER_VERSION),
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": "Đọc ảnh sau theo đúng cấu trúc yêu cầu.",
                                },
                                {
                                    "type": "input_image",
                                    "image_url": image.data_url(),
                                    "detail": "auto",
                                },
                            ],
                        }
                    ],
                    text_format=EvidenceReading,
                    store=False,
                    max_output_tokens=READER_OUTPUT_TOKENS,
                    reasoning=cast(Any, {"effort": cfg.agent.analysis_reasoning_effort}),
                )
        except TimeoutError:
            raise ReadFailed("analysis_timeout", retryable=True) from None
        except OpenAIError:
            raise ReadFailed("upstream_error", retryable=True) from None
        parsed = response.output_parsed
        if parsed is None:
            raise ReadFailed("unreadable_output", retryable=True)
        usage = response.usage
        return ReaderOutput(
            reading=parsed,
            usage={
                "input_tokens": usage.input_tokens if usage else 0,
                "output_tokens": usage.output_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
            },
            version=reader_version(),
        )
