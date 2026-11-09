"""Query diacritic restoration from the published corpus text. Local, no model call."""

from __future__ import annotations

import pytest
from moodprint_agent.knowledge.restore import Restorer

CORPUS = [
    "Bị bạn nhắn tin đe dọa thì hãy chụp màn hình rồi mới chặn người gửi.",
    "Khi bị đe dọa, hãy nói với giáo viên chủ nhiệm hoặc người lớn bạn tin.",
    "Cách thở chậm để bình tĩnh lại khi đang hoảng sợ.",
    "Bạn có thể nhờ người lớn đi cùng khi báo cho nhà trường.",
    "Chụp màn hình có ngày giờ để làm bằng chứng cho nhà trường.",
    "Nhắn tin cho bạn thân hoặc người thân để được giúp đỡ.",
]


@pytest.fixture()
def restorer() -> Restorer:
    return Restorer.from_texts(CORPUS)


def test_unaccented_vietnamese_is_restored_from_context(restorer: Restorer) -> None:
    assert restorer.restore("bi ban nhan tin de doa") == "bị bạn nhắn tin đe dọa"
    assert restorer.restore("chup man hinh") == "chụp màn hình"


def test_queries_that_already_have_diacritics_are_left_alone(restorer: Restorer) -> None:
    assert restorer.restore("bị bạn nhắn tin") == "bị bạn nhắn tin"


def test_english_and_unknown_text_are_left_alone(restorer: Restorer) -> None:
    text = "how do i tell my teacher about bullying"
    assert restorer.restore(text) == text


def test_mixed_text_keeps_unknown_words_unchanged(restorer: Restorer) -> None:
    assert restorer.restore("chup man hinh tiktok") == "chụp màn hình tiktok"


def test_restoration_is_idempotent(restorer: Restorer) -> None:
    once = restorer.restore("nhan tin cho ban than")
    assert restorer.restore(once) == once
    assert once == "nhắn tin cho bạn thân"


def test_empty_input(restorer: Restorer) -> None:
    assert restorer.restore("") == ""
    assert Restorer.from_texts([]).restore("bi ban") == "bi ban"
