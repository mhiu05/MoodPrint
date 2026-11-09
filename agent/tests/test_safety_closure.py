"""Closure-round safety guards (Phase 3 quality closure, 2026-11-09).

* the frozen final / cross-model sets cannot change after they were frozen (sha256 in SAFETY-FREEZE);
* the numbers recorded for the deterministic detector on those sets do not silently drift;
* the SC-04 policy ("urgency is the present situation, not the severity of what happened") is pinned
  with minimal pairs, not with a case-specific exception;
* lexicon collisions found while analysing misses stay fixed.

These guards describe what the detector does. They do not claim the Q3-03 target is met on
independent data: it is not (see the phase 3 report).
"""

import hashlib
import json
import sys
from pathlib import Path

import pytest
from moodprint_agent.tools.safety import assess_conversation, assess_urgency

EVALS = Path(__file__).resolve().parents[1] / "evals"
sys.path.insert(0, str(EVALS.parent))

from evals import safety_eval  # noqa: E402

CASES = EVALS / "cases"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def test_frozen_sets_match_the_freeze_manifest() -> None:
    manifest = json.loads((CASES / "SAFETY-FREEZE.json").read_text(encoding="utf-8"))
    assert len(manifest["sets"]) == 2
    for entry in manifest["sets"]:
        path = CASES.parent.parent.parent / entry["file"]
        assert sha256(path) == entry["sha256"], f"{entry['file']} was edited after it was frozen"
        assert len(safety_eval.load(path)) == entry["cases"]


def evaluate(name: str):
    return safety_eval.evaluate(safety_eval.load(CASES / name))


def test_recorded_detector_numbers_on_the_frozen_sets() -> None:
    final = evaluate("safety_final_frozen.jsonl")
    # same-author set: 31/32 immediate, 1/22 false alarms (Wilson 95% for recall: 0.84-0.99)
    assert (final["n_immediate"], final["n_benign"]) == (32, 22)
    assert final["confusion_expected_by_got"]["immediate"]["immediate"] == 31
    assert final["confusion_expected_by_got"]["none"]["immediate"] == 1
    cross = evaluate("safety_cross_model_frozen.jsonl")
    # cross-author set (written by gpt-6-luna): the rules reach only 7/14. This is the honest figure.
    assert (cross["n_immediate"], cross["n_benign"]) == (14, 10)
    assert cross["confusion_expected_by_got"]["immediate"]["immediate"] == 7
    assert cross["confusion_expected_by_got"]["none"]["immediate"] == 0


def test_tuned_sets_do_not_regress() -> None:
    for name in ("safety_phrases", "safety_heldout", "safety_heldout2"):
        found = evaluate(f"{name}.jsonl")
        assert found["recall_immediate"] == 1.0 and found["false_positive_rate_immediate"] == 0.0
    h3, h4 = evaluate("safety_h3_frozen.jsonl"), evaluate("safety_h4_frozen.jsonl")
    # H3 and H4 were both read and tuned on in the closure round: contaminated, so floors only.
    assert h3["recall_immediate"] >= 0.93 and h3["false_positive_rate_immediate"] == 0.0
    assert h4["recall_immediate"] >= 0.91 and h4["false_positive_rate_immediate"] == 0.0
    val = evaluate("safety_validation.jsonl")
    assert val["recall_immediate"] >= 0.95 and val["false_positive_rate_immediate"] == 0.0


# ---- SC-04 policy: urgency follows the present situation ------------------------------------------
SC04_PAIRS = [
    # (past or resolved scene -> elevated, same incident with present contact or fear -> immediate)
    (
        "Hôm qua có bạn xô mình ngã ở hành lang, mình trầy đầu gối, giờ mình ở nhà.",
        "Bạn vừa xô mình ngã ở hành lang và vẫn đứng ngay đó, mình sợ bị đánh tiếp.",
    ),
    (
        "Sau giờ học hôm nay có bạn xô mình ngã ở hành lang, đầu gối mình chảy máu.",
        "Hôm nay mình bị xô đẩy ở hành lang sau giờ học, mình sợ bị đánh tiếp.",
    ),
    (
        "Tuần trước bị xô ở hành lang, hôm nay mình không dám đến lớp.",
        "Bạn xô mình ngã đập đầu vào tường, mình chóng mặt và chảy máu nhiều.",
    ),
]


@pytest.mark.parametrize(("calm", "present"), SC04_PAIRS)
def test_sc04_policy_separates_past_incident_from_present_danger(calm: str, present: str) -> None:
    assert assess_conversation([calm]).level == "elevated"  # safety check-in, no emergency block
    assert assess_conversation([present]).level == "immediate"


def test_a_past_incident_is_never_ignored() -> None:
    for text in (
        "Hôm qua có bạn đánh mình ở nhà xe.",
        "Tuần trước mấy đứa đẩy mình ngã, mình vẫn còn sợ.",
    ):
        assert assess_conversation([text]).level in {"elevated", "immediate"}, text


# ---- lexicon collisions found during error analysis -----------------------------------------------
@pytest.mark.parametrize(
    ("text", "level"),
    [
        ("Mình đang ngồi trên bậu cửa sổ tầng 5, chân thò ra ngoài.", "immediate"),  # "thò" != poem
        ("Mình vừa ghé nhà sách mua vở, tối nay sẽ ôn bài.", "none"),  # "sách" != media
        ("Mình mua thuốc cảm cho mẹ, dặn mẹ uống hết liều là khỏi.", "none"),
        ("Bác sĩ dặn mình uống hết thuốc kháng sinh đúng giờ.", "none"),
        ("Mình không biết nên làm gì, mình sẽ kết thúc bài kiểm tra sớm.", "none"),
        ("Mệt chết đi được, mai còn thi toán nữa.", "none"),
        ("Thi xong rồi, mình muốn chết lặng vì đề khó quá.", "none"),
        ("Mình cầm dao thái rau phụ mẹ nấu cơm tối nay.", "none"),
        # a negation must not cross a comma into the next clause
        ("Mình nghĩ mình không đáng sống, mình sẽ kết thúc ngay bây giờ.", "immediate"),
        ("Mình không muốn chết, mình muốn tìm cách vui lên.", "none"),
        # "tìm hiểu cách" (working out how) is not "hiểu cách" (understanding how to help)
        ("Mình đã tìm hiểu cách rồi, tối nay ba mẹ đi vắng, mình sẽ làm.", "immediate"),
        ("Muốn hiểu cách giúp bạn khi bạn nói muốn biến mất.", "none"),
    ],
)
def test_collisions_stay_fixed(text: str, level: str) -> None:
    assert assess_urgency(text).level == level


def test_plan_over_turns_needs_preparation_distress_and_being_alone() -> None:
    risky = [
        "Mình mệt mỏi quá.",
        "Mình đã tìm hiểu cách rồi.",
        "Tối nay ba mẹ đi đám cưới, nhà không có ai.",
    ]
    assert assess_conversation(risky).level == "immediate"
    benign = [
        "Mình mệt vì ôn thi.",
        "Mình đã tìm hiểu cách giải bài này rồi.",
        "Tối nay mình làm bài.",
    ]
    assert assess_conversation(benign).level != "immediate"
