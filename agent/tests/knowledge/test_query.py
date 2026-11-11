from safevoice_agent.knowledge.query import lexical_tokens, prepare_query, redact_identifiers
from safevoice_agent.knowledge.textnorm import fold_vietnamese


def test_fold_matches_the_school_bullying_example() -> None:
    assert fold_vietnamese("Đường đi bắt nạt ở trường") == "duong di bat nat o truong"


def test_fold_is_accent_insensitive_and_stable() -> None:
    assert fold_vietnamese("bị nhắn tin") == fold_vietnamese("bi nhan tin")
    assert fold_vietnamese("  Bị   nhắn\n tin ") == "bi nhan tin"


def test_redaction_removes_contact_details_without_placeholders() -> None:
    text = redact_identifiers("viết tới ban@example.com hoặc 0912345678 và https://x.test/a @lop")
    assert "ban@example.com" not in text
    assert "0912345678" not in text
    assert "https://x.test" not in text
    assert "@lop" not in text
    assert "111" in redact_identifiers("gọi 111 khi cần")


def test_tsquery_drops_user_operators_and_stopwords() -> None:
    prepared = prepare_query("bị '; drop table & | ! : trong nhóm", max_chars=300)
    assert prepared.tsquery is not None
    assert all(token.isalnum() for token in prepared.tsquery.split(" | "))
    assert "drop" in prepared.tsquery
    assert "&" not in prepared.tsquery
    assert "bi" not in prepared.tsquery.split(" | ")
    assert "trong" not in prepared.tsquery.split(" | ")


def test_truncation_stops_on_a_word_boundary() -> None:
    prepared = prepare_query("một hai ba bốn năm", max_chars=10)
    assert prepared.embed_text.endswith("hai") or " " not in prepared.embed_text[-1:]
    assert len(prepared.embed_text) <= 10


def test_empty_after_redaction_does_not_build_a_query() -> None:
    prepared = prepare_query("ban@example.com", max_chars=300)
    assert prepared.empty
    assert lexical_tokens("a") == []
