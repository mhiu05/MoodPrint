import re
import secrets
from uuid import UUID

EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "application/pdf": "pdf",
    "audio/mpeg": "mp3",
    "video/mp4": "mp4",
    "text/plain": "txt",
}


def original_key(owner_id: UUID, evidence_id: UUID, mime: str | None) -> str:
    ext = EXTENSIONS.get(mime or "")
    suffix = f".{ext}" if ext else ""
    return f"users/{owner_id}/originals/{evidence_id}/{secrets.token_hex(8)}{suffix}"


def derived_key(owner_id: UUID, evidence_id: UUID, kind: str, derivative_id: UUID, ext: str) -> str:
    if kind not in {"thumbnail", "ocr_text", "transcript", "ai_analysis"} or not re.fullmatch(
        r"[a-z0-9]{1,8}", ext
    ):
        raise ValueError("Invalid derivative kind or extension")
    return f"users/{owner_id}/derived/{evidence_id}/{kind}/{derivative_id}.{ext}"
