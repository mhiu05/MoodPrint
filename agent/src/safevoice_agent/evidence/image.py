"""Decode untrusted evidence images into a clean derivative; never touch the original.

The bytes the user uploaded are hashed as received (``source_sha256``) and then only *read*. What
may leave the system is a freshly re-encoded PNG built from decoded pixels: container metadata
(EXIF/GPS, text chunks, ICC, embedded payloads) is not carried over, orientation is applied and the
size is bounded. Formats are decided by magic bytes, never by the declared MIME type or extension.
"""

import hashlib
import io
from dataclasses import dataclass
from typing import Final

from PIL import Image, ImageFile, ImageOps, UnidentifiedImageError

# Explicit decompression-bomb ceiling (pixels); Pillow also warns above half of it.
MAX_PIXELS: Final = 40_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
ImageFile.LOAD_TRUNCATED_IMAGES = False

_PNG: Final = b"\x89PNG\r\n\x1a\n"


class ImageRejected(ValueError):
    """The image cannot be analysed; ``code`` is safe to show and never contains content."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class PreparedImage:
    source_sha256: str
    source_mime: str
    source_bytes: int
    derivative_png: bytes
    derivative_sha256: str
    width: int
    height: int

    def data_url(self) -> str:
        import base64

        return "data:image/png;base64," + base64.b64encode(self.derivative_png).decode("ascii")


def sniff_mime(data: bytes) -> str | None:
    if data.startswith(_PNG):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def prepare_image(
    data: bytes,
    *,
    allowed_mime: tuple[str, ...],
    max_bytes: int,
    max_px: int,
) -> PreparedImage:
    if len(data) > max_bytes:
        raise ImageRejected("object_too_large")
    mime = sniff_mime(data)
    if mime is None or mime not in allowed_mime:
        # SVG, PDF, GIF and anything else: refused by content, whatever it claims to be.
        raise ImageRejected("unsupported_media")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if getattr(probe, "n_frames", 1) > 1 or getattr(probe, "is_animated", False):
                raise ImageRejected("unsupported_media")
            probe.verify()
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            if width < 1 or height < 1 or width * height > MAX_PIXELS:
                raise ImageRejected("image_too_large")
            image.load()
            oriented = ImageOps.exif_transpose(image)
            if oriented.mode in ("RGBA", "LA", "P"):
                rgba = oriented.convert("RGBA")
                canvas = Image.new("RGB", rgba.size, (255, 255, 255))
                canvas.paste(rgba, mask=rgba.getchannel("A"))
                pixels = canvas
            else:
                pixels = oriented.convert("RGB")
            if max(pixels.size) > max_px:
                pixels.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
            # Rebuild from raw pixels: no .info, no EXIF, no ancillary chunks can survive.
            clean = Image.frombytes("RGB", pixels.size, pixels.tobytes())
            buffer = io.BytesIO()
            clean.save(buffer, format="PNG", optimize=True)
    except ImageRejected:
        raise
    except Image.DecompressionBombError:
        raise ImageRejected("image_too_large") from None
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise ImageRejected("unreadable_image") from None
    png = buffer.getvalue()
    return PreparedImage(
        source_sha256=hashlib.sha256(data).hexdigest(),
        source_mime=mime,
        source_bytes=len(data),
        derivative_png=png,
        derivative_sha256=hashlib.sha256(png).hexdigest(),
        width=clean.size[0],
        height=clean.size[1],
    )
