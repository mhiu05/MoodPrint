# WS-08 — Luyện nói

Ưu tiên P2. Độ phức tạp L: provider mới, audio trên mobile, role-play cần an toàn riêng. Nhánh `mhiu05/feat-refactor-ws08-voice`. Thiết kế ở [08](../08-speaking-practice-design.md).

## 1. Mục tiêu và giá trị

Em tập nói trước khi nói thật, để bước tới người lớn thật bớt khó.

## 2. Hiện trạng đã xác minh

STT hoàn chỉnh cho WAV 30 giây. Không có TTS, không có phiên. OpenAI TTS tắt 06/01/2027.

## 3. Khoảng trống

Abstraction, TTS, phiên, role-play, tổng kết, ledger, UI giữ để nói.

## 4. Kiến trúc đề xuất

Theo [08](../08-speaking-practice-design.md). Mỗi lượt là một lượt `troly` trên hội thoại tạm, `run.practice` mang `mode`, `scenario_id`. `tools_for` trả rỗng trong phiên luyện nói.

## 5. Phạm vi

Trong: ba chế độ, push-to-talk, transcript sửa được, tổng kết, lưu có xác nhận. Ngoài: realtime, lưu audio.

## 6. File và symbol bị ảnh hưởng

`modules/voice/routes.py`, `service.py` (bọc sau protocol, thêm `language`, `prompt`); `main.py` (`app.state.transcriber`); `core/config.py`; `ai/accounting.py` (`budget_liability`); `ai/assistant/turn.py`, `prompt.py`.

## 7. File mới

`backend/app/modules/practice/{__init__,models,schemas,service,routes,providers,scenarios,summary}.py`; `practice/scenarios/*.json`; `frontend/src/features/school/practice/{PracticeHome,PracticeRoom,HoldToTalk,AudioPlayback}.tsx`; `backend/evals/practice/`.

## 8. API contract

Xem [08 §8](../08-speaking-practice-design.md#8-api).

```python
class PracticeStart(DTO):
    mode: Literal["retell", "trusted_adult", "call_111"]
    scenario_id: str = Field(max_length=32)
    difficulty: Literal["gentle", "challenging"] = "gentle"

class PracticeTurn(DTO):
    text: MessageText
    client_message_id: UUID
    expected_version: int = Field(ge=1)

class SpeechRequest(DTO):
    message_id: UUID
```

Setting mới: `tts_provider`, `tts_api_key`, `tts_voice`, `practice_global_concurrency`, `practice_max_turns`, `practice_tts_max_chars`.

## 9. Dữ liệu và migration

`practice_sessions`, `speech_usage` trong `0035_support_practice`.

## 10. Task

| ID | Ưu tiên | Phụ thuộc | Thay đổi, ở đâu | Hành vi mong đợi | Lệnh test | Pass / fail |
| --- | --- | --- | --- | --- | --- | --- |
| WS-08-T01 | P1 | WS-04 | `providers.py`, bọc `OpenAITranscriber`; thêm `language="vi"`, `prompt` | Hành vi profile default không đổi; `STT_MODEL` hỗ trợ `prompt` | `pytest -q tests/test_voice*.py tests/test_practice_providers.py` | Pass |
| WS-08-T02 | P1 | T01 | Migration phần practice; ORM; `speech_liability` vào `budget_liability` | Ledger fail closed khi không biết giá; không ghi `ai_usage` | `pytest -q tests/test_speech_usage.py tests/test_accounting*.py` | Pass |
| WS-08-T03 | P1 | T02 | Routes phiên; hội thoại tạm; giới hạn 20 lượt, 20 phút | Người khác 404; hết hạn tự đóng | `pytest -q tests/test_practice_sessions.py` | Pass |
| WS-08-T04 | P1 | T03 | `scenarios`, prompt theo chế độ, không tool ghi | Luôn công bố AI; `call_111` không xưng tổng đài viên | `pytest -q tests/test_practice_prompt.py` | Pass |
| WS-08-T05 | P1 | T03, WS-03 | Turn đi qua safety; đỏ dừng phiên | Template hiện; phiên `ended`; không gọi TTS | `pytest -q tests/test_practice_safety.py` | Pass |
| WS-08-T06 | P1 | T02, OD-04 | `FptSpeechSynthesizer` (hoặc provider được chọn), `FakeSynthesizer`, route speech | Chỉ đọc message của chính run; ≤ 400 ký tự; lỗi 503, UI hiện chữ; không lưu | `pytest -q tests/test_practice_speech.py` | Pass: client không truyền được text |
| WS-08-T07 | P2 | T04 | `challenging`: danh sách phản ứng duyệt sẵn, tối đa một lần; tắt khi nhãn nhạy cảm | Em tự bật; có câu gợi ý đáp | `pytest -q tests/test_practice_challenging.py` | Pass |
| WS-08-T08 | P1 | T04 | `summary.py`, proposal `practice_summary_save` | Lưu cần xác nhận | `pytest -q tests/test_practice_summary.py` | Pass |
| WS-08-T09 | P1 | T03 | Semaphore 5, 429 `PRACTICE_BUSY` | Quá tải không làm hỏng chat | `pytest -q tests/test_practice_concurrency.py` | Pass |
| WS-08-T10 | P1 | T03 | UI `HoldToTalk`, `PracticeRoom`, dùng `encodeWav`, `pcm-worklet.js` | Pointer, Space, chế độ chạm; sóng âm tôn trọng reduced motion; nhập chữ luôn có; thu lại, dừng, thoát | `npm test`; `npx playwright test tests/e2e/school-practice.spec.ts` | Pass với mic giả của Chromium |
| WS-08-T11 | P2 | T04 | `evals/practice`, 20 kịch bản | Báo cáo | `python -m evals.practice --offline <file>` | Pass runner |
| WS-08-T12 | P1 | T10, OD-04 | Bake-off theo [08 §6](../08-speaking-practice-design.md#6-nhà-cung-cấp) | Báo cáo WER, độ trễ, nghe thử | Người thực hiện | **Cần người** |

## 11. An toàn và bảo mật

Xem [08 §9](../08-speaking-practice-design.md#9-an-toàn). Không thu giọng trẻ em thật để test.

## 12. Test và dataset

Mic giả: `--use-fake-device-for-media-stream`, `--use-file-for-fake-audio-capture`.

## 13. Acceptance criteria

Ba chế độ chạy; TTS lỗi vẫn dùng được; không có audio trên server.

## 14. Phụ thuộc và blocker

OD-04 cần API key. iOS Safari có quy tắc phát audio theo tương tác; nút phát phải do người dùng bấm.

## 15. Rollback

`TTS_PROVIDER=none`; hoặc ẩn tab Luyện nói.

## 16. Definition of Done

G3 đạt, hoặc đạt phần chữ và ghi rõ TTS đang chờ OD-04.

## 17. Ghi chú cho Grok

Không dùng `gpt-4o-mini-tts`, kể cả tạm thời. Không dùng Realtime làm TTS mà không báo owner: đó là model sinh giọng, không đảm bảo đọc nguyên văn. `api-reference.md` cần cập nhật khi thêm route.
