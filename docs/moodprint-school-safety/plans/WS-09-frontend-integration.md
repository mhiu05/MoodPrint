# WS-09 — Tích hợp frontend

Ưu tiên P1. Độ phức tạp XL: toàn bộ UI mới, nhiều trạng thái, hai nhóm tuổi. Nhánh `mhiu05/feat-refactor-ws09-ui`. Đặc tả ở [09](../09-ux-and-user-flows.md).

## 1. Mục tiêu và giá trị

Một giao diện yên tĩnh, rõ ràng, luôn có lối thoát và lối gọi giúp.

## 2. Hiện trạng đã xác minh

`RealApp.tsx` 2340 dòng dính bot, group, inbox. Có `ApiClient`, `stream.ts`, `resourceCache`, `useResource` (export từ `RealApp`), `OfflineBanner`, `CitationText`, `Dialog`, `StatePanel`, `ErrorNotice`, `useMotionPolicy`, `tokens.css`.

## 3. Khoảng trống

Shell mới, 4 tab, khẩn cấp, thoát nhanh, PIN, Hồ sơ, Tìm hỗ trợ, tên trung tính.

## 4. Kiến trúc đề xuất

`frontend/src/features/school/`, lazy chunk riêng. `useResource` và `SessionContext` nằm trong `RealApp`: **tách sang `frontend/src/features/shared/`** bằng PR refactor không đổi hành vi, thay vì import `RealApp` vào shell mới.

```text
features/school/
  SchoolApp.tsx  school.css  routes.ts
  shell/{AppBar,TabBar,EmergencyButton,EmergencySheet,QuickExit,NeutralMode}.tsx
  chat/{ChatScreen,Composer,MessageList,EmergencyCardView,ProposalCardView,SourceSheet}.tsx
  cases/{CaseList,CaseTimeline,EventDetail,EvidenceUpload,SelfCheck,PinGate,PdfPreview}.tsx
  support/{SupportPage,PlatformGuide,TrustedAdults,SafetyPlan,Card111View}.tsx
  practice/...
  settings/SettingsPage.tsx
  copy/{vi-11-14,vi-15-17}.ts
  safety/{screen.ts,rules.generated.json}
```

Copy tập trung trong `copy/`, chọn theo `ageGroup`.

## 5. Phạm vi

Trong: mọi màn hình ở [09](../09-ux-and-user-flows.md). Ngoài: thay đổi giao diện của profile default.

## 6. File và symbol bị ảnh hưởng

`frontend/src/AppEntry.tsx`, `appEntryRoute.ts`, `api/contracts.ts`, `api/stream.ts`, `api/journalUpload.ts` (đổi tên hàm tổng quát, giữ export cũ), `playwright.config.ts`.

## 7. File mới

Như §4. Spec: `frontend/tests/e2e/school-*.spec.ts`, `frontend/tests/fullstack/school-kb-{a,b,c}.spec.ts`.

## 8. API contract

Sinh từ OpenAPI. Thêm vào `stream.ts`: `validCards` nhận `emergency`, `proposal`.

## 9. Dữ liệu và migration

Không.

## 10. Task

| ID | Ưu tiên | Phụ thuộc | Thay đổi, ở đâu | Hành vi mong đợi | Lệnh test | Pass / fail |
| --- | --- | --- | --- | --- | --- | --- |
| WS-09-T01 | P0 | WS-02-T09 | Tách `useResource`, `useSession` sang `features/shared`; shell, 4 tab, route | Spec cũ không đổi; 360px không tràn | `npm test`; `npm run test:e2e` | Pass: toàn bộ fixture suite cũ |
| WS-09-T02 | P0 | T01 | `EmergencyButton`, `EmergencySheet`, tĩnh, không API | Mở được khi API chết; `tel:`; focus trap của `Dialog` | `npx playwright test tests/e2e/school-emergency.spec.ts` | Pass với mọi route API trả 500 |
| WS-09-T03 | P0 | T01 | `QuickExit`, `/trung-tinh`, xóa cache, `location.replace` | Back không hiện nội dung; drafts mất | `npx playwright test tests/e2e/school-quick-exit.spec.ts` | Pass |
| WS-09-T04 | P0 | T02 | `/ho-tro` public, dùng `public-cards.generated.json` | Không gọi API; đọc được khi chưa đăng nhập | `npx playwright test tests/e2e/school-support.spec.ts` | Pass |
| WS-09-T05 | P0 | WS-04-T07 | `ChatScreen`, stream, `AIActivity` thân thiện, `EmergencyCardView`, `ProposalCardView`, dừng | Đủ trạng thái; không lộ tên tool; không có tên bot cũ | `npx playwright test tests/e2e/school-chat.spec.ts` | Pass |
| WS-09-T06 | P0 | WS-05-T10 | Citation, `SourceSheet`, nhãn tham khảo | Nhãn hiện theo `sourceMarked`, không theo text | Spec trên | Pass |
| WS-09-T07 | P1 | WS-03-T10 | Khi gửi lỗi mạng: chạy `screen.ts`; đỏ thì hiện template offline | Giữ nguyên tin đã gõ | `npm test`; spec offline | Pass |
| WS-09-T08 | P1 | WS-06-T03 | `CaseList`, `CaseTimeline`, `EventDetail`, lịch sử phiên bản | Thời điểm xấp xỉ hiển thị đúng; bí danh | `npx playwright test tests/e2e/school-cases.spec.ts` | Pass |
| WS-09-T09 | P1 | WS-06-T06 | `EvidenceUpload`, `SelfCheck`, tiến trình, hash | Chọn "Có hoặc không chắc" không gọi API upload | Spec trên | Pass |
| WS-09-T10 | P1 | WS-06-T08 | `PinGate` | Không lộ tiêu đề khi khóa | Spec trên | Pass |
| WS-09-T11 | P1 | WS-06-T11 | `PdfPreview`, chọn phần, tải về | Ba nhãn | Spec trên | Pass |
| WS-09-T12 | P1 | WS-07 | `TrustedAdults`, `SafetyPlan`, `Card111View`, sao chép tin | Không có nút gửi | `npx playwright test tests/e2e/school-support-plan.spec.ts` | Pass |
| WS-09-T13 | P1 | T05 | `SettingsPage`: giới hạn AI, tên trung tính, cỡ chữ, chế độ chạm, xóa dữ liệu | Tên trung tính đổi `document.title` | `npm test` | Pass |
| WS-09-T14 | P1 | T05–T13 | Copy hai nhóm tuổi trong `copy/` | Không còn chuỗi cứng trong component; test so khóa hai file | `npm test` | Pass |
| WS-09-T15 | P0 | T05–T13 | Ma trận trạng thái: loading, empty, error, offline, timeout, denied, quota | Mỗi màn hình có test | `npx playwright test tests/e2e/school-states.spec.ts` | Pass |
| WS-09-T16 | P0 | T15 | Axe mọi route, 360, 390, 768, 1280; cảnh báo chữ 200%; rà tên cũ | 0 violation; `rg` không còn Điều phối, Mây trong `features/school` | `npx playwright test tests/e2e/school-a11y.spec.ts` | Pass |
| WS-09-T17 | P2 | OD-06 | Tinh chỉnh hình ảnh theo hướng được chọn | Screenshot mobile, desktop trong PR | Visual config | Owner xem |

## 11. An toàn và bảo mật

Không lưu nội dung vào `localStorage`. `resourceCache` chỉ trong RAM, xóa khi thoát nhanh. Không log văn bản ra console. Link citation mở tab mới với `rel="noreferrer"`.

## 12. Test và dataset

Thêm mọi spec vào `testMatch`; `playwright.owned.config.ts` dùng chung specs.

## 13. Acceptance criteria

G4 đạt: [10](../10-evaluation-and-quality-gates.md).

## 14. Phụ thuộc và blocker

API các WS; OD-06. Không sửa `frontend/` khi fullstack đang chạy: Vite HMR tải lại trang.

## 15. Rollback

Shell chỉ tải khi `appProfile=school_safety_demo`.

## 16. Definition of Done

G4 đạt, ảnh mobile và desktop trong PR.

## 17. Ghi chú cho Grok

Không dựng lại group chat nhiều bot. Không thêm thư viện state hay UI. CSP chặn inline style: dùng class.
