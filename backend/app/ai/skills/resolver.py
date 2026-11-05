from app.ai.agents import V3_IDS
from app.ai.proactive.safety import distress_screen
from app.ai.search.policy import folded
from app.ai.skills.registry import AGENTS, SPECS


def resolve_skill(prompt: str, manual_id: str | None, agent: str) -> str | None:
    if agent not in V3_IDS:
        return None
    if distress_screen([prompt]):
        return None
    if manual_id:
        if manual_id not in SPECS:
            raise ValueError("unknown skill")
        if agent not in AGENTS[manual_id]:
            raise ValueError("skill not for agent")
        return manual_id
    text = folded(prompt)
    if any(p in text for p in ("khong muon", "khong can", "dung goi y", "da di choi", "tung di choi")):
        return None
    requested = any(p in text for p in ("goi y", "muon", "giup", "nen", "co the", "hay "))
    hangout = requested and any(p in text for p in ("di choi", "di dau", "vui choi"))
    learn = requested and any(p in text for p in ("hoc dieu moi", "hoc gi", "hoc them", "hoc mot dieu"))
    matches = [identity for identity, matched in (("hangout", hangout), ("learn-new-thing", learn)) if matched]
    patterns = {
        "weekly-review": ("nhin lai tuan", "tong ket tuan", "tuan qua cua minh", "tuan nay minh the nao"),
        "mood-patterns": ("mau cam xuc", "hay buon khi", "hay met khi", "hay lo khi", "lap di lap lai"),
        "guided-journal": ("viet nhat ky", "khong biet viet gi", "goi y viet"),
        "reframe-thought": ("viet lai suy nghi", "nghi theo cach khac", "goc nhin khac"),
    }
    matches.extend(identity for identity, phrases in patterns.items()
                   if agent in AGENTS[identity] and any(phrase in text for phrase in phrases))
    return matches[0] if len(matches) == 1 else None
