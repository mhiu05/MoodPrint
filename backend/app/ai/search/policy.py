import re
import unicodedata
from dataclasses import dataclass

from app.ai.schemas import PromptOptions


def folded(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
                   if unicodedata.category(c) != "Mn")


PRIVATE_WORDS = ("nhat ky", "mat khau", "password", "token", "api key", "so dien thoai", "dia chi nha", "ho so",
                 "ky uc", "can cu cam xuc", "memory")
PERSONAL = re.compile(
    r"\b(toi|minh|gia dinh|ho ten|ngay sinh|con gai|con trai|vo toi|chong toi|benh an|chan doan|"
    r"my|mine|our|his|her|their|daughter|son|wife|husband|mother|father|friend|diagnosed|diagnosis|"
    r"patient|passport|social security|credit card|personal)\b")
NAMED_PERSON = re.compile(r"\b(?:anh|chị|cô|chú|bác|ông|bà|bạn|bé|em|cháu)\s+[A-ZĐÀ-Ỹ]")
WRAPPERS = ("giúp mình ", "giup minh ", "cho mình ", "cho minh ", "mình muốn ", "minh muon ", "tôi muốn ", "toi muon ")
# Closed public labels. Only these strings (never the user's words) can reach the provider.
TOPICS = (
    (r"\bpython\b", "Python"), (r"\breact\b", "React"), (r"\bjavascript\b", "JavaScript"),
    (r"\btypescript\b", "TypeScript"), (r"\bopenai\b", "OpenAI"),
    (r"tri tue nhan tao|\bai\b", "trí tuệ nhân tạo"), (r"lap trinh", "lập trình"),
    (r"cong nghe", "công nghệ"), (r"khoa hoc", "khoa học"), (r"thien van", "thiên văn học"),
    (r"lich su", "lịch sử"), (r"hoi hoa|hoc ve", "học vẽ"), (r"am nhac", "âm nhạc"),
    (r"sinh hoc", "sinh học"), (r"vat ly", "vật lý"), (r"hoa hoc", "hóa học"),
    (r"toan hoc", "toán học"), (r"ngoai ngu|tieng anh", "học tiếng Anh"),
    (r"nhiep anh", "nhiếp ảnh"), (r"nau an|cong thuc mon", "nấu ăn"), (r"\bsach\b", "sách"),
    (r"\bphim\b", "phim"), (r"bong da", "bóng đá"), (r"the thao", "thể thao"),
    (r"du lich", "du lịch"), (r"le hoi", "lễ hội"), (r"su kien", "sự kiện"),
    (r"gia vang", "giá vàng"), (r"ty gia|ti gia", "tỷ giá"),
    (r"khi hau", "khí hậu"), (r"moi truong", "môi trường"),
    (r"thoi tiet", "thời tiết"), (r"quan ca phe|cafe", "quán cà phê"),
    (r"cong vien", "công viên"), (r"nha hang", "nhà hàng"), (r"bao tang", "bảo tàng"),
    (r"dia diem|di choi", "địa điểm vui chơi"),
)
# Public gazetteer: the 34 provincial units plus well-known destinations. A place outside it
# (a street, school or home) is dropped, never copied.
PLACES = (
    (r"ha noi", "Hà Nội"), (r"ho chi minh|sai gon|tp ?hcm", "TP. Hồ Chí Minh"), (r"da nang", "Đà Nẵng"),
    (r"hai phong", "Hải Phòng"), (r"can tho", "Cần Thơ"), (r"\bhue\b", "Huế"), (r"lai chau", "Lai Châu"),
    (r"dien bien", "Điện Biên"), (r"son la", "Sơn La"), (r"lang son", "Lạng Sơn"),
    (r"quang ninh", "Quảng Ninh"), (r"thanh hoa", "Thanh Hóa"), (r"nghe an", "Nghệ An"),
    (r"ha tinh", "Hà Tĩnh"), (r"cao bang", "Cao Bằng"), (r"tuyen quang", "Tuyên Quang"),
    (r"lao cai", "Lào Cai"), (r"thai nguyen", "Thái Nguyên"), (r"phu tho", "Phú Thọ"),
    (r"bac ninh", "Bắc Ninh"), (r"hung yen", "Hưng Yên"), (r"ninh binh", "Ninh Bình"),
    (r"quang tri", "Quảng Trị"), (r"quang ngai", "Quảng Ngãi"), (r"gia lai", "Gia Lai"),
    (r"khanh hoa", "Khánh Hòa"), (r"lam dong", "Lâm Đồng"), (r"dak lak", "Đắk Lắk"),
    (r"dong nai", "Đồng Nai"), (r"tay ninh", "Tây Ninh"), (r"vinh long", "Vĩnh Long"),
    (r"dong thap", "Đồng Tháp"), (r"ca mau", "Cà Mau"), (r"an giang", "An Giang"),
    (r"da lat", "Đà Lạt"), (r"nha trang", "Nha Trang"), (r"hoi an", "Hội An"), (r"vung tau", "Vũng Tàu"),
    (r"sa ?pa", "Sa Pa"), (r"ha long", "Hạ Long"), (r"phu quoc", "Phú Quốc"), (r"quy nhon", "Quy Nhơn"),
)
TIMES = ((r"hom nay", "hôm nay"), (r"ngay mai", "ngày mai"), (r"cuoi tuan", "cuối tuần"),
         (r"tuan nay", "tuần này"), (r"thang nay", "tháng này"))


def private_prompt(prompt: str) -> bool:
    """True when the current prompt carries identifiers or a personal disclosure."""
    text = " ".join(prompt.split())
    for prefix in WRAPPERS:
        if text.lower().startswith(prefix):
            text = text[len(prefix):]
            break
    norm = folded(text)
    return bool(any(word in norm for word in PRIVATE_WORDS)
                or re.search(r"@|https?://|sk-|\b\d[\d +().-]{7,}\d\b|[<>]", text, re.I)
                or PERSONAL.search(norm) or NAMED_PERSON.search(text))


def safe_query(prompt: str) -> str | None:
    """Project the current prompt onto closed public labels, or refuse (None).

    Refuses personal statements instead of guessing which names/relationships/details are safe
    to expose to a public search service. Zero free-form words are copied: topic, gazetteer
    place and time labels only, so unknown topics ask for a clearer public subject.
    """
    text = " ".join(prompt.split())
    if not 2 <= len(text) <= 300 or private_prompt(text):
        return None
    norm = folded(text)
    canonical = [topic for pattern, topic in TOPICS if re.search(pattern, norm)]
    if not canonical:
        return None
    result = " · ".join(canonical[:2])
    place = next((label for pattern, label in PLACES if re.search(pattern, norm)), None)
    when = next((label for pattern, label in TIMES if re.search(pattern, norm)), None)
    if place:
        result += " tại " + place
    if when:
        result += " " + when
    if any(word in norm for word in ("moi nhat", "tin moi", "cap nhat", "latest", "news")):
        result = "Thông tin mới nhất về " + result
    elif any(word in norm for word in ("khoa hoc", "tai lieu", "course", "resource")):
        result = "Tài liệu học về " + result
    return result


@dataclass(frozen=True)
class SearchIntent:
    query: str | None
    web: bool = False
    maps: bool = False
    area: str | None = None


def search_intent(prompt: str, options: PromptOptions) -> SearchIntent:
    text = folded(prompt)
    negated = any(p in text for p in ("khong tim", "dung tim", "khong muon di", "khong can tra"))
    maps = "maps_search" in options.tools or (not negated and any(p in text for p in (
        "tim quan", "quan ca phe", "dia diem", "google maps", "nha hang", "cong vien gan")))
    web = "web_search" in options.tools or (not negated and any(p in text for p in (
        "moi nhat", "tin moi", "tra cuu", "tim tren web", "web search", "cap nhat", "thoi tiet")))
    # Area is always explicit; never infer from timezone, journal, profile or GPS.
    area = options.area
    if maps and not area:
        match = re.search(r"\b(?:ở|tại|\bo\b|\btai\b)\s+(.{2,120})$", prompt, re.I)
        if match and not any(p in folded(match[1]) for p in ("gan minh", "gan nha", "gan toi")):
            area = match[1].strip().rstrip("?.!")
    return SearchIntent(safe_query(prompt), web, maps, area)


def clarification_area(prompt: str) -> str | None:
    """Accept a public city, optionally preceded by a numbered district, as an area reply.

    Never interpret arbitrary prose, personal disclosures or street/home addresses as a
    continuation. The original current-turn area is used only after this closed check.
    """
    if not 2 <= len(prompt) <= 120:
        return None
    value = re.sub(r"[.,]+", " ", folded(prompt)).strip()
    value = re.sub(r"^(?:o|tai)\s+", "", value)
    value = re.sub(r"^(?:quan|huyen|phuong|q|p)\s*\d{1,2}\s+", "", value)
    value = " ".join(value.split())
    if any(re.fullmatch(pattern, value) for pattern, _ in PLACES):
        return prompt.strip()
    return None


def search_ready(settings, provider: str) -> bool:
    common = (settings.ai_accounting_enabled and settings.ai_daily_budget_usd > 0
              and 0 < settings.ai_search_daily_budget_usd <= settings.ai_daily_budget_usd
              and settings.openai_model == "gpt-6-luna" and settings.ai_multi_message_enabled)
    if provider == "openai_web":
        return bool(common and settings.ai_web_search_enabled and settings.ai_web_search_pricing_version
                    and settings.ai_web_search_token_bound_verified)
    return bool(common and settings.ai_maps_search_enabled and settings.maps_search_worker_enabled
                and settings.apify_api_token.get_secret_value() and settings.apify_maps_actor_build
                and settings.apify_maps_pricing_version and settings.apify_maps_charge_bound_verified)
