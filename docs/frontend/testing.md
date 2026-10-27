# Các lớp kiểm thử frontend

## Lệnh và môi trường

Từ `frontend/`:

```powershell
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
npm.cmd run test:e2e
```

Không có script `lint` trong package hiện tại. Typecheck/build và production guard không phải ESLint. Vitest chỉ thu thập `src/**/*.test.ts`; browser specs chạy qua Playwright.

| Config | Nguồn dữ liệu | Server / mục đích |
| --- | --- | --- |
| `playwright.config.ts` | `page.route` fixtures trong tests | Vite 5173; có thể reuse server |
| `playwright.owned.config.ts` | Cùng fixture specs | Vite riêng 5190, proxy 59998 không dùng, không reuse server |
| `playwright.fullstack.config.ts` | FastAPI/PostgreSQL thật + synthetic auth/SDK fake model | Harness dùng 8002/5174 |
| `playwright.supabase.config.ts` | Tích hợp Supabase qua harness riêng | Opt-in, đọc runner trước khi chạy |
| `playwright.provider.config.ts`, `playwright.live.config.ts` | Có thể gọi provider thực | Cần target/credentials/budget được phép |
| `playwright.visual.config.ts` | Screenshot workflow riêng | Xem spec/cấu hình trước khi cập nhật baseline |

Không suy ra mọi file trong `tests/e2e/` đều được chạy: `testMatch` cấu hình mặc định liệt kê spec cụ thể. Dùng `--list` để xem collection hiện tại.

## Chạy browser suite có server sở hữu riêng

```powershell
npx.cmd playwright test --config playwright.owned.config.ts --reporter=list --output "$env:TEMP\moodprint-browser-results"
```

Cách này tránh dùng Vite 5173 của người phát triển. Thư mục output nằm ngoài repository, không commit trace/screenshot có thể chứa thông tin phiên. Chromium phải có sẵn; nếu cần cài, dùng `npx.cmd playwright install chromium` hoặc đặt `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` theo config.

## Fullstack

Từ root, khởi động DB local rồi đặt `TEST_DATABASE_URL` đến DB riêng hậu tố `_test`; từ backend:

```powershell
uv run --locked python ../scripts/test_fullstack.py
```

Runner kiểm tra ports 8002/5174, tạo process riêng và dừng process do nó tạo. `tests.e2e_server` chỉ dùng cho automated tests, không phải production bypass. Không chạy song song pytest và fullstack trên cùng database vì fixture có reset schema. Không sửa frontend khi fullstack đang chạy vì HMR có thể tải lại browser.

## Coverage hiện tại

- Unit: HTTP intent retry, SSE validation, audio encode, profile rules, PII advisory, activity view/clock, motion policy và production imports.
- Fixture E2E: auth/recovery, consent/states, AI history/error handling, discovery/social, activity dock/timer, admin, responsive/a11y/motion.
- Fullstack: HTTP thật, isolation hai user, privacy/revocation, matching v2, hoạt động chung, moderation, persistent chat và mood evidence.

Scorer của fullstack mặc định là v1; riêng nhánh v2 của matching spec cần `E2E_MATCHING_SCORER=v2` trong môi trường harness. Xem lệnh và giới hạn trong [matching evaluation](../matching/evaluation.md).

E2E fixture không chứng minh backend persistence; synthetic fullstack không chứng minh live provider; unit test không chứng minh browser permission micro trên máy thật. Báo rõ skipped, warning và phần không chạy.
