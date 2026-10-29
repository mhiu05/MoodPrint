# Nhịp journal integration

Status: NOT_STARTED. Extend `backend/app/ai/runtime.py::tools`, `provider.py`, `context.py` and private source-evidence types. Do not create a replacement assistant.

## Authorization and bounded retrieval

Only ordinary `bot_id == nhip` receives `search_journal_entries`. Arguments contain query<=80, optional dates and limit<=5; extra fields including user_id forbidden. Server uses run.actor + a fresh locked User, checks existing AI authorization/data version before and after retrieval and before publication. Exclude drafts, expired dates, other owners and media bytes.

`journal.service.search_for_ai(db,user,query='',from_date=None,to_date=None,limit=5)` returns actual IDs/revisions/date/mood/emotion/factor metadata and bounded snippets with truncation/coverage. Never place whole history in prompts. Retrieved prose is untrusted content, not instructions.

## Evidence and links

Ordinary Nhịp private output may include source_entry_ids; public `AiOutput` remains text/cards because `frontend/src/api/stream.ts` rejects extra fields. Backend validates every ID against current run evidence and appends `/self/entry/{UUID}` links. No read means no source claim. Forged IDs/URLs fail validation. Frontend `MessageMarkdown.tsx` currently strips anchors; add only a safe internal journal anchor renderer.

Explicit mood_scope turns continue using `MoodAnalysisPlan` and deterministic `render_mood_analysis`; do not mix the journal tool into that evidence schema. Other four assistant permission matrices stay intact. Legacy `Mood.note` never becomes journal evidence.

## Context and privacy

Mark turns that used journal evidence with a dedicated current-run context policy so saved derivative prose is not reused after source changes. Clear ephemeral evidence at terminal/finally and guest expiry. Journal writes increment user.data_version and invalidate runtime; remote-worker publication must also fence stale evidence.

Existing AI consent remains required, and an explicit current-turn refusal to read journals suppresses the tool. Default access does not enable MEM, semantic memory or history. Existing proposal/confirmation requirements remain. Do not diagnose, claim causality or invent memories; explain sampled coverage and insufficient data. No journal embeddings, automatic memory, media transcription or social disclosure.

Verification targets: owner-only tool fixture, dispatcher matrix, valid and forged citation IDs, provider fake-model round trip, source edit/delete/AI withdrawal during in-flight generation, context reload, legacy mood/context regressions and usable internal entry navigation.
