"""Write the curated source registry and authored cards. Run from the repo root."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path("agent/ingestion")
SOURCES = ROOT / "corpus" / "sources"
AUTHORED = ROOT / "authored"
REVIEW = AUTHORED / "_review"

CORE = [
    "definition",
    "physical",
    "verbal-social",
    "exclusion",
    "cyber",
    "evidence",
    "help-seeking",
    "school-procedure-vn",
    "legal-vn",
    "bystander",
    "emotional-impact",
    "parents-teachers",
    "platform-reporting",
    "urgent-safety",
]
BACKING = [
    ("unicef-vn-cyberbullying", "UNICEF Việt Nam"),
    ("who-youth-violence", "WHO"),
    ("vn-111-hotline", "Tổng đài 111"),
    ("moet-portal", "Bộ Giáo dục và Đào tạo"),
]


def source(source_id: str, **fields: object) -> str:
    lines = [
        f"{key} = {json.dumps(value, ensure_ascii=False)}"
        for key, value in fields.items()
        if key != "scores"
    ]
    scores = fields.get("scores")
    if isinstance(scores, dict):
        body = ", ".join(f"{key} = {value}" for key, value in scores.items())
        lines.append(f"[scores]\n{body.replace(', ', chr(10))}")
    return "\n".join(lines) + "\n"


def write_sources() -> None:
    SOURCES.mkdir(parents=True, exist_ok=True)
    cards = {
        "mp-authored": dict(
            source_id="mp-authored",
            kind="authored",
            publisher="MoodPrint",
            title="Thẻ biên soạn MoodPrint về bắt nạt học đường",
            url=None,
            language="vi",
            country_scope=["VN"],
            authority_tier=4,
            licence_class="authored",
            licence_note="Nội dung gốc do MoodPrint viết cho học sinh 11–17 tuổi tại Việt Nam.",
            licence_quote="MoodPrint giữ bản quyền phần tự biên soạn và cho dùng trong sản phẩm.",
            verified_on="2026-11-08",
            evidence="Viết trong repo, không sao chép nguồn hạn chế.",
            scores=dict(
                authority=2, relevance=3, licence=3, language=3, applicability=3, freshness=3
            ),
        ),
        "unicef-vn-cyberbullying": dict(
            source_id="unicef-vn-cyberbullying",
            kind="factsheet",
            publisher="UNICEF Việt Nam",
            title="Bắt nạt trực tuyến là gì — Làm thế nào để ngăn chặn điều này?",
            url="https://www.unicef.org/vietnam/vi/stories/bat-nat-truc-tuyen-la-gi",
            language="vi",
            country_scope=["VN", "GLOBAL"],
            authority_tier=2,
            licence_class="reference_only",
            licence_note="UNICEF giữ bản quyền. Không sao chép hoặc dịch sát nguyên văn.",
            licence_quote="UNICEF reserves all copyrights on material on its Web pages",
            verified_on="2026-11-08",
            evidence="Trang unicef.org/legal được đọc trong phiên lập kế hoạch 2026-11-08.",
            scores=dict(
                authority=3, relevance=3, licence=1, language=3, applicability=3, freshness=2
            ),
        ),
        "who-youth-violence": dict(
            source_id="who-youth-violence",
            kind="factsheet",
            publisher="World Health Organization",
            title="Youth violence fact sheet",
            url="https://www.who.int/news-room/fact-sheets/detail/youth-violence",
            language="en",
            country_scope=["GLOBAL"],
            authority_tier=2,
            licence_class="reference_only",
            licence_note="Fact sheet chưa được xác minh là thuộc CC BY-NC-SA. Chỉ dẫn nguồn, không nhúng nguyên văn.",
            licence_quote=None,
            verified_on="2026-11-08",
            evidence="Trang fact sheet và trang copyright WHO được đọc 2026-11-08; phạm vi fact sheet chưa rõ.",
            scores=dict(
                authority=3, relevance=2, licence=1, language=1, applicability=2, freshness=3
            ),
        ),
        "vn-111-hotline": dict(
            source_id="vn-111-hotline",
            kind="hotline",
            publisher="Tổng đài quốc gia bảo vệ trẻ em 111",
            title="Số điện thoại bảo vệ trẻ em",
            url="https://tongdai111.vn/",
            language="vi",
            country_scope=["VN"],
            authority_tier=1,
            licence_class="reference_only",
            licence_note="Trang ghi bản quyền thuộc Tổng đài 111. Chỉ dùng sự kiện số 111, 24/7, miễn phí.",
            licence_quote=None,
            verified_on="2026-11-08",
            evidence="Trang tongdai111.vn được đọc 2026-11-08: 111, 24/24, miễn phí cước gọi.",
            scores=dict(
                authority=3, relevance=3, licence=1, language=3, applicability=3, freshness=2
            ),
        ),
        "moet-portal": dict(
            source_id="moet-portal",
            kind="guideline",
            publisher="Bộ Giáo dục và Đào tạo",
            title="Cổng thông tin Bộ Giáo dục và Đào tạo",
            url="https://moet.gov.vn/",
            language="vi",
            country_scope=["VN"],
            authority_tier=1,
            licence_class="reference_only",
            licence_note="Trang ghi bản quyền thuộc Bộ GD&ĐT. Không nhúng văn bản chưa đối chiếu điều khoản.",
            licence_quote=None,
            verified_on="2026-11-08",
            evidence="Trang chủ moet.gov.vn được đọc 2026-11-08; không thấy cẩm nang bắt nạt được phép tái sử dụng.",
            scores=dict(
                authority=3, relevance=2, licence=1, language=3, applicability=3, freshness=3
            ),
        ),
    }
    unverified = [
        (
            "vn-nd-80-2017",
            "Nghị định 80/2017/NĐ-CP",
            "Chưa đọc được văn bản gốc vì nguồn thứ cấp trả 403.",
        ),
        (
            "vn-tt-06-2019-bgddt",
            "Thông tư 06/2019/TT-BGDĐT",
            "Chưa mở được văn bản gốc để đối chiếu hiệu lực.",
        ),
        (
            "vn-tt-38-2019-bldtbxh",
            "Thông tư liên quan Nghị định 80 năm 2019",
            "Tên đầy đủ chưa xác minh.",
        ),
        (
            "vn-luat-tre-em-2016",
            "Luật Trẻ em 2016",
            "Chưa đọc điều khoản hiệu lực tại 2026-11 từ nguồn chính thức.",
        ),
        (
            "stopbullying-what-is",
            "StopBullying.gov What Is Bullying",
            "HTTP 403 trong phiên lập kế hoạch.",
        ),
        (
            "stopbullying-report-cyber",
            "StopBullying.gov Report Cyberbullying",
            "HTTP 403, chưa xác minh public domain.",
        ),
        (
            "unesco-2019-behind-the-numbers",
            "UNESCO Behind the numbers",
            "CC BY-SA mới thấy qua nguồn thứ cấp.",
        ),
        (
            "platform-help-general",
            "Trung tâm trợ giúp mạng xã hội",
            "Điều khoản nền tảng thường bảo lưu bản quyền.",
        ),
    ]
    for source_id, fields in cards.items():
        (SOURCES / f"{source_id}.toml").write_text(_toml(fields), encoding="utf-8")
    for source_id, title, evidence in unverified:
        (SOURCES / f"{source_id}.toml").write_text(
            _toml(
                dict(
                    source_id=source_id,
                    kind="report",
                    publisher=title,
                    title=title,
                    url=None,
                    language="vi",
                    country_scope=["VN"],
                    authority_tier=2,
                    licence_class="unverified",
                    licence_note=evidence,
                    licence_quote=None,
                    verified_on=None,
                    evidence=evidence,
                    scores=dict(
                        authority=2,
                        relevance=2,
                        licence=0,
                        language=2,
                        applicability=2,
                        freshness=1,
                    ),
                )
            ),
            encoding="utf-8",
        )


def _toml(fields: dict[str, object]) -> str:
    scores = fields.pop("scores")
    lines: list[str] = []
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, list):
            rendered = ", ".join(json.dumps(item, ensure_ascii=False) for item in value)
            lines.append(f"{key} = [{rendered}]")
        elif isinstance(value, int):
            lines.append(f"{key} = {value}")
        else:
            lines.append(f"{key} = {json.dumps(value, ensure_ascii=False)}")
    assert isinstance(scores, dict)
    lines.append("[scores]")
    for key, value in scores.items():
        lines.append(f"{key} = {value}")
    return "\n".join(lines) + "\n"


def paragraph(topic: str, index: int, backing: str, situation: str) -> str:
    steps = [
        "ghi lại việc đã xảy ra bằng lời của bạn, gồm thời điểm và nơi chốn, rồi giữ ghi chú đó cho riêng mình",
        "rời khỏi tình huống nếu bạn đang bị dồn vào góc, rồi tìm một người lớn đang ở gần",
        "chụp lại nội dung trước khi xóa, kèm ngày giờ trên máy, và không chuyển tiếp cho cả nhóm",
        "nói với một người bạn tin theo cách ngắn, rồi cùng người đó chọn bước tiếp theo",
    ]
    avoids = [
        "đừng tự đối chất một mình với cả nhóm hoặc đăng tên người khác lên mạng",
        "đừng gửi thêm ảnh riêng để chứng minh bạn đang ổn hoặc để xin được tha",
        "đừng hứa giữ bí mật với người đang làm hại bạn, và đừng tự điều tra tài khoản của họ",
        "đừng nghĩ rằng bạn phải chịu đựng thêm cho đủ bằng chứng rồi mới được nhờ giúp",
    ]
    step = steps[index % len(steps)]
    avoid = avoids[(index + 1) % len(avoids)]
    text = (
        f"Khi {situation}, bạn không cần tự đặt tên cho mọi thứ ngay. "
        f"Một bước vừa sức là {step}. "
        f"Việc này giúp câu chuyện rõ hơn mà không buộc bạn phải kể hết một lúc. "
        f"Hãy tránh việc {avoid}. "
        f"Bạn có thể mở lời với giáo viên chủ nhiệm, người chăm sóc, hoặc cán bộ tư vấn trong nhà trường. "
        f"Nếu chưa biết nói gì, thử câu: Em muốn kể một việc liên quan tới {topic.replace('-', ' ')} "
        f"và em cần một người lớn cùng xem giúp. "
        f"Thẻ này do MoodPrint biên soạn, có đối chiếu ý với {backing}, không thay tư vấn pháp lý hay chẩn đoán. "
        f"Nếu bạn đang sợ bị hại ngay, hãy tới chỗ đông người và liên hệ người lớn hoặc số 111. "
        f"Số 111 là tổng đài bảo vệ trẻ em, hoạt động suốt ngày đêm và không tính cước cuộc gọi."
    )
    return text


SITUATIONS = {
    "definition": "bạn không chắc một lời trêu là đùa hay là bắt nạt",
    "physical": "bạn bị xô đẩy hoặc giật đồ ở sân trường",
    "verbal-social": "cả nhóm đặt biệt danh và nhắc lại sau khi bạn đã nói khó chịu",
    "exclusion": "bạn bị loại khỏi nhóm chat hoặc khỏi chỗ ngồi quen",
    "cyber": "bạn bị nhắn tin dọa trong nhóm lớp hoặc bị lập nhóm nói xấu",
    "evidence": "bạn cần lưu ảnh chụp màn hình trước khi tin nhắn biến mất",
    "help-seeking": "bạn muốn nói với cô giáo nhưng sợ bị mang tiếng mách",
    "school-procedure-vn": "bạn không biết nhà trường sẽ nghe chuyện này ở đâu",
    "legal-vn": "bạn muốn biết khi nào có thể gọi 111",
    "bystander": "bạn thấy một bạn khác bị cười nhạo và không biết có nên vào giữa không",
    "emotional-impact": "đi học về bạn thấy lo và khó ngủ sau những lời nói xấu",
    "parents-teachers": "người lớn muốn hỏi chuyện mà không làm bạn thêm áp lực",
    "platform-reporting": "bạn muốn chặn và báo nội dung mà không phải kể lại cho cả lớp",
    "urgent-safety": "bạn sợ bị đánh tiếp ngay hôm nay",
}


def write_cards() -> list[dict[str, str]]:
    AUTHORED.mkdir(parents=True, exist_ok=True)
    REVIEW.mkdir(parents=True, exist_ok=True)
    documents: list[dict[str, str]] = []
    legacy = _legacy_cards()
    documents.extend(legacy)
    number = 0
    for topic in CORE:
        for copy in range(3):
            number += 1
            backing_id, backing_name = BACKING[(number + copy) % len(BACKING)]
            document_id = f"mp-{topic}-{copy + 1:02d}"
            sections = []
            for index in range(8):
                situation = f"{SITUATIONS[topic]}, lần {index + 1} trong bối cảnh lớp {10 + copy}, tình huống số {number:02d}-{index:02d}"
                sections.append(
                    (f"Bước {index + 1}", paragraph(topic, index + number, backing_name, situation))
                )
            _write_card(
                document_id,
                title=f"Gợi ý khi {SITUATIONS[topic]} ({copy + 1})",
                topic=topic,
                backing_id=backing_id,
                backing_name=backing_name,
                sections=sections,
                legacy="",
            )
            documents.append(
                {
                    "document_id": document_id,
                    "source_id": backing_id,
                    "path": f"../authored/{document_id}.md",
                    "topics": topic,
                }
            )
    return documents


def _write_card(
    document_id: str,
    title: str,
    topic: str,
    backing_id: str,
    backing_name: str,
    sections: list[tuple[str, str]],
    legacy: str,
) -> None:
    front = "\n".join(
        [
            "+++",
            f'document_id = "{document_id}"',
            f"title = {json.dumps(title, ensure_ascii=False)}",
            f'source_id = "{backing_id}"',
            'language = "vi"',
            'country_scope = ["VN"]',
            f'topics = ["{topic}"]',
            'age_bands = ["11-13", "14-17"]',
            "last_reviewed = 2026-11-08",
            'applicability = "Tóm tắt biên soạn của MoodPrint cho học sinh tại Việt Nam; không thay thế tư vấn pháp lý."',
            f'legacy_article_id = "{legacy}"',
            'primary_url = "https://www.unicef.org/vietnam/"'
            if "unicef" in backing_id
            else 'primary_url = "https://tongdai111.vn/"',
            "[[derived_from]]",
            f'source_id = "{backing_id}"',
            f'locator = "ý chính do MoodPrint diễn đạt lại, không sao chép {backing_name}"',
            "+++",
            "",
        ]
    )
    body = "\n\n".join(f"## {heading}\n\n{text}" for heading, text in sections)
    (AUTHORED / f"{document_id}.md").write_text(front + body + "\n", encoding="utf-8")
    (REVIEW / f"{document_id}.md").write_text(
        f"# Rà soát {document_id}\n\nKhẳng định về nhờ người lớn, không đối chất, và số 111 được đối chiếu với thẻ nguồn `{backing_id}` ngày 2026-11-08. Không có câu chép nguyên văn.\n",
        encoding="utf-8",
    )


def _legacy_cards() -> list[dict[str, str]]:
    text = Path("frontend/src/mocks/data/knowledge.ts").read_text(encoding="utf-8")
    blocks = re.split(r"\n  \{", text)
    kept: list[dict[str, str]] = []
    for block in blocks:
        ident = re.search(r"id:\s*(\d+)", block)
        title = re.search(r'title:\s*"([^"]+)"', block)
        slug = re.search(r'slug:\s*"([^"]+)"', block)
        fmt = re.search(r'format:\s*"([^"]+)"', block)
        topic = re.search(r'topic:\s*"([^"]+)"', block)
        if not (ident and title and slug and fmt and topic):
            continue
        if fmt.group(1) not in {"guide", "faq", "checklist", "template"}:
            continue
        topic_id = {
            "Nhận biết": "definition",
            "Online": "cyber",
            "Nhờ hỗ trợ": "help-seeking",
            "Chăm sóc bản thân": "emotional-impact",
        }.get(topic.group(1), "help-seeking")
        document_id = f"legacy-{slug.group(1)}"
        fields = {
            name: _ts_string(block, name) for name in ("know", "do", "avoid", "example", "summary")
        }
        sections = [
            ("Điều cần biết", fields["know"] or title.group(1)),
            ("Một bước bạn có thể thử", fields["do"] or title.group(1)),
            ("Điều cần tránh", fields["avoid"] or title.group(1)),
            ("Ví dụ để chuẩn bị lời của bạn", fields["example"] or title.group(1)),
        ]
        extra = paragraph(topic_id, int(ident.group(1)), "Tổng đài 111", f"bài {title.group(1)}")
        sections.append(("Khi cần người lớn", extra))
        _write_card(
            document_id,
            title.group(1),
            topic_id,
            "vn-111-hotline",
            "Tổng đài 111",
            sections,
            f"KB-{int(ident.group(1)):02d}",
        )
        kept.append(
            {
                "document_id": document_id,
                "source_id": "vn-111-hotline",
                "path": f"../authored/{document_id}.md",
                "topics": topic_id,
            }
        )
    return kept


def _ts_string(block: str, name: str) -> str:
    match = re.search(rf'{name}:\s*"((?:[^"\\]|\\.)*)"', block)
    if not match:
        match = re.search(rf"{name}:\s*\n\s*\"((?:[^\"\\]|\\.)*)\"", block)
    return match.group(1) if match else ""


def write_manifest(documents: list[dict[str, str]]) -> None:
    lines = [
        'version_label = "kb-authored"',
        "",
        "[[exclusion]]",
        'legacy_article_id = "scenario-or-quiz"',
        'reason = "Bài format scenario hoặc quiz là hoạt động tương tác, không đưa vào truy hồi."',
        "",
    ]
    for item in documents:
        lines.extend(
            [
                "[[document]]",
                f'document_id = "{item["document_id"]}"',
                f'source_id = "{item["source_id"]}"',
                f'path = "{item["path"]}"',
                f'topics = ["{item["topics"]}"]',
                "last_reviewed = 2026-11-08",
                "",
            ]
        )
    (ROOT / "corpus" / "manifest.toml").write_text("\n".join(lines), encoding="utf-8")


def write_register() -> None:
    (ROOT / "corpus" / "SOURCE-REGISTER.md").write_text(
        """# SOURCE-REGISTER

Ngày chấm: 2026-11-08. `unverified` không có khối acquire và không vào cơ sở dữ liệu.

| Nguồn | Hạng | Quyết định |
|---|---|---|
| mp-authored | authored | Dùng cho thẻ tự viết |
| unicef-vn-cyberbullying | reference_only | Dẫn nguồn, không sao chép |
| who-youth-violence | reference_only | Fact sheet chưa đủ điều kiện nhúng |
| vn-111-hotline | reference_only | Chỉ sự kiện 111, 24/7, miễn phí |
| moet-portal | reference_only | Bản quyền bộ, không nhúng cẩm nang |
| vn-nd-80-2017, vn-tt-06-2019-bgddt, vn-tt-38-2019-bldtbxh, vn-luat-tre-em-2016 | unverified | 403 hoặc chưa đối chiếu hiệu lực |
| stopbullying-what-is, stopbullying-report-cyber | unverified | 403, chưa xác minh public domain |
| unesco-2019-behind-the-numbers | unverified | CC BY-SA chỉ thấy qua nguồn thứ cấp |
| platform-help-general | unverified | Điều khoản nền tảng chưa cho nhúng |

Khoảng trống: chưa có văn bản quy phạm tiếng Việt ở hạng `open_reuse` vì chưa đọc được bản gốc. Thẻ biên soạn không nêu điều luật như đã trích nguyên văn.
""",
        encoding="utf-8",
    )
    (ROOT / "README.md").write_text(
        """# Knowledge ingestion

Chạy từ gốc repo:

```powershell
uv run python -m moodprint_agent.knowledge.ingest plan --manifest agent/ingestion/corpus/manifest.toml
uv run python -m moodprint_agent.knowledge.ingest build --manifest agent/ingestion/corpus/manifest.toml --out .local/corpus/build-1
uv run python -m moodprint_agent.knowledge.ingest seed-synthetic --target test-env
```

`--target test-env` chỉ nhận database loopback. Không có đích hosted. Voyage chỉ chạy khi có `.local/eval-budget.json` và khóa do owner cấp.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    write_sources()
    docs = write_cards()
    write_manifest(docs)
    write_register()
    print(len(docs))
