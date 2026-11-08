"""Evaluation case schema and loader. Cases are synthetic; ids are stable so history is comparable."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CASE_DIR = Path(__file__).resolve().parent / "cases"
Urgency = Literal["none", "elevated", "immediate"]


class Setup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    corpus: Literal["fixture", "poisoned", "empty"] = "fixture"
    case_note: str | None = None  # text planted in the user's own case (injection via record data)
    memories: list[str] = Field(default_factory=list)  # approved memories shown to the model
    stale_memories: list[str] = Field(default_factory=list)
    attach_case: bool = False  # the conversation is linked to the synthetic case


class Expect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tools_called: list[str] = Field(default_factory=list)  # A-07: each must be called
    tools_forbidden: list[str] = Field(default_factory=list)  # A-08 / A-15
    urgency: Urgency | None = None  # A-12: minimum level of the last turn ('none' = exactly none)
    citations: Literal["required", "none", "any"] = "any"  # A-04 / A-06
    approvals: list[Literal["approve", "reject"]] = Field(default_factory=list)
    writes: int | None = None  # domain writes after all decisions
    candidates: int | None = None  # memory candidates the agent created (never memories)
    forbidden_text: list[str] = Field(default_factory=list)  # must not appear in any answer
    required_text_any: list[str] = Field(default_factory=list)  # at least one must appear


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    suite: Literal["chat", "knowledge", "injection", "approval", "memory", "screenshot", "roleplay"]
    risk: Literal["normal", "high"] = "normal"
    turns: list[str] = Field(default_factory=list)
    setup: Setup = Field(default_factory=Setup)
    expect: Expect = Field(default_factory=Expect)
    rubric_ids: list[str] = Field(default_factory=list)
    image: str | None = None  # screenshot fixture name
    scenario: str | None = None  # roleplay scenario key
    difficulty: int = 1
    note: str = ""


def load_cases(*suites: str) -> list[Case]:
    cases: list[Case] = []
    for path in sorted(CASE_DIR.glob("*.jsonl")):
        if path.stem.startswith("safety_"):
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                case = Case.model_validate(json.loads(line))
                if not suites or case.suite in suites:
                    cases.append(case)
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case ids")
    return cases
