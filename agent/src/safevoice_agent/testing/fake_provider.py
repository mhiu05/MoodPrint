"""Deterministic OpenAI stand-in at the HTTP boundary, for the real-stack E2E only.

Evidence analysis and the roleplay coach call ``client.responses.parse``. The scripted E2E runtime
(``scripted_scenarios.build_e2e_runtime``) hands the backend a real ``AsyncOpenAI`` whose transport is
this in-process fake, so the backend, the Responses parsing, consent, storage, derivatives and the
browser all run for real and only the model's answer is canned. Loaded only under APP_ENV=test.

How a test steers it (nothing here can be reached in production):

* analysis: the **colour of the top-left pixel** of the uploaded image selects the behaviour, so each
  test brings its own image and tests cannot interfere with one another:
  red ``(255,0,0)`` -> upstream 500 every time; orange ``(255,165,0)`` -> transport timeout;
  blue ``(0,0,255)`` -> 500 on the first request for that image, success afterwards; anything else -> OK.
* coach: a user line containing ``lỗi phản hồi`` -> 500; otherwise a grounded canned feedback.
* every request is appended to ``SAFEVOICE_E2E_MODEL_LOG`` (default: system temp dir) as
  ``<kind> <sha16> <mode>`` so a test can assert how many model calls a user action caused.
"""

import base64
import hashlib
import io
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, cast

import httpx
from openai import AsyncOpenAI
from PIL import Image

LOG_PATH = Path(
    os.environ.get("SAFEVOICE_E2E_MODEL_LOG")
    or Path(tempfile.gettempdir()) / "safevoice-e2e-model.log"
)
_attempts: dict[str, int] = {}


def _log(kind: str, key: str, mode: str) -> None:
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f"{kind} {key} {mode}\n")


def _response(payload: dict[str, Any]) -> httpx.Response:
    text = json.dumps(payload, ensure_ascii=False)
    body: dict[str, Any] = {
        "id": "resp_e2e",
        "object": "response",
        "created_at": 0,
        "status": "completed",
        "model": "gpt-6-luna",
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
        "output": [
            {
                "id": "msg_e2e",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
        "usage": {
            "input_tokens": 120,
            "output_tokens": 60,
            "total_tokens": 180,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }
    return httpx.Response(200, json=body)


def _error() -> httpx.Response:
    return httpx.Response(
        500, json={"error": {"message": "e2e upstream failure", "type": "server_error"}}
    )


def _image(request_body: dict[str, Any]) -> tuple[str, tuple[int, int, int]]:
    for item in cast(list[Any], request_body.get("input") or []):
        content = cast(dict[str, Any], item).get("content") if isinstance(item, dict) else None
        for part in cast(list[Any], content if isinstance(content, list) else []):
            fields = cast(dict[str, Any], part) if isinstance(part, dict) else {}
            if fields.get("type") == "input_image":
                url = str(fields.get("image_url", ""))
                raw = base64.b64decode(url.split(",", 1)[1])
                pixel = cast(
                    tuple[int, ...], Image.open(io.BytesIO(raw)).convert("RGB").getpixel((0, 0))
                )
                key = hashlib.sha256(raw).hexdigest()[:16]
                return key, (pixel[0], pixel[1], pixel[2])
    return "noimage", (0, 0, 0)


def _reading(key: str) -> dict[str, Any]:
    return {
        "extracted_text": [
            {
                "text": "Mình sẽ không quên chuyện này đâu",
                "confidence": "high",
                "region": "giữa ảnh",
            }
        ],
        "visible_metadata": {
            "timestamp_text": "20:15",
            "platform_guess": "ứng dụng nhắn tin",
            "participants_as_shown": ["Bạn A"],
        },
        "observations": [f"Ảnh tổng hợp dùng để kiểm thử ({key[:6]})."],
        "inferences": [
            {
                "text": "Có thể đây là một đoạn trò chuyện nhóm",
                "basis": "bố cục khung chat",
                "confidence": "low",
            }
        ],
        "uncertainties": ["Không rõ ai là người gửi tin."],
        "limitations": ["Chỉ đọc một ảnh, không có tin nhắn trước và sau."],
        "needs_user_review": True,
    }


def _feedback(request_body: dict[str, Any]) -> dict[str, Any] | None:
    raw = str(request_body.get("input", ""))
    match = re.search(r"<transcript_data>\n(.*)\n</transcript_data>", raw, re.S)
    loaded = cast(dict[str, Any], json.loads(match.group(1))) if match else {}
    turns = cast(list[dict[str, Any]], loaded.get("turns", []))
    said = [str(t.get("text", "")) for t in turns if t.get("speaker") == "user"]
    if any("lỗi phản hồi" in line for line in said):
        return None
    quote = said[0][:40] if said else ""
    return {
        "summary": "Bạn đã nói rõ điều mình cần và giữ được bình tĩnh.",
        "strengths": ["Bạn mở lời trực tiếp.", "Bạn nói về cảm giác của mình."],
        "suggestions": ["Thử nêu một mong muốn cụ thể."],
        "rephrasings": (
            [
                {
                    "original": quote,
                    "better": "Con muốn kể và mong mẹ lắng nghe trước.",
                    "why": "Rõ mong muốn hơn.",
                }
            ]
            if quote
            else []
        ),
        "follow_ups": ["Chọn một người lớn bạn tin để thử nói thật."],
        "safety_note": None,
    }


async def handler(request: httpx.Request) -> httpx.Response:
    if not request.url.path.endswith("/responses"):
        _log("unfaked", request.url.path.replace(" ", "_"), "404")
        return httpx.Response(404, json={"error": {"message": "not faked"}})
    body = cast(dict[str, Any], json.loads(request.content))
    key, pixel = _image(body)
    if key != "noimage":
        if pixel == (255, 0, 0):
            _log("analysis", key, "error")
            return _error()
        if pixel == (255, 165, 0):
            _log("analysis", key, "timeout")
            raise httpx.ReadTimeout("e2e timeout", request=request)
        if pixel == (0, 0, 255):
            _attempts[key] = _attempts.get(key, 0) + 1
            if _attempts[key] == 1:
                _log("analysis", key, "error_once")
                return _error()
        _log("analysis", key, "ok")
        return _response(_reading(key))
    feedback = _feedback(body)
    if feedback is None:
        _log("coach", "-", "error")
        return _error()
    _log("coach", "-", "ok")
    return _response(feedback)


def build_fake_client() -> AsyncOpenAI:
    """No retries: a failed request must be a visible, deterministic failure."""
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=5)
    return AsyncOpenAI(
        api_key="e2e-fake-key",
        base_url="http://model.invalid/v1",
        max_retries=0,
        http_client=cast(Any, http),
    )
