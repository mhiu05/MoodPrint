"""Citations come from the run's retrieval ledger, never from the model's memory.

The model may write ``[S1]`` markers. After the answer is complete we keep only markers whose
reference exists in this run's ledger (filled by ``knowledge_search``), renumber them in order of
first appearance, and drop the rest. An empty ledger therefore always yields zero citations.
"""

import re
from dataclasses import dataclass
from typing import Final

from moodprint_shared.contracts.knowledge import SourceCitation

from moodprint_agent.tools.context import RunScratch

_MARKER: Final = re.compile(r"\s?\[\s*S\s*(\d{1,3})\s*\]", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ResolvedAnswer:
    content: str
    citations: tuple[SourceCitation, ...]
    unverified_markers: int


def markers_in(content: str) -> list[str]:
    return [f"S{match.group(1)}" for match in _MARKER.finditer(content)]


def resolve_citations(content: str, scratch: RunScratch | None) -> ResolvedAnswer:
    ledger = scratch.citations if scratch is not None else {}
    order: dict[str, int] = {}
    unverified = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal unverified
        ref = f"S{match.group(1)}"
        if ref not in ledger:
            unverified += 1
            return ""
        number = order.setdefault(ref, len(order) + 1)
        lead = " " if match.group(0)[:1].isspace() else ""
        return f"{lead}[{number}]"

    cleaned = _MARKER.sub(replace, content)
    cleaned = re.sub(r"[ \t]+([,.;:!?])", r"\1", cleaned)
    citations = tuple(ledger[ref] for ref in order)
    return ResolvedAnswer(cleaned, citations, unverified)
