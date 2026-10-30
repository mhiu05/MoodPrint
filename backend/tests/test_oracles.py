"""Synthetic, hand-checked vectors for the existing frontend domain algorithms."""

from copy import deepcopy
from datetime import datetime

import pytest

from app.modules.matching.scoring import eligibility, half_up, recommendations, score
from app.modules.mood.scoring import demo_date, mood_summary


def profile(**changes):
    return {
        "interests": ["reading", "music", "walking"],
        "values": ["respect", "sincerity"],
        "style": "balanced",
        "goal": "shared-interests",
        "languages": ["vi"],
        "sources": [],
        **changes,
    }


def candidate(identifier="C01", **changes):
    return {
        "id": identifier,
        "alias": "Synthetic peer",
        "color": "sage",
        "profile": profile(),
        "version": 3,
        "consentVersion": 2,
        "allowed": True,
        "identity": {"displayName": "private", "gender": "private"},
        **changes,
    }


def state(**changes):
    return {
        "ready": True,
        "age": "adult",
        "consent": {"MATCH": True, "AI": False, "MEM": False},
        "published": profile(version=2, valid=True),
        "clock": 1000,
        "candidates": [candidate()],
        "blocked": [],
        "cooldowns": {},
        "requests": [],
        "connections": [],
        **changes,
    }


@pytest.mark.parametrize(
    ("numerator", "denominator", "expected"),
    [(77499, 1000, 77), (77500, 1000, 78), (77501, 1000, 78)],
)
def test_half_up_rounds_only_at_the_final_half(numerator, denominator, expected):
    assert half_up(numerator, denominator) == expected


@pytest.mark.parametrize(
    ("interests", "values", "style", "expected"),
    [
        (["reading", "music", "walking"], ["respect", "sincerity"], "listening", 90),
        (["reading", "music", "cooking"], ["respect", "sincerity"], "balanced", 78),
        (["music", "walking", "photography"], ["respect", "sincerity"], "direct", 68),
        (["reading", "walking", "english"], ["respect", "curiosity"], "listening", 44),
    ],
)
def test_score_preserves_hand_checked_frontend_vectors(interests, values, style, expected):
    assert score(profile(), profile(interests=interests, values=values, style=style)) == expected


def test_score_deduplicates_tags_without_mutating_inputs():
    left = profile(interests=["reading", "music", "walking", "reading"])
    right = profile(
        interests=["reading", "music", "cooking"],
        values=["respect", "sincerity", "respect"],
        languages=["vi", "vi"],
    )
    original = deepcopy((left, right))
    assert score(left, right) == 78
    assert (left, right) == original


@pytest.mark.parametrize(
    "changes",
    [
        {"interests": ["unknown", "music", "walking"]},
        {"interests": ["reading", "music"]},
        {"values": ["respect"]},
        {"languages": []},
        {"style": "unknown"},
        {"goal": "unknown"},
        {"rawText": "private"},
        {"sources": [{"id": "PI01", "version": True}]},
    ],
)
def test_invalid_profile_scores_zero(changes):
    assert score(profile(), profile(**changes)) == 0


def test_opposite_styles_remove_style_points():
    assert score(profile(style="direct"), profile(style="listening")) == 80


def test_integral_json_number_source_version_matches_javascript_integer_check():
    assert score(profile(), profile(sources=[{"id": "PI01", "version": 1.0}])) == 100


@pytest.mark.parametrize(
    "peer",
    [
        candidate(allowed=False),
        candidate(profile=profile(goal="friendship")),
        candidate(profile=profile(languages=["en"])),
        candidate(profile=profile(interests=["reading", "music", "reading"])),
    ],
)
def test_eligibility_applies_hard_filters_before_scoring(peer):
    assert not eligibility(profile(), peer)


def test_eligibility_requires_one_shared_language():
    assert eligibility(profile(), candidate(profile=profile(languages=["vi", "en"])))


def test_recommendations_have_exact_order_reasons_and_public_projection():
    peers = [
        candidate("C01", profile=profile(interests=["reading", "music", "cooking"])),
        candidate(
            "C02",
            profile=profile(
                interests=["reading", "walking", "english"],
                values=["respect", "curiosity"],
                style="listening",
            ),
        ),
        candidate(
            "C03",
            profile=profile(interests=["music", "walking", "photography"], style="direct"),
        ),
        candidate("C04", profile=profile(style="listening")),
        candidate("C05", profile=profile(languages=["en"])),
    ]
    snapshot = state(candidates=peers)
    original = deepcopy(snapshot)
    cards = recommendations(snapshot)
    assert [(card["candidate"]["id"], card["score"]) for card in cards] == [
        ("C04", 90),
        ("C01", 78),
        ("C03", 68),
        ("C02", 44),
    ]
    assert cards[0] == {
        "candidate": {
            "id": "C04",
            "alias": "Synthetic peer",
            "color": "sage",
            "profile": {
                "interests": ["reading", "music", "walking"],
                "values": ["respect", "sincerity"],
                "style": "listening",
                "goal": "shared-interests",
                "languages": ["vi"],
            },
        },
        "scoringVersion": "mock-v1",
        "profileVersion": 2,
        "peerVersion": 3,
        "score": 90,
        "reasons": ["Cùng thích đọc sách", "Cùng thích nghe nhạc", "Cùng thích đi bộ"],
    }
    assert snapshot == original
    cards[0]["candidate"]["profile"]["interests"].append("puzzles")
    assert snapshot == original


def test_threshold_includes_exactly_thirty_and_excludes_twenty_nine():
    peers = [
        candidate(
            "exact",
            profile=profile(
                interests=["reading", "music", "cooking", "english", "photography", "puzzles"],
                values=["respect", "sincerity", "curiosity", "kindness"],
                style="direct",
            ),
        ),
        candidate(
            "below",
            profile=profile(
                interests=[
                    "reading",
                    "music",
                    "walking",
                    "cooking",
                    "english",
                    "photography",
                    "puzzles",
                ],
                values=["curiosity", "kindness"],
            ),
        ),
    ]
    # 45*2/7 + 35*2/4 = 30.357...; 45*3/7 + 10 = 29.285...
    assert score(profile(style="listening"), peers[0]["profile"]) == 30
    assert score(profile(style="listening"), peers[1]["profile"]) == 29
    cards = recommendations(
        state(published=profile(style="listening", version=2, valid=True), candidates=peers)
    )
    assert [(card["candidate"]["id"], card["score"]) for card in cards] == [("exact", 30)]


def test_tied_candidates_use_ascending_ascii_id_and_top_five():
    peers = [candidate(identifier) for identifier in ["C9", "C2", "C10", "C1", "C8", "C0"]]
    cards = recommendations(state(candidates=peers))
    assert [card["candidate"]["id"] for card in cards] == ["C0", "C1", "C10", "C2", "C8"]


def test_reasons_follow_taxonomy_order_and_include_values_and_style():
    peer = candidate(
        profile=profile(
            interests=["cooking", "english", "puzzles"],
            values=["sincerity", "respect"],
        )
    )
    cards = recommendations(state(candidates=[peer]))
    assert cards[0]["reasons"] == [
        "Cùng coi trọng tôn trọng",
        "Cùng coi trọng chân thành",
        "Cùng cách trò chuyện",
    ]


@pytest.mark.parametrize(
    "changes",
    [
        {"ready": False},
        {"age": "teen"},
        {"consent": {"MATCH": False}},
        {"published": profile(version=2, valid=False)},
        {"published": None},
        {"blocked": ["C01"]},
        {"cooldowns": {"C01": 1001}},
        {"requests": [{"candidateId": "C01", "status": "pending"}]},
        {"connections": [{"candidateId": "C01", "status": "open"}]},
    ],
)
def test_recommendation_filters_reject_ineligible_state_or_pair(changes):
    assert recommendations(state(**changes)) == []


def test_expired_cooldown_and_terminal_markers_allow_discovery():
    snapshot = state(
        cooldowns={"C01": 1000},
        requests=[{"candidateId": "C01", "status": "cancelled"}],
        connections=[{"candidateId": "C01", "status": "closed"}],
    )
    assert len(recommendations(snapshot)) == 1


def test_absent_cooldown_does_not_exclude_before_unix_epoch():
    assert len(recommendations(state(clock=-1000))) == 1


def clock(value="2026-10-22T12:00:00+00:00"):
    return int(datetime.fromisoformat(value).timestamp() * 1000)


def mood(identifier, date, value, time=1000):
    return {"id": identifier, "date": date, "value": value, "time": time, "note": "", "version": 1}


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [("2026-10-22T16:59:59.999+00:00", "2026-10-22"), ("2026-10-22T17:00:00+00:00", "2026-10-23")],
)
def test_mood_date_crosses_midnight_at_utc_plus_seven(timestamp, expected):
    assert demo_date(clock(timestamp)) == expected


def test_mood_summary_preserves_missing_days_and_uses_distinct_day_values():
    entries = [
        mood(f"MD{i}", f"2026-10-{day}", value)
        for i, (day, value) in enumerate([(16, 3), (17, 2), (18, 4), (20, 3), (21, 4)])
    ]
    result = mood_summary(entries, clock())
    assert [bucket["date"] for bucket in result["buckets"]] == [
        "2026-10-16",
        "2026-10-17",
        "2026-10-18",
        "2026-10-19",
        "2026-10-20",
        "2026-10-21",
        "2026-10-22",
    ]
    assert [
        bucket["entry"]["value"] if bucket["entry"] else None for bucket in result["buckets"]
    ] == [3, 2, 4, None, 3, 4, None]
    assert {key: result[key] for key in ["count", "mean", "min", "max"]} == {
        "count": 5,
        "mean": 3.2,
        "min": 2,
        "max": 4,
    }
    entries.append(mood("today", "2026-10-22", 2))
    assert mood_summary(entries, clock())["mean"] == 3
    entries.pop()
    assert mood_summary(entries, clock())["mean"] == 3.2


def test_latest_time_then_descending_ascii_id_wins_without_input_mutation():
    entries = [
        mood("Z", "2026-10-22", 5, 999),
        mood("A", "2026-10-22", 1, 1000),
        mood("B", "2026-10-22", 4, 1000),
        mood("old", "2026-10-15", 2, 2000),
        mood("future", "2026-10-23", 3, 2000),
    ]
    original = deepcopy(entries)
    result = mood_summary(entries, clock())
    assert result["buckets"][-1]["entry"]["id"] == "B"
    assert {key: result[key] for key in ["count", "mean", "min", "max"]} == {
        "count": 1,
        "mean": 4,
        "min": 4,
        "max": 4,
    }
    assert entries == original


def test_empty_week_keeps_all_seven_null_buckets_and_null_statistics():
    result = mood_summary([], clock())
    assert len(result["buckets"]) == 7
    assert all(bucket["entry"] is None for bucket in result["buckets"])
    assert {key: result[key] for key in ["count", "mean", "min", "max"]} == {
        "count": 0,
        "mean": None,
        "min": None,
        "max": None,
    }
