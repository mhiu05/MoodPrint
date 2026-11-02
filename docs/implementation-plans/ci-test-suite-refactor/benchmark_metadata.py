"""Summarize saved GitHub API timestamps; no API/network/test calls."""
import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def delta(start, end):
    return (datetime.fromisoformat(end.replace("Z", "+00:00")) - datetime.fromisoformat(start.replace("Z", "+00:00"))).total_seconds()


def summarize(root):
    runs = read(root / "github-runs.json")
    byid = {run["databaseId"]: run for run in runs}
    measured, steps = [], defaultdict(list)
    for path in sorted(root.glob("github-jobs-*.json")):
        for job in read(path)["jobs"]:
            if job["conclusion"] != "success":
                continue
            run = byid.get(job["run_id"])
            seconds = delta(job["started_at"], job["completed_at"])
            row = {"run_id": job["run_id"], "job_id": job["id"], "sha": job["head_sha"], "branch": job["head_branch"], "run_attempt": job["run_attempt"], "job_seconds": seconds, "workflow_seconds": delta(run["createdAt"], job["completed_at"]) if run else None, "url": job["html_url"], "steps": []}
            for step in job["steps"]:
                if step.get("started_at") and step.get("completed_at"):
                    value = delta(step["started_at"], step["completed_at"])
                    row["steps"].append({"name": step["name"], "seconds": value, "conclusion": step["conclusion"]})
                    if step["conclusion"] == "success":
                        steps[step["name"]].append(value)
            measured.append(row)
    pairs = defaultdict(list)
    for run in runs:
        pairs[(run["headSha"], run["headBranch"])].append(run)
    duplicates = []
    for (sha, branch), group in pairs.items():
        if {r["event"] for r in group} >= {"push", "pull_request"}:
            duplicates.append({"sha": sha, "branch": branch, "run_ids": [r["databaseId"] for r in group], "events": [r["event"] for r in group], "conclusions": [r["conclusion"] for r in group]})
    return {"method": "API job timestamps, one job/run; job sum equals verify critical path; workflow includes startup/queue; sample not identical workloads; not a before/after experiment", "sample_runs": len(runs), "successful_measured_jobs": len(measured), "job_seconds_median": statistics.median(r["job_seconds"] for r in measured), "job_seconds_min": min(r["job_seconds"] for r in measured), "job_seconds_max": max(r["job_seconds"] for r in measured), "step_summary": {name: {"n": len(values), "median_seconds": statistics.median(values), "min_seconds": min(values), "max_seconds": max(values)} for name, values in sorted(steps.items())}, "duplicate_push_pr_groups": duplicates, "runs": measured}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    report = summarize(args.evidence_dir)
    (args.evidence_dir / "ci-baseline.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("runs", "step_summary")}, indent=2))
