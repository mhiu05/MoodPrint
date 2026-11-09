"""Chunking merges small adjacent sections but never crosses legal article boundaries."""

from __future__ import annotations

from moodprint_agent.knowledge.ingest.chunk import blocks_from_markdown, chunk_document
from moodprint_agent.knowledge.ingest.embed import embedding_input
from moodprint_agent.knowledge.ingest.models import ChunkParams, ParsedDocument


def _doc(body: str) -> ParsedDocument:
    return ParsedDocument(document_id="doc-a", blocks=blocks_from_markdown(body))


def _sentence(seed: str, words: int) -> str:
    return " ".join(f"{seed}{index}" for index in range(words)) + "."


def test_small_sections_are_merged_up_to_the_target() -> None:
    body = "\n\n".join(
        f"## Mục {n}\n\nCâu mở đầu của mục {n}. {_sentence(f'tu{n}x', 40)}" for n in range(1, 5)
    )
    chunks = chunk_document(_doc(body), ChunkParams(), "markdown")
    assert 1 <= len(chunks) < 4
    for chunk in chunks:
        assert len(chunk.text) <= ChunkParams().target_max
    assert chunks[0].heading == "Mục 1"
    assert "Mục 2." in chunks[0].text  # later headings stay inside the text for context


def test_a_section_that_is_already_long_enough_is_not_merged() -> None:
    long_text = " ".join(_sentence(f"w{n}", 30) for n in range(1, 6))
    assert len(long_text) >= ChunkParams().target_min
    body = f"## Dài\n\n{long_text}\n\n## Ngắn\n\nChỉ một câu ngắn nhưng đủ dài để giữ lại thành chunk riêng."
    chunks = chunk_document(_doc(body), ChunkParams(), "markdown")
    headings = [chunk.heading for chunk in chunks]
    assert headings[0] == "Dài"
    assert "Ngắn" in headings


def test_legal_articles_stay_separate() -> None:
    body = (
        "## Điều 1 khoản 1 — Phạm vi\n\nNghị định này quy định về môi trường giáo dục.\n\n"
        "## Điều 2 khoản 5 — Định nghĩa\n\nBạo lực học đường là hành vi hành hạ, ngược đãi."
    )
    chunks = chunk_document(_doc(body), ChunkParams(short_min=10), "markdown")
    assert [chunk.heading for chunk in chunks] == [
        "Điều 1 khoản 1 — Phạm vi",
        "Điều 2 khoản 5 — Định nghĩa",
    ]


def test_chunk_ids_are_stable_between_runs() -> None:
    body = "## A\n\nMột câu đủ dài để tạo chunk thử nghiệm ổn định.\n\n## B\n\nCâu thứ hai cũng đủ dài."
    first = chunk_document(_doc(body), ChunkParams(), "markdown")
    second = chunk_document(_doc(body), ChunkParams(), "markdown")
    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]


def test_embedding_input_carries_title_and_heading() -> None:
    value = embedding_input("Tiêu đề tài liệu", "Mục một", "Nội dung chính.")
    assert value.startswith("Tiêu đề tài liệu")
    assert "Mục một" in value
    assert value.endswith("Nội dung chính.")
    assert embedding_input("", "", "Chỉ nội dung.") == "Chỉ nội dung."
