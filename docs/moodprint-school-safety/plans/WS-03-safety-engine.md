# WS-03 — Safety engine

Ưu tiên P0. Độ phức tạp L: 8 nhãn, ngôn ngữ phi chuẩn, eval 300 mẫu, nhánh đỏ trước mọi cổng. Nhánh `mhiu05/feat-refactor-ws03-safety`. Thiết kế chuẩn ở [06](../06-ai-orchestration-and-safety.md).

## 1. Mục tiêu và giá trị

Học sinh nói ra tín hiệu nguy hiểm thì nhận ngay hướng dẫn và số gọi, kể cả khi AI hỏng.

## 2. Hiện trạng đã xác minh

Xem [01 §4](../01-codebase-audit.md#4-lỗ-hổng-an-toàn-ưu-tiên-số-1-o4). Không có template trong chat. Không có số khẩn cấp trong code.

## 3. Khoảng trống

Toàn bộ.

## 4. Kiến trúc đề xuất

`backend/app/safety/`. Tầng 0–2 thuần Python, không mạng, không import `agents`. Nhánh đỏ nằm trong `send`, trước `available_for`, `admission`, quota guest. `distress_screen` giữ nguyên byte cho profile default.

## 5. Phạm vi

Trong: engine, template, sự kiện, nhánh đỏ, classifier, postcheck, rule phía client, eval. Ngoài: áp cho bot cũ (OD-13).

## 6. File và symbol bị ảnh hưởng

`ai/chat_routes.py` (`send`, `create_conversation`, `persistent_events`); `ai/schemas.py` (`Card`, `EmergencyCard`); `ai/persistence.py`; `ai/provider.py`; `frontend/src/api/stream.ts` (`validCards`).

## 7. File mới

`backend/app/safety/{__init__,normalize,rules,context,classifier,decision,postcheck,templates,models,recorder}.py`; `safety/rules/vi-v1.json`; `safety/templates/vi-v1.json`; `safety/golden-vectors.json`; `ai/assistant/admission.py`; `backend/alembic/versions/0031_safety_events.py`; `backend/evals/safety/{__init__,__main__,report}.py`, `dataset.jsonl`; `scripts/export_safety_rules.py`; `frontend/src/features/school/safety/{rules.generated.json,screen.ts,screen.test.ts}`.

## 8. API contract

```python
SafetyLabel = Literal["physical_threat_immediate", "weapon", "severe_injury",
    "sexual_abuse_exploitation", "extortion_coercion", "self_harm",
    "adult_perpetrator", "retaliation_risk"]
SafetyLevel = Literal["green", "yellow", "red"]

@dataclass(frozen=True)
class RuleHit:
    rule_id: str
    label: SafetyLabel
    level: SafetyLevel
    modifier: Literal["none", "negated", "hypothetical", "quoted", "third_party"]

@dataclass(frozen=True)
class SafetyDecision:
    level: SafetyLevel
    labels: tuple[SafetyLabel, ...]
    tier: Literal["rule", "context", "classifier", "timeout", "none"]
    rule_pack_version: str
    skip_model: bool            # True với sexual_abuse_exploitation
    template_group: Literal["violence", "sexual", "self_harm", "extortion"] | None
```

| Hàm | Chữ ký |
| --- | --- |
| `normalize_text` | `(text: str) -> NormalizedText` |
| `screen` | `(n: NormalizedText) -> list[RuleHit]` |
| `screen_context` | `(recent: Sequence[NormalizedText], current: NormalizedText) -> list[RuleHit]` |
| `decide` | `(hits, assessment: SafetyAssessment \| None, outcome: ClassifierOutcome) -> SafetyDecision` |
| `template_for` | `(group, age_group) -> SafetyTemplate` |
| `postcheck` | `(texts: Sequence[str], ctx: PostcheckContext) -> PostCheckResult` |
| `record_event` | `(db, user_id, run_id, request_id, surface, decision) -> None` |

Không có route mới. `final` của SSE mang `EmergencyCard` trong `cards`.

## 9. Dữ liệu và migration

`0031_safety_events`, xem [05 §3](../05-data-model-and-migrations.md#3-safety).

## 10. Task

| ID | Ưu tiên | Phụ thuộc | Thay đổi, ở đâu | Hành vi mong đợi | Lệnh test | Pass / fail |
| --- | --- | --- | --- | --- | --- | --- |
| WS-03-T01 | P0 | WS-02 | `normalize.py` | NFC, lowercase, bỏ dấu, `đ→d`, teencode, ghép ký tự chèn, rút lặp; ≤ 5 ms cho 2000 ký tự | `pytest -q tests/test_safety_normalize.py` | Pass: `m.u.ố.n c.h.ế.t → muon chet`, `ko → khong`, `chetttt → chet`. Fail: backtracking chậm |
| WS-03-T02 | P0 | T01 | `rules.py`, `vi-v1.json` đủ 8 nhãn | 15 câu ở [01 §4](../01-codebase-audit.md#4-lỗ-hổng-an-toàn-ưu-tiên-số-1-o4) cho đúng mức. "nó bảo mai mang dao đến" đỏ. "tao không định tự tử đâu" không đỏ. "bị đánh hội đồng trong game" không đỏ | `pytest -q tests/test_safety_rules.py` | Pass: bảng 15 câu đúng |
| WS-03-T03 | P0 | T02 | `context.py` | "nó dọa ngày mai" + "mang dao" ở hai tin → đỏ. Tin của AI không tính. Quá 30 phút không ghép | `pytest -q tests/test_safety_context.py` | Pass |
| WS-03-T04 | P0 | T02 | `decision.py` | Lấy mức cao nhất; classifier không hạ được mức rule; `skip_model` đúng; timeout → vàng | `pytest -q tests/test_safety_decision.py` | Pass: bảng trạng thái đầy đủ |
| WS-03-T05 | P0 | T04 | `templates.py`, `vi-v1.json`, `EmergencyCard` vào `Card`; `validCards`, TS | Mọi cặp nhóm × tuổi có template; số chỉ thuộc allowlist; `troly` output không tạo được card này | `pytest -q tests/test_safety_templates.py`; `npm test` | Pass |
| WS-03-T06 | P0 | T04 | Migration 0031, `models.py`, `recorder.py`, retention 90 ngày, `docs/supabase/schema.md` | Hàng không có nội dung; test quét mọi cột | `pytest -q tests/test_safety_events.py` | Pass: văn bản nhập không xuất hiện trong bảng và log |
| WS-03-T07 | P0 | T05, T06 | `assistant/admission.py::screen_turn`, `emergency_accept`; `send` gọi ngay sau kiểm tra `previous`, trước `available_for`. `create_conversation` bỏ cổng `available_for` cho `troly`. Hỗ trợ cả hội thoại lưu và tạm | Đỏ: 202, run `completed`, tin người dùng và template được lưu, SSE đủ `final` `completed`, không `ai_usage`, không gọi provider. Hoạt động khi `AI_ENABLED=false`, khi hết ngân sách, khi hết lượt ngày | `pytest -q tests/test_safety_red_path.py` | Pass: provider giả bị gọi 0 lần ở mọi tổ hợp lỗi. Replay idempotent |
| WS-03-T08 | P0 | T07 | `classifier.py` qua `provider.run_once`, cắt input 8.000 token ước lượng, `reasoning.effort` thấp, `max_tokens=400`; `BOUNDED_CALL_RESERVATION_NANO`, tham số `reservation_nano` trong `reserve_accounting` | Timeout → vàng trong ≤ 3 giây; lỗi → vàng; không gọi khi `skip_model`; dùng `settings.openai_model` | `pytest -q tests/test_safety_classifier.py tests/test_accounting*.py` | Pass: `budget_liability` không fail closed |
| WS-03-T09 | P0 | T05 | `postcheck.py` | Mỗi dòng bảng postcheck có ≥ 5 mẫu xấu bị chặn, ≥ 3 mẫu lành không bị chặn | `pytest -q tests/test_safety_postcheck.py` | Pass |
| WS-03-T10 | P1 | T02 | `scripts/export_safety_rules.py`, `screen.ts`, `golden-vectors.json`, bước drift trong `verify.yml` | Python và TS cho cùng kết quả trên golden vectors | `python ../scripts/export_safety_rules.py`; `npm test` | Pass: drift = 0 |
| WS-03-T11 | P0 | T02 | `evals/safety/dataset.jsonl` ≥ 300 mẫu, runner `--offline` | Báo cáo theo nhãn, nhóm tuổi, không nội dung; test CI giữ recall tầng 0–2 không giảm so với baseline ghi trong repo | `python -m evals.safety --offline` | Pass: chạy được, có số |
| WS-03-T12 | P0 | T08, T11, OD-11 | `--live --confirm-live --max-usd`, chạy holdout | Đạt ngưỡng OD-08 | Lệnh live | Pass: đạt. Fail: sửa rule trên `dev`, không chạm `holdout` |
| WS-03-T13 | P0 | T07 | Test log: bắt mọi record logging trong nhánh đỏ và lượt thường | Không record nào chứa nội dung | `pytest -q tests/test_safety_logging.py` | Pass |

## 11. An toàn và bảo mật

- Template là dữ liệu tĩnh, không qua model.
- Rule pack không log văn bản khớp.
- Classifier bọc input là dữ liệu.
- Prompt đối kháng không đổi được tầng 0–2.
- `sexual_abuse_exploitation`: không gửi nội dung tới OpenAI. Có test assert.

## 12. Test và dataset

Xem [10](../10-evaluation-and-quality-gates.md).

## 13. Acceptance criteria

- Nhánh đỏ không phụ thuộc OpenAI, Voyage, ngân sách, quota.
- Bộ eval đạt ngưỡng.
- `distress_screen` không đổi, test cũ pass.

## 14. Phụ thuộc và blocker

WS-02. OD-02 (duyệt template), OD-08, OD-11.

## 15. Rollback

`safety` chỉ chạy cho `troly`; profile default không bị ảnh hưởng. Bảng `safety_events` giữ nguyên.

## 16. Definition of Done

G1 phần an toàn đạt, template có người duyệt.

## 17. Ghi chú cho Grok

Đừng cố đạt recall bằng cách mở rộng regex quá mức: báo động nhầm cao làm mất giá trị. Gián tiếp để classifier lo. Không dùng văn bản thật của trẻ em để làm dataset. `persistent_events` là hàm forward-only: template phải nằm trong `AiMessageRecord.cards` để replay đúng.
