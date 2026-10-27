# Technical Documentation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this documentation plan task-by-task. The user's request authorizes completion, verification, detailed commits and push to main.

**Goal:** Viết tài liệu kỹ thuật tiếng Việt trong `ARCHITECTURE.md` và năm nhóm `docs/agents`, `docs/frontend`, `docs/backend`, `docs/supabase`, `docs/matching`.

**Architecture:** Mô tả hành vi hiện tại từ mã nguồn, hợp đồng OpenAPI, migration và test; phân biệt capability, consent, lưu trữ và bằng chứng kiểm thử. Dùng liên kết tương đối để đọc được trên GitHub và trong IDE.

**Tech Stack:** React 19, TypeScript, Vite, FastAPI, Pydantic, SQLAlchemy, PostgreSQL/pgvector, Supabase Auth, OpenAI Agents SDK; phiên bản chính xác do lockfile quyết định.

**Spec:** Yêu cầu người dùng trong phiên làm việc ngày 28/10/2026: tài liệu cụ thể, kiểm thử lại, chia commit toàn bộ và push main.

## Global Constraints

- Không sửa `.gitignore`, không ghi đè `.env`, không đưa secret hoặc dữ liệu thật vào tài liệu.
- Giữ nguyên ý định của sáu file frontend đã sửa trước phiên; kiểm thử và commit thành nhóm riêng.
- Chỉ kiểm thử dữ liệu tổng hợp trên PostgreSQL local có tên kết thúc `_test`.
- Không chạy live model, hosted migration hoặc deploy trong nhiệm vụ tài liệu.
- Main hiện tại là nhánh người dùng yêu cầu push; không force push.

## Review Focus

- Không đồng nhất transcript lưu trong PostgreSQL với context AI tạm thời trong RAM.
- Không trình bày matching v2 như cấu hình mặc định khi Settings mặc định là v1.
- Không hướng dẫn local PostgreSQL dùng trực tiếp hosted Auth không cùng `auth.sessions`.
- Không mô tả RLS là lớp phân quyền đã được triển khai cho schema private.
- Không gọi kết quả fake model, proxy labels hoặc skipped tests là bằng chứng live/production.

## Task 1: Khảo sát và baseline

- [x] Đọc README, manifest, CI, migration, module và các thay đổi có sẵn.
- [x] Chạy Ruff, mypy, typecheck, Vitest và build trước khi viết tài liệu.
- [x] Khởi động PostgreSQL disposable riêng ở 15432 khi 55432 bị Windows chặn bind.
- [x] Bắt đầu pytest và Playwright owned trên 5190; ghi nhận lỗi baseline riêng.

## Task 2: Tài liệu và điều hướng

- [x] Viết `ARCHITECTURE.md`, `docs/README.md` và tài liệu theo năm subsystem.
- [x] Viết runbook local, cấu hình, API, schema, migration, kiểm thử và giới hạn vận hành.
- [x] Sửa liên kết tài liệu không còn tồn tại trong README và các hướng dẫn liên quan.
- [x] Kiểm tra link nội bộ và đối chiếu API/config/schema với nguồn.

## Task 3: Xác minh và phát hành Git

- [ ] Hoàn tất pytest, Playwright UI và full-stack tổng hợp; migration upgrade/check trên DB riêng.
- [x] Xuất OpenAPI, sinh TypeScript và kiểm tra drift; chạy kiểm tra SQL review và deployment unit tests.
- [x] Review độc lập; khắc phục sai lệch tài liệu và bổ sung regression cho thay đổi frontend có sẵn.
- [ ] Ghi kết quả, chia commit có mô tả, push main, xác minh remote và working tree.
