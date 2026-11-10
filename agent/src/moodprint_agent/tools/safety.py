"""Deterministic urgency layer. No model, no network, no logging of message content.

``assess_urgency`` returns ``none | elevated | immediate`` plus the *names* of the signal groups
that fired. It is deliberately one layer of several: keyword recall alone does not establish
that the system is safe, and the live evaluation reads every high-risk answer separately.

How it avoids being a bag of keywords:
* text is folded (diacritics, case), stretched letters collapsed and common teen spellings
  normalised, so ``chếtttt`` and ``ko muon song nua`` match;
* each sentence is judged on its own, then adjusted by context: negation, past tense,
  hypothetical or media framing, quoted/reported speech and who the subject is;
* several turns are combined, so an earlier worrying statement plus a later timing/means cue
  becomes ``immediate``.
"""

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final, Literal

UrgencyLevel = Literal["none", "elevated", "immediate"]
_RANK: Final[dict[UrgencyLevel, int]] = {"none": 0, "elevated": 1, "immediate": 2}

# Verified static support content. Copied from the frontend support feature (tel:111 and the
# tongdai111.vn source, checked 2026-11-07). Do not add a number that has no verified source.
SUPPORT_VERIFIED_ON: Final = "2026-11-07"
EMERGENCY_BLOCK: Final = (
    "\n\n---\n"
    "**Nếu bạn đang gặp nguy hiểm ngay lúc này:** hãy đến chỗ có người lớn bạn tin "
    "(thầy cô, bảo vệ trường, người thân, hàng xóm) hoặc nhờ họ ở cạnh bạn ngay. "
    "Bạn có thể gọi **Tổng đài Quốc gia bảo vệ trẻ em 111** (miễn phí, 24/24; nguồn "
    "tongdai111.vn, kiểm tra ngày 07/11/2026). "
    "MoodPrint là AI, không phải người trực và không tự liên hệ ai thay bạn. "
    "Mở trang Hỗ trợ ngay: /support/urgent"
)
ELEVATED_HINT: Final = (
    "Người dùng có dấu hiệu căng thẳng hoặc lo ngại về an toàn. Ưu tiên hỏi thăm nhẹ nhàng, "
    "hỏi xem bạn có đang an toàn không và gợi ý nói với một người lớn đáng tin."
)


@dataclass(frozen=True, slots=True)
class UrgencyAssessment:
    level: UrgencyLevel
    signals: tuple[str, ...] = ()

    @property
    def immediate(self) -> bool:
        return self.level == "immediate"


NONE: Final = UrgencyAssessment("none")


# ---------------------------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------------------------
_TEEN: Final[dict[str, str]] = {
    "ko": "khong",
    "k": "khong",
    "hok": "khong",
    "hong": "khong",
    "khum": "khong",
    "kg": "khong",
    "j": "gi",
    "dc": "duoc",
    "dk": "duoc",
    "mik": "minh",
    "mk": "minh",
    "mink": "minh",
    "tui": "toi",
    "vs": "voi",
    "bn": "ban",
    "trc": "truoc",
    "ns": "noi",
    "cx": "cung",
    "wa": "qua",
    "ntn": "nhu the nao",
    "bh": "bay gio",
    "lun": "luon",
    "nua": "nua",
    "kms": "tu tu",
}
_QUOTES: Final = re.compile(r"[\"“”«»]([^\"“”«»]+)[\"“”«»]|(?<!\w)'([^']{3,})'(?!\w)")
_SENTENCE: Final = re.compile(r"[.!?;\n…]+")
# An adversative starts a new assertion: its negation/media frame stays local.
_CONTEXT_BREAK: Final = re.compile(r"\b(?:nhưng|nhung|tuy nhiên|tuy nhien)\b", re.IGNORECASE)
# A comma before a new subject ("…không đáng sống, mình sẽ…") ends the clause, so a negation
# stays local to the clause it belongs to.
_SUBJECT_BREAK: Final = re.compile(r",\s*(?=(?:mình|em|tôi|tao|tớ|tui|mik)\b)", re.IGNORECASE)


def fold(text: str) -> str:
    """Lower-case, strip diacritics (đ→d), collapse stretched letters, map teen spellings."""
    lowered = unicodedata.normalize("NFC", text.lower())
    # Protect two words that would collide after diacritics are stripped:
    # "đừng" (don't) vs "đứng" (stand) and "từng" (once) vs the verb "tung" (to leak).
    lowered = re.sub("đừng", "dungz", lowered)
    lowered = re.sub("từng", "tungz", lowered)
    lowered = re.sub("kiểm tra", "kiemtra", lowered)  # exam, not "kiếm" (sword)
    lowered = re.sub("biệt danh", "bietdanh", lowered)  # nickname, not "danh" (to hit)
    decomposed = unicodedata.normalize("NFD", lowered.replace("đ", "d"))
    ascii_text = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    ascii_text = re.sub(r"(?<=[a-z])3(?=[a-z])", "e", ascii_text)
    ascii_text = re.sub(r"(?<=[a-z])0(?=[a-z])", "o", ascii_text)
    ascii_text = re.sub(r"(.)\1{2,}", r"\1", ascii_text)
    words: list[str] = re.findall(r"[a-z0-9]+", ascii_text)
    return " ".join(_TEEN.get(word, word) for word in words)


# ---------------------------------------------------------------------------------------------
# Pattern vocabulary (all patterns run on folded text)
# ---------------------------------------------------------------------------------------------
_NEG = r"(?:khong|chua|dungz|chang|chua bao gio|khong he|khong the nao)"
_FIRST = re.compile(r"\b(?:minh|em|toi|tao|con|to)\b")
_POSSESSED = re.compile(
    r"\b(?:ban|nguoi|anh|chi|em|me|bo|co|thay)(?: \w+)? (?:cua )(?:minh|em|toi)\b"
)
_THIRD = re.compile(
    r"\b(?:ban (?:ay|than|minh|lop|cung lop)|em ay|anh ay|chi ay|cau ay|nguoi ta|no|co ay|"
    r"nhan vat|hoc sinh)\b"
)
_MEDIA = re.compile(
    r"\b(?:bai hat|phim|truyen|bai tho|cau tho|nha tho|game|meme|tiktok|cuon sach|quyen sach|nhan vat|bai van|phan tich|ca khuc|"
    r"lyric|kich|tieu thuyet|bao chi|bao dien tu|tin tuc|ban tin|bai viet|dua tin|thoi su|phong van|"
    r"van ban|trang web|bai bao)\b"
)
# Joking or playful framing: a "threat" between friends who laugh is not a threat.
_JOKE = re.compile(
    r"\b(?:dua|dua thoi|dua vui|cuoi|cuoi lan|haha|hihi|kkk|troll|choi game|dau game|vui)\b"
)
# Wanting to understand or prevent harm is information-seeking, not a disclosure.
_INFO = re.compile(
    r"\b(?:phong tranh|phong ngua|(?<!tim )hieu cach|muon hieu|lam sao de|lam the nao de|cach de)\b"
)
_COMMIT = re.compile(
    r"\b(?:minh|em|toi) (?:se|dinh|toan)(?: \w+){0,2} (?:lam|ket thuc|di|thuc hien)\b|"
    r"\b(?:di luon|lam luon|cho xong|nghi xong|het cach)\b"
)
# A leading "if…" is a what-if question; a trailing "…if you tell" is the condition of a threat.
_HYPO = re.compile(r"^(?:\w+ ){0,2}(?:neu|gia su|gia nhu|gia thu|lo nhu|gia dinh|neu nhu)\b")
_BENIGN_OBJECT = re.compile(
    r"\b(?:got|bep|nau|hoa qua|trai cay|picnic|cat banh|bua an|an com|thuc hanh|nghe thuat|"
    r"roc giay|thu cong|my thuat|cat giay|lam banh|dung cu|hoc cu|thai rau|thai thit|rau|"
    r"phu me nau|nau com)\b"
)
# Taking prescribed or ordinary medicine as directed is not an overdose.
_BENIGN_MED = re.compile(
    r"\b(?:khang sinh|thuoc cam|thuoc ho|vitamin|bac si dan|theo don|dung gio|dung lieu|"
    r"thuoc bo|sau khi an)\b"
)
# "tức muốn chết", "đói muốn chết": hyperbole. Physical/neutral ones carry no signal; emotional
# ones ("buồn muốn chết") are not dismissed but kept at elevated.
_HYPERBOLE_NEUTRAL = re.compile(
    r"\b(?:tuc|doi|khat|nong|lanh|cuoi|buon cuoi|vui|xau ho|buon ngu|thich|yeu|moi|ngai|dau|ghet|"
    r"met|buon ngu|nhuc|an|no) (?:den muc |phat )?muon chet\b"
)
_HYPERBOLE_CHET = re.compile(
    r"\bchet (?:di )?(?:duoc|mat|roi|luon|nguoi|do|diem|ngat|lang|dung)\b|"
    r"\b(?:cuoi|met|doi|nong|lanh|ngai|xau ho|tuc|khat|buon ngu|nho|thich|yeu) chet\b"
)
_HYPERBOLE_EMOTIONAL = re.compile(r"\b(?:buon|chan|so|bat luc|kho chiu|ap luc) muon chet\b")
_VIOLENT_WORD = re.compile(r"\b(?:danh|dap|giet|chem|dam|xu ly|hanh hung|doa)\b")
_PAST = re.compile(
    r"\b(?:hoi|tungz|da tungz|truoc day|nam ngoai|thang truoc|tuan truoc|ngay xua|luc nho|"
    r"hoi nho|(?<!dung )(?<!o )(?<!ngoi )ngay do|thoi do|lan do|hom qua|truoc kia|nam truoc)\b"
)
_RESOLVED = re.compile(r"\b(?:gio on|da on|da qua|khong con nua|xoa roi|da het)\b")
_IMMINENT = re.compile(
    r"\b(?:bay gio|ngay bay gio|luc nay|ngay lap tuc|toi nay|hom nay|chieu nay|sang nay|"
    r"dem nay|lat nua|mot lat|sap|dang|chuan bi|da mua|san sang|tan hoc|sau gio hoc|sau hoc|"
    r"het gio|ra choi|tan truong|ngay mai|trong ngay|vua nhan|vua noi|ngoai kia|truoc cong|"
    r"o cong|ngay luc nay|nhu bay gio)\b"
)
# Markers that put the situation in the present. Day words ("hôm nay", "tối nay") do not: "tuần trước
# bị xô… hôm nay mình không dám đến lớp" is a past event with a present consequence.
_NOW_STRONG = re.compile(
    r"\b(?:bay gio|ngay bay gio|luc nay|ngay luc nay|ngay lap tuc|dang|vua|sap|lat nua|mot lat|"
    r"ngoai kia|truoc cong|o cong|nhu bay gio|van dung|van o)\b"
)
_FEAR = re.compile(r"\b(?:so|so hai|hoang so|lo so|run|khong dam|kinh khung|hoang)\b")
_MEANS = re.compile(
    r"\b(?:dao|thuoc ngu|thuoc|day thung|san thuong|ban cong|kiem|vu khi|sung|day|cau)\b"
)
# Wishing to stop existing, in the user's own voice (plain wording; severity is decided in context).
_IDEATION = re.compile(
    r"\b(?:muon|dinh|toan|se|nghi (?:den|toi) chuyen)\b.{0,12}\b(?:chet|tu tu|tu sat|bien mat|"
    r"ket thuc|di luon|dung lai|khong con)\b|"
    r"\bkhong (?:thay |con )?(?:ly do|y nghia)\b.{0,20}\b(?:tiep tuc|song|ton tai)\b|"
    r"\bket thuc (?:tat ca|het|moi thu|cuoc song|doi)\b|\bbien mat khoi\b|"
    r"\b(?:chiu|chong) (?:het |khong )?(?:noi|duoc)\b.{0,25}\bdi luon\b|\bdi luon cho xong\b"
)

# Overdose quantities are distinct from taking ordinary medicine as directed.
_OVERDOSE: Final = re.compile(
    r"\b(?:uong|nuot) (?:rat nhieu|qua nhieu|ca (?:dong|nam|vi|lo|hop))(?: \w+){0,3} thuoc\b"
)
_PRESENT_CONTACT: Final = re.compile(
    r"\b(?:van|dang) (?:\w+ ){0,4}(?:cua|day|do|canh|ben canh|truoc mat|ngoai|truoc nha|cong)\b|"
    r"\b(?:nhin thay|thay)\b.{0,35}\b(?:o cong|truoc nha|ngoai cua)\b|"
    r"\b(?:o cong|truoc nha|ngoai cua) roi\b"
)
_PASSIVE_PHYSICAL: Final = re.compile(
    r"\bbi (?:(?:(?:mot|hai|ba|ca) )?(?:ban(?: ay| do)?|nhom(?: ban| nguoi)?|"
    r"nguoi(?: do| ay| la)?)(?: \w+){0,1} )?"
    r"(?:danh(?! (?:gia|thuc|bai|van|dau|so|may|dan|chu|rang)\b)|dam|xo day|xo|hanh hung|tan cong)\b"
)
_ABSTRACT_QUOTE: Final = re.compile(
    r"\b(?:cau|tinh huong|vi du|bai tap) gia dinh(?: (?:nhu sau|la|rang))?$"
)
_NEGATED_HARM_PREFIX: Final = re.compile(
    r"^khong (?:co )?ai (?:(?:dang|dinh|se|chuan bi) )?"
    r"(?:(?:chan (?:cua|duong)|danh|dap|dam|tat|tan cong) (?:hay|hoac) "
    r"(?:(?:dang|dinh|se|chuan bi) )?)*$"
)


def _conditional_self_plan(clause: str) -> bool:
    """A timed first-person conditional commitment is a plan, not an abstract what-if."""
    return bool(
        _HYPO.search(clause)
        and _NOW_RE.search(clause)
        and re.search(r"\bthi (?:minh|em|toi|tao|to) (?:se|dinh|toan)\b", clause)
        and re.search(r"\b(?:tu tu|tu sat|treo co|nhay|cat (?:tay|co tay)|uong.*thuoc)\b", clause)
    )


# group, base level, pattern, intrinsic_negation (pattern already contains its own "khong")
_P = tuple[str, UrgencyLevel, "re.Pattern[str]", bool]


def _p(group: str, level: UrgencyLevel, pattern: str, intrinsic: bool = False) -> _P:
    return (group, level, re.compile(pattern), intrinsic)


_RULES: Final[tuple[_P, ...]] = (
    _p(
        "self_harm",
        "immediate",
        r"(?:^(?:(?:nam ngoai|nam truoc|thang truoc|tuan truoc|truoc day) )?"
        r"(?:minh|em|toi|con|to) (?:uoc gi|mong|muon)|\b(?:uoc gi|mong) "
        r"(?:(?:sang mai|ngay mai|toi nay|sau nay) )?(?:minh|toi|to)) "
        r"khong (?:phai )?(?:thuc day|tinh day) nua\b",
        True,
    ),
    _p("self_harm", "immediate", _OVERDOSE.pattern),
    # --- self harm: active intent / plan / means ---------------------------------------------
    _p("self_harm", "immediate", r"\bmuon (?:chet|tu tu|tu sat|tu ket lieu)\b"),
    _p("self_harm", "immediate", r"\bmuon (?:ket thuc|dung) (?:cuoc song|cuoc doi|tat ca|het)\b"),
    _p("self_harm", "immediate", r"\bmuon bien mat khoi (?:the gioi|cuoc song|doi)\b"),
    _p(
        "self_harm",
        "immediate",
        r"\b(?:se|di|dinh|toan|sap|quyet dinh|nghi minh se) (?:di )?"
        r"(?:chet|tu tu|tu sat|tu ket lieu|ket thuc cuoc song|treo co)\b",
    ),
    _p("self_harm", "immediate", r"\b(?:tu tu|tu sat|tu ket lieu)\b"),
    _p(
        "self_harm",
        "immediate",
        r"\bkhong (?:con )?(?:muon|thiet) (?:song|con song|ton tai)\b",
        True,
    ),
    _p("self_harm", "immediate", r"\bsong (?:lam gi|de lam gi|chang con y nghia)\b"),
    _p(
        "self_harm",
        "immediate",
        r"\bkhong (?:con )?(?:ly do|y nghia) (?:gi )?(?:de )?(?:song|ton tai)\b",
        True,
    ),
    _p("self_harm", "immediate", r"\bchet (?:di )?(?:cho|la) (?:roi|xong|het|day)\b"),
    _p(
        "self_harm",
        "immediate",
        r"\b(?:tu )?(?:cat|rach) (?:co tay|mach)\b|\brach tay\b|\btu cat tay\b",
    ),
    _p("self_harm", "immediate", r"\bnhay (?:lau|cau|xuong)\b"),
    _p("self_harm", "immediate", r"\b(?:treo co|uong (?:het )?thuoc ngu|uong thuoc de)\b"),
    _p(
        "self_harm",
        "immediate",
        r"\b(?:uong|nuot) (?:het|nhieu|ca (?:vi|lo|hop))\b.{0,25}\bthuoc|"
        r"\bthuoc.{0,25}\b(?:uong|nuot) (?:het|nhieu|ca (?:vi|lo|hop))\b",
    ),
    _p(
        "self_harm",
        "immediate",
        r"\btu (?:lam|gay) (?:dau|ton thuong|thuong tich)\b|\btu lam hai ban than\b",
    ),
    _p("self_harm", "immediate", r"\blam hai ban than\b"),
    _p("self_harm", "immediate", r"\bcham dut (?:tat ca|cuoc song|cuoc doi|moi thu|het)\b"),
    _p("self_harm", "immediate", r"\b(?:thu|loi) tuyet menh\b|\bviet (?:di chuc|thu tu biet)\b"),
    _p("self_harm", "immediate", r"\bchan song\b"),
    _p(
        "self_harm",
        "immediate",
        r"\bket thuc (?:doi|cuoc song|cuoc doi|tat ca)(?: cua)?(?: minh| em| toi| ban than)?\b",
    ),
    # --- self harm: passive / thoughts -------------------------------------------------------
    _p(
        "self_harm",
        "elevated",
        r"\b(?:muon|uoc)(?: duoc)? (?:bien mat|duoc ngu (?:mai|luon|vinh vien)|moi thu (?:dung lai|ket thuc))\b",
    ),
    _p(
        "self_harm",
        "elevated",
        r"\b(?:gia nhu|gia nhu la|uoc gi) (?:minh )?(?:chua (?:tungz )?sinh ra|khong (?:co|ton tai))\b",
    ),
    _p("self_harm", "elevated", r"\bchua (?:tungz )?sinh ra\b"),
    _p(
        "self_harm",
        "elevated",
        r"\b(?:moi nguoi|bo me|ai cung) (?:se )?(?:tot hon|nhe long hon|vui hon) (?:neu|khi) (?:khong co|minh)",
    ),
    _p(
        "self_harm",
        "elevated",
        r"\bbien mat\b.*\b(?:buon|nho|biet)\b|\b(?:neu|gia nhu) minh (?:bien mat|chet)\b",
    ),
    _p("self_harm", "elevated", r"\bnghi (?:den|toi) (?:cai chet|chuyen chet|chet|chuyen tu tu)\b"),
    _p("self_harm", "elevated", r"\bchan (?:moi thu|tat ca|het)\b"),
    _p(
        "self_harm",
        "immediate",
        r"\bcam (?:lo |vi |hop )?(?:thuoc|dao|day)\b.{0,60}\b(?:uong het|nuot het|cat|tu lam dau|"
        r"nghi den chuyen)\b|\b(?:uong|nuot) het\b",
    ),
    _p(
        "self_harm",
        "immediate",
        r"\b(?:want to|wanna) (?:die|disappear|end (?:it|my life))\b|\bkill myself\b",
    ),
    _p(
        "self_harm",
        "immediate",
        r"\b(?:se|dinh|toan) ket thuc\b(?! (?:bai|buoi|cuoc hop|tiet|gio|phan|chuong|nam hoc|hoc ky|mon|truyen|cau|video|phim|tran|tuan|thang|som)\b)(?! ngay (?!bay gio|lap tuc|luc nay))|\bnghi xong cach\b.{0,40}\b(?:chet|bien mat|ket thuc)\b",
    ),
    # --- threats / being hurt ----------------------------------------------------------------
    _p(
        "threat",
        "elevated",
        r"\b(?:doa|de doa|uy hiep|hanh hung)\b.*\b(?:danh|giet|chem|dap|dam|minh|em|toi)\b",
    ),
    _p("threat", "elevated", r"\b(?:doa|de doa) (?:danh|dap|giet|chem|dam|xu)\b"),
    _p(
        "threat",
        "elevated",
        r"\b(?:se|muon|dinh|toan) (?:danh|dap|giet|chem|xu ly|xo|hanh) (?:minh|em|toi|may|nguoi)\b",
    ),
    _p(
        "threat",
        "elevated",
        r"\b(?:tao|bon tao|tui tao|toi) (?:se )?(?:danh|dap|giet|chem|xu) (?:may|em)\b",
    ),
    _p(
        "threat",
        "immediate",
        r"\bchan (?:minh|em|toi) (?:o|tai|tren|duong)\b|\bcho (?:minh|em|toi) o (?:cong|nha xe|san sau|hanh lang)\b",
    ),
    _p("threat", "immediate", r"\bso (?:di|ve|o|ra) (?:mot minh|nha mot minh)\b"),
    _p(
        "threat",
        "immediate",
        r"\b(?:co nguoi|ai do|mot nguoi|nhom nguoi|dang bi|bi)(?: dang)? "
        r"(?:theo doi|bam theo|theo sau|chan duong|bao vay|vay)\b",
    ),
    _p("threat", "immediate", r"\bkhong dam (?:ra|ve|di|ve nha)\b"),
    _p(
        "threat",
        "immediate",
        r"\b(?:dang )?(?:cho|doi|dung (?:cho|doi)|rinh) (?:minh |em |toi )?(?:o |ngoai |truoc |tai )?"
        r"(?:cong|san sau|nha xe|hanh lang|ngoai kia|truoc cong|cua lop)\b",
    ),
    _p(
        "threat",
        "elevated",
        r"\b(?:keo|lon|bat|day|nhot) (?:minh|em|toi) (?:vao|ra|di|xuong)\b|"
        r"\b(?:chan duong|chan minh|dap minh|xu minh)\b",
    ),
    _p(
        "threat",
        "immediate",
        r"\b(?:co nguoi|ai do|mot nguoi|nhom nguoi)(?: dang)? di theo (?:minh|em|toi)\b",
    ),
    _p(
        "threat",
        "elevated",
        r"\b(?:bao|noi|nhan|hen)(?: la)? (?:se )?(?:gap|tim|doi|cho) (?:minh|em|toi)\b.{0,25}"
        r"\b(?:sau gio hoc|sau hoc|tan hoc|o cong|rieng|mang theo)\b",
    ),
    _p(
        "threat",
        "immediate",
        r"\b(?:they|he|she|people) (?:will|are going to|gonna) (?:hurt|beat|kill|attack) (?:me|us)\b",
    ),
    _p(
        "threat",
        "elevated",
        r"\bhen (?:minh|em|toi) (?:sau gio hoc|tan hoc|o cong|rieng|o nha xe|cong truong|san sau)\b|\bco ban hen (?:minh|em|toi)\b",
    ),
    _p(
        "threat",
        "elevated",
        r"\b(?:bao|noi|nhan|doa|tuyen bo)(?: la)?(?: se)? "
        r"(?:danh|dap|giet|chem|dam|xu ly) (?:minh|em|toi|con)\b",
    ),
    _p("threat", "elevated", r"\b(?:giet|chem|dam) (?:minh|em|toi)\b"),
    _p(
        "physical",
        "elevated",
        r"\bdang (?:danh|dap|da|xo|dam) (?:mot |may )?(?:ban|nguoi|em|bac|co)\b",
    ),
    _p(
        "physical",
        "immediate",
        r"\bdang (?:giu|nam|keo|ghim) (?:tay|toc|ao|co) (?:minh|em|toi)?\b|"
        r"\bkhong cho (?:minh|em|toi) (?:di|ra|ve)\b|\b(?:giu|nam) (?:tay )?(?:minh|em|toi) lai\b|"
        r"\bgiup voi\b.{0,40}\b(?:danh|keo|dap|da)\b|\b(?:danh|keo|dap|da)\b.{0,40}\bgiup voi\b",
    ),
    # --- physical harm ------------------------------------------------------------------------
    _p("physical", "elevated", _PASSIVE_PHYSICAL.pattern),
    _p(
        "physical",
        "immediate",
        r"\b(?:dang|van) chan (?:cua|duong)\b.{0,60}\b(?:chuan bi|dinh|toan|sap|se) "
        r"(?:danh|dap|dam|tat|tan cong) (?:minh|em|toi)\b",
    ),
    _p(
        "physical",
        "elevated",
        r"\b(?:bi|dang bi) (?:xo day|xo|day|danh|dap|tat|do|hanh hung|dam|chem|nem do|nem vat|giat toc|tan cong)\b",
    ),
    _p(
        "physical",
        "elevated",
        r"\b(?:xo|day|danh|dap|tat|do|hanh hung|dam|giat toc|tan cong|nem do) "
        r"(?:minh|em|toi)(?: nga)?\b",
    ),
    # --- weapons / violence by others ---------------------------------------------------------
    _p(
        "violence",
        "immediate",
        r"\b(?:mang|cam|giau|co|doa dung) (?:con |theo )?(?:dao|kiem|vu khi|sung|gay)\b",
    ),
    _p("violence", "immediate", r"\b(?:se|dinh|toan) (?:mang|cam|dung) (?:dao|kiem|vu khi|sung)\b"),
    _p("violence", "elevated", r"\b(?:muon|se|dinh|toan) (?:danh|dap|giet|chem|dam|tan cong)\b"),
    # --- coerced / leaked private images ------------------------------------------------------
    _p(
        "image",
        "immediate",
        r"\b(?:doa|de doa|uy hiep|tong tien|doi tien|ep|bat)\b.{0,50}\b(?:anh|hinh|clip|video)\b.{0,30}\b(?:rieng tu|nhay cam|nong|khoa than|kin|than)\b",
    ),
    _p(
        "image",
        "immediate",
        r"\b(?:doa|de doa|uy hiep)\b.{0,40}\b(?:lo|dang|phat tan|tung|lan truyen|cong khai|gui)\b.{0,25}\b(?:anh|hinh|clip|video)\b",
    ),
    _p(
        "image",
        "immediate",
        r"\b(?:ep|bat) (?:minh|em|toi) (?:phai )?(?:gui|chup|quay)\b.{0,25}\b(?:anh|hinh|clip|video)\b.{0,25}\b(?:nhay cam|rieng tu|nong|khoa than|than)\b",
    ),
    _p(
        "image",
        "immediate",
        r"\b(?:anh|hinh|clip|video)\b.{0,25}\b(?:rieng tu|nhay cam|nong|khoa than|kin)\b.{0,25}\b(?:bi|da bi|dang bi)\b.{0,12}\b(?:lan truyen|phat tan|tung|dang|lo|chia se|gui)\b",
    ),
    _p(
        "image",
        "immediate",
        r"\b(?:dang|tung|phat tan|lan truyen|up) (?:video|clip|anh|hinh) (?:rieng tu|nhay cam|nong|khoa than)\b",
    ),
    _p(
        "image",
        "immediate",
        r"\b(?:doa|de doa) (?:dang|tung|lo|phat tan) (?:anh|hinh|clip|video)\b",
    ),
    _p(
        "image",
        "immediate",
        r"\bdoi tien\b.{0,40}\b(?:anh|hinh|clip|video)\b|\b(?:anh|hinh|clip|video)\b.{0,40}\bdoi tien\b",
    ),
    # Private material together with a threat, or still being spread right now.
    _p(
        "image",
        "immediate",
        r"\b(?:anh|hinh|clip|video)\b.{0,12}\b(?:rieng tu|nhay cam|nong|khoa than|kin)\b.{0,70}"
        r"\b(?:doa|de doa|uy hiep|ep)\b|\b(?:doa|de doa|uy hiep|ep)\b.{0,70}"
        r"\b(?:anh|hinh|clip|video)\b.{0,12}\b(?:rieng tu|nhay cam|nong|khoa than|kin)\b",
    ),
    _p(
        "image",
        "immediate",
        r"\bdang (?:gui|dang|chia se|phat tan|lan truyen)\b.{0,20}\b(?:anh|hinh|clip|video)\b.{0,12}"
        r"\b(?:rieng tu|nhay cam|nong|khoa than|kin)\b",
    ),
    _p(
        "image",
        "immediate",
        r"\b(?:doa|de doa|uy hiep) (?:se )?(?:dang|gui|lo|phat tan|lan truyen|dua)(?: them)?\b",
    ),
    _p(
        "image",
        "immediate",
        r"\bneu (?:minh |em |toi )?khong\b.{0,45}\b(?:anh|hinh|clip|video)\b.{0,45}\b(?:se )?"
        r"(?:dang|lo|phat tan|gui|dua|cong khai|chia se)\b",
        True,
    ),
    _p(
        "image",
        "immediate",
        r"\bkhong (?:gui|lam theo|tra tien|chuyen tien)\b.{0,25}\b(?:la|thi)\b.{0,30}\b(?:dua|dang|gui|lo|cong khai)\b"
        r".{0,25}\b(?:cho|len|ca)\b",
        True,
    ),
    _p(
        "abuse",
        "immediate",
        r"\b(?:cham|so|dung|om|hon) (?:vao )?(?:minh|em)\b.{0,50}\b(?:bao dung|khong muon|khong cho|ma minh da)\b|"
        r"\bcham vao (?:minh|em)\b",
    ),
    # --- abuse --------------------------------------------------------------------------------
    _p(
        "abuse", "immediate", r"\bbi (?:xam hai|so mo|cuong buc|hiep|lam dung|bao hanh|dung cham)\b"
    ),
    _p(
        "abuse",
        "immediate",
        r"\b(?:bo|me|cha|duong|thay|nguoi lon|anh|chu|bac|ong|ba|co|hang xom)\b(?: \w+){0,3} (?:danh|dap|so mo|xam hai|hiep|dung cham|bat nat) (?:minh|em|con|vao minh|vao em)\b",
    ),
    _p("abuse", "immediate", r"\b(?:so mo|xam hai|dung cham) (?:minh|em|vao minh|vao em)\b"),
    _p("abuse", "immediate", r"\bhay (?:so mo|dung cham) (?:minh|em)\b"),
    _p("abuse", "elevated", r"\bbao hanh\b"),
)


def _negated(clause: str, start: int, intrinsic: bool) -> bool:
    if intrinsic:
        # "khong muon song nua" is itself the signal; only a second negation cancels it.
        return bool(re.search(r"\b" + _NEG + r"\b(?: \w+){0,2} $", clause[:start]))
    window = clause[max(0, start - 40) : start]
    return bool(re.search(r"\b" + _NEG + r"\b(?: \w+){0,5} $", window))


def _top(levels: Iterable[UrgencyLevel]) -> UrgencyLevel:
    best: UrgencyLevel = "none"
    for level in levels:
        if _RANK[level] > _RANK[best]:
            best = level
    return best


def _step_down(level: UrgencyLevel) -> UrgencyLevel:
    return "elevated" if level == "immediate" else "none"


def first_person_ideation(clause: str) -> bool:
    """The speaker themself wishes to stop existing (not a description of someone else)."""
    own = _POSSESSED.sub(" ", clause)
    if not _FIRST.search(own):
        return False
    if _HYPERBOLE_CHET.search(clause) or _HYPERBOLE_NEUTRAL.search(clause):
        return False
    # "mình không muốn chết đâu" is the opposite of ideation: a preceding negation cancels it.
    return any(not _negated(clause, m.start(), False) for m in _IDEATION.finditer(clause))


def _clause_signals(clause: str, *, quoted: bool) -> list[tuple[str, UrgencyLevel]]:
    found: list[tuple[str, UrgencyLevel]] = []
    media = bool(_MEDIA.search(clause))
    hypothetical = bool(_HYPO.search(clause)) and not _conditional_self_plan(clause)
    past = bool(_PAST.search(clause)) and not _NOW_STRONG.search(clause.replace("hom qua", ""))
    resolved = bool(_RESOLVED.search(clause))
    own = _POSSESSED.sub(" ", clause)
    first_person = bool(_FIRST.search(own.split(" noi ")[-1]))
    third = bool(_THIRD.search(own) or _POSSESSED.search(clause)) and not first_person
    imminent = bool(_IMMINENT.search(clause))
    for group, base, pattern, intrinsic in _RULES:
        match = pattern.search(clause)
        if match is None:
            continue
        if group in {"physical", "threat", "violence"} and _NEGATED_HARM_PREFIX.fullmatch(
            clause[: match.start()]
        ):
            continue
        if _negated(clause, match.start(), intrinsic):
            continue
        level = base
        if media and group in {"self_harm", "violence", "threat", "physical"}:
            continue
        if _INFO.search(clause) and group == "self_harm" and not first_person_ideation(clause):
            continue  # asking how to prevent or help is information-seeking
        if (
            _JOKE.search(clause)
            and group in {"threat", "violence", "physical"}
            and not _FEAR.search(clause)
        ):
            continue  # friends laughing about "I'll hit you": no signal
        if group == "self_harm":
            if _BENIGN_MED.search(clause) and not _OVERDOSE.search(clause):
                continue
            if _HYPERBOLE_NEUTRAL.search(clause) or _HYPERBOLE_CHET.search(clause):
                continue
            if _HYPERBOLE_EMOTIONAL.search(clause):
                level = "elevated"
            if hypothetical:
                level = "elevated"
            if past or resolved:
                level = "elevated"
            if quoted:
                level = "elevated" if level == "immediate" else level
            if (
                third
                and not _FIRST.search(clause)
                and imminent
                and re.search(r"\b(?:nhay|san thuong|ban cong|tu tu|cat tay|uong het)\b", clause)
            ):
                found.append(("third_party", "immediate"))
                continue
            if third and not _FIRST.search(clause):
                found.append(
                    (
                        "third_party",
                        "immediate" if imminent and _MEANS.search(clause) else "elevated",
                    )
                )
                continue
            if third:
                found.append(("third_party", "elevated"))
                continue
            if level == "elevated" and imminent and base == "elevated" and _MEANS.search(clause):
                level = "immediate"
        elif group == "threat":
            if hypothetical and not _FEAR.search(clause):
                continue
            if "hen" in clause.split() and not _FEAR.search(clause):
                continue  # an ordinary arrangement ("hẹn bạn làm bài nhóm"), not a threat
            if past:
                level = "elevated"
            elif imminent and (
                _FEAR.search(clause)
                or _VIOLENT_WORD.search(clause)
                or re.search(r"\b(?:keo|chan|bat|lon|nhot|xu)\b", clause)
            ):
                level = "immediate"
        elif group == "physical":
            if hypothetical:
                continue
            if past:
                level = "elevated"
            elif (imminent or _PRESENT_CONTACT.search(clause)) and (
                _FEAR.search(clause) or "tiep" in clause
            ):
                level = "immediate"
            elif _PASSIVE_PHYSICAL.search(clause) and re.search(r"\bdang bi\b", clause):
                level = "immediate"
            elif (
                third
                and imminent
                and re.search(r"\b(?:keu cuu|cuu|dang bi danh|dang danh|dang dap)\b", clause)
            ):
                level = "immediate"  # someone else is being hurt right now
        elif group == "violence":
            if _BENIGN_OBJECT.search(clause) and not _VIOLENT_WORD.search(clause):
                continue  # kitchen knife at a picnic
            if hypothetical:
                level = _step_down(level)
            if level == "elevated" and imminent and _MEANS.search(clause):
                level = "immediate"
            if (
                base == "elevated"
                and imminent
                and re.search(r"\b(?:nay|mai|sau gio hoc|tan hoc)\b", clause)
            ):
                level = "immediate"
        else:  # image, abuse
            if hypothetical:
                continue
            if past or resolved:
                level = "elevated"
        if level != "none":
            found.append((group, level))
    return found


# ---------------------------------------------------------------------------------------------
# Concept composition (second layer)
#
# The per-phrase rules above only fire on wording somebody already thought of. This layer instead
# detects *concepts* (an act, a means, the time frame, who is present, a condition for a threat)
# and fires when the combination means danger, whatever the exact words are. It is still a
# keyword system: it widens recall, it does not make the system safe (see the S-06 addendum).
# ---------------------------------------------------------------------------------------------
_NOW = (
    r"(?:toi nay|dem nay|chieu nay|sang nay|trua nay|ngay bay gio|bay gio|luc nay|ngay luc nay|"
    r"lat nua|mot lat|\d+ ?(?:phut|p|gio|tieng) nua|cuoi gio|tan hoc|sau gio hoc|ngay mai|sang mai|"
    r"mai|hom nay|truoc \d+ ?gio|\d+ ?gio (?:chieu|toi|sang|dem) nay)"
)
_NOW_RE: Final = re.compile(r"\b" + _NOW + r"\b")
_C_SELF_ACT: Final = re.compile(
    r"\b(?:chet|tu tu|tu sat|nhay (?:xuong|lau|cau|tu|thang)|nhay\b|treo co|cat (?:tay|co tay)|"
    r"rach (?:tay|co tay)|uong (?:het )?thuoc|nuot (?:het )?thuoc|ket thuc (?:moi thu|tat ca|cuoc song|"
    r"doi)|cham dut|bien mat|ra di|lan cuoi|day thung|lam chuyen dai)\b"
)
_C_INTENT: Final = re.compile(
    r"\b(?:se|dinh|toan|quyet dinh|chuan bi|chon xong|nghi xong|da mua|da gom|chac minh|"
    r"khong ai phai|la lan cuoi)\b"
)
_C_MEANS_ACQ: Final = re.compile(
    r"\b(?:gom|mua|giau|tich|tim|chuan bi|lay)(?: het| nhieu| mot)?(?: \w+){0,3} "
    r"(?:thuoc|day thung|day|dao|luoi dao|thuoc ngu)\b"
)
_C_HEIGHT: Final = re.compile(
    r"\b(?:mep|ban cong|san thuong|bau cua so|cua so tang|tren cau|tang thuong|tang \d+|"
    r"len cau|tren noc)\b"
)
_C_PERCH: Final = re.compile(r"\b(?:dang|van) (?:dung|ngoi|nam|leo|o)\b")
_C_FAREWELL: Final = re.compile(
    r"\b(?:xin loi (?:cho )?(?:ca nha|moi nguoi|me|ba|bo|gia dinh)|de lai thu|thu (?:cho|de lai) "
    r"(?:me|ba|bo|ca nha)|don het do|tam biet|lan cuoi|cam on (?:ban )?da (?:nghe|o canh|giup|"
    r"lang nghe)|khong (?:con )?phai lo (?:cho|ve)?|khong lam phien|se khong con|gui loi chao)\b"
)
_C_PREP: Final = re.compile(
    r"\b(?:tim hieu cach|chuan bi xong|da chon xong|nghi xong cach|da biet cach|xong het roi)\b"
)
_C_ALONE: Final = re.compile(
    r"\b(?:nha khong co ai|khong co ai o nha|di vang|di dam cuoi|di vang het|mot minh|1 minh|"
    r"khi moi nguoi di|khi khong con ai|moi nguoi di het)\b"
)
_C_DISTRESS: Final = re.compile(
    r"\b(?:met moi|met lam|chan|vo nghia|buon|khong chiu noi|tuyet vong|co don|kiet suc|"
    r"khong con y nghia|ap luc)\b"
)
_C_ONGOING: Final = re.compile(
    r"\b(?:chua (?:ngung|dung|cam)|van (?:chay|dang chay)|dang chay|khong ngung|buon ngu|"
    r"choang|chong mat|dau bat dau|bat dau (?:choang|chong mat|dau))\b"
)
_C_PERP: Final = re.compile(
    r"\b(?:nguoi la|nguoi dan ong|nguoi lon|mot nhom|nhom|tui no|tui no|ba dua|hai dua|may dua|"
    r"may anh|anh lop \d+|anh lop tren|xe|ten do|thang do|gia dinh|ong ay|nguoi yeu cu|nguoi yeu)\b"
)
_C_FOLLOW: Final = re.compile(
    # Folding conflates "chờ mình" (waiting for me) with "cho mình" (give me).
    # Exclude explicit help-request complements from this concept only; a separate
    # disclosure of present contact or violence must still escalate normally.
    r"\b(?:bam theo|theo sau|theo doi|di theo|vay|chan (?:minh|em|toi|duong|cua)|"
    r"cho (?:minh|em|toi)(?! (?:biet\b|cach\b|loi khuyen\b|goi y\b|"
    r"(?:mot|vai|hai|ba) (?:buoc|cach|goi y|vi du|loi khuyen)\b))|"
    r"cho truoc|dung (?:cho|truoc|ngoai)|go cua|den tim|den nha|rinh|lon vao|keo (?:minh|em|toi)|"
    r"len tim|cam (?:dao|gay|vu khi)|rut dien thoai)\b"
)
_C_WEAPON: Final = re.compile(
    r"\b(?:dao|gay|keo|kiem|sung|luoi dao|bom|axit|vu khi|dao cao|day lung|day dien|xich)\b"
)
_C_ATTACK: Final = re.compile(
    r"\b(?:danh|dam|dap|da|giet|chem|de|doa|xu|lon|hanh hung|dap dau|bop co|tat|nem|tra thu|"
    r"xu ly|day do)\b"
)
_C_INJURY: Final = re.compile(
    r"\b(?:bat tinh|ngat|khong tinh|khong day (?:noi|duoc)|nam co|co nguoi lai|chay mau|"
    r"mau chay|be bet|mat ca|khong tho|bam tim|nga (?:xuong|guc|nhao)|nam duoi dat)\b"
)
_C_IMG: Final = re.compile(
    r"\b(?:anh|hinh|clip|video|tin nhan)\b.{0,30}\b(?:rieng tu|nhay cam|nong|khoa than|khong mac|"
    r"cu|rieng)\b|\b(?:rieng tu|nhay cam|khoa than)\b.{0,15}\b(?:anh|hinh|clip|video)\b|"
    r"\banh khong mac\b"
)
_C_IMG_ANY: Final = re.compile(r"\b(?:anh|hinh|clip|video)\b")
_C_COND: Final = re.compile(
    r"\b(?:neu (?:khong|em khong|minh khong|toi khong)|khong thi|bat (?:minh|em|toi)|ep (?:minh|em|toi)|"
    r"doi tien|tong tien|chuyen tien|tra tien|gui them|doi gui|doi minh|dieu kien|tu choi)\b"
)
_C_SPREAD: Final = re.compile(
    r"\b(?:tung|dang len|dang|dua (?:cho|len)|gui cho|len (?:group|fb|facebook|nhom|trang)|"
    r"cong khai|chia se|lan truyen|phat tan|chuyen tay|ba me|cho (?:ca|toan) (?:lop|truong|khoi|"
    r"nhom|ban be))\b|\bgui\b.{0,30}\bcho\b"
)
_C_SPREADING_NOW: Final = re.compile(
    r"\b(?:dang (?:duoc )?(?:chuyen tay|chia se|lan truyen|phat tan|dang)|vua bi (?:chia se|dang|"
    r"tung|lo)|hang chuc nguoi xem|nhieu nguoi xem|ca lop da xem)\b"
)
_C_ADULT: Final = re.compile(
    r"\b(?:chu|bo|ba|me ke|bo duong|di ghe|anh ho|chu ho|thay|co giao|bac|ong|nguoi lon|hang xom|"
    r"anh|nguoi quen)\b"
)
_C_TOUCH: Final = re.compile(
    r"\b(?:so|cham vao|om|hon|vao phong|sờ|bat nat|coi (?:dai|quan)|goi (?:em|minh) (?:ra|vao|sang|lai)|"
    r"o lai mot minh|chi rieng)\b"
)
# A disclosure can name the body area rather than use "chạm vào mình". Keep it in
# the composition layer so negation, past tense, media and information-seeking
# framing retain the same handling as the other contact concepts.
_C_INTIMATE_TOUCH: Final = re.compile(
    r"\b(?:cham|so|dung) (?:vao )?(?:vung kin|cho kin|bo phan sinh duc) (?:cua )?(?:minh|em|toi)\b"
)
# Require an external actor or passive disclosure: ordinary self-care and a
# consensual medical examination must not acquire an abuse signal from this rule.
_C_OTHER_TOUCH_ACTOR: Final = re.compile(
    r"\b(?:(?:nguoi (?:do|ay|khac|ta)|(?:mot|co) nguoi|ai do|ban (?:ay|do)|chu(?: ho)?|"
    r"anh ho|chi ho|bo|cha|me|ba|ong|thay|co giao|bac(?! si\b)|hang xom)(?: \w+){0,3}|bi) $"
)
_C_ACCESS: Final = re.compile(
    r"\b(?:ban dem|khong co ai|dung noi|toi nay|cuoi tuan|lai den|lai o|o nha|o lai|hom truoc|"
    r"bao em|bao minh)\b"
)
_C_CONFINE: Final = re.compile(
    r"\b(?:khoa|nhot|nhot|nhot) (?:cua )?(?:minh|em|toi)\b|\bnhot (?:minh|em|toi)\b"
)
_C_THIRD_SELF: Final = re.compile(
    r"\b(?:rach tay|cat tay|cat co tay|nhay|uong thuoc|uong het|nuot thuoc|treo co|cam dao|"
    r"luoi dao|tu tu|bi nhot trong|khoa minh)\b"
)


def _compose(clause: str, *, quoted: bool) -> list[tuple[str, UrgencyLevel]]:
    """Concept-level rules. ``clause`` is already folded."""
    # "họ nói nếu em không chuyển tiền thì…" is a reported condition, not a what-if question.
    reported = re.match(r"^\w+ (?:noi|bao|nhan|doa|nhac|ra dieu kien)\b", clause) is not None
    if (
        _MEDIA.search(clause)
        or (_HYPO.search(clause) and not reported and not _conditional_self_plan(clause))
        or _INFO.search(clause)
    ):
        return []
    if _HYPERBOLE_NEUTRAL.search(clause) or _HYPERBOLE_EMOTIONAL.search(clause):
        return []
    if _HYPERBOLE_CHET.search(clause):
        return []
    past = bool(_PAST.search(clause)) and not _NOW_STRONG.search(clause.replace("hom qua", ""))
    resolved = bool(_RESOLVED.search(clause))
    if resolved:
        return []
    own = _POSSESSED.sub(" ", clause)
    first = bool(_FIRST.search(own))
    third = bool(_THIRD.search(own) or _POSSESSED.search(clause)) and not first
    now = bool(_NOW_RE.search(clause))
    soft: UrgencyLevel = "elevated" if (past or quoted) else "immediate"
    out: list[tuple[str, UrgencyLevel]] = []

    def ok(pattern: "re.Pattern[str]") -> bool:
        match = pattern.search(clause)
        return match is not None and not _negated(clause, match.start(), False)

    # -- self harm -----------------------------------------------------------------------
    act = ok(_C_SELF_ACT)
    if act and ok(_C_INTENT) and now and not _BENIGN_OBJECT.search(clause) and not third:
        out.append(("self_harm", soft))
    if ok(_C_MEANS_ACQ) and now and (first or not third) and not _BENIGN_OBJECT.search(clause):
        if re.search(r"\b(?:thuoc|day thung|luoi dao|thuoc ngu)\b", clause):
            out.append(("self_harm", soft))
    if (
        ok(_C_HEIGHT)
        and ok(_C_PERCH)
        and first
        and not re.search(r"\b(?:chup|ngam|view|canh)\b", clause)
    ):
        out.append(("self_harm", soft))
    if (
        ok(_C_FAREWELL)
        and first
        and (
            len(set(_C_FAREWELL.findall(clause))) >= 2
            or (now and _C_FAREWELL.search(clause) is not None)
        )
    ):
        out.append(("self_harm", soft))
    if (
        re.search(r"\b(?:cat|rach) (?:tay|co tay)\b", clause)
        and _C_ONGOING.search(clause)
        and first
    ):
        out.append(("self_harm", "immediate"))
    if (
        re.search(r"\b(?:vua|da) (?:nuot|uong|cat|rach)\b", clause)
        and _C_ONGOING.search(clause)
        and first
    ):
        out.append(("self_harm", "immediate"))
    # a named method together with finality, in the speaker's own voice
    if (
        re.search(r"\b(?:nhay (?:tu|xuong|khoi)|treo co|cat co tay|tu tu|uong het thuoc)\b", clause)
        and ok(_C_SELF_ACT)
        and first
        and not third
        and re.search(r"\b(?:la|se|luon|cho xong|dinh|toan|khong chiu noi|ket thuc)\b", clause)
        and not _BENIGN_OBJECT.search(clause)
        and not re.search(r"\b(?:bungee|du lich|tro choi|boi|xuong ho)\b", clause)
    ):
        out.append(("self_harm", soft))
    # worked out how, and when
    if (
        re.search(r"\b(?:nghi xong cach|da chon xong|da biet cach|tim hieu cach)\b", clause)
        and now
        and first
        and re.search(r"\b(?:se lam|minh lam|thuc hien|ra tay)\b", clause)
    ):
        out.append(("self_harm", soft))
    # a third person in acute self-harm
    other = bool(
        _THIRD.search(clause)
        or re.search(
            r"\b(?:ban (?:than|cung (?:phong|lop|ban)|minh|em)|anh (?:minh|trai)|chi (?:minh|gai))\b",
            clause,
        )
    )
    if (
        (third or other)
        and _C_THIRD_SELF.search(clause)
        and (not _BENIGN_MED.search(clause) or _OVERDOSE.search(clause))
        and re.search(r"\b(?:dang|vua|sap)\b", clause)
    ):
        out.append(("third_party", "immediate"))
    if (
        other
        and re.search(r"\b(?:tay|co tay)\b.{0,12}\bchay mau\b", clause)
        and re.search(r"\b(?:vua|dang)\b", clause)
    ):
        out.append(("third_party", "immediate"))

    # -- threats, presence and weapons -----------------------------------------------------
    victim = bool(re.search(r"\b(?:minh|em|toi|con)\b", clause))
    if _C_FOLLOW.search(clause) and victim and re.search(r"\b(?:dang|van|cu|vua)\b", clause):
        if _C_PERP.search(clause) or re.search(r"\b(?:ai do|co nguoi|nguoi)\b", clause):
            out.append(("threat", "elevated" if past else "immediate"))
    if (
        _C_FOLLOW.search(clause)
        and victim
        and now
        and (_C_ALONE.search(clause) or _FEAR.search(clause) or _C_WEAPON.search(clause))
        and re.search(r"\b(?:ai do|co nguoi|nguoi|ho|no|tui)\b", clause)
    ):
        out.append(("threat", "elevated" if past else "immediate"))
    if (
        _C_WEAPON.search(clause)
        and now
        and re.search(r"\b(?:mang|cam|dem|den|ra|tim|xu|giet|dam|doi)\b", clause)
        and (_C_ATTACK.search(clause) or _C_FOLLOW.search(clause) or victim)
    ):
        if not _BENIGN_OBJECT.search(clause) and not _JOKE.search(clause):
            out.append(("violence", soft))
    if (
        re.search(r"\b(?:dang|vua)\b", clause)
        and _C_ATTACK.search(clause)
        and (_C_INJURY.search(clause) or re.search(r"\b(?:lien tuc|dap dau|duoi theo)\b", clause))
    ):
        out.append(("physical", "immediate" if not past else "elevated"))
    if (
        _C_INJURY.search(clause)
        and _C_ATTACK.search(clause)
        and not past
        and (third or re.search(r"\b(?:ban|em|anh|chi|me|bo)\b", clause))
        and re.search(r"\b(?:bi|dang|vua)\b", clause)
    ):
        out.append(("physical", "immediate"))
    # The person who hurt or threatened the speaker is still there, and the speaker is afraid or was
    # just hit: the urgency is the present contact, not the severity of what already happened.
    if (
        re.search(
            r"\b(?:van|dang|chua) (?:dung|o|ngoi|dut)? ?(?:ngay )?(?:do|day|canh|ben canh|truoc mat)\b",
            clause,
        )
        and victim
        and (
            _FEAR.search(clause)
            or _VIOLENT_WORD.search(clause)
            or re.search(r"\b(?:xo|de (?:len|minh|em|toi))\b", clause)
        )
        and not past
    ):
        out.append(("physical", "immediate"))
    # A serious injury is happening now (medical emergency), whatever caused it.
    if (
        re.search(
            r"\b(?:chong mat|choang|buon non|bat tinh|chay mau nhieu|khong cam duoc mau|mau khong cam|"
            r"khong dung duoc|khong cu dong|gay (?:tay|chan|xuong))\b",
            clause,
        )
        and victim
        and re.search(r"\b(?:bi|dap|nga|xo|danh|va)\b", clause)
        and not past
    ):
        out.append(("physical", "immediate"))
    if _C_CONFINE.search(clause):
        out.append(
            (
                "physical",
                "immediate" if _C_ATTACK.search(clause) or _FEAR.search(clause) else "elevated",
            )
        )

    # -- private images ------------------------------------------------------------------------
    img = bool(_C_IMG.search(clause))
    if img and _C_COND.search(clause) and _C_SPREAD.search(clause):
        out.append(("image", soft))
    if (img or _C_IMG_ANY.search(clause)) and _C_SPREADING_NOW.search(clause) and img:
        out.append(("image", soft))
    if img and re.search(r"\b(?:ep|bat) (?:minh|em|toi)\b", clause):
        out.append(("image", soft))

    # -- abuse -----------------------------------------------------------------------------------
    adult = bool(_C_ADULT.search(clause))
    contact = _C_INTIMATE_TOUCH.search(clause)
    if contact and ok(_C_INTIMATE_TOUCH) and _C_OTHER_TOUCH_ACTOR.search(clause[: contact.start()]):
        out.append(("abuse", soft))
    if adult and _C_TOUCH.search(clause) and victim and (_C_ACCESS.search(clause) or now):
        out.append(("abuse", soft))
    if (
        re.search(r"\b(?:cam|coi|rut)\b.{0,20}\b(?:day lung|day dien|roi|gay|dao)\b", clause)
        and re.search(r"\b(?:goi|bat|keu)\b.{0,12}\b(?:em|minh|con)\b", clause)
    ) or (
        adult
        and re.search(r"\b(?:danh|dap|dung)\b", clause)
        and victim
        and re.search(r"\b(?:tiep|lai|nua)\b", clause)
        and now
    ):
        out.append(("abuse", soft))
    return out


def _conversation_signals(turns: Sequence[str]) -> list[tuple[str, UrgencyLevel]]:
    """Plan-over-turns: preparation + being alone + distress across the recent messages."""
    if len(turns) < 2:
        return []
    joined = fold(" . ".join(turns[-4:]))
    if _MEDIA.search(joined) or _HYPO.search(joined) or _INFO.search(joined):
        return []
    if (
        _C_PREP.search(joined)
        and _C_DISTRESS.search(joined)
        and (_NOW_RE.search(joined) or _C_ALONE.search(joined))
        and (_C_ALONE.search(joined) or re.search(r"\bminh (?:se )?lam\b", joined))
    ):
        return [("self_harm", "immediate")]
    return []


def assess_urgency(text: str, *, prior: Sequence[str] = ()) -> UrgencyAssessment:
    """Assess one message. ``prior`` holds earlier user messages of the same conversation."""
    levels: list[UrgencyLevel] = []
    signals: set[str] = set()

    def absorb(source: str, *, quoted: bool) -> None:
        # Judge each sentence whole (a fear can sit in the next comma-part) and again split at
        # a new subject (so a negation cannot leak across it); signals are the union.
        pieces: list[str] = []
        for sentence in _SENTENCE.split(source):
            # Split before evaluating, so an earlier denial cannot negate later intent.
            if _CONTEXT_BREAK.search(sentence):
                pieces.extend(_CONTEXT_BREAK.split(sentence))
                continue
            parts = _SUBJECT_BREAK.split(sentence)
            pieces.append(sentence)
            if len(parts) > 1:
                pieces.extend(parts)
        for sentence in pieces:
            clause = fold(sentence)
            if not clause:
                continue
            for group, level in _clause_signals(clause, quoted=quoted):
                signals.add(group)
                levels.append(level)
            for group, level in _compose(clause, quoted=quoted):
                signals.add(group)
                levels.append(level)
        # The same concepts can be spread over a few sentences of one message.
        whole = fold(source)
        if whole and len(_SENTENCE.split(source)) > 1:
            for group, level in _compose(whole, quoted=quoted):
                signals.add(group)
                levels.append(level)

    quoted_spans = list(_QUOTES.finditer(text))
    unquoted = _QUOTES.sub(" ", text)
    absorb(unquoted, quoted=False)
    frame = fold(unquoted)
    playful = bool(_JOKE.search(frame)) and not _FEAR.search(frame)
    if not _MEDIA.search(frame) and not playful:
        for span in quoted_spans:
            prefix = fold(re.split(r"[.!?;\n]", text[: span.start()])[-1])
            if _ABSTRACT_QUOTE.search(prefix):
                continue  # only this explicitly introduced hypothetical quote
            # A quoted threat the user received is still a threat; quoted ideation is softened.
            absorb(span.group(1) or span.group(2), quoted=True)
    best = _top(levels)

    folded_all = fold(_QUOTES.sub(" ", text))
    if best != "immediate" and not _MEDIA.search(folded_all) and not _INFO.search(folded_all):
        # "I see no reason to go on. Today I will end it": two clauses, one decision.
        if (
            first_person_ideation(folded_all)
            and _IMMINENT.search(folded_all)
            and (_COMMIT.search(folded_all) or _MEANS.search(folded_all))
            and not _HYPO.search(folded_all)
        ):
            best = "immediate"
            signals.add("self_harm")
            signals.add("ideation_with_commitment")
        elif best == "none" and first_person_ideation(folded_all) and not _HYPO.search(folded_all):
            best = "elevated"  # a clear wish to stop existing is never silently ignored
            signals.add("self_harm")

    if prior:
        for group, level in _conversation_signals([*prior, text]):
            if _RANK[level] > _RANK[best]:
                best = level
            signals.add(group)
            signals.add("plan_over_turns")
        previous = [assess_urgency(message) for message in prior[-4:]]
        earlier = _top(assessment.level for assessment in previous)
        earlier_signals = {signal for assessment in previous for signal in assessment.signals}
        current = fold(text)
        # Time and a pronoun alone do not mean danger ("now I am doing homework").
        # Link the new cue to the kind of concern already disclosed.
        self_harm_escalation = (
            "self_harm" in earlier_signals
            and _IMMINENT.search(current)
            and (
                _C_ALONE.search(current)
                or _COMMIT.search(current)
                or (
                    _MEANS.search(current)
                    and not _BENIGN_MED.search(current)
                    and not _BENIGN_OBJECT.search(current)
                )
            )
        )
        contact_escalation = (
            (
                earlier_signals & {"threat", "abuse", "violence"}
                or ("physical" in earlier_signals and _FEAR.search(current))
            )
            and _PRESENT_CONTACT.search(current)
            and (
                # Generic third-person references may name a new helper. Reuse the
                # prior aggressor only for anaphora, or with a current danger cue.
                re.search(
                    r"\b(?:(?:ban|anh|chi|co|em|cau) ay|no|bon no|tui no|nhom do|nguoi do|ke do|ten do|thang do)\b",
                    current,
                )
                or (
                    _C_PERP.search(current)
                    and (
                        _FEAR.search(current)
                        or _C_FOLLOW.search(current)
                        or _C_ATTACK.search(current)
                    )
                )
            )
        )
        if (
            best != "immediate"
            and (self_harm_escalation or contact_escalation)
            and not (_MEDIA.search(current) or _HYPO.search(current) or _INFO.search(current))
        ):
            best = "immediate"
            signals.add("escalation_over_turns")
        elif earlier != "none" and best == "none":
            best = "elevated"  # preserve a check-in without inventing a present emergency
            signals.add("recent_high_risk")
    return UrgencyAssessment(best, tuple(sorted(signals))) if best != "none" else NONE


def assess_conversation(user_messages: Sequence[str]) -> UrgencyAssessment:
    """Assess the newest message in the context of the previous ones (multi-turn risk)."""
    if not user_messages:
        return NONE
    return assess_urgency(user_messages[-1], prior=list(user_messages[:-1]))


_REPLY_ESCALATION = re.compile(
    r"\b(?:ban|em) (?:dang|co the dang) (?:gap )?nguy hiem (?:ngay|luc nay)|"
    r"\bgoi (?:ngay )?(?:111|113|114|115|cap cuu)\b|\bcan (?:giup do|cap cuu) (?:ngay|khan cap)\b"
)


def assess_reply(reply: str) -> UrgencyAssessment:
    """Second pass over the model's own answer: it escalated, so the static block must be there."""
    folded = fold(reply)
    match = _REPLY_ESCALATION.search(folded)
    if match is not None and not _negated(folded, match.start(), False):
        return UrgencyAssessment("immediate", ("assistant_escalation",))
    return NONE


def with_emergency_block(content: str) -> str:
    """Append the static block exactly once, whatever the model wrote."""
    if "Tổng đài Quốc gia bảo vệ trẻ em 111" in content:
        return content
    return content.rstrip() + EMERGENCY_BLOCK


def combine(*assessments: UrgencyAssessment) -> UrgencyAssessment:
    """Highest level wins; signal names are unioned."""
    level = _top(a.level for a in assessments)
    signals = tuple(sorted({s for a in assessments for s in a.signals}))
    return UrgencyAssessment(level, signals) if level != "none" else NONE
