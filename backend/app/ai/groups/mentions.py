"""@mention parsing for AI groups (05). Pure, deterministic, conservative.

A mention is ``@`` + a display name at a word boundary (so an e-mail address is never one),
outside quoted text (``"…"``, ``“…”``) and outside quote lines (``> …``). Picker ids from the
client are the stable form; both are merged and later checked against active members.
"""

import re
import unicodedata

from app.ai.collaboration.policy import fold

NAMES: dict[str, tuple[str, ...]] = {
    "dieuphoi": ("dieu phoi", "dieuphoi"),
    "nhatky": ("nhat ky", "nhatky"),
    "hoatdong": ("hoat dong", "hoatdong"),
    "all": ("moi nguoi", "tat ca", "ca nhom", "everyone", "all"),
}
ORDER = ("nhatky", "hoatdong", "dieuphoi")  # @mọi người: specialists first, Điều phối gathers last
_QUOTED = re.compile(r"\"[^\"\n]*\"|“[^”\n]*”|«[^»\n]*»")


def _unquoted(text: str) -> str:
    lines = [line for line in text.splitlines() if not line.lstrip().startswith(">")]
    return _QUOTED.sub(" ", "\n".join(lines))


def parse_mentions(text: str) -> tuple[tuple[str, ...], bool]:
    """(agents in mention order, everyone) found in the text."""
    folded = fold(unicodedata.normalize("NFC", _unquoted(text or "")))
    found: list[str] = []
    everyone = False
    for match in re.finditer(r"(?<![\w.])@", folded):
        tail = folded[match.end():]
        for agent, names in NAMES.items():
            if any(re.match(re.escape(name) + r"(?![\w])", tail) for name in names):
                if agent == "all":
                    everyone = True
                elif agent not in found:
                    found.append(agent)
                break
    return tuple(found), everyone


def resolve(text: str, picked: list[str]) -> tuple[tuple[str, ...], bool]:
    """Union of picker ids and parsed text mentions, picker order first."""
    parsed, everyone = parse_mentions(text)
    ordered: list[str] = []
    for agent in [*picked, *parsed]:
        if agent == "all":
            everyone = True
        elif agent not in ordered:
            ordered.append(agent)
    return tuple(ordered), everyone
