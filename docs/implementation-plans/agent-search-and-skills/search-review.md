# Independent search and skills review — 2026-11-03

Reviewed the working tree against HEAD and plans 00, 02, 03 and 04. Scope includes
search/skills, direct runtime/provider/protocol/history, migrations 0025–0027,
Maps worker and financial lifecycle. This is a review of an actively changing
working tree; the implementer received important findings immediately and has
already changed several affected paths.

No real `.env`, secret, provider, AWS or hosted database was accessed. No DB test,
commit, `.gitignore` change or product-code edit was made by the reviewer. Pure
Python/ScriptedModel and Node URL experiments used synthetic data only.

## Status update — 2026-11-03 (continuation session)

The four findings below were re-verified against the current source and are **resolved**;
the original text is kept as the review record.

| Finding | Current code | Regression (fake/disposable PG) |
| --- | --- | --- |
| R1 | `policy.safe_query` copies zero user words: closed topic labels, a public gazetteer place and a time label only; `private_prompt` refuses disclosures; unregistered topics return `unsupported_topic` (no paid attempt) | `test_web_search.py` private/unsupported/slot cases incl. both inputs quoted below |
| R2 | `source_backed` persisted on every bot bubble of a search turn; `history_protocol` redacts by marker | `test_uncited_sibling_page_is_redacted_for_old_clients_but_exported_in_full` (page holding only the uncited sibling, default and explicit protocol 2, SSE v1/v2, export) |
| R3 | `context.model_messages` stops ordinary history at the source-backed boundary | `test_search_turn_boundary_cannot_launder_sources_into_ordinary_history` |
| R4 | `public_https_url` rejects alternative numeric IPv4 forms | `test_untrusted_citation_url_rejected` with hex/octal/short/decimal/mapped forms |

R8 has an explicit interleaving regression:
`test_late_start_ref_after_lease_takeover_is_aborted_and_cleaned_without_replay`.

## Findings at review time (now resolved, see status above)

### R1 — P1: the public-query projection still passes private third-person disclosures

Location: `backend/app/ai/search/policy.py:safe_query` (line 13), called by
`search_intent`; `search/turn.py:prepare_turn` forwards its result to
`WebSearchService`, and `search/web.py` uses it directly as Responses `input`.

The implementation passes the entire normalized prompt once a keyword blacklist
accepts it. It does not construct the minimized public topic required by plan 02.
The initial implementation passed this exact synthetic input unchanged:

```text
Find the latest treatment options for my daughter Alice Nguyen diagnosed with HIV
```

The implementer added English relationship/diagnosis terms and Vietnamese
third-person checks. After that change, a pure test still returned the following
synthetic private statement unchanged:

```text
Tin mới nhất về cách giúp bé Lan bị bạo hành ở trường Nguyễn Trãi
```

The public topic could be supporting a child experiencing school abuse; the
child's name, school and disclosure should not become a public-search query.
Manual Web selection guarantees this accepted value reaches the child adapter.
Adding keywords only closes individual examples, so this remains open pending a
conservative public-topic projection or refusal outside recognized safe forms.

Regression: spy on the fake Web adapter for both inputs; assert no personal
statement/name/school is dispatched. If a minimized query cannot be formed, return
`needs_query` without making a paid search attempt.

### R2 — P2: legacy history redacts individual bubbles, allowing uncited siblings through

Location: `backend/app/ai/schemas.py:history_protocol` (line 357) and
`backend/app/ai/search/citations.py:render_grounded_reply` (line 24).

The grounded renderer requires at least one citation across the whole reply, but
does not require a citation on every bubble. This is a valid grounded reply:

```python
GroundedReply(messages=[
    {"segments": [{"text": "Uncited factual first bubble.", "sourceIds": []}]},
    {"segments": [{"text": "Cited second bubble.", "sourceIds": ["s1"]}]},
])
```

With a real backend `s1` registry entry, rendering succeeds. A pure reproduction
then passed the resulting two AIMessage objects through `history_protocol(...,
2)` and observed the first text unchanged. SSE correctly replaces the entire
turn, so reload/history behaves differently from live/replay. Pagination makes
inspecting only siblings present in the response insufficient.

Persist or derive a source-backed marker for the whole authoritative run and
apply it to every bot bubble in that run. Regression should cover default2
history and a page containing only the uncited sibling, as well as protocol3 and
full-fidelity export.

### R3 — P2: subsequent ordinary turns lose historical search provenance

Location: `backend/app/ai/chat_routes.py` lines 486 and 522; context projection in
`backend/app/ai/context.py:model_messages`, `turn_messages` and `build_history`
(lines 52, 83 and 101).

Search turns retain `TEXT_POLICY`. Ordinary subsequent turns therefore include
their assistant prose in history. `turn_messages`/`build_history` discard
citations and cards, leaving searched claims as plain assistant text. A pure
projection reproduction produced:

```python
[
    {"role": "assistant", "content": "Uncited factual first bubble.\n\nCited second bubble."},
    {"role": "user", "content": "Repeat the previous answer"},
]
```

A normal, including protocol2, follow-up can repeat those claims through the
non-grounded output contract with neither citations nor a source-backed marker.
The legacy output guard then has no metadata with which to replace the reply.

Use a fail-closed context boundary for earlier search-derived turns, or a
source-aware continuation that retains backend source authority. Add an
end-to-end fake test: cited search → ordinary repeat/summarize request → legacy
history/replay must not expose the searched facts as unmarked prose.

### R4 — P2: browser numeric-IP forms bypass the public citation URL policy

Location: `backend/app/ai/schemas.py:public_https_url` (line 59), especially the
`ipaddress` fallback around line 71.

Pure Python accepted both `https://0x7f.1/` and
`https://0x7f.0.0.1/`. Pure Node `new URL(value).href` canonicalized both to
`https://127.0.0.1/`. The fallback rejects decimal-only hosts but accepts hex IPv4
forms as DNS names. A citation can consequently navigate loopback despite the
public-HTTPS contract. There is no backend URL fetch, so this is a link-safety
violation rather than demonstrated server-side SSRF.

Reject alternative numeric IPv4 encodings or normalize/classify their browser
meaning before accepting a host. Regression should cover hex loopback/private
forms alongside the existing decimal, IPv6, localhost and credential cases.

## Important findings repaired during this review

These were reported promptly. The current tree was re-read to confirm the stated
code changes; DB-dependent regression execution belongs to the implementer.

### R5 — P1: journal branches bypassed source-authority validation

Original location: `provider.py` early `journal_mode` returns, before the generic
`SEARCH_PROVENANCE_REQUIRED` guard. `NhipReply`/`NhipOutput` inherit cards including
`places` and `maps_search`; journal rendering passed cards unchanged.

A pure ScriptedModel reproduction, with `ai_multi_message_enabled=True`,
`bot_id="nhatky"`, `context.sources={}`, no search and a fabricated PlacesCard,
returned `unsearched_nhatky_accepted_card: places`. The fake venue included an
invented address, 4.9 rating and Google Maps URL and received the default Apify
provider label. It could have been persisted and displayed as sourced data.

Current tree routes journal, mood and generic non-search branches through the
shared `search_free_reply` check. The implementer also corrected a regression
fixture so journal evidence validation does not reject the fixture before the
search guard is exercised.

### R6 — P1: expired/cancelled Maps jobs could never reach vendor cleanup

Original location: `maps_jobs.py:advance_one` branch ordering.
`authorized()` rejects expiry/cancellation, setting `cancelled=True`. The
cancel/abort branch preceded `cleanup_due`, so every expired user-owned job took
abort/status forever and never deleted its input/dataset/KV/queue/run metadata.

Current tree checks `cleanup_due` first, and successful cleanup clears vendor ref
and scope/session/conversation identifiers. The implementer reports an expired
job regression with a failing-before/passing-after result.

### R7 — P2: partial cleanup retries were stopped by DELETE 404

Original location: `search/apify.py:_request` and `cleanup` (lines 36 and 117).
Cleanup deletes multiple vendor resources sequentially. A successful first
DELETE followed by a crash/error made the next attempt stop on the already
deleted first resource, leaving later resources indefinitely.

Current tree treats DELETE 404 as an idempotent success, allowing cleanup to
continue through queue, dataset and run metadata.

### R8 — P2: late start refs were stranded after lease takeover

Location: `maps_jobs.py:start_search.save_ref` (around line 88).
If a starter stalls after the paid start until its 30-second lease expires, a
worker may recover the no-ref row and set `cleanup_done=True`. A late starter
then stores the known vendor ref and marks cancellation on fence mismatch, but
the previous implementation left `cleanup_done=True`; workers would never select
the retained ref for abort/cleanup.

Current tree resets `cleanup_done=False` whenever a non-null late ref is stored.
The result remains cancelled rather than revived. A regression should explicitly
interleave no-ref lease takeover with late ref publication, then prove the
worker cleans that ref without calling start again.

## Financial and lifecycle observations

- Search claims use the common budget advisory lock, and global budget readers
  route through `budget_liability`, including proactive and orchestration readers.
- Web admission clears the provisional external token fallback before atomically
  reserving the child AiUsage row. Global liability counts attached child tokens
  through AiUsage; the search subset counts them through its join. This avoids
  an obvious double reservation/double count on the inspected path.
- Unknown provider usage retains the conservative token reservation and external
  fee liability; expired recovery does not re-dispatch Web. Maps workers poll,
  abort, read and clean known refs and contain no actor start/model call.
- Financial rows detach rather than cascade on account deletion. The fallback
  token amount and uncertainty marker allow liability to survive deleting the
  child usage/run. No definite financial undercount was established in this
  read-only review. The existing cross-midnight test covers a detached fallback,
  not every attached/detached lifecycle combination.
- Maps reuse appends a backend PlacesCard to the user-initiated follow-up reply,
  so saved replies persist normalized places while temporary chat results remain
  in RAM/vendor storage. Jobs do not create a new model call after completion.

Suggested remaining financial regression matrix: attached settled/uncertain
child; detached child/run deletion; account tombstone; midnight crossover;
feature off; recovery and metadata retention. Assert global and subset totals
separately and exact once-counting, using disposable DBs/fakes only.
