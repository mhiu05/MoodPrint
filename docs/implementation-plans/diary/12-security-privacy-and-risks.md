# Security, privacy and risks

Status: NOT_STARTED (implementation), PASS (risk audit). Existing mood notes explicitly promise not to be sent to AI. Journal V2 therefore uses a new table and clear notice, never a migration that silently shares old notes.

| Risk | Required control / evidence |
| --- | --- |
| IDOR via entry/media UUID | Backend Actor, live session and owner-filtered lookup before every read/write/sign; cross-owner tests return404. |
| Default journal AI access expands to all bots | Nhịp-only dispatcher; current AI authorization; no new toggle or implicit MEM/history/VOICE enablement. |
| Prompt injection or invented memory | Treat snippets as data; model cannot choose owner, write entry, grant consent or sign media; source IDs validated backend. |
| Stale/deleted sources in final/reloaded context | User.data_version fence, ephemeral evidence cleanup, journal-derived current-run policy. |
| Public bytes or leaked service key | Private bucket, no direct browser broad Storage grant, SecretStr backend key, short signed reads and exact CSP origin. |
| Oversize/type spoofing | DTO reservation limits plus provider-verified metadata; explicit MIME list; immutable safe extension, no SVG/HTML; object rejection queues deletion. |
| Interrupted save/upload | Server draft, retained reservation, retry/progress; no sensitive automatic localStorage. |
| DB row deleted but remote bytes remain | Durable outbox survives account deletion; retryable worker and expired-pending sweep; hosted cleanup must be exercised before release. |
| Old signed capability after deletion | Upload capability lasts2h and read capability up to60s; no claim of instant token revocation; delayed orphan sweep after24h. |
| Guest privacy/lifetime | Existing transaction/output fences, explicit inventory classification and queued media deletion; tests at expiry boundary. |
| Retention/export expansion |90-day account-local journal policy; metadata/text export includes no signed URLs or automatic binaries; no embeddings/transcripts. |
| Load |<=50 list rows, <=5 AI excerpts,10attachments/entry, serial browser upload, chunked files; worker batches and indexed owner/date queries. |

No hosted production data is needed for this work. Provider configuration, private bucket/CORS/limits, production migration approval, backup retention and operational monitoring remain release prerequisites. A local test cannot establish provider retention or deletion from backups.
