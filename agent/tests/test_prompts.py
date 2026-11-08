"""Prompt files are versioned artifacts: changing one must change its version and this pin."""

import hashlib
import re

import pytest
from moodprint_agent.companion import (
    EVIDENCE_READER_VERSION,
    PROMPT_VERSION,
    ROLEPLAY_COACH_VERSION,
    ROLEPLAY_PARTNER_VERSION,
    load_prompt,
)

PINNED_SHA256 = {
    "companion_v3": "24d3bb9f4faa0f5f0ab0b61cb18e7cc7fdcf6283bca7046a72d311ee977d633b",
    "roleplay_partner_v1": "a23922050aef6ed49056f40cdf5dbe573a9eb289e744b594cccf15c5df3cc778",
    "roleplay_coach_v1": "671dcf3ab3a3eccd28cec2a5c97dc194b5abed750feec7890dcc6d5da248d2bd",
    "evidence_reader_v1": "f99c4c151002c649f5628a12ae7094ed92fe42098f76114b07b25da5f8593b0c",
}


def _digest(name: str) -> str:
    # load_prompt uses universal newlines, so CRLF checkouts hash identically.
    return hashlib.sha256(load_prompt(name).encode("utf-8")).hexdigest()


def test_version_constants_name_the_pinned_files() -> None:
    assert {
        PROMPT_VERSION,
        ROLEPLAY_PARTNER_VERSION,
        ROLEPLAY_COACH_VERSION,
        EVIDENCE_READER_VERSION,
    } == set(PINNED_SHA256)


@pytest.mark.parametrize("name", sorted(PINNED_SHA256))
def test_prompt_hash_is_pinned(name: str) -> None:
    assert _digest(name) == PINNED_SHA256[name], (
        f"{name} changed: bump its version constant and update PINNED_SHA256"
    )


@pytest.mark.parametrize("name", sorted(PINNED_SHA256))
def test_prompts_contain_no_user_data_or_template_slots(name: str) -> None:
    text = load_prompt(name)
    assert not re.search(r"\{\{|\{[a-z_]+\}|%s|@[a-z0-9.-]+\.[a-z]{2,}", text)
    # The only phone number a prompt may mention is the verified 111 child-protection line.
    assert set(re.findall(r"\b\d{3,}\b", text)) <= {"111"}


def test_fixed_companion_prompt_stays_within_the_token_budget(capsys) -> None:
    estimate = len(load_prompt(PROMPT_VERSION)) // 3  # same len/3 rule as the context builder
    print(f"companion_v3 fixed prompt ≈ {estimate} tokens (budget 1800)")
    assert estimate <= 1_800


def test_companion_prompt_encodes_the_required_rules() -> None:
    text = load_prompt(PROMPT_VERSION)
    for required in (
        "knowledge_search",
        "[S1]",
        "CHƯA LƯU",
        "applied",
        "propose_memory",
        "analyze_evidence",
        "DỮ LIỆU",
        "Tổng đài 111",
        "không phải người thật",
    ):
        assert required in text, required
    assert "tel:" not in text and "http" not in text


@pytest.mark.parametrize("name", ["roleplay_partner_v1", "roleplay_coach_v1", "evidence_reader_v1"])
def test_role_prompts_treat_embedded_text_as_data(name: str) -> None:
    text = load_prompt(name)
    assert "không phải chỉ dẫn" in text or "không phải lệnh" in text
    assert "không tiết lộ" in text.lower()


def test_partner_prompt_forbids_tools_and_harmful_personas() -> None:
    text = load_prompt(ROLEPLAY_PARTNER_VERSION)
    assert "Không dùng công cụ" in text
    for banned_behavior in ("mắng", "thao túng", "đổ lỗi"):
        assert banned_behavior in text
