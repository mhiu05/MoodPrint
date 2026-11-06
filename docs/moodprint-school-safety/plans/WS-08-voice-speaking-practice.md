# WS-08 — Luyện nói

Ưu tiên P1. Độ phức tạp L: dùng Realtime làm bộ đọc, audio trên mobile, role-play cần an toàn riêng. Nhánh `mhiu05/feat-refactor-ws08-voice`. Thiết kế ở [08](../08-speaking-practice-design.md).

## 1. Mục tiêu và giá trị

Em tập nói trước khi nói thật, để bước tới người lớn thật bớt khó.

## 2. Hiện trạng đã xác minh

STT hoàn chỉnh cho WAV 30 giây. Không có TTS, không có phiên. `gpt-4o-mini-tts` tắt 06/01/2027. `websockets` có sẵn trong runtime. Owner chốt dùng `OPENAI_API_KEY` cho cả STT và TTS.

## 3. Khoảng trống

Abstraction, TTS, kiểm tra đọc đúng, phiên, role-play, tổng kết, ledger, UI giữ để nói.

## 4. Kiến trúc đề xuất

Theo [08](../08-speaking-practice-design.md). Mỗi lượt là một lượt `troly` trên hội thoại tạm, `run.practice` mang `mode`, `scenario_id`. `tools_for` trả rỗng trong phiên luyện nói.

## 5. Phạm vi

Trong: ba chế độ cho cả khách và tài khoản trình bày, push-to-talk, transcript sửa được, tổng kết, lưu có xác nhận, ca SC-09. Ngoài: GPT-Live, Realtime speech-to-speech, lưu audio.

## 6. File và symbol bị ảnh hưởng

`modules/voice/routes.py`, `service.py` (bọc sau protocol, thêm `language`, `prompt`); `main.py` (`app.state.transcriber`); `core/config.py`; `ai/accounting.py` (`budget_liability`); `ai/assistant/turn.py`, `prompt.py`.

## 7. File mới

`backend/app/modules/practice/{__init__,models,schemas,service,routes,providers,verbatim,scenarios,summary}.py`; `practice/scenarios/*.json`; `frontend/src/features/school/practice/{PracticeHome,PracticeRoom,HoldToTalk,Waveform,AudioPlayback}.tsx`; `backend/evals/practice/`.

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

Setting mới: `tts_provider` (`none`, `openai_realtime`), `tts_model` (mặc định `gpt-realtime-2.1-mini`), `tts_voice` (mặc định `marin`, TO_VERIFY với Realtime), `practice_global_concurrency`, `practice_max_turns`, `practice_tts_max_chars`. Không có key mới: dùng `openai_api_key`.

## 9. Dữ liệu và migration

`practice_sessions`, `speech_usage` trong `0035_support_practice`.

## 10. Task

| ID | Ưu tiên | Phụ thuộc | Thay đổi, ở đâu | Hành vi mong đợi | Lệnh test | Pass / fail |
| --- | --- | --- | --- | --- | --- | --- |
| WS-08-T01 | P1 | WS-04 | `providers.py`, bọc `OpenAITranscriber`; thêm `language="vi"`, `prompt` | Hành vi profile default không đổi | `pytest -q tests/test_voice*.py tests/test_practice_providers.py` | Pass |
| WS-08-T02 | P1 | T01 | Migration phần practice; ORM; `speech_liability` vào `budget_liability` | Ledger fail closed khi không biết giá; không ghi `ai_usage` | `pytest -q tests/test_speech_usage.py tests/test_accounting*.py` | Pass |
| WS-08-T03 | P1 | T02 | Routes phiên; hội thoại tạm; giới hạn 20 lượt, 20 phút | Người khác 404; hết hạn tự đóng | `pytest -q tests/test_practice_sessions.py` | Pass |
| WS-08-T04 | P1 | T03 | `scenarios`, prompt theo chế độ, không tool ghi | Luôn công bố AI; `call_111` không xưng tổng đài viên | `pytest -q tests/test_practice_prompt.py` | Pass |
| WS-08-T05 | P1 | T03, WS-03 | Turn đi qua safety; đỏ dừng phiên | Template hiện; phiên `ended`; không gọi TTS | `pytest -q tests/test_practice_safety.py` | Pass |
| WS-08-T06 | P1 | T02 | `verbatim.py`: `verbatim_ok(expected, transcript)` | Khớp sau chuẩn hóa ≥ 0,92; thiếu chữ số là fail; câu thêm lời ngoài văn bản là fail; postcheck trên transcript | `pytest -q tests/test_practice_verbatim.py` | Pass: bảng mẫu đúng và lệch |
| WS-08-T07 | P1 | T06 | `OpenAIRealtimeSynthesizer` qua `AsyncOpenAI.realtime.connect`, đúng các bước ở [08 §6](../08-speaking-practice-design.md#cách-làm-realtime-thành-bộ-đọc); `FakeSynthesizer` | Timeout 10 giây; giới hạn 2 MB; đóng WebSocket mọi nhánh; ghi `speech_usage` từ `response.done` | `pytest -q tests/test_practice_tts.py` với server WS giả | Pass |
| WS-08-T08 | P1 | T07 | Route speech | Chỉ đọc message của chính run; ≤ 400 ký tự; `verbatim_ok` sai → 503 `SPEECH_UNAVAILABLE`, audio bị bỏ; không lưu | `pytest -q tests/test_practice_speech.py` | Pass: client không truyền được text |
| WS-08-T09 | P1 | T08 | Kiểm tra tự động 20 câu: tỷ lệ `verbatim_ok`, độ trễ, chi phí, kết quả vào `.tmp/tts-trial/` | `verbatim_ok` ≥ 95%; nếu thấp hơn báo owner | `python -m evals.practice.tts_trial --confirm-live --max-usd 0.25` | Pass |
| WS-08-T10 | P1 | T04 | `challenging`: danh sách phản ứng duyệt sẵn, tối đa một lần; tắt khi nhãn nhạy cảm | Em tự bật; có câu gợi ý đáp | `pytest -q tests/test_practice_challenging.py` | Pass |
| WS-08-T11 | P1 | T04 | `summary.py`, proposal `practice_summary_save` | Lưu cần xác nhận | `pytest -q tests/test_practice_summary.py` | Pass |
| WS-08-T12 | P1 | T03 | Semaphore 5, 429 `PRACTICE_BUSY` | Quá tải không làm hỏng chat | `pytest -q tests/test_practice_concurrency.py` | Pass |
| WS-08-T13 | P1 | T03 | UI `HoldToTalk`, `Waveform`, `PracticeRoom`, dùng `encodeWav`, `pcm-worklet.js` | Pointer, Space, chế độ chạm; sóng âm theo RMS thật, tôn trọng reduced motion; orb `listening` 64; nhập chữ luôn có; thu lại, dừng, thoát | `npm test`; `npx playwright test tests/e2e/school-practice.spec.ts` | Pass với mic giả của Chromium |
| WS-08-T14 | P1 | T04 | `evals/practice`: 20 kịch bản, 5 chạy live | Trong trần 0,40 USD | `python -m evals.practice --live --confirm-live --max-usd 0.40 --output <file>` | Pass |

## 11. An toàn và bảo mật

Xem [08 §9](../08-speaking-practice-design.md#9-an-toàn). Không thu giọng trẻ em thật để test. Chỉ gửi lời của AI sang TTS.

## 12. Test và dataset

Mic giả: `--use-fake-device-for-media-stream`, `--use-file-for-fake-audio-capture`.

## 13. Acceptance criteria

Ba chế độ chạy với model thật trên staging; TTS lỗi vẫn dùng được; không có audio trên server; không phát audio chưa qua `verbatim_ok`.

## 14. Phụ thuộc và blocker

WS-02-T12 mở giọng nói cho khách. iOS Safari có quy tắc phát audio theo tương tác; nút phát phải do người dùng bấm. Nếu độ trễ hoặc tiếng Việt của Realtime không đạt, đặt `TTS_PROVIDER=none` và báo owner.

## 15. Rollback

`TTS_PROVIDER=none`; chữ vẫn chạy.

## 16. Definition of Done

G3 đạt.

## 17. Ghi chú cho Grok

Đừng phát audio trước khi kiểm tra, kể cả để giảm độ trễ. Không dùng `agents.voice`: cần `numpy` và không có bước sửa transcript. Sửa `docs/backend/api-reference.md` khi thêm route. Xem mục TO_VERIFY về định dạng PCM ở [08](../08-speaking-practice-design.md).
