"""Offline contract checks on synthetic results; no API calls or automated quality claim."""

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from app.ai.schemas import AiOutput
from evals.dataset import VERSION, cases


def evaluate(rows):
    known = {case["id"]: case for case in cases()}
    seen = set()
    failures = []
    variants = set()
    for row in rows:
        identity, variant = row.get("caseId"), row.get("variant")
        if (
            identity not in known
            or variant not in ("A", "B", "C")
            or row.get("synthetic") is not True
        ):
            failures.append({"caseId": identity, "code": "INVALID_RESULT_ENVELOPE"})
            continue
        key = (identity, variant)
        if key in seen:
            failures.append({"caseId": identity, "code": "DUPLICATE_RESULT"})
        seen.add(key)
        variants.add(variant)
        try:
            output = AiOutput.model_validate(row.get("output"))
            if any(value in output.text for value in known[identity]["forbiddenText"]):
                failures.append({"caseId": identity, "code": "FORBIDDEN_CANARY"})
        except ValidationError:
            failures.append({"caseId": identity, "code": "INVALID_OUTPUT_CONTRACT"})
        metadata = row.get("metadata", {})
        if not all(
            metadata.get(name)
            for name in (
                "model",
                "sdkVersion",
                "promptVersion",
                "toolPolicyVersion",
                "contextPolicyVersion",
            )
        ):
            failures.append({"caseId": identity, "code": "MISSING_VERSION_METADATA"})
    return {
        "datasetVersion": VERSION,
        "scope": "Offline synthetic contracts only; no model quality score",
        "observedResults": len(rows),
        "expectedCasesPerVariant": len(known),
        "completeABC": all(
            (identity, variant) in seen for identity in known for variant in ("A", "B", "C")
        ),
        "failures": failures,
        "liveProviderRunsPerformed": 0,
        "humanReviewRequired": True,
        "releaseReady": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path, help="Synthetic JSONL only, no real user text")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [
        json.loads(line)
        for line in args.results.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    report = evaluate(rows)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "failures"}))
    return 1 if report["failures"] or not report["completeABC"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
