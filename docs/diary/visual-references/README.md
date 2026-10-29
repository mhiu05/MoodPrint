# MoodPrint - Mobile Emotion Journal Visual References

These six PNGs are **separate, enlarged crops of the approved six-screen UI concept**, not pixel-perfect implementation specifications. Preserve the existing MoodPrint design language and validate Vietnamese copy, interaction details, responsive behavior, and accessibility in the actual app.

| File | Screen | Scope |
| --- | --- | --- |
| `01_nhat_ky_cam_xuc.png` | Nhật ký cảm xúc | Check-in with 5 mood levels; detailed emotions and influences; bottom navigation. |
| `02_ghi_lai_khoanh_khac.png` | Ghi lại khoảnh khắc | Text editor, audio recording/player, photo attachments, save entry. |
| `03_kham_pha_them.png` | Khám phá thêm | Nhịp đồng hành, writing prompts, memories, emotional insights. On mobile, place **below** the main journal form. |
| `04_lich_nhat_ky.png` | Lịch nhật ký | Monthly mood calendar, entries by date. |
| `05_khoanh_khac_cua_ban.png` | Khoảnh khắc của bạn | Timeline, content search and filters, media previews. |
| `06_nhip_dong_hanh.png` | Nhịp đồng hành | Journaling AI companion with evidence links to original memories. |

## Decisions already agreed

- Light theme: warm white/cream, sage and deep green, gently rounded corners.
- Responsive web app: mobile one column with sticky bottom nav; desktop may use a right sidebar.
- Journal content is viewable only by the authenticated account owner; the Nhịp assistant can read it by default **under the product's stated privacy policy and access controls**. Never expose journal data to other accounts or to other assistants without authorization.
- Support text, voice, and photos. Video is illustrated in some concepts but should be separately assessed for MVP scope.
- Avoid treating mockup text, dates, statistics, or tiny UI artifacts as canonical product data; verify actual date/day-of-week and accessibility.
- For React implementation, audit the existing code first. Run Playwright visual screenshots on 390px, 430px and desktop to compare proportions and interactions.
