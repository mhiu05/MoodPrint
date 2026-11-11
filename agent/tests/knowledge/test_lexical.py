"""IDF-weighted lexical coverage: a shared common word must not pass the gate."""

from __future__ import annotations

import pytest
from safevoice_agent.knowledge.lexical import (
    TermStats,
    chunk_terms,
    content_bigrams,
    coverage_score,
    query_terms,
)

CHUNKS = [
    "Bắt nạt qua tin nhắn: hãy chụp màn hình rồi mới chặn người gửi.",
    "Khi bị đe dọa, hãy nói với giáo viên chủ nhiệm hoặc người lớn bạn tin.",
    "Cách thở chậm: hít vào bốn nhịp, thở ra sáu nhịp để bình tĩnh.",
    "Bạn có thể nhờ người lớn đi cùng khi báo cho nhà trường.",
    "Cách chụp màn hình có ngày giờ để làm bằng chứng.",
    "Cách báo cáo tài khoản giả mạo trên mạng xã hội.",
]


@pytest.fixture()
def stats() -> TermStats:
    return TermStats.from_texts(CHUNKS)


def test_rare_terms_weigh_more_than_common_ones(stats: TermStats) -> None:
    assert stats.idf("mao") > stats.idf("cach")  # df 1 versus df 3
    assert stats.idf("khongcotrongkho") >= stats.idf("mao")  # unseen terms weigh the most


def test_common_word_alone_does_not_make_an_off_topic_query_pass(stats: TermStats) -> None:
    query = query_terms("cách thay lốp xe đạp")
    best = max(
        coverage_score(
            query, chunk_terms(chunk), stats, bigrams=content_bigrams("cách thay lốp xe đạp")
        )
        for chunk in CHUNKS
    )
    assert best < 0.25


def test_on_topic_query_covers_its_chunk(stats: TermStats) -> None:
    text = "chụp màn hình tin nhắn rồi chặn"
    query = query_terms(text)
    score = coverage_score(query, chunk_terms(CHUNKS[0]), stats, bigrams=content_bigrams(text))
    assert score > 0.6
    other = coverage_score(query, chunk_terms(CHUNKS[2]), stats, bigrams=content_bigrams(text))
    assert other < score


def test_unaccented_query_matches_accented_chunk(stats: TermStats) -> None:
    text = "chup man hinh tin nhan"
    score = coverage_score(
        query_terms(text), chunk_terms(CHUNKS[0]), stats, bigrams=content_bigrams(text)
    )
    assert score > 0.6


def test_phrase_bonus_prefers_adjacent_words(stats: TermStats) -> None:
    text = "chụp màn hình xe"  # "xe" is absent, so coverage stays below 1 and the bonus shows
    adjacent = coverage_score(
        query_terms(text),
        chunk_terms(CHUNKS[4]),
        stats,
        bigrams=content_bigrams(text),
        phrase_bonus=0.2,
    )
    plain = coverage_score(
        query_terms(text), chunk_terms(CHUNKS[4]), stats, bigrams=[], phrase_bonus=0.2
    )
    assert adjacent > plain
    assert 0.0 <= adjacent <= 1.0


def test_typed_diacritics_are_respected(stats: TermStats) -> None:
    chunk = chunk_terms("Bật thông báo để không bỏ lỡ tin nhắn quan trọng.")
    accented = coverage_score(query_terms("bắt"), chunk, stats, bigrams=[])
    unaccented = coverage_score(query_terms("bat"), chunk, stats, bigrams=[])
    assert accented == 0.0  # "bắt" is not "bật"
    assert unaccented == 1.0  # a query typed without marks still matches by folded form


def test_empty_query_scores_zero(stats: TermStats) -> None:
    assert coverage_score([], chunk_terms(CHUNKS[0]), stats, bigrams=[]) == 0.0
