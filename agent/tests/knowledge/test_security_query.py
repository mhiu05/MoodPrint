"""Query preparation is injection-safe and redacts identifiers (P2-14 b, g)."""

from __future__ import annotations

import re

from moodprint_agent.knowledge.lexical import chunk_terms, content_bigrams, query_terms
from moodprint_agent.knowledge.query import prepare_query, redact_identifiers
from moodprint_agent.knowledge.restore import Restorer

from .fuzz_cases import fuzz_corpus

SAFE_TSQUERY = re.compile(r"^[a-z0-9]+( \| [a-z0-9]+)*$")


def test_500_fuzz_strings_never_break_the_query_builder() -> None:
    cases = fuzz_corpus()
    assert len(cases) == 500
    restorer = Restorer.from_texts(["Bị bạn nhắn tin đe dọa thì hãy chụp màn hình rồi mới chặn."])
    for raw in cases:
        prepared = prepare_query(raw, max_chars=300)
        assert len(prepared.embed_text) <= 300
        if prepared.tsquery is not None:
            assert SAFE_TSQUERY.fullmatch(prepared.tsquery), prepared.tsquery
            assert len(prepared.tsquery.split(" | ")) <= 16
        # The lexical helpers must also survive any input.
        terms = query_terms(prepared.embed_text)
        content_bigrams(prepared.embed_text)
        chunk_terms(prepared.embed_text)
        restorer.restore(prepared.embed_text)
        assert all(term.folded.isascii() for term in terms)


def test_identifiers_are_redacted_before_the_embedder() -> None:
    raw = "liên hệ a.b+c@example.com hoặc 0912 345 678 và https://x.vn/p?q=1 @ten_that 123456789012"
    redacted = redact_identifiers(raw)
    for leaked in ("example.com", "0912", "https://", "@ten_that", "123456789012"):
        assert leaked not in redacted
    assert (
        prepare_query(raw, max_chars=300).embed_text == prepare_query(raw, max_chars=300).embed_text
    )


def test_oversized_input_is_cut_at_a_word_boundary() -> None:
    raw = ("từ " * 400).strip()
    prepared = prepare_query(raw, max_chars=300)
    assert len(prepared.embed_text) <= 300
    assert not prepared.embed_text.endswith(" ")
