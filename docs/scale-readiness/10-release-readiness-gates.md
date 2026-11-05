# Release readiness gates

> **Implementation, 2026-11-05:** Yêu cầu hiện hành cho phép local engineering và read-only cloud. Target AI toàn ứng dụng **$50/ngày**, chưa kích hoạt production; campaign staging tối đa **$3 tổng cộng**, chỉ `gpt-6-luna` generation, không judge API. D03/D05/D10/D12 đã được chấp thuận. Mỗi production mutation cần approval riêng. Các đoạn audit-only/$20/$5 bên dưới là baseline lịch sử. [Tiến độ](12-implementation-progress.md), [cloud](13-cloud-inventory-redacted.md), [approval proposals](14-owner-decisions-required.md), [kết quả](15-test-results.md) là nguồn cập nhật; release vẫn **NO-GO**.

**Audit status: NO-GO cho tuyên bố đạt đủ ba mục tiêu.** Không có benchmark production hoặc T1–T8 hoàn chỉnh trong audit. Chỉ owner mới có thể chấp nhận exception hoặc cấp release authorization; một exception không biến requirement chưa đạt thành PASS.

[Workload/SLO](02-capacity-and-bottleneck-analysis.md), [commands và safety](07-load-testing-and-benchmark-plan.md), [roadmap](08-implementation-roadmap.md), [manual facts](09-human-action-checklist.md).

## Cách đóng gate

Mỗi gate cần: timestamp theo timezone ghi rõ, run ID, SHA và image digest, môi trường L0/L1/L2, resolved numeric config, dataset/case, denominator/raw counts, p50/p95/p99 và sample count, expected vs actual outcome, owner/reviewer, cost estimate/reserved/settled/actual, cleanup result. Thiếu metric hoặc pending provider billing giữ UNKNOWN ở phần đó. Không lấy source test assertion, run cũ khác SHA, screenshot 50 tabs hoặc fake provider PASS làm bằng chứng real capacity.

| Gate | Điều kiện PASS | Hiện tại | Owner / evidence cần |
|---|---|---|---|
| G00 provenance/scope | Exact candidate SHA/main/CI/image attestations đúng, không user changes ngoài scope, release hold chỉ bỏ bằng quyết định riêng | Baseline local VERIFIED; prod/CI candidate UNKNOWN | HUMAN+CODEX, Git Hub/EC2 metadata |
| G01 cloud facts | Compute/region/role/pooler/Auth/SMTP/SES/OpenAI quotas có numeric facts đúng target | UNKNOWN | HUMAN H01/09 |
| G02 secret/recovery | Credential hygiene, runtime/migration keys tách, DB+Storage/EBS restore rehearsal có RPO/RTO | UNKNOWN; scratch credential cần xoay | HUMAN H02 |
| G03 registered 1000 |1000 distinct Auth confirmed +app records đúng; T1 growth/query/privacy; controlled cohort mail evidence nếu tạo mới | Chưa chạy | HUMAN approved Auth +CODEX analysis |
| G04 distributed signup |100 valid new signups/60 s nhiều IP thật; đủ 100 created/SES accepted/delivered/confirmed và SLO 07 | Chưa chạy | P1-A, T2 |
| G05 NAT signup |100 valid new signups/60 s cùng IP và confirmation/login follow-on, vẫn giữ negative anti-abuse | **FAIL by current policy inference**40/900 | HUMAN policy +P1-A02/A03 +T3 |
| G06 DB budget | Steady/overlap/admin/migration count trong actual role/server/pooler; no timeouts; p95 checkout wait<100 ms | Formula 8/16 VERIFIED; actual limits UNKNOWN | P2-D01/D02, T6/T7/T8 |
| G07 financial bound | Ca p20 invariant mọi interleaving; 50 parents chỉadmit khi token/call/tool bound thực đủ remaining; uncertain không refund | **FAIL 50 under current $2 envelope** | P3-I02/I08, fake barriers +fault matrix |
| G08 fake AI 50 |50 registered parents +50 SSE thực simultaneous, 15 phút, profile single/multi/mixed, production-equivalent pool/accounting/resources | Chưa chạy | P3-I07/P5-L01, T4 |
| G09 real AI 50 | G08 +actual model/project quota, provider requests/calls/tokens trace, 15 phút real closed loop 50 với approval/cap | Chưa approved/chưa chạy | HUMAN P3-I09 +T5 |
| G10 mixed workload | Auth+AI, proactive/guest/journal/embedding/maps không phá interactive SLO, budget/capacity đúng origin | Chưa chạy | T6/T7 |
| G11 SSE/privacy | Disconnect/replay/cancel/revocation/slow reader không leak/duplicate call; DB checks giữ authorization | Source có safe guards, chưa full fault evidence | P3-I05, P2-D08, T8 |
| G12 resource/sustained | No OOM/restart/pool timeout; RSS/CPU/loop lag/credit projection đạt 06; 15 phút real +2 h mock soak | UNKNOWN | P4-E01, T4/T7/T8 |
| G13 observability | Actual gauges/histograms/alerts đủ, canary delivery; không log PII/secret | Templates VERIFIED, installed UNKNOWN | P4-E03 +H-E04 |
| G14 deploy rollback | Native Linux unit checks+health/SSE/drain+worker fence; image rollback compatible DB; maintenance RTO được chấp nhận | Windows suite không xanh do environment; staging rehearsal chưa có | P4-E02, T8 |
| G15 final review | MUST P0/P1 closed, no unknown critical facts, cleanup complete, owner approve release target/window | OPEN | HUMAN +reviewer |

## Các mức tuyên bố được phép

- **Static reviewed:** chỉ chứng minh config/code/evidence inventory; không nói chịu 50 users.
- **Local synthetic PASS:** đúng fake provider/local PG/profile đã chạy; không nói SES/OpenAI/Supabase hosted đạt.
- **Target-size staging PASS:** chứng minh host/topology/network đã dùng, ghi rõ model/SMTP mock hay real.
- **Real-provider staging PASS:** đúng model/quota/dataset/duration tại thời điểm run; vẫn không cam kết mọi prompt/mix/future quota.
- **Release authorized:** owner đồng ý sau G15; chưa đồng nghĩa deployed. Deployment verified cần exact SHA/digest+public readiness+approved smoke sau deploy trong nhiệm vụ riêng.

## Điều kiện dừng ngay

- [ ] Gặp target không đúng, traffic production, mailbox ngoài manifest, egress paid không approved, hoặc secret/PII trong output.
- [ ] Cost liability đạt safety bound hoặc unknown price/call bound; không mở budget để tiếp tục.
- [ ] OOM/unplanned restart, DB pool timeout, connection exhaustion, wrong user replay, duplicate call/charge hoặc spent vượt cap.
- [ ] Signup/confirm/login bị 429 hàng loạt: giữ error counts, không vô hiệu hóa limiter/CAPTCHA/suppression.
- [ ] Deploy/readiness thất bại: giữ maintenance, rollback reviewed digest nếu compatible; không tự apply SQL để bỏ health gate.

Procedure: dừng new arrivals →cancel only test runs theo policy →reconcile known usage/retain unknown liability →cleanup owned resources →ghi incident/no-go →review root cause. Retry run mới có run ID/config diff; không xóa run failed để chọn run đẹp.

## Release checklist giao owner

- [ ] Tôi đã xem report T1–T8, các UNKNOWN và cost scope, không chỉ synthetic PASS.
- [ ] Tôi chấp nhận policies NAT/context/budget/RPO/RTO và SPOF một EC2.
- [ ] Các secret/SMTP/DNS/SES production/quota/provider limits đúng target.
- [ ] Tôi có backup, maintenance window, người điều khiển dừng và rollback.
- [ ] Tôi cấp riêng authorization target SHA/digest/window/deploy; tài liệu này không tự gỡ release hold, push/merge/deploy.

Audit hiện chưa đánh dấu checkbox nào. Cloud/paid gates không được đóng bằng config example hoặc giả định gói Pro/Essentials.
