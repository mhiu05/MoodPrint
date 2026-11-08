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


def fold(text: str) -> str:
    """Lower-case, strip diacritics (đ→d), collapse stretched letters, map teen spellings."""
    lowered = unicodedata.normalize("NFC", text.lower())
    # Protect two words that would collide after diacritics are stripped:
    # "đừng" (don't) vs "đứng" (stand) and "từng" (once) vs the verb "tung" (to leak).
    lowered = re.sub("đừng", "dungz", lowered)
    lowered = re.sub("từng", "tungz", lowered)
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
    r"\b(?:bai hat|phim|truyen|tho|game|meme|tiktok|sach|nhan vat|bai van|phan tich|ca khuc|"
    r"lyric|kich|tieu thuyet|bao chi|bao dien tu|tin tuc|ban tin|bai viet|dua tin|thoi su|phong van|"
    r"van ban|trang web|bai bao)\b"
)
# Joking or playful framing: a "threat" between friends who laugh is not a threat.
_JOKE = re.compile(
    r"\b(?:dua|dua thoi|dua vui|cuoi|cuoi lan|haha|hihi|kkk|troll|choi game|dau game|vui)\b"
)
# Wanting to understand or prevent harm is information-seeking, not a disclosure.
_INFO = re.compile(
    r"\b(?:phong tranh|phong ngua|hieu cach|muon hieu|lam sao de|lam the nao de|cach de)\b"
)
_COMMIT = re.compile(
    r"\b(?:minh|em|toi) (?:se|dinh|toan)(?: \w+){0,2} (?:lam|ket thuc|di|thuc hien)\b|"
    r"\b(?:di luon|lam luon|cho xong|nghi xong|het cach)\b"
)
# A leading "if…" is a what-if question; a trailing "…if you tell" is the condition of a threat.
_HYPO = re.compile(r"^(?:\w+ ){0,2}(?:neu|gia su|gia nhu|gia thu|lo nhu|gia dinh|neu nhu)\b")
_BENIGN_OBJECT = re.compile(
    r"\b(?:got|bep|nau|hoa qua|trai cay|picnic|cat banh|bua an|an com|thuc hanh|nghe thuat|"
    r"roc giay|thu cong|my thuat|cat giay|lam banh|dung cu|hoc cu)\b"
)
# "tức muốn chết", "đói muốn chết": hyperbole. Physical/neutral ones carry no signal; emotional
# ones ("buồn muốn chết") are not dismissed but kept at elevated.
_HYPERBOLE_NEUTRAL = re.compile(
    r"\b(?:tuc|doi|khat|nong|lanh|cuoi|buon cuoi|vui|xau ho|buon ngu|thich|yeu|moi|ngai|dau|ghet|"
    r"met|buon ngu|nhuc|an|no) (?:den muc |phat )?muon chet\b"
)
_HYPERBOLE_EMOTIONAL = re.compile(r"\b(?:buon|chan|so|bat luc|kho chiu|ap luc) muon chet\b")
_VIOLENT_WORD = re.compile(r"\b(?:danh|dap|giet|chem|dam|xu ly|hanh hung|doa)\b")
_PAST = re.compile(
    r"\b(?:hoi|tungz|da tungz|truoc day|nam ngoai|thang truoc|tuan truoc|ngay xua|luc nho|"
    r"hoi nho|ngay do|thoi do|lan do|hom qua|truoc kia|nam truoc)\b"
)
_RESOLVED = re.compile(r"\b(?:gio on|da on|da qua|khong con nua|xoa roi|da het)\b")
_IMMINENT = re.compile(
    r"\b(?:bay gio|ngay bay gio|luc nay|ngay lap tuc|toi nay|hom nay|chieu nay|sang nay|"
    r"dem nay|lat nua|mot lat|sap|dang|chuan bi|da mua|san sang|tan hoc|sau gio hoc|sau hoc|"
    r"het gio|ra choi|tan truong|ngay mai|trong ngay|vua nhan|vua noi|ngoai kia|truoc cong|"
    r"o cong|ngay luc nay|nhu bay gio)\b"
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

# group, base level, pattern, intrinsic_negation (pattern already contains its own "khong")
_P = tuple[str, UrgencyLevel, "re.Pattern[str]", bool]


def _p(group: str, level: UrgencyLevel, pattern: str, intrinsic: bool = False) -> _P:
    return (group, level, re.compile(pattern), intrinsic)


_RULES: Final[tuple[_P, ...]] = (
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
        r"\b(?:se|dinh|toan) ket thuc\b|\bnghi xong cach\b.{0,40}\b(?:chet|bien mat|ket thuc)\b",
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
    # "mình không muốn chết đâu" is the opposite of ideation: a preceding negation cancels it.
    return any(not _negated(clause, m.start(), False) for m in _IDEATION.finditer(clause))


def _clause_signals(clause: str, *, quoted: bool) -> list[tuple[str, UrgencyLevel]]:
    found: list[tuple[str, UrgencyLevel]] = []
    media = bool(_MEDIA.search(clause))
    hypothetical = bool(_HYPO.search(clause))
    past = bool(_PAST.search(clause)) and not _IMMINENT.search(clause.replace("hom qua", ""))
    resolved = bool(_RESOLVED.search(clause))
    own = _POSSESSED.sub(" ", clause)
    first_person = bool(_FIRST.search(own.split(" noi ")[-1]))
    third = bool(_THIRD.search(own) or _POSSESSED.search(clause)) and not first_person
    imminent = bool(_IMMINENT.search(clause))
    for group, base, pattern, intrinsic in _RULES:
        match = pattern.search(clause)
        if match is None:
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
            if _HYPERBOLE_NEUTRAL.search(clause):
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
            elif imminent and (_FEAR.search(clause) or "tiep" in clause):
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


def assess_urgency(text: str, *, prior: Sequence[str] = ()) -> UrgencyAssessment:
    """Assess one message. ``prior`` holds earlier user messages of the same conversation."""
    levels: list[UrgencyLevel] = []
    signals: set[str] = set()

    def absorb(source: str, *, quoted: bool) -> None:
        for sentence in _SENTENCE.split(source):
            clause = fold(sentence)
            if not clause:
                continue
            for group, level in _clause_signals(clause, quoted=quoted):
                signals.add(group)
                levels.append(level)

    quoted_spans = [m.group(1) or m.group(2) for m in _QUOTES.finditer(text)]
    unquoted = _QUOTES.sub(" ", text)
    absorb(unquoted, quoted=False)
    frame = fold(unquoted)
    playful = bool(_JOKE.search(frame)) and not _FEAR.search(frame)
    if not _MEDIA.search(frame) and not playful:  # lyrics, film lines and jokes are not threats
        for span in quoted_spans:
            # A quoted threat the user received is still a threat; quoted ideation is softened.
            absorb(span, quoted=True)
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
        earlier = _top(assess_urgency(message).level for message in prior[-4:])
        current = fold(text)
        if (
            best != "immediate"
            and earlier != "none"
            and _IMMINENT.search(current)
            and (_FIRST.search(current) or _MEANS.search(current) or _FEAR.search(current))
        ):
            best = "immediate"
            signals.add("escalation_over_turns")
        elif earlier == "immediate" and best == "none":
            best = "elevated"  # the conversation stays on watch after a high-risk turn
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
