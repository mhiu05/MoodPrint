import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

ROOT = Path(__file__).parent


@dataclass(frozen=True)
class SkillSpec:
    id: str
    name: str
    description: str
    version: str
    body: str
    body_hash: str


SPECS = {
    "hangout": ("Đi chơi", "Gợi ý hoạt động vừa sức và địa điểm khi bạn cần.", "2"),
    "learn-new-thing": ("Học điều mới", "Chọn một điều thú vị và thử trong 5–15 phút.", "1"),
}


class SkillRegistry:
    def __init__(self, root: Path = ROOT):
        self.root = root.resolve()
        result = {}
        for identity, (name, description, version) in SPECS.items():
            try:
                directory, path = root / identity, root / identity / "SKILL.md"
                if root.is_symlink() or directory.is_symlink() or path.is_symlink() or not path.resolve().is_relative_to(self.root):
                    raise ValueError("symlink or escaped skill path")
                if path.stat().st_size > 16384:
                    raise ValueError("oversize skill")
                raw = path.read_bytes()
                if len(raw) > 16384:
                    raise ValueError("oversize skill")
                text = raw.decode("utf-8", errors="strict")
                opening, header, body = text.split("---", 2)
                if opening.strip():
                    raise ValueError("missing skill frontmatter")
                metadata = {}
                for line in header.strip().splitlines():
                    key, value = line.split(":", 1)
                    if key.strip() in metadata:
                        raise ValueError("duplicate metadata")
                    metadata[key.strip()] = value.strip()
                if metadata != dict(id=identity, name=name, description=description, version=version) or not body.strip():
                    raise ValueError("skill metadata mismatch")
                result[identity] = SkillSpec(identity, name, description, version, body.strip(), hashlib.sha256(raw).hexdigest())
            except (OSError, UnicodeError, ValueError):
                logging.getLogger("moodprint").warning("metric=skill_unavailable skill=%s", identity)
        self._skills = MappingProxyType(result)

    def load(self):
        return self._skills

    def instructions(self, identity: str) -> str:
        if identity not in self._skills:
            raise ValueError("skill unavailable")
        return self._skills[identity].body
