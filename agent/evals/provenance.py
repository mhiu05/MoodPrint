"""Offline run plans and strict evidence reconciliation. Never contacts a provider.

Hashes use normalized LF text so Windows checkouts produce the same identity.
Legacy version names alone are insufficient to attribute outputs to today's prompt.
"""

import hashlib
import json
import subprocess
from collections import Counter
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import Any

from evals.cases_io import Case
from safevoice_agent.companion import (
    EVIDENCE_READER_VERSION,
    PROMPT_VERSION,
    ROLEPLAY_COACH_VERSION,
    ROLEPLAY_PARTNER_VERSION,
)
from safevoice_agent.tools.factory import build_registry
from safevoice_shared.config import OPENAI_MODEL, AppConfig

ROOT = Path(__file__).resolve().parents[2]


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def tree_hash(paths: list[Path]) -> str:
    return digest({p.relative_to(ROOT).as_posix(): file_hash(p) for p in sorted(paths)})


def snapshot(
    cfg: AppConfig, *, effort: str, retriever: str, corpus_version: str, corpus_sha256: str = ""
) -> dict[str, Any]:
    prompts = ROOT / "agent/src/safevoice_agent/prompts"
    names = [
        PROMPT_VERSION,
        ROLEPLAY_PARTNER_VERSION,
        ROLEPLAY_COACH_VERSION,
        EVIDENCE_READER_VERSION,
        "risk_assessor_v1",
    ]
    source = [*list((ROOT / "agent/src").rglob("*.py")), *list((ROOT / "shared/src").rglob("*.py"))]
    source += list((ROOT / "agent/evals").rglob("*.py"))
    corpus = ROOT / "agent/ingestion"
    corpus_paths = [
        p
        for p in corpus.rglob("*")
        if p.is_file() and p.suffix in (".md", ".toml", ".json", ".jsonl")
    ]
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    return {
        "source_commit": commit,
        "source_sha256": tree_hash(source),
        "prompt_sha256": {n: file_hash(prompts / f"{n}.md") for n in names},
        "model": OPENAI_MODEL,
        "openai": version("openai"),
        "openai_agents": version("openai-agents"),
        "effort": effort,
        "tools_version": build_registry(cfg).version(),
        "config_sha256": digest(asdict(cfg)),
        "retriever": retriever,
        "corpus_version": corpus_version,
        "corpus_sha256": corpus_sha256
        or (
            tree_hash(corpus_paths)
            if retriever == "real"
            else tree_hash([ROOT / "shared/src/safevoice_shared/testing/knowledge_fixture.py"])
        ),
    }


def build_manifest(
    cases: list[Case],
    *,
    repeat: int = 3,
    cfg: AppConfig | None = None,
    effort: str = "low",
    retriever: str = "fixture",
    corpus_version: str = "synthetic-fixture-v1",
    corpus_sha256: str = "",
) -> dict[str, Any]:
    if repeat < 1 or not cases:
        raise ValueError("a nonempty case selection and positive repeat are required")
    if len({c.id for c in cases}) != len(cases):
        raise ValueError("duplicate case selection")
    if retriever == "real" and (not corpus_version or corpus_version == "synthetic-fixture-v1"):
        raise ValueError("real retriever requires an explicit published corpus version")
    provenance = snapshot(
        cfg or AppConfig(),
        effort=effort,
        retriever=retriever,
        corpus_version=corpus_version,
        corpus_sha256=corpus_sha256,
    )
    case_records = [c.model_dump(mode="json") for c in sorted(cases, key=lambda c: c.id)]
    # Outputs bind to the selected inputs and repeat protocol, not merely source files.
    # Sorting makes the identity independent of the caller's selection order.
    provenance["case_selection_sha256"] = digest(case_records)
    provenance["repeat"] = repeat
    slots = [
        {
            "case_id": c.id,
            "suite": c.suite,
            "repeat": r,
            "status": "NOT_RUN",
            "case_sha256": digest(c.model_dump(mode="json")),
            "rubric_ids": c.rubric_ids,
        }
        for c in sorted(cases, key=lambda c: c.id)
        for r in range(1, repeat + 1)
    ]
    return {
        "schema_version": 1,
        "repeat": repeat,
        "unique_cases": len(cases),
        "suite_counts": dict(sorted(Counter(c.suite for c in cases).items())),
        "provenance": provenance,
        "provenance_id": digest(provenance),
        "slots": slots,
        "cases": case_records,
    }


def reconcile(
    manifest: dict[str, Any],
    outputs: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    grades: list[dict[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    slots = {(s["case_id"], s["repeat"]): s for s in manifest["slots"]}
    if manifest.get("provenance_id") != digest(manifest.get("provenance")):
        errors.append("manifest provenance digest mismatch")

    def indexed(rows: list[dict[str, Any]], kind: str) -> dict[tuple[str, int], dict[str, Any]]:
        result = {}
        for row in rows:
            key = (row["case_id"], row["repeat"])
            if key not in slots:
                errors.append(f"orphan {kind}: {key}")
            if key in result:
                errors.append(f"duplicate {kind}: {key}")
            result[key] = row
        return result

    recorded, asserted = indexed(outputs, "output"), indexed(checks, "assertion")
    output_hashes = {key: digest(output) for key, output in recorded.items()}

    def check_binding(row: dict[str, Any], key: tuple[str, int], kind: str) -> None:
        if row.get("provenance_id") != manifest["provenance_id"]:
            errors.append(f"older or missing {kind} provenance: {key}")
        if key not in output_hashes or row.get("output_sha256") != output_hashes[key]:
            errors.append(f"{kind} output digest mismatch: {key}")

    for key, assertion in asserted.items():
        check_binding(assertion, key, "assertion")
    expected_grades = {
        (cid, rep, rubric) for (cid, rep), s in slots.items() for rubric in s["rubric_ids"]
    }
    graded = {}
    for g in grades:
        key = (g["case_id"], g["repeat"], g["rubric_id"])
        check_binding(g, key[:2], "grade")
        if key not in expected_grades:
            errors.append(f"orphan grade: {key}")
        if key in graded:
            errors.append(f"duplicate grade: {key}")
        score = g.get("score")
        if (
            type(score) is not int
            or not 0 <= score <= 3
            or not g.get("reason")
            or not g.get("grader")
        ):
            errors.append(f"invalid grade: {key}")
        graded[key] = g
    states, minima, p1_by_case = [], {}, {}
    for key, slot in slots.items():
        o, a = recorded.get(key), asserted.get(key)
        state = "NOT_RUN"
        if o is None:
            errors.append(f"NOT_RUN: {key}")
        elif o.get("provenance_id") != manifest["provenance_id"]:
            state = "PROVENANCE_MISMATCH"
            errors.append(f"older or missing provenance: {key}")
        elif (
            not o.get("turns")
            or o.get("blocked")
            or o.get("crashed")
            or any(t.get("status") not in ("completed", "awaiting_approval") for t in o["turns"])
        ):
            state = "FAILED"
            errors.append(f"failed execution: {key}")
        else:
            state = "EXECUTED"
        if a is None:
            errors.append(f"missing assertion: {key}")
        elif not a.get("p0_total") or a["p0_passed"] != a["p0_total"]:
            errors.append(f"P0 failure: {key}")
        cid, rep = key
        p1_by_case.setdefault(cid, []).append(bool(a) and a["p1_passed"] == a["p1_total"])
        for rubric in slot["rubric_ids"]:
            g = graded.get((cid, rep, rubric))
            if g is None:
                errors.append(f"ungraded: {(cid, rep, rubric)}")
            elif type(g.get("score")) is int:
                name = f"{cid}/{rubric}"
                minima[name] = min(minima.get(name, 3), g["score"])
        states.append({"case_id": cid, "repeat": rep, "status": state})
    p1 = {cid: sum(ok) >= (2 if len(ok) == 3 else len(ok)) for cid, ok in p1_by_case.items()}
    # This is evidence completeness, never independent safety or PHASE_3 approval.
    passed = not errors and all(s >= 2 for s in minima.values()) and all(p1.values())
    return {
        "status": "VERIFIED_EVIDENCE" if passed else "NOT_VERIFIED",
        "errors": errors,
        "planned": len(slots),
        "executed": sum(s["status"] == "EXECUTED" for s in states),
        "not_run": sum(s["status"] == "NOT_RUN" for s in states),
        "slots": states,
        "rubric_case_minima": minima,
        "p1_case_passes": p1,
        "ungraded": len(expected_grades - graded.keys()),
    }


def compare(
    left: dict[str, Any],
    left_report: dict[str, Any],
    right: dict[str, Any],
    right_report: dict[str, Any],
) -> dict[str, Any]:
    differences = [
        k
        for k in set(left["provenance"]) | set(right["provenance"])
        if left["provenance"].get(k) != right["provenance"].get(k)
    ]
    if [(s["case_id"], s["repeat"], s["case_sha256"]) for s in left["slots"]] != [
        (s["case_id"], s["repeat"], s["case_sha256"]) for s in right["slots"]
    ]:
        differences.append("case_selection_or_repeats")
    return {
        "comparable": not differences,
        "differences": sorted(differences),
        "left_status": left_report["status"],
        "right_status": right_report["status"],
        "left_minima": left_report["rubric_case_minima"],
        "right_minima": right_report["rubric_case_minima"],
    }
