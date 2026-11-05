from app.ai.agents import V3_IDS
from app.ai.search.policy import folded
from app.ai.skills.registry import SPECS


def resolve_skill(prompt: str, manual_id: str | None, agent: str) -> str | None:
    if agent not in V3_IDS:
        return None
    if manual_id:
        if manual_id not in SPECS:
            raise ValueError("unknown skill")
        return manual_id
    text = folded(prompt)
    if any(p in text for p in ("khong muon", "khong can", "dung goi y", "da di choi", "tung di choi")):
        return None
    requested = any(p in text for p in ("goi y", "muon", "giup", "nen", "co the", "hay "))
    hangout = requested and any(p in text for p in ("di choi", "di dau", "vui choi"))
    learn = requested and any(p in text for p in ("hoc dieu moi", "hoc gi", "hoc them", "hoc mot dieu"))
    if hangout == learn:
        return None
    return "hangout" if hangout else "learn-new-thing"
