"""A related chunk is not proof of the requested fact."""

import pytest
from safevoice_agent.knowledge.scoring import RawHit
from safevoice_shared.contracts.knowledge import SourceCitation
from safevoice_shared.knowledge_support import assess_support


def hit(
    body: str,
    *,
    title: str = "School safety",
    country: str = "VN",
    applicability: str = "General guidance",
) -> RawHit:
    citation = SourceCitation(
        source_id="mp-authored",
        document_id="guide",
        title=title,
        publisher="SafeVoice",
        url=None,
        section=None,
        published_at=None,
        last_reviewed=None,
        applicability=applicability,
        country_scope=[country],
    )
    return RawHit("guide#001", "guide", body, citation, vector_score=0.99, lexical_score=0.99)


@pytest.mark.parametrize(
    "query",
    [
        "Học sinh đánh bạn bị phạt bao nhiêu tiền?",
        "hoc sinh bao nhieu tuoi thi chiu trach nhiem hinh su",
        "Quy chế kỷ luật riêng của trường THCS An Bình là gì?",
        "Quy trình chuyển trường vì bị bắt nạt gồm những giấy tờ nào?",
        "Bắt nạt tại công ty thì pháp luật quy định thế nào?",
        "Luật chống bắt nạt ở Canada quy định gì?",
        "Số điện thoại riêng của hiệu trưởng trường mình là gì?",
        "Cần uống thuốc nào để chữa trầm cảm sau khi bị bắt nạt?",
        "Sau bạo lực trường bắt buộc trả lời trong mấy ngày?",
        "Nghị định 80/2017 hiện nay còn hiệu lực không?",
    ],
)
def test_related_high_scoring_guidance_cannot_supply_missing_facts(query: str) -> None:
    evidence = hit("Hãy báo với giáo viên và giữ lại bằng chứng. Tổng đài 111 hỗ trợ trẻ em.")
    assert not assess_support(query, evidence).supported


def test_mentions_of_an_absent_fact_are_not_positive_evidence() -> None:
    evidence = hit("Thẻ này không nêu mức phạt 5 triệu đồng hay thời hạn 7 ngày. Hãy hỏi trường.")
    assert not assess_support("Mức phạt đánh bạn là bao nhiêu tiền?", evidence).supported
    assert not assess_support("Trường phải trả lời trong bao nhiêu ngày?", evidence).supported


def test_numeric_evidence_must_match_the_requested_facet() -> None:
    evidence = hit("Nghị định 80/2017 có hiệu lực từ 5/9/2017. Tổng đài 111 trực 24/24.")
    assert not assess_support("Đánh bạn bị phạt bao nhiêu tiền?", evidence).supported
    assert not assess_support("Thời hạn xử lý bạo lực là bao nhiêu ngày?", evidence).supported
    assert assess_support("Tổng đài bảo vệ trẻ em hoạt động mấy giờ?", evidence).supported


def test_positive_specific_evidence_can_open_a_capability() -> None:
    evidence = hit(
        "Mức phạt tiền cho hành vi A là 5 triệu đồng.", applicability="Vietnam legal excerpt"
    )
    assert assess_support("Mức phạt tiền hành vi A là bao nhiêu?", evidence).supported
    assert assess_support(
        "Thủ tục chuyển trường cần gì?",
        hit("Quy trình chuyển trường gồm nộp đơn xin chuyển và học bạ."),
    ).supported


@pytest.mark.parametrize(
    "query",
    [
        "Cách lưu ảnh chụp màn hình tin nhắn đe dọa?",
        "bi ban danh o lop thi nen nho ai",
        "Quy trình chung khi trường nhận báo cáo bạo lực là gì?",
        "Tổng đài bảo vệ trẻ em có số mấy?",
        "Bạn mình bị ép gửi ảnh riêng thì nên làm gì?",
        "Nghị định 80/2017 định nghĩa bạo lực học đường thế nào?",
        "Nếu bị bắt nạt thì ghi nhật ký theo mấy bước?",
    ],
)
def test_general_guidance_is_preserved(query: str) -> None:
    assert assess_support(
        query, hit("Hướng dẫn hỗ trợ, tổng đài 111, ghi nhật ký và báo người lớn.")
    ).supported


def test_foreign_law_needs_jurisdiction_in_candidate_metadata() -> None:
    evidence = hit(
        "Anti-bullying law in Canada requires a policy.",
        country="CA",
        applicability="Canada legal excerpt",
    )
    assert assess_support("Luật chống bắt nạt ở Canada quy định gì?", evidence).supported
    assert not assess_support("Luật chống bắt nạt ở Mỹ quy định gì?", evidence).supported


@pytest.mark.parametrize(
    "query",
    [
        "cách xóa email rác cho trống bộ nhớ",
        "dịch đoạn văn tiếng Pháp",
        "lịch chiếu phim hành động",
        "thuật toán báo cáo doanh thu",
    ],
)
def test_unrelated_task_intents_cannot_borrow_safety_vocabulary(query: str) -> None:
    assert not assess_support(
        query, hit("Lưu tin nhắn, lập báo cáo và lên kế hoạch hành động an toàn.")
    ).supported


def test_support_checks_the_entire_query_before_embedding_truncation() -> None:
    query = "cần giúp về bắt nạt " * 20 + "mức phạt bao nhiêu tiền?"
    assert not assess_support(query, hit("Hỗ trợ học sinh bị bắt nạt.")).supported


def test_vietnamese_according_to_law_is_not_a_foreign_jurisdiction() -> None:
    assert assess_support(
        "Định nghĩa bạo lực học đường theo pháp luật",
        hit("Định nghĩa bạo lực học đường ở Việt Nam."),
    ).supported


def test_emergency_directory_query_accepts_a_published_hotline() -> None:
    assert assess_support(
        "so dien thoai khan cap khi bi bao luc", hit("Tổng đài bảo vệ trẻ em 111, miễn phí 24/24.")
    ).supported
    assert not assess_support(
        "Số điện thoại khẩn cấp của hiệu trưởng", hit("Tổng đài bảo vệ trẻ em 111, miễn phí 24/24.")
    ).supported


@pytest.mark.parametrize(
    "query",
    [
        "Số điện thoại hotline của hiệu trưởng trường mình là gì?",
        "Số điện thoại tổng đài riêng của thành phố mình là gì?",
        "Số tổng đài ở tỉnh mình để báo trường là số nào?",
    ],
)
def test_local_directories_cannot_borrow_the_national_hotline_number(query: str) -> None:
    assert not assess_support(
        query, hit("Tổng đài Quốc gia bảo vệ trẻ em 111, miễn phí 24/24.")
    ).supported
