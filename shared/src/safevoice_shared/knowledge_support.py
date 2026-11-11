"""Bounded evidence requirements, independent of similarity and rank.

This is a conservative capability catalogue, not a semantic entailment model. Rules
require a positive, facet-specific statement in the *same chunk*. Merely mentioning
an unavailable fact, an unrelated number, or another jurisdiction never supplies it.
General advice still uses the calibrated relevance gate. No network or model calls.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from safevoice_shared.contracts.knowledge import SourceCitation


class Evidence(Protocol):
    @property
    def text(self) -> str: ...

    @property
    def citation(self) -> SourceCitation: ...


def fold_vietnamese(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", value.casefold()) if not unicodedata.combining(c)
    ).replace("\u0111", "d")


VERSION = "evidence-support-v2"
INSUFFICIENT_EVIDENCE_MESSAGE = (
    "Kho tri thức hiện tại chưa có đủ thông tin để trả lời câu hỏi này. "
    "Bạn có thể kiểm tra nguồn chính thức hoặc nhờ thầy cô, nhà trường hay người có chuyên môn xác nhận."
)


@dataclass(frozen=True, slots=True)
class SupportDecision:
    supported: bool
    reason: str


@dataclass(frozen=True, slots=True)
class Requirement:
    name: str
    query_pattern: str
    evidence_pattern: str


# Only capabilities actually requested by the question are enforced. Adding source
# coverage needs positive evidence, not a query-ID exception or a higher cosine.
REQUIREMENTS = (
    Requirement(
        "monetary_amount",
        r"(?:muc phat|phat.{0,25}(?:tien|bao nhieu)|boi thuong|vien phi|tien phat|tien den bu)",
        r"(?:phat|boi thuong|den bu).{0,80}\d[\d., ]*\s*(?:trieu|nghin|ngan|dong|vnd|dollar|usd)",
    ),
    Requirement(
        "criminal_age",
        r"(?:trach nhiem hinh su|tuoi chiu.*hinh su)",
        r"(?:tu|du|tren|duoi)\s+\d+\s+tuoi.{0,100}(?:hinh su)|hinh su.{0,100}\d+\s+tuoi",
    ),
    Requirement(
        "transfer_procedure",
        r"chuyen truong",
        r"chuyen truong.{0,100}(?:don|ho so|hoc ba|nop|tiep nhan)",
    ),
    Requirement(
        "workplace",
        r"(?:noi lam viec|cong ty|cong so|dong nghiep|workplace)",
        r"(?:noi lam viec|cong ty|cong so|dong nghiep|workplace)",
    ),
    Requirement(
        "statutory_deadline",
        r"(?:bao nhieu|may|toi da|thoi han|bat buoc).{0,35}(?:ngay|gio|tuan|thang).{0,35}(?:tra loi|xu ly|giai quyet)|(?:tra loi|xu ly|giai quyet).{0,35}(?:bao nhieu|may|thoi han).{0,20}(?:ngay|gio|tuan|thang)",
        r"(?:tra loi|xu ly|giai quyet).{0,80}\d+\s*(?:ngay|gio|tuan|thang)",
    ),
)

# These are tasks outside the published school-safety guidance, not all queries
# containing a common noun such as 'message', 'report' or 'action'.
_UNSUPPORTED_TASK = re.compile(
    r"\b(?:dich (?:cau|doan|van ban)|translation|thuat toan|doanh thu|tin nhan rac|email rac|"
    r"bo nho (?:dien thoai|may tinh)|lich chieu|xem phim|phim hanh dong|thoi tiet|"
    r"gia vang|ty so|lich thi dau|tich phan|lam banh|trong cay)\b"
)
_MEDICAL = re.compile(
    r"\b(?:thuoc (?:gi|nao|chua)|uong thuoc|lieu (?:thuoc|dung)|ke don|chan doan)\b"
)
_LEGAL_CURRENT = re.compile(
    r"\b(?:con hieu luc|hieu luc hien (?:nay|hanh)|da (?:het hieu luc|bi thay the)|luat moi nhat)\b"
)
_INSTITUTION = re.compile(
    r"\b(?:quy che|noi quy|ky luat|quy trinh).{0,100}\b(?:truong (?:thcs|thpt|tieu hoc|minh|em)|rieng cua truong)\b"
)
_DIRECTORY = re.compile(r"\b(?:so dien thoai|so lien he|dia chi|danh ba)\b")
_HOTLINE = re.compile(r"\b(?:tong dai|hotline|111|113|115)\b")
_COUNTRIES = (
    (r"\b(?:o|tai|cua) (?:my|hoa ky|nuoc my|united states|usa)\b", "US"),
    (r"\bcanada\b", "CA"),
    (r"\b(?:uc|australia)\b", "AU"),
    (r"\b(?:o|tai|cua) (?:anh|nuoc anh|uk)\b", "GB"),
    (r"\bsingapore\b", "SG"),
    (r"\b(?:nhat ban|japan)\b", "JP"),
    (r"\b(?:han quoc|korea)\b", "KR"),
    (r"\b(?:trung quoc|china)\b", "CN"),
    (r"\b(?:o|tai|cua) (?:duc|germany)\b", "DE"),
    (r"\b(?:o|tai|cua) (?:phap|france)\b", "FR"),
)
_NEGATIVE = re.compile(
    r"\b(?:khong (?:neu|noi|co|quy dinh|cung cap|xac nhan|bao gom)|chua (?:co|xac nhan|kiem chung)|thieu|tuy thuoc)\b"
)


def _positive_statements(hit: Evidence) -> list[str]:
    # Headings/citation numbers do not turn a disclaimer into a legal fact.
    text = fold_vietnamese(hit.text)
    return [s for s in re.split(r"[.!?;\n]+\s*", text) if s and not _NEGATIVE.search(s)]


def assess_support(query: str, hit: Evidence) -> SupportDecision:
    """Reject specific unsupported scope even if a candidate scores 1.0.

    Evaluate the complete redacted question, before the 300-character embed cut.
    Conservative rejection reasons are codes only, so telemetry need not log queries.
    """
    q = fold_vietnamese(query)
    positive = _positive_statements(hit)
    if _UNSUPPORTED_TASK.search(q):
        return SupportDecision(False, "unsupported_task")
    if _MEDICAL.search(q):
        return SupportDecision(False, "clinical_coverage_unavailable")
    if re.search(r"\b(?:luat|phap ly|phap luat|quy dinh|law)\b", q):
        for pattern, country in _COUNTRIES:
            if re.search(pattern, q) and country not in hit.citation.country_scope:
                return SupportDecision(False, "jurisdiction_mismatch")
    if _LEGAL_CURRENT.search(q):
        # Current legal status must have an explicit reviewed applicability record.
        applicability = fold_vietnamese(hit.citation.applicability)
        if not re.search(
            r"(?:hieu luc hien hanh da (?:xac nhan|kiem chung)|current legal status verified)",
            applicability,
        ):
            return SupportDecision(False, "legal_status_unverified")
    if _INSTITUTION.search(q):
        # A national framework is not a school's policy. No published record currently
        # declares an institution; future ingestion must identify it in its title.
        name = re.search(r"\btruong ((?:thcs|thpt|tieu hoc) [\w ]+?)(?: la | quy | nhu |\?|$)", q)
        if name is None or name[1].strip() not in fold_vietnamese(hit.citation.title):
            return SupportDecision(False, "institution_policy_unavailable")
    if (_DIRECTORY.search(q) or _HOTLINE.search(q)) and re.search(
        r"\b(?:hieu truong|giao vien|truong (?:minh|em|thcs|thpt)|tinh (?:minh|em)|thanh pho (?:minh|em)|rieng cua)\b",
        q,
    ):
        return SupportDecision(False, "local_directory_unavailable")
    if _DIRECTORY.search(q):
        if _HOTLINE.search(q) or (
            "khan cap" in q and not re.search(r"hieu truong|giao vien|truong (?:minh|em)", q)
        ):
            if not any(_HOTLINE.search(s) and re.search(r"\b\d{3}\b", s) for s in positive):
                return SupportDecision(False, "hotline_number_missing")
        else:
            return SupportDecision(False, "local_directory_unavailable")
    for requirement in REQUIREMENTS:
        if re.search(requirement.query_pattern, q) and not any(
            re.search(requirement.evidence_pattern, s) for s in positive
        ):
            return SupportDecision(False, requirement.name + "_missing")
    return SupportDecision(True, "supported_scope")


def requires_specific_support(query: str) -> bool:
    """Buffer precise factual answers until a retrieval has supplied the evidence."""
    q = fold_vietnamese(query)
    return bool(
        _MEDICAL.search(q)
        or _LEGAL_CURRENT.search(q)
        or _INSTITUTION.search(q)
        or _DIRECTORY.search(q)
        or _UNSUPPORTED_TASK.search(q)
        or any(re.search(r.query_pattern, q) for r in REQUIREMENTS)
        or (
            re.search(r"\b(?:luat|phap ly|phap luat|quy dinh|law)\b", q)
            and any(re.search(pattern, q) for pattern, _ in _COUNTRIES)
        )
    )
