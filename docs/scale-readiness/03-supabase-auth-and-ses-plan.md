# 03 — Supabase Auth và kế hoạch email SES

> **Implementation, 2026-11-05:** Yêu cầu hiện hành cho phép local engineering và read-only cloud. Target AI toàn ứng dụng **$50/ngày**, chưa kích hoạt production; campaign staging tối đa **$3 tổng cộng**, chỉ `gpt-6-luna` generation, không judge API. D03/D05/D10/D12 đã được chấp thuận. Mỗi production mutation cần approval riêng. Các đoạn audit-only/$20/$5 bên dưới là baseline lịch sử. [Tiến độ](12-implementation-progress.md), [cloud](13-cloud-inventory-redacted.md), [approval proposals](14-owner-decisions-required.md), [kết quả](15-test-results.md) là nguồn cập nhật; release vẫn **NO-GO**.

**Ngày audit:** 2026-11-05. **Trạng thái:** audit mã nguồn và kế hoạch, chưa triển khai, chưa benchmark, chưa gửi email. Mọi cấu hình thực tế trên Supabase/AWS được ghi **UNKNOWN** nếu chưa có bằng chứng đọc từ môi trường đích. Các con số giới hạn trong tài liệu nhà cung cấp là tham chiếu, không phải quota của MoodPrint.

Đọc cùng [00 — Executive summary](00-executive-summary.md), [07 — Load testing và benchmark](07-load-testing-and-benchmark-plan.md), [08 — Roadmap](08-implementation-roadmap.md), [09 — Việc HUMAN phải làm](09-human-action-checklist.md), [10 — Release gates](10-release-readiness-gates.md). Chương này cung cấp nhóm task `P1-A01…P1-A11` cho roadmap và release gates.

## Kết luận có thể kiểm chứng

1. `IP_LIMIT = AttemptLimiter(40, 900)` có thật tại `backend/app/modules/auth/routes.py:228`. Đây là ngân sách **attempt** chung cho login, signup, confirmation, recovery và reset; không phải 40 signup thành công. Với một process, bucket sạch, 100 signup hợp lệ từ cùng IP trong 60 giây, tối đa 40 request đi qua IP gate và ít nhất 60 nhận local 429. Thành công upstream/email có thể thấp hơn. Chưa chạy phép thử này.
2. 100 IP người dùng khác nhau không đồng nghĩa 100 IP ở Supabase: BFF chỉ gửi publishable `apikey`, chưa gửi `Sb-Forwarded-For` (`provider.py:128`, `provider.py:144`). Suy luận cần đo: provider có thể gom vào IP egress backend. Cách nhận IP phía proxy và cấu hình IP-forwarding hosted đều **UNKNOWN**.
3. Adapter tạo và đóng `httpx.AsyncClient` cho từng exchange (`provider.py:139-147`). Đây không phải leak client; thiếu tái sử dụng connection giữa các exchange/request. Một login có ít nhất password grant rồi `/user`, trước khi ghi app DB (`provider.py:164-188`, `routes.py:241-251`). Chưa có số đo để quy mọi latency cho TLS/pooling.
4. Local và upstream rate limit đều thành `AUTH_RATE_LIMITED`, nhưng chưa truyền `Retry-After` (`limits.py:28`, `provider.py:46-49`, `provider.py:154-155`). UI giữ metadata khi có header (`frontend/src/api/client.ts:149`), không tự replay login. Cần phân loại nội bộ để biết tầng nào chặn.
5. Signup/recovery/resend đã có response tránh dò email và CAPTCHA. Cần giữ các bảo vệ này. Khoảng trống là bao quát status/error provider, kết quả timeout không xác định, provisioning concurrent và đo delivery; không phải bỏ confirmation hay mở limit để đạt số đẹp.
6. Không tìm thấy bằng chứng rằng SES đã nối vào hosted Auth. Region, sandbox, quota gửi/giây, quota rolling 24 giờ, SMTP, sender identity, DNS và delivery đều **UNKNOWN**. Vì vậy chưa thể cam kết 100 signup có thư trong 60 giây.

## AS-IS: luồng thực tế

| Luồng | Hành vi đã đọc | Bằng chứng chính xác |
|---|---|---|
| Signup | Origin check → khai báo đủ 18 tuổi → normalize email → IP attempt → email attempt → provider `/signup` → `202 {status: sent}`. Không insert app `User` tại signup. Khai báo tuổi này chưa được lưu thành `AgeDeclaration` ở bước này. | `backend/app/modules/auth/routes.py:299-314`; `backend/app/contracts.py:137-147` |
| Login | Origin → IP 40/900 → email 10/900 → `/token?grant_type=password` → `/user` → đối chiếu subject/issuer/audience/expiry/anonymous → app transaction. | `routes.py:232-257`; `backend/app/modules/auth/provider.py:164-207` |
| Provision app | `INSERT User ON CONFLICT(auth_subject) DO NOTHING`, rồi khóa user `FOR UPDATE`, kiểm tra status/kind/suspension, insert bốn consent nếu chưa có, tạo opaque app session. | `routes.py:251-281`; unique `User.auth_subject` tại `backend/app/infrastructure/database/models.py:44`; consent composite PK tại `models.py:119-120` |
| Cookie/session | Hash opaque session/CSRF ở DB; session cookie Http Only, Same Site strict, secure production. Login commit xong mới dựng session view bằng transaction khác. `GET /session` đã dùng một checkout chung cho xác thực và view. | `routes.py:282-296`, `routes.py:176-189` |
| Confirmation resend | IP budget chung; email key `confirm:<email>` 3/3600; provider `/resend` với type signup và callback. | `routes.py:317-324`; `provider.py:275-283` |
| Recovery | IP budget chung; email key `recover:<email>` 3/3600; `/recover`; response không phân biệt email có tồn tại. | `routes.py:327-334`; `provider.py:285-292` |
| Callback | Parse fragment/query một lần trước React, xóa URL về `/#/`, recovery token chỉ giữ trong memory; confirmed callback là thông báo UI, login sau đó vẫn xác thực backend/provider. Không có PKCE code exchange trong parser hiện tại. | `frontend/src/features/auth/callback.ts:8-26`; `frontend/src/main.tsx:11` |
| Password reset | Xác minh bearer qua `/user`, từ chối anonymous, `PUT /user`, best-effort local provider logout, rồi tăng `User.auth_version` để kết thúc app sessions cũ. Không yêu cầu widget CAPTCHA lần nữa. | `routes.py:337-354`; `provider.py:245-252`, `provider.py:294-312` |
| Request đã đăng nhập | Xác minh expiry/revoked/auth_version/user status/provider session sống; CSRF cho writes; transaction xác minh lại sau lock. Refresh idle app session có throttle 15 phút. | `backend/app/core/security.py:36-58`, `security.py:84-104`, `security.py:131-175` |

### Chống lạm dụng và các boundary phải giữ

- `LOGIN_LIMIT(10,900)` dùng `email:<normalized>` khi login; reauth dùng key riêng. `EMAIL_LIMIT(3,3600)` tách `signup:`, `confirm:`, `recover:`; một email có thể có ngân sách riêng cho từng thao tác. `IP_LIMIT` dùng chung tất cả public auth trên cùng `ip:<request.client.host>` (`routes.py:221-229`, `routes.py:238-239`, `routes.py:311-340`, `routes.py:361`). Attempts thất bại sau gate vẫn tiêu hao ngân sách.
- Limiter là `dict/deque` RAM với monotonic clock, trượt cửa sổ; restart mất bucket, process khác không chia sẻ (`backend/app/core/limits.py:1-34`). `check()` không có `await`, nên không có bằng chứng race asyncio bên trong một process; vấn đề scale là phạm vi state. Topology được hỗ trợ hiện tại là một worker (`backend/app/__main__.py:9-17`; `deploy/README.md:5`).
- `_client_key` dựa `request.client`, không tự tin XFF do browser gửi. Uvicorn bật proxy headers và trông cậy `FORWARDED_ALLOW_IPS`; giá trị deployed chưa được xác minh (`backend/app/__main__.py:10-17`). Caddy có reverse proxy nhưng không chứng minh runtime trust chain (`deploy/Caddyfile:20-25`). Nếu trust sai, nhiều client có thể chung địa chỉ proxy; nếu trust quá rộng, attacker có thể giả IP. Cả hai là **giả thuyết cấu hình**, chưa phải incident đã quan sát.
- Backend yêu cầu token khi `auth_captcha_enabled`, chuyển đúng `gotrue_meta_security.captcha_token`; upstream `captcha_failed` thành 422 riêng (`provider.py:131-137`, `provider.py:156-159`). Frontend đọc `/public/experience`, lấy token bằng `take()` rồi xóa/reset trước attempt; không giữ token trong storage (`frontend/src/features/auth/useAuthCaptcha.ts:13-27`; `CaptchaChallenge.tsx:39-62`). Cờ runtime và CAPTCHA secret/provider/site key thực tế: **UNKNOWN**.
- Signup map `user_already_exists/email_exists` về cùng kết quả (`provider.py:270-272`). Resend nhận cả 400/422 như notice; recovery nhận 400/404/422 như notice sau bước phân loại CAPTCHA/429/5xx (`provider.py:149-162`, `provider.py:282-292`). Cách này bảo vệ enumeration nhưng có thể che lỗi vận hành 4xx chưa biết: cần white list theo error code và test contract, không công khai tồn tại email.
- UI busy guard ngăn double submit trong screen (`frontend/src/features/real/Auth.tsx:100-112`). Auth requests đều `publicWrite:true`, không truyền idempotency key (`Auth.tsx:124-165`). `ApiClient` chỉ tự tạo key cho write không phải public (`frontend/src/api/client.ts:88-109`); request chỉ fetch một lần, chưa có auto retry (`client.ts:120-129`). Không được diễn giải `retryable:true` thành quyền tự replay side effect.
- `frontend/src/api/session.ts:21-68` kiểm tra cấu trúc session, không xác thực credential và không thay backend authority. Việc giảm DB/auth checks để đạt throughput sẽ làm mất bảo vệ revocation; không đưa vào TO-BE.

## Mô hình 100 signup trong 60 giây

Phải tách `signup request được nhận`, `provider identity tạo`, `provider chấp nhận gửi`, `SES nhận`, `recipient server nhận` và `user confirm`. `202 sent` của app không chứng minh đã có mail trong inbox.

| Kịch bản synthetic, bucket ban đầu sạch | Dự đoán từ code hiện tại | Không được suy diễn |
|---|---|---|
| 100 email riêng, 100 client cùng NAT/public IP, một worker, tất cả payload qua validation/age gate | Chỉ 40 qua IP gate trong cửa sổ 900 giây; request 41–100 bị local 429 trước provider. Nếu có login/recovery trước đó, còn ít slot hơn. | 40 account tạo hoặc 40 email delivered; 60 lỗi do SES; kết quả thật đã benchmark. |
| 100 email riêng, 100 IP backend đã xác minh, đều trải trong 60 giây | Local IP gate không chặn chỉ vì tổng 100; email gate riêng không chặn lần đầu. Provider/project/email/CAPTCHA và tài nguyên backend có thể giới hạn. | Provider cũng thấy 100 IP; tất cả thành công khi local không 429. |
| 100 client nhưng request.client cùng proxy vì trust chain sai | Tương tự shared IP, dù người dùng phân tán. | Khẳng định hosted đang sai, vì chưa đọc runtime. |
| 100 request cùng email | Email gate cho phép tối đa 3 signup attempts/giờ, dù đổi IP. | Nâng IP gate giải quyết được email cooldown. |
| 100 login mới, hoặc signup rồi confirm/login dồn cùng NAT | Dùng cùng IP bucket; login cần hai provider exchanges và app DB. | Lấy benchmark signup-only làm bằng chứng login/session đạt SLA. |

H0 kiểm chứng offline: current policy chặn NAT đúng theo code; H1 kiểm chứng cấu hình: proxy/backend/IP upstream gom người dùng; H2 kiểm chứng capacity: email quota hoặc provider throttle; H3 kiểm chứng hiệu năng: client churn/DB checkout/lock chậm. Chỉ đổi chính sách sau khi phân biệt H0–H3. Kịch bản NAT và distributed phải báo cáo riêng trong [07](07-load-testing-and-benchmark-plan.md).

### Upstream IP forwarding: quyết định cần chốt

[Supabase Rate limits](https://supabase.com/docs/guides/auth/rate-limits) hiện mô tả `Sb-Forwarded-For` cần **secret API key** và bật IP forwarding; publishable và legacy anon/service_role không được hỗ trợ. Đừng chỉ thêm header vào adapter hiện tại. Các limit provider/project cũng không biến mất nhờ forwarding.

TO-BE chọn một trong hai sau khi HUMAN xác minh cấu hình: (A) tiếp tục publishable key, chủ động thiết kế admission theo egress/provider budget; hoặc (B) server-only secret key cho adapter auth chuyên biệt, với IP đã chuẩn hóa từ proxy tin cậy và feature flag. Phương án B cần review theo endpoint rằng CAPTCHA/rate-limit/permission vẫn đúng, không được vô tình đổi sang admin signup hay auto-confirm. Không nhận `Sb-Forwarded-For`/XFF trực tiếp từ client làm nguồn thẩm quyền; không cấp secret cho frontend, log, response, generated schema hay test fixture thật. Cách dùng secret chưa được triển khai/kiểm thử trong audit này.

## TO-BE: mục tiêu vận hành

- Admission nhiều lớp: giới hạn email/action và brute-force vẫn giữ; IP có hard abuse ceiling, short burst policy và lớp CAPTCHA/risk riêng. Nếu cần cho sự kiện NAT, phải định nghĩa rõ số request hợp lệ được nhận và hành vi 429/wait list. Không có yêu cầu mọi request phải 2xx bất kể rủi ro. Một worker hiện tại giữ nguyên cho tới khi state toàn hệ thống sẵn sàng.
- Provider I/O dùng một client theo app lifespan với connection/concurrency bounds, timeout riêng; gửi header/bearer theo request, không mutate shared headers/cookies. Login vẫn xác minh provider. Không giữ app transaction/row lock trong lúc chờ provider.
- Error contract thống nhất nhưng metrics tách `local_ip`, `local_email`, `provider_request`, `provider_email`, `captcha`, `provider_unavailable`, `db_busy`. Public response không lộ email tồn tại; cooldown có `Retry-After` hữu hạn. Sự cố chưa rõ kết quả không hiện thông báo chắc chắn “đã gửi”.
- Public auth side effects dùng state machine rõ `not_started/attempting/accepted/rejected/unknown` nếu cần dedup; timeout sau wire là `unknown`, không resend/recreate tự động. Không lưu password/recovery bearer/CAPTCHA/raw email vào receipt/log; không hứa exactly-once xuyên app ↔ Supabase khi provider không có contract đó.
- App provisioning giữ unique constraint, `ON CONFLICT` và khóa theo user. Chứng minh bằng concurrent test thay vì thêm global lock. Signup vẫn xác nhận email; account mới vẫn eligibility unknown và phải khai báo lại trước protected features.
- Email từ Supabase Auth qua **custom SMTP SES**, không thêm đường backend gửi thư xác nhận thứ hai. Email template/redirect giữ auth callback đúng luồng hiện tại; thay PKCE nếu có phải là task riêng có kiểm thử.

## SES: bằng chứng còn thiếu và capacity envelope

| Mục phải đọc từ môi trường đích | Trạng thái audit | Owner chứng minh |
|---|---|---|
| Supabase custom SMTP enabled, host/port/From, project send quota, cooldown, confirm-email setting, callback allowlist | **UNKNOWN** | HUMAN cung cấp bản đọc đã bỏ secrets; CODEX đối chiếu contract |
| SES account + region + Production Access Enabled + Sending Enabled | **UNKNOWN** | HUMAN |
| SES Max Send Rate, Max 24 Hour S end, Sent Last 24 Hours, quota headroom | **UNKNOWN** | HUMAN |
| Identity Verified For Sending Status, DKIM, MAIL FROM, SPF/DMARC alignment, suppression state | **UNKNOWN** | HUMAN |
| SMTP credential scope/rotation, recipient delivery, bounce/complaint pipeline/alarms | **UNKNOWN** | HUMAN |

[Supabase custom SMTP](https://supabase.com/docs/guides/auth/auth-smtp) mô tả default SMTP chỉ dành thử nghiệm, giới hạn hiện công bố 2 email/giờ và recipient là thành viên project; khi gắn custom SMTP có mức khởi đầu 30 email/giờ. Đây là lý do phải đọc quota Auth sau khi nối SES, không coi custom SMTP là bỏ giới hạn. Không tắt email confirmation để né nghẽn.

[SES sending quotas](https://docs.aws.amazon.com/ses/latest/dg/manage-sending-quotas.html) tách quota rolling 24 giờ và tốc độ nhận/giây theo region; quota tính theo recipient. Sandbox hiện công bố 200 recipient/24 giờ và 1/giây. [Production access](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html) vẫn yêu cầu sender được xác minh; trong sandbox chỉ gửi tới (1) email identity đã verify, (2) mailbox simulator, hoặc (3) địa chỉ thuộc domain đã verify. Production quota của dự án không suy từ mặc định.

Capacity cần chốt: 100 signup/60 giây = trung bình 1, 67 email/giây nếu mỗi signup tạo đúng một thư. Cộng resend/recovery và retry có kiểm soát thành `E_peak`; thêm headroom do HUMAN duyệt. Kiểm tra đồng thời `E_peak <= quota Auth được duyệt`, tốc độ SES đủ cho phân bố burst, và `existing rolling sends + planned recipients <= daily quota`. 1, 67 là phép tính nhu cầu, không phải throughput đo được hoặc quota cần xin chính xác. Nếu không đủ, admission phải làm phẳng burst và nói rõ thời gian chờ, không khẳng định gửi rồi.

Thiết kế sender riêng cho auth; DNS DKIM và [custom MAIL FROM](https://docs.aws.amazon.com/ses/latest/dg/mail-from.html), [DMARC rollout](https://docs.aws.amazon.com/ses/latest/dg/send-email-authentication-dmarc.html) do HUMAN xác nhận. MAIL FROM tùy chọn của SES nhưng được đề xuất như gate của kế hoạch để kiểm soát alignment/fallback; không tuyên bố SES luôn bắt buộc. Với SMTP, dùng [credentials theo region](https://docs.aws.amazon.com/ses/latest/dg/smtp-credentials.html), không dùng password AWS hay derive từ STS temporary credentials; quản lý secret và rotation ngoài repo. Event pipeline cần [configuration set](https://docs.aws.amazon.com/ses/latest/dg/using-configuration-sets.html) áp vào email thực tế; default configuration set của identity là lựa chọn khi Supabase SMTP không thêm header tùy ý. Phân biệt send/delivery/bounce/complaint theo [SES events](https://docs.aws.amazon.com/ses/latest/dg/event-publishing-retrieving-sns-examples.html); delivery tới mail server vẫn không bảo đảm inbox.

## Task triển khai có thể giao

Độ phức tạp: S ≤ 1 ngày, M 1–3 ngày, L 3–5 ngày kỹ thuật; không bao gồm thời gian phê duyệt quota/DNS. Chi phí là yếu tố tăng thêm, chưa phải báo giá. Mỗi task chỉ được triển khai trong phiên được cho phép sửa code/config; tài liệu này không thực hiện chúng.

### P1-A01 — MUST — Đóng băng baseline auth và bằng chứng hosted

- **Vấn đề/evidence:** chưa biết quota, proxy trust và SMTP thật; code default không chứng minh deployed state (`config.py:19-26`, `__main__.py:10-17`, `provider.py:128`). **Nguyên nhân:** repository không phải nguồn trạng thái cloud.
- **Owner/phụ thuộc:** HUMAN đọc dashboard/quota/DNS; CODEX tổng hợp; không phụ thuộc task khác. **Files:** `docs/supabase/auth.md`, `deploy/runtime.env.example`, chương 09/10; không chép env/secret thô.
- **Giải pháp/checklist:** [ ] Ghi timestamp/project ref rút gọn/region/release SHA. [ ] Thu thập các dòng UNKNOWN ở bảng trên. [ ] Xác nhận IP trust chain và tầng egress. [ ] Ghi quyết định NAT/distributed và target latency/email ở 00/07/10.
- **Test/acceptance:** review bằng chứng bỏ secrets, đối chiếu provider docs; UNKNOWN bắt buộc còn thiếu phải giữ gate BLOCKED, không “pass do default”. **Độ phức tạp:** S. **Rủi ro:** lộ cấu hình nhạy cảm. **Rollback:** thu hồi artifact không an toàn, không thay runtime. **Chi phí:** công đọc/đối chiếu; không API trả phí/email.

### P1-A02 — MUST — Admission NAT vẫn chống brute force và email bombing

- **Vấn đề/evidence:** IP bucket 40/900 dùng chung public auth (`routes.py:227-229`, `routes.py:311-340`). **Nguyên nhân xác nhận từ code:** budget theo địa chỉ mạng, không theo số người; giới hạn throughput có chủ đích.
- **Owner/phụ thuộc:** CODEX thiết kế/implement; HUMAN duyệt policy; sau A01. **Files:** `backend/app/core/limits.py`, `backend/app/modules/auth/routes.py`, auth tests; shared-store sau này phải đồng bộ roadmap 08.
- **Giải pháp/checklist:** [ ] Tách risk/burst/quota theo action nhưng giữ tổng abuse ceiling. [ ] Giữ email cooldown và login email throttle. [ ] Thêm per-IP burst + CAPTCHA hợp lệ làm một tín hiệu, không bypass limiter. [ ] Định nghĩa 429/wait list cho NAT lớn. [ ] Chỉ chọn con số sau benchmark và ngân sách provider/email. [ ] Nếu chuyển bucket sang shared store, dùng HMAC key và retention hữu hạn thay raw email/IP trong telemetry hoặc key công khai.
- **Test/acceptance:** deterministic clock, 39/40/41, hết 900 giây, mixed actions, email case fold, failed CAPTCHA cũng tốn ngân sách, NAT 100 và distributed 100; attacker đổi email/IP vẫn không tạo mail vô hạn. Báo số admitted/rejected riêng; không yêu cầu 100/100 2xx bằng cách nâng limit. **Độ phức tạp:** M–L. **Rủi ro:** khóa nhầm NAT hoặc hở spam. **Rollback:** policy flag về baseline, không bỏ CAPTCHA/confirmation. **Chi phí:** không cloud mới ở một worker; shared limiter nếu cần phải được budget riêng.

### P1-A03 — MUST — Chứng minh IP trust chain và chốt upstream forwarding

- **Vấn đề/evidence:** `_client_key` lấy `request.client`; adapter publishable chưa forwarding (`routes.py:221-223`, `provider.py:128`, `provider.py:144-147`). **Giả thuyết:** distributed client bị gom vào BFF egress; chưa có log/cấu hình xác nhận.
- **Owner/phụ thuộc:** CODEX code/tests + HUMAN runtime/provider setting; A01, A02. **Files:** `backend/app/__main__.py`, `provider.py`, `core/config.py`, `deploy/Caddyfile`, deployment docs/tests.
- **Giải pháp/checklist:** [ ] Xác định proxy nào được tin và chặn direct API ingress. [ ] Test client IP qua chuỗi proxy. [ ] Chọn A hoặc B ở mục forwarding. [ ] Nếu B: secret riêng server, feature flag, header IP đã parse/validate, bật provider setting do HUMAN thực hiện. [ ] Không dùng legacy service_role làm cách sửa tắt.
- **Test/acceptance:** spoofed XFF/Sb header không thay trusted identity; IPv4/IP v 6/invalid/unknown xử lý fail-safe; hai IP độc lập không vô tình chung local bucket; Mock Transport bắt headers đúng; no secret trong browser/log; provider CAPTCHA vẫn được thực thi. **Độ phức tạp:** M. **Rủi ro:** secret privilege, spoofing, sai trusted proxy. **Rollback:** tắt forwarding flag + giữ admission conservative; giữ secret server-only cho tới rotation/revoke đúng quy trình. **Chi phí:** không quota tăng tự động; công quản lý secret.

### P1-A04 — SHOULD — Bounded provider client theo app lifespan

- **Vấn đề/evidence:** client tạo mỗi `_send` (`provider.py:139-147`); login có hai exchange (`provider.py:164-188`). **Nguyên nhân xác nhận:** lifetime client ngắn; ảnh hưởng latency là giả thuyết cần số đo.
- **Owner/phụ thuộc:** CODEX; A01; có thể làm độc lập A02. **Files:** `backend/app/main.py` lifespan, `provider.py`, settings, provider/auth tests.
- **Giải pháp/checklist:** [ ] Inject client theo app lifespan và giữ Mock Transport seam. [ ] `aclose` shutdown. [ ] Giới hạn max connections/keepalive, semaphore + queue deadline, connect/read/write/pool timeout rõ. [ ] Header/bearer chỉ theo request, tránh cookie/shared-state bleed. [ ] Không auto retry POST/PUT auth.
- **Test/acceptance:** concurrent fixture hai token không bleed auth; pool/concurrency bound; timeout/cancel/shutdown giải phóng slot; một lifecycle đóng client đúng một lần; baseline auth tests giữ nguyên; local benchmark tách cold/warm p95 và queue wait. **Độ phức tạp:** M. **Rủi ro:** shared bearer/cookie, cạn outbound sockets. **Rollback:** flag về per-call client, giữ bound admission. **Chi phí:** thêm RAM/socket hữu hạn; chưa chứng minh cần instance lớn hơn. [HTTPX async lifecycle](https://www.python-httpx.org/async/) hỗ trợ tái sử dụng client có scope.

### P1-A05 — MUST — Error mapping và Retry-After không lộ email

- **Vấn đề/evidence:** limiter/provider 429 không đặt retry_after; `_call` xóa loại rate limit; resend/recovery chấp nhận nhóm 4xx rộng (`limits.py:28`, `provider.py:46-49`, `provider.py:149-162`, `provider.py:282-292`). **Nguyên nhân:** contract public cố ý đơn giản nhưng diagnostic và cooldown thiếu.
- **Owner/phụ thuộc:** CODEX; A01; phối hợp 07/10. **Files:** `limits.py`, `provider.py`, `core/errors.py:103-105`, `frontend/src/api/client.ts`, `features/real/Auth.tsx`, auth tests.
- **Giải pháp/checklist:** [ ] Local retry_after dựa timestamp hết window, làm tròn lên. [ ] Parse/clamp upstream Retry-After an toàn nếu có. [ ] Giữ code công khai uniform, phân loại nội bộ bounded enum. [ ] White list mã “unknown/already exists” được che; lỗi SMTP/config/quota chưa biết thành lỗi khả dụng an toàn, không giả sent. [ ] UI cooldown/manual retry, CAPTCHA mới.
- **Test/acceptance:** known/unknown/already-registered có cùng public notice; captcha_failed luôn 422; provider 429/5xx/malformed/SMTP 4 xx mapping rõ; không lộ body/timing có chủ đích/email/token; cooldown không âm/vô hạn; không tự replay login. **Độ phức tạp:** M. **Rủi ro:** enumeration hoặc UI hứa sai email. **Rollback:** mapping cũ sau khi giữ alert; không lộ raw provider error để debug. **Chi phí:** metrics cardinality hữu hạn, không hạ tầng mới bắt buộc.

### P1-A06 — MUST — Kiểm soát retry và side effect không xác định

- **Vấn đề/evidence:** public writes chưa có idempotency contract; transport lỗi thành retryable 503 (`Auth.tsx:124-165`, `client.ts:88-109`, `provider.py:149-153`). **Nguyên nhân:** request timeout có thể xảy ra sau provider tạo identity/gửi mail; hiện chưa có reconciliation cho registered signup. Anonymous path đã phân biệt ambiguous, nhưng không được copy nguyên và giả provider hỗ trợ idempotency (`provider.py:209-243`).
- **Owner/phụ thuộc:** CODEX + HUMAN quyết định UX khi unknown; A02/A05. **Files:** auth routes/provider/contracts, `ApiClient`, `AuthScreen`, auth tests; migration chỉ nếu ADR chọn durable receipt và phải review DB riêng.
- **Giải pháp/checklist:** [ ] Phân loại trước-wire/explicit-rejected/accepted/unknown. [ ] Không retry side-effect POST do network/5xx tự động. [ ] Nếu thêm intent key, chống replay + atomic claim + TTL/cooldown; cùng key khác intent báo conflict an toàn. [ ] Không lưu/hash trực tiếp password hoặc raw bearer/CAPTCHA trong receipt. [ ] Unknown hướng dẫn kiểm tra email/đăng nhập hoặc resend theo cooldown; không đánh đồng “tạo chắc chắn thất bại”.
- **Test/acceptance:** simulated timeout sau provider side effect, duplicate concurrent key và captcha dùng một lần; không phát thêm email vô hạn; unknown không bị báo sent/success giả; reset thành công upstream nhưng DB increment lỗi có recovery path được thiết kế/test. Không claim exactly-once toàn hệ thống. **Độ phức tạp:** L. **Rủi ro:** replay/bí mật lưu lâu, khóa intent kẹt. **Rollback:** tắt durable intent mới, giữ one-shot/manual retry và cooldown; không replay hàng unknown. **Chi phí:** nếu có store, thêm bounded writes/retention; quyết định trước khi tạo dịch vụ mới.

### P1-A07 — MUST — Chứng minh provisioning concurrent và partial failure

- **Vấn đề/evidence:** đã có unique/on-conflict/row lock, không thiếu mutex (`routes.py:251-281`, `models.py:44`); provider session được tạo trước DB; login commit trước `session_view` khác transaction (`routes.py:241`, `routes.py:296`). **Giả thuyết cần test:** concurrent same-subject tranh lock; grant đã tạo nhưng DB/response lỗi để lại phiên chưa phát cho browser.
- **Owner/phụ thuộc:** CODEX; A04/A05; phối hợp DB capacity 02. **Files:** auth routes, app models, security/session tests; không nới DB permission để bypass provider-session helper.
- **Giải pháp/checklist:** [ ] Local disposable DB test 2/10/100 login đồng thời cùng subject và subject khác. [ ] Verify một User, bốn Consent, từng session hợp lệ; nhiều session cho cùng user có thể hợp lệ, không mặc định là lỗi. [ ] Fault inject flush/commit/session-view, policy cleanup provider orphan là best-effort có giới hạn. [ ] Đo lock wait/checkout, giới hạn deadline; giữ unique constraint và account lock.
- **Test/acceptance:** không duplicate user/consent, không 500 integrity race, không mất auth_version/suspension checks; không cấp cookie thành công trước DB commit; response lỗi không làm UI authenticated; same-subject serialization không chặn global toàn bộ user. **Độ phức tạp:** M. **Rủi ro:** deadlock, sign out nhầm session. **Rollback:** bỏ tối ưu mới, giữ upsert/row-lock baseline; không xóa session hợp lệ hàng loạt. **Chi phí:** chỉ local DB test; hosted benchmark chưa được phép.

### P1-A08 — MUST — SES readiness và custom SMTP có bằng chứng

- **Vấn đề/evidence:** không có runtime bằng chứng SES; `provider.py:254-289` chỉ giao email side effect cho Supabase. **Nguyên nhân:** sender/quota là cấu hình dịch vụ ngoài repo, hiện UNKNOWN.
- **Owner/phụ thuộc:** HUMAN thực hiện AWS/DNS/Supabase sau phê duyệt thay đổi; CODEX chuẩn bị runbook + kiểm tra artifact; A01. **Files:** `docs/supabase/auth.md`, deploy runbook, 09/10; credentials không vào files repo.
- **Giải pháp/checklist:** [ ] Chốt region/domain auth/From/MAIL FROM; đọc account+identity+quota. [ ] DNS verify + DKIM, SPF/DMARC alignment và fallback quyết định rõ. [ ] IAM SMTP sender scope hẹp + secret rotation; cấu hình TLS SMTP endpoint/port theo region do provider hỗ trợ. [ ] Nếu sandbox, HUMAN xin production access; không giả quota tăng đã duyệt. [ ] Nối custom SMTP, kiểm tra lại Supabase send limit/cooldown/redirect/templates, giữ email confirmation.
- **Test/acceptance:** ảnh/bản đọc redacted ghi rõ Verified For Sending Status/DKIM/MAIL FROM/quota/SMTP/allowlist và owner; kế hoạch send thật phải được HUMAN cho phép riêng; hiện chưa có email send được thực hiện. Production gate không pass khi sandbox/recipient/quota chưa rõ. **Độ phức tạp:** M + thời gian AWS/DNS. **Rủi ro:** sai DNS/alignment/secret hoặc mất recovery mail. **Rollback:** snapshot config đã bỏ secrets + tham chiếu secret cũ còn hợp lệ, đổi lại SMTP đã verify trước; không tắt confirmation. **Chi phí:** SES recipient/data, DNS, secret/log/event services theo region/plan; tổng USD UNKNOWN, cần budget HUMAN.

### P1-A09 — MUST — Email observability, suppression và canary

- **Vấn đề/evidence:** app chỉ nhận upstream HTTP response; `202 sent` không có delivery receipt (`routes.py:314`, `routes.py:324`, `routes.py:334`). **Nguyên nhân:** Auth API acceptance và email delivery khác boundary.
- **Owner/phụ thuộc:** HUMAN SES configuration set/events/alarms + CODEX contract/runbook; A05/A08, chương 10. **Files:** auth metrics, ops docs và evidence schema; không log recipient list/message body/link token.
- **Giải pháp/checklist:** [ ] Kích hoạt event pipeline thực tế qua default configuration set hoặc identity notification phù hợp. [ ] Theo dõi send/delivery/bounce/complaint/reject/delay và suppression, dedup event theo message/event ID. [ ] Dashboard local/provider throttle riêng, latency/timeout/lock/DB pressure. [ ] Alarm theo policy HUMAN duyệt, không tự bịa threshold AWS. [ ] Controlled canary confirmation/recovery tới địa chỉ được phép khi được ủy quyền riêng; kiểm tra link scanner/expired-link và token cleanup.
- **Test/acceptance:** offline fixtures cho duplicate/out-of-order events; privacy/redaction test; khi được phép canary, timestamp từ API đến recipient-server receipt/confirmation đo riêng, mailbox inbox do HUMAN xác nhận; khả năng dừng signup surge mà recovery vẫn được bảo vệ bằng budget riêng. **Độ phức tạp:** M. **Rủi ro:** lộ PII hoặc metrics pass giả. **Rollback:** dừng pipeline mới có lưu evidence tối thiểu an toàn, giữ alarm/old sender; không reset suppression list để “sửa delivery”. **Chi phí:** event/log retention + SES canary nhỏ theo budget, chưa thực hiện.

### P1-A10 — MUST — Synthetic regression và gate auth burst

- **Vấn đề/evidence:** tests hiện có cover single-user flow/CAPTCHA nhưng chưa chứng minh NAT 100, provider egress, pool lifecycle, partial failures, delivery (`backend/tests/test_auth_flows.py:151-242`, `test_auth_captcha.py:39-112`; frontend `tests/e2e/auth.spec.ts:53-364`). **Nguyên nhân:** fake provider không mô phỏng quota/SMTP thật; cần ma trận riêng.
- **Owner/phụ thuộc:** CODEX; A02–A07, A08/A09 cho hosted gate riêng; chương 07/10. **Files:** các auth tests hiện hữu, local benchmark harness dự kiến trong 07; không dùng live account provisioning làm load fixture.
- **Giải pháp/checklist:** [ ] Mock Transport/ASGI local kiểm thử NAT/distributed/mixed actions và cooldown boundary. [ ] Frontend route mocks kiểm thử 429 Retry-After + CAPTCHA fresh + unknown outcome giữ fields/no replay. [ ] Concurrent disposable DB provisioning + pool exhaustion. [ ] Xuất admitted/local 429/provider 429/5xx/p95/queue/lock theo phase. [ ] Hosted canary tách riêng, chỉ chạy khi được phép.
- **Test/acceptance:** toàn bộ check liên quan pass với DB guard; không rơi qua HTTP thật/email/AI. NAT expected rejection được báo đúng, không coi expected abuse throttle là crash; distributed success chỉ kết luận trong synthetic boundary. Release production đòi A01/A08/A09 evidence riêng. **Độ phức tạp:** M. **Rủi ro:** dùng nhầm hosted test DB/provider. **Rollback:** bỏ harness mới, không thay guards hoặc đè `DATABASE_URL` thành test URL. **Chi phí:** local CPU/DB; hosted cost gate riêng chưa mở.

### P1-A11 — OPTIONAL — Wait list hoặc Send Email Hook khi quota không đáp ứng burst

- **Vấn đề/evidence:** custom SMTP không tự cung cấp app-controlled queue; provider gửi trong signup/recovery (`provider.py:254-289`). **Điều kiện kích hoạt:** sau A08/A09 thấy quota hợp lệ vẫn thấp hơn surge đã duyệt, hoặc business chấp nhận delayed signup.
- **Owner/phụ thuộc:** HUMAN chọn UX/quota/budget; CODEX ADR trước code; A01–A10. **Files dự kiến:** admission UI/API hoặc adapter/hook riêng, queue worker/runbook/tests; không thêm ngay trong phase một.
- **Giải pháp/checklist:** [ ] Ưu tiên admission/wait list không giữ password. [ ] Nếu chọn hook/queue, xác minh contract Supabase hiện hành, bảo vệ web hook, dedup và TTL, retry bounded/backoff, suppression, dead-letter và cancellation. [ ] Chỉ một sender, không custom SMTP và app resend chạy song song tạo thư trùng. [ ] Recovery có SLA và quota riêng.
- **Test/acceptance:** queue saturation/duplicate/hook retry/expired links không resend vô hạn; dừng worker không mất request đã xác nhận nhận; acceptance UI nói rõ trạng thái pending. **Độ phức tạp:** L. **Rủi ro:** token expiry, email duplication, giữ PII lâu. **Rollback:** tắt hook/queue mới có drain/fence, quay về sender đã verify; không replay DLQ đại trà. **Chi phí:** queue/worker/telemetry + vận hành; UNKNOWN tới ADR/budget.

## Lệnh kiểm chứng dự kiến, chưa chạy trong audit

Chỉ dùng dependencies đã cài và local disposable PostgreSQL được provision đúng harness. `backend/tests/conftest.py:27-60` tắt provider/AI/env thật; fixture tại `conftest.py:68-112` có **drop/create** tables sau guard. `backend/tests/database_target.py:10-65` yêu cầu loopback, tên `_test`, owner/marker theo `MOODPRINT_TEST_RUN_ID`; tên `_test` đơn thuần chưa đủ. Không đặt `TEST_DATABASE_URL` từ production/migration URL, không bỏ guard để chạy cho qua. Thiếu local DB thì báo skipped, không coi là pass integration.

```powershell
# Từ E:\MoodPrint\backend; không dùng tests/live hoặc e2e_auth.py làm load test.
uv run --locked pytest tests/test_auth_flows.py tests/test_auth_captcha.py tests/test_session_reliability.py

# Từ E:\MoodPrint\frontend, dùng node_modules hiện hữu; toàn bộ API route mocks.
node node_modules/vitest/vitest.mjs run src/api/client.test.ts src/api/session.test.ts src/api/sessionPolicy.test.ts src/features/auth/ageDeclaration.test.ts
node node_modules/@playwright/test/cli.js test tests/e2e/auth.spec.ts --config=playwright.config.ts
```

`frontend/playwright.config.ts:32-38` khởi động local Vite với `MOODPRINT_MOCK_API_ONLY=1`, không reuse dev server có real proxy. Các lệnh trên là checklist cho triển khai sau, không phải kết quả test của tài liệu này. Không gửi email thật, không tạo hosted account, không load Supabase hoặc đổi rate-limit/config cloud trong đợt audit.

## Nguồn và giới hạn bằng chứng

Nguồn chính thức được đọc ngày 2026-11-05; nội dung có thể thay đổi trước khi triển khai. Supabase [changelog](https://supabase.com/changelog) đã được quét; [thay đổi TLS CBC](https://supabase.com/changelog/cbc-tls-ciphers-deprecated) dự kiến sớm nhất 2026-11-10 liên quan Auth HTTPS. Image Python/httpx mới không tự chứng minh negotiated cipher thực tế; kiểm tra trong canary được phép, không hạ TLS verification. Changelog self-hosted SAML không chứng minh MoodPrint dùng SAML.

Tài liệu [CAPTCHA](https://supabase.com/docs/guides/auth/auth-captcha), [observability](https://supabase.com/docs/guides/observability), [custom SMTP](https://supabase.com/docs/guides/auth/auth-smtp), [rate limits](https://supabase.com/docs/guides/auth/rate-limits) định hướng việc kiểm tra provider. Kết luận code dựa file/line ở trên; kết luận throughput/provider/email thực tế vẫn **UNKNOWN** cho tới khi có evidence trong 07/09/10. Không có runtime/config/test/.gitignore nào được sửa bởi chương audit này.
