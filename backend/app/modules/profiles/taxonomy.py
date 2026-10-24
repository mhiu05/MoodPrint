"""Versioned product taxonomy; no fixtures, personal data or model inference."""

from app.contracts import DTO


class TaxonomyDTO(DTO):
    version: str = "v1"
    interests: dict[str, str]
    values: dict[str, str]
    styles: dict[str, str]
    goals: dict[str, str]
    languages: dict[str, str]


TAXONOMY = TaxonomyDTO(
    interests={
        "reading": "Đọc sách",
        "music": "Âm nhạc",
        "walking": "Đi bộ",
        "cooking": "Nấu ăn",
        "english": "Học tiếng Anh",
        "photography": "Chụp ảnh",
        "puzzles": "Giải đố",
    },
    values={
        "respect": "Tôn trọng",
        "sincerity": "Chân thành",
        "curiosity": "Ham học hỏi",
        "kindness": "Tử tế",
    },
    styles={"balanced": "Cân bằng", "listening": "Thích lắng nghe", "direct": "Thích nói thẳng"},
    goals={
        "shared-interests": "Tìm bạn cùng sở thích / cùng học",
        "friendship": "Tìm bạn trò chuyện",
    },
    languages={"vi": "Tiếng Việt", "en": "Tiếng Anh"},
)
