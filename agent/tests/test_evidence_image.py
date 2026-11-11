"""U-AG-100…112: untrusted image decoding. Pure functions, synthetic images, no network."""

import hashlib
import io

import pytest
from PIL import Image
from safevoice_agent.evidence.image import ImageRejected, prepare_image, sniff_mime

ALLOWED = ("image/jpeg", "image/png", "image/webp")


def _encode(image: Image.Image, fmt: str, **kwargs: object) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, **kwargs)  # type: ignore[arg-type]
    return buffer.getvalue()


def _prepare(data: bytes, *, max_bytes: int = 8_000_000, max_px: int = 2048):
    return prepare_image(data, allowed_mime=ALLOWED, max_bytes=max_bytes, max_px=max_px)


@pytest.mark.parametrize(
    "fmt, mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")]
)
def test_supported_formats_become_a_clean_png_and_the_original_is_hashed_as_received(
    fmt: str, mime: str
) -> None:
    original = _encode(Image.new("RGB", (64, 48), (20, 120, 200)), fmt)
    prepared = _prepare(original)
    assert prepared.source_mime == mime
    assert prepared.source_sha256 == hashlib.sha256(original).hexdigest()
    assert prepared.derivative_png.startswith(b"\x89PNG")
    assert (prepared.width, prepared.height) == (64, 48)
    assert prepared.derivative_sha256 == hashlib.sha256(prepared.derivative_png).hexdigest()
    assert prepared.data_url().startswith("data:image/png;base64,")


def test_exif_gps_and_text_chunks_never_reach_the_derivative() -> None:
    exif = Image.Exif()
    exif[0x010F] = "SyntheticCameraMaker"  # Make
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2] = "N", (21.0, 1.0, 30.0)
    original = _encode(Image.new("RGB", (40, 40), "white"), "JPEG", exif=exif)
    assert b"SyntheticCameraMaker" in original  # the fixture really carries metadata
    prepared = _prepare(original)
    assert b"SyntheticCameraMaker" not in prepared.derivative_png
    assert b"Exif" not in prepared.derivative_png
    with Image.open(io.BytesIO(prepared.derivative_png)) as reopened:
        assert not reopened.getexif()
        assert "exif" not in reopened.info

    png_info = Image.new("RGB", (8, 8), "white")
    from PIL.PngImagePlugin import PngInfo

    meta = PngInfo()
    meta.add_text("Comment", "secret-location-note")
    original_png = _encode(png_info, "PNG", pnginfo=meta)
    assert b"secret-location-note" in original_png
    assert b"secret-location-note" not in _prepare(original_png).derivative_png


def test_exif_orientation_is_applied_before_metadata_is_dropped() -> None:
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 270 to display: a 40x20 sensor image shows as 20x40
    original = _encode(Image.new("RGB", (40, 20), "white"), "JPEG", exif=exif)
    prepared = _prepare(original)
    assert (prepared.width, prepared.height) == (20, 40)


def test_large_images_are_downscaled_to_the_pixel_limit() -> None:
    prepared = _prepare(_encode(Image.new("RGB", (3000, 1500), "white"), "PNG"), max_px=2048)
    assert max(prepared.width, prepared.height) == 2048
    assert prepared.width / prepared.height == pytest.approx(2.0, rel=0.01)


def test_transparency_is_flattened_so_hidden_alpha_content_is_not_sent() -> None:
    rgba = Image.new("RGBA", (10, 10), (255, 0, 0, 0))  # fully transparent red
    prepared = _prepare(_encode(rgba, "PNG"))
    with Image.open(io.BytesIO(prepared.derivative_png)) as out:
        assert out.mode == "RGB"
        assert out.getpixel((0, 0)) == (255, 255, 255)


@pytest.mark.parametrize(
    "data, code",
    [
        (
            b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
            "unsupported_media",
        ),
        (b"%PDF-1.7\n%synthetic", "unsupported_media"),
        (b"GIF89a\x01\x00\x01\x00\x00\x00\x00;", "unsupported_media"),
        (b"MZ\x90\x00 not an image", "unsupported_media"),
        (b"", "unsupported_media"),
    ],
)
def test_formats_are_decided_by_content_not_by_what_the_file_claims(data: bytes, code: str) -> None:
    with pytest.raises(ImageRejected) as caught:
        _prepare(data)
    assert caught.value.code == code


def test_animated_images_are_rejected() -> None:
    frames = [Image.new("RGB", (16, 16), c) for c in ("red", "blue")]
    animated = io.BytesIO()
    frames[0].save(animated, format="WEBP", save_all=True, append_images=frames[1:], duration=50)
    with pytest.raises(ImageRejected) as caught:
        _prepare(animated.getvalue())
    assert caught.value.code == "unsupported_media"


def test_a_png_header_with_a_corrupt_body_is_unreadable_not_a_crash() -> None:
    good = _encode(Image.new("RGB", (32, 32), "white"), "PNG")
    with pytest.raises(ImageRejected) as caught:
        _prepare(good[: len(good) // 2])
    assert caught.value.code == "unreadable_image"


def test_the_byte_limit_is_enforced_before_decoding() -> None:
    with pytest.raises(ImageRejected) as caught:
        _prepare(_encode(Image.new("RGB", (64, 64), "white"), "PNG"), max_bytes=100)
    assert caught.value.code == "object_too_large"


def test_a_decompression_bomb_is_refused() -> None:
    # ~10 MB of pixels as a 1-bit PNG compresses to a few KB but would decode to 81M pixels.
    bomb = _encode(Image.new("1", (9000, 9000)), "PNG")
    assert len(bomb) < 1_000_000
    with pytest.raises(ImageRejected) as caught:
        _prepare(bomb)
    assert caught.value.code == "image_too_large"


def test_sniffing_ignores_declared_names() -> None:
    assert sniff_mime(_encode(Image.new("RGB", (4, 4)), "PNG")) == "image/png"
    assert sniff_mime(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
    assert sniff_mime(b"\xff\xd8\xff\xe0") == "image/jpeg"
    assert sniff_mime(b"<?xml") is None
