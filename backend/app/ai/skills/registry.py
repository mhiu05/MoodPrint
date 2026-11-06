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
    "hangout": ("Đi chơi", "Gợi ý hoạt động, khám phá địa điểm và lên kế hoạch đi chơi cá nhân hóa theo sở thích, thời gian, ngân sách và nhu cầu của người dùng.", "1"),
    "learn-new-thing": ("Học điều mới", "Chọn một điều thú vị và thử trong 5–15 phút.", "1"),
    "weekly-review": ("Nhìn lại tuần", "Cùng nhìn lại 7 ngày qua từ chính những gì bạn đã ghi.", "1"),
    "mood-patterns": ("Nhận ra mẫu cảm xúc", "Tìm điều hay đi cùng một cảm xúc trong nhật ký, không kết luận nguyên nhân.", "1"),
    "guided-journal": ("Viết nhật ký có gợi ý", "Vài câu gợi ý ngắn để bạn viết vài dòng cho hôm nay.", "1"),
    "reframe-thought": ("Viết lại suy nghĩ", "Nhìn một suy nghĩ khó từ góc khác, công bằng và nhẹ nhàng hơn.", "1"),
}

AGENTS: dict[str, tuple[str, ...]] = {
    "hangout": ("dieuphoi", "nhatky", "hoatdong"),
    "learn-new-thing": ("dieuphoi", "nhatky", "hoatdong"),
    "weekly-review": ("nhatky",),
    "mood-patterns": ("nhatky",),
    "guided-journal": ("nhatky", "dieuphoi"),
    "reframe-thought": ("dieuphoi", "nhatky"),
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
