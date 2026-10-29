# Nhịp text-only journal contract

Status: **PASS** for the existing tool contract. The new assertion was added and not re-run against PostgreSQL in this session.

Nhịp remains the only assistant with `search_journal_entries`. Other assistants do not receive that tool. The model cannot pass a user id; `search_for_ai` filters on the locked account owner.

## Allowed

Saved journal text, mood value, detailed emotions, factors, local date, entry id, and version. Results are a bounded sample inside 90 account-local days. Drafts, other owners, future dates, and entries older than the window are excluded. The backend turns verified ids into `/self/entry/` links. Instructions tell the model not to invent memories, diagnose, or treat a missing read as evidence.

## Not in this release

Image interpretation, OCR, audio transcription, audio understanding, video interpretation, frame analysis, and media embeddings. Media bytes are not selected. `search_for_ai` returns only:

`id`, `version`, `localDate`, `mood`, `emotions`, `factors`, `snippet`, `snippetTruncated`

`test_journal_search_is_owner_saved_date_and_size_bounded` now asserts that key set and that the JSON does not contain `media` or `objectPath`.

Journal-derived context stays on the current run. It is not written into long-term memory or embeddings by this tool. Legacy mood notes stay out of this tool; the separate mood summary still requires an explicit date range and still omits notes.
