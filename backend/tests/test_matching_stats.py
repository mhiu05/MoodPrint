"""T-METRIC-01: counters move exactly once per action; the report suppresses small cells."""

import importlib.util
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select

from app.modules.social.models import MatchingStatsDaily
from tests.social_helpers import key, published_pair

pytestmark = pytest.mark.postgres


async def totals(app):
    async with app.state.database.sessions() as db:
        rows = (await db.scalars(select(MatchingStatsDaily))).all()
    return {row.scoring_version: (row.impressions, row.requests, row.accepts) for row in rows}


async def test_impressions_requests_and_accepts_count_once(clients):
    app, actors, refs = await published_pair(clients)
    (a, _), (b, _) = actors
    assert await totals(app) == {"rules-v1.1": (2, 0, 0)}  # one card for each viewer
    headers = key()
    body = {"candidateRef": refs[0]}
    sent = await a.post("/api/v1/connection-requests", json=body, headers=headers)
    replay = await a.post("/api/v1/connection-requests", json=body, headers=headers)
    assert sent.status_code == replay.status_code == 201
    assert await totals(app) == {"rules-v1.1": (2, 1, 0)}
    incoming = (await b.get("/api/v1/connection-requests")).json()[0]
    headers = key()
    accept = {"expectedVersion": incoming["version"]}
    path = f"/api/v1/connection-requests/{incoming['id']}/accept"
    assert (await b.post(path, json=accept, headers=headers)).status_code == 200
    assert (await b.post(path, json=accept, headers=headers)).status_code == 200
    assert await totals(app) == {"rules-v1.1": (2, 1, 1)}


async def test_v2_impressions_are_counted_under_rules_v2(clients):
    app, actors = clients
    app.state.settings.matching_scorer = "v2"
    await published_pair(clients)
    assert await totals(app) == {"rules-v2": (2, 0, 0)}


def report_module():
    path = Path(__file__).resolve().parents[2] / "scripts/report_beta_metrics.py"
    spec = importlib.util.spec_from_file_location("report_beta_metrics", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_report_suppresses_cells_below_five_and_refuses_hosted_targets():
    report = report_module()
    day = date(2026, 10, 25)
    rows = [(day, "rules-v1.1", 40, 6, 3), (day, "rules-v2", 4, 1, 0)]
    assert report.summarize(rows) == [
        {
            "scoringVersion": "rules-v1.1",
            "impressions": 40,
            "requests": 6,
            "accepts": "<5",
            "requestRate": 0.15,
            "acceptRate": None,
        },
        {
            "scoringVersion": "rules-v2",
            "impressions": "<5",
            "requests": "<5",
            "accepts": "<5",
            "requestRate": None,
            "acceptRate": None,
        },
    ]
    with pytest.raises(SystemExit):
        report.check_target("postgresql+psycopg://u:p@db.example.supabase.co:5432/postgres", False)
    assert report.check_target("postgresql+psycopg://u:p@127.0.0.1:16432/x_test", False)
