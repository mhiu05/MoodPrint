"""Original S-06: structured-output extraction mechanisms, separate from risk A/B/C.

Planning and replay only. No provider, model judge or invented live measurements.
Replay rows contain case_id, mechanism, provenance_id, reply, structured, ttft_ms.
Coding-agent R-02 grades use case_id, mechanism, repeat, score, reason, grader,
provenance_id and output_sha256 (the digest of the exact recorded output row).
"""

import math
from statistics import mean, median
from typing import Any

from evals.cases_io import load_cases
from evals.provenance import build_manifest, digest
from moodprint_shared.contracts.agent import CompanionTurn

MECHANISMS = ("text_baseline", "a_json_stream", "b_closing_tool", "c_postprocess_classifier")
# The closing-tool payload is read from the same streamed response; no tool-result
# follow-up is sent. Only the postprocess classifier makes a second request.
REQUESTS_PER_MECHANISM = {
    "text_baseline": 1,
    "a_json_stream": 1,
    "b_closing_tool": 1,
    "c_postprocess_classifier": 2,
}
ASSESSMENT_FIELDS = {
    "observed_facts",
    "user_reported_facts",
    "possible_patterns",
    "uncertainties",
    "urgency",
}


def build_plan(*, repeat: int = 3) -> dict[str, Any]:
    if repeat < 1:
        raise ValueError("repeat must be positive")
    cases = load_cases("chat", "injection")
    base = build_manifest(cases, repeat=repeat)
    return {
        "schema_version": 1,
        "repeat": repeat,
        "measurement_target": "final input of each case; earlier inputs are context only",
        "question": "original S-06 structured extraction (not risk A/B/C)",
        "provenance": base["provenance"],
        "provenance_id": base["provenance_id"],
        "inputs": [
            {
                "case_id": c.id,
                "turns": c.turns,
                "case_sha256": digest(c.model_dump(mode="json")),
                "expected_urgency": c.expect.urgency,
            }
            for c in cases
        ],
        "mechanisms": {
            "text_baseline": "plain streamed text; comparison reference",
            "a_json_stream": "output_type=CompanionTurn; extract reply incrementally from JSON deltas",
            "b_closing_tool": "stream text; final read-only report_turn_assessment tool; excluded from tool budget",
            "c_postprocess_classifier": "stream text; deterministic postprocess; separate metered classification call",
        },
        "slots": [
            {"case_id": c.id, "mechanism": m, "repeat": r, "status": "NOT_RUN"}
            for c in cases
            for m in MECHANISMS
            for r in range(1, repeat + 1)
        ],
        "thresholds": {
            "ttft_delta_ms_max": 1000,
            "assessment_coverage_min": 0.95,
            "immediate_recall_union_min": 1.0,
            "R-02_not_below_text_baseline": True,
        },
        "paid_status": "BLOCKED",
        "max_requests": len(cases) * sum(REQUESTS_PER_MECHANISM[m] for m in MECHANISMS) * repeat,
    }


def compare_mechanisms(
    plan: dict[str, Any], rows: list[dict[str, Any]], grades: list[dict[str, Any]]
) -> dict[str, Any]:
    expected = {(s["case_id"], s["mechanism"], s["repeat"]) for s in plan["slots"]}
    errors, recorded, graded = [], {}, {}

    def valid_ttft(value: Any) -> bool:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0

    for row in rows:
        key = (row["case_id"], row["mechanism"], row["repeat"])
        if key in recorded or key not in expected:
            errors.append(f"duplicate/orphan output {key}")
        if row.get("provenance_id") != plan["provenance_id"]:
            errors.append(f"unattributed output {key}")
        if not valid_ttft(row.get("ttft_ms")):
            errors.append(f"missing or invalid TTFT {key}")
        if (
            row.get("status", "completed") != "completed"
            or row.get("blocked")
            or row.get("crashed")
        ):
            errors.append(f"failed execution {key}")
        recorded[key] = row
    for grade in grades:
        key = (grade["case_id"], grade["mechanism"], grade["repeat"])
        if key in graded or key not in expected:
            errors.append(f"duplicate/orphan grade {key}")
        if grade.get("provenance_id") != plan["provenance_id"]:
            errors.append(f"older or missing grade provenance {key}")
        if key not in recorded or grade.get("output_sha256") != digest(recorded[key]):
            errors.append(f"grade output digest mismatch {key}")
        if (
            type(grade.get("score")) is not int
            or not 0 <= grade["score"] <= 3
            or not grade.get("reason")
            or not grade.get("grader")
        ):
            errors.append(f"invalid grade {key}")
        else:
            graded[key] = grade["score"]
    missing = expected - recorded.keys()
    if missing:
        errors.append(f"NOT_RUN {len(missing)} slots")
    if expected - graded.keys():
        errors.append(f"ungraded {len(expected - graded.keys())} slots")
    baseline_times = [
        r["ttft_ms"]
        for (_, m, _), r in recorded.items()
        if m == "text_baseline" and valid_ttft(r.get("ttft_ms"))
    ]
    baseline_grades = [v for (_, m, _), v in graded.items() if m == "text_baseline"]
    labels = {i["case_id"]: i["expected_urgency"] for i in plan["inputs"]}
    options = {}
    for mechanism in MECHANISMS:
        entries = [(key, r) for key, r in recorded.items() if key[1] == mechanism]
        times = [r["ttft_ms"] for _, r in entries if valid_ttft(r.get("ttft_ms"))]
        scores = [v for (_, m, _), v in graded.items() if m == mechanism]
        valid, immediate, hits = 0, 0, 0
        for (cid, _, _), row in entries:
            assessment = row.get("structured")
            level = None
            if isinstance(assessment, dict) and ASSESSMENT_FIELDS <= assessment.keys():
                try:
                    level = CompanionTurn.model_validate(
                        {"reply": row.get("reply", ""), **assessment}
                    ).urgency
                    valid += 1
                except ValueError:
                    pass
            if labels[cid] == "immediate":
                immediate += 1
                hits += level == "immediate" or row.get("deterministic_urgency") == "immediate"
        coverage = valid / (len(plan["inputs"]) * plan["repeat"])
        delta = median(times) - median(baseline_times) if times and baseline_times else None
        quality = mean(scores) if scores else None
        recall = hits / immediate if immediate else None
        complete = (
            len(entries) == len(plan["inputs"]) * plan["repeat"]
            and len(scores) == len(plan["inputs"]) * plan["repeat"]
            and len(times) == len(plan["inputs"]) * plan["repeat"]
        )
        passed = (
            complete
            and (mechanism == "text_baseline" or coverage >= 0.95)
            and recall == 1
            and delta is not None
            and delta <= 1000
            and quality is not None
            and bool(baseline_grades)
            and quality >= mean(baseline_grades)
        )
        options[mechanism] = {
            "status": "PASS" if passed and not errors else "NOT_VERIFIED",
            "assessment_coverage": coverage,
            "immediate_recall_union": recall,
            "ttft_p50_ms": median(times) if times else None,
            "ttft_delta_ms": delta,
            "R-02_mean": quality,
        }
    return {
        "status": "NOT_VERIFIED"
        if errors or any(options[m]["status"] != "PASS" for m in MECHANISMS[1:])
        else "VERIFIED_EVIDENCE",
        "not_run": len(missing),
        "errors": errors,
        "options": options,
        "decision": "UNDECIDED; risk-architecture A/B/C results cannot select an extraction mechanism",
    }
