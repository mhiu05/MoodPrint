"""T-OPS-01: alarm config parses and is consistent; metric log lines are content-free."""

import json
import logging
import re
from pathlib import Path

import pytest

from app.core import logs
from tests.activity_helpers import enable, respond, started
from tests.social_helpers import key, open_room

ROOT = Path(__file__).resolve().parents[2]
ALARMS = json.loads((ROOT / "deploy/aws/cloudwatch-alarms.json").read_text(encoding="utf-8"))
AGENT = json.loads((ROOT / "deploy/aws/cloudwatch-agent.json").read_text(encoding="utf-8"))
SOURCE = "\n".join(
    path.read_text(encoding="utf-8") for path in (ROOT / "backend/app").rglob("*.py")
)
ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-|[0-9a-f]{32}|@", re.I)


def filter_metrics():
    return {
        transform["metricName"]
        for item in ALARMS["metricFilters"]
        for transform in item["metricTransformations"]
    }


def alarm_metrics(alarm):
    if "metrics" in alarm:
        return [query["metricName"] for query in alarm["metrics"] if "metricName" in query]
    return [alarm["metricName"]]


def test_log_groups_keep_thirty_days():
    collected = AGENT["logs"]["logs_collected"]["files"]["collect_list"]
    assert collected and all(entry["retention_in_days"] == 30 for entry in collected)
    assert {entry["log_group_name"] for entry in collected} == {ALARMS["logGroupName"]}


def test_every_filter_matches_a_line_the_backend_emits():
    for item in ALARMS["metricFilters"]:
        literal = item["filterPattern"].strip('"')
        prefix = literal.split(" ")[0]
        assert prefix.startswith("metric="), item["filterName"]
        assert f'"{prefix}' in SOURCE or f"'{prefix}" in SOURCE, literal
        for transform in item["metricTransformations"]:
            assert transform["metricNamespace"] == ALARMS["namespace"]


def test_every_alarm_references_a_filter_or_agent_metric():
    agent = {
        f"{name}_{measure}"
        for name, spec in AGENT["metrics"]["metrics_collected"].items()
        for measure in spec["measurement"]
    }
    known = filter_metrics()
    required = {"Http5xxCount", "ReadinessFailing", "AiRunFailedRate", "AiBudget80", "DiskUsed80"}
    assert required <= {alarm["alarmName"] for alarm in ALARMS["alarms"]}
    for alarm in ALARMS["alarms"]:
        for name in alarm_metrics(alarm):
            assert name in known or name in agent, (alarm["alarmName"], name)
        if "metrics" in alarm:
            expression = next(q for q in alarm["metrics"] if "expression" in q)
            ids = {q["id"] for q in alarm["metrics"]}
            assert set(re.findall(r"\b[a-z]\w*\b", expression["expression"])) <= ids


def test_operational_lines_reach_stdout_once():
    logger = logging.getLogger("moodprint")
    before = list(logger.handlers)
    try:
        logs.configure()
        logs.configure()
        added = [h for h in logger.handlers if h not in before]
        assert len(added) == 1 and logger.level == logging.INFO
    finally:
        for handler in logger.handlers[:]:
            if handler not in before:
                logger.removeHandler(handler)
        logger.setLevel(logging.NOTSET)


@pytest.mark.postgres
async def test_metric_lines_are_content_free(clients, caplog):
    app, actors, _, room = await open_room(clients)
    enable(app)
    (a, _), (b, _) = actors
    with caplog.at_level(logging.INFO, logger="moodprint"):
        sid = (await started(a, b, room))["id"]
        await respond(b, sid, 1, text="BÍ-MẬT-RIÊNG")
        ref = (
            await a.post(f"/api/v1/connections/{room}/peer-reference", json={}, headers=key())
        ).json()["peerRef"]
        report = await a.post(
            "/api/v1/reports", json={"peerRef": ref, "reason": "Xúc phạm"}, headers=key()
        )
        assert report.status_code == 201, report.text
        await a.post(f"/api/v1/connections/{room}/block", json={}, headers=key())
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("metric=")]
    names = {line.split(" ")[0] for line in lines}
    assert {"metric=activity_started", "metric=report_created", "metric=activity_aborted"} <= names
    assert "metric=activity_aborted kind=icebreaker reason=blocked" in lines
    for line in lines:
        assert not ID.search(line) and "BÍ-MẬT" not in line and "Xúc phạm" not in line, line
