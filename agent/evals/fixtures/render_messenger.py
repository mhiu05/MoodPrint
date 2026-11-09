"""Rasterise the eight fictional Messenger-style SVG fixtures to PNG with Pillow.

The SVGs contain only rectangles, circles and text, so a tiny renderer is enough and avoids a
browser dependency. Output is committed (agent/evals/fixtures/messenger_0N.png); regenerate with
``uv run python agent/evals/fixtures/render_messenger.py``.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "frontend" / "public" / "fixtures"
OUT = Path(__file__).resolve().parent
SCALE = 2
NS = "{http://www.w3.org/2000/svg}"
FONTS = (
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
BOLD = (
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)


def font(size: float, bold: bool) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in BOLD if bold else FONTS:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, int(size * SCALE))
    return ImageFont.load_default(size=int(size * SCALE))


def color(value: str | None, default: str = "#000000") -> str:
    return value if value and value != "none" else default


def render(svg: Path) -> Image.Image:
    root = ET.fromstring(svg.read_text(encoding="utf-8"))
    width, height = (float(root.get(k, "0")) for k in ("width", "height"))
    image = Image.new("RGB", (int(width * SCALE), int(height * SCALE)), "white")
    draw = ImageDraw.Draw(image)

    def walk(node: ET.Element, inherited: dict[str, str]) -> None:
        style = {
            **inherited,
            **{
                k: v
                for k, v in node.attrib.items()
                if k in ("fill", "font-size", "font-weight", "stroke")
            },
        }
        tag = node.tag.removeprefix(NS)
        if tag == "rect":
            x, y, w, h = (float(node.get(k, "0")) for k in ("x", "y", "width", "height"))
            radius = float(node.get("rx", "0"))
            box = [x * SCALE, y * SCALE, (x + w) * SCALE, (y + h) * SCALE]
            fill = color(node.get("fill"), "#ffffff")
            if radius:
                draw.rounded_rectangle(box, radius=radius * SCALE, fill=fill)
            else:
                draw.rectangle(box, fill=fill)
        elif tag == "circle":
            cx, cy, r = (float(node.get(k, "0")) for k in ("cx", "cy", "r"))
            draw.ellipse(
                [(cx - r) * SCALE, (cy - r) * SCALE, (cx + r) * SCALE, (cy + r) * SCALE],
                fill=color(node.get("fill"), "#cccccc"),
            )
        elif tag == "text":
            size = float(re.sub(r"[^0-9.]", "", style.get("font-size", "12")) or 12)
            bold = style.get("font-weight", "400") not in ("400", "normal")
            face = font(size, bold)
            text = "".join(node.itertext())
            x, y = float(node.get("x", "0")) * SCALE, float(node.get("y", "0")) * SCALE
            anchor = node.get("text-anchor", "start")
            box = draw.textbbox((0, 0), text, font=face)
            span = box[2] - box[0]
            if anchor == "middle":
                x -= span / 2
            elif anchor == "end":
                x -= span
            draw.text(
                (x, y), text, font=face, fill=color(style.get("fill"), "#253d43"), anchor="ls"
            )
        for child in node:
            walk(child, style)

    walk(root, {})
    return image


def main() -> None:
    for svg in sorted(SOURCE.glob("messenger_0*.svg")):
        target = OUT / f"{svg.stem}.png"
        render(svg).save(target, optimize=True)
        print(target.name, target.stat().st_size)


if __name__ == "__main__":
    main()
