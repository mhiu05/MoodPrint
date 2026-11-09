# Quality closure: corpus provenance and database least privilege

Date: 2026-11-09. Worktree branch: `mhiu05/feat-refactor`; initial HEAD `2dde44dcac5eb57c061c362805dc612a542baa35`. This report describes the corpus/security workstream only. It does not replace the historical Phase 2/3 reports or the restricted internal-development decision DR-INT-02. No release or hosted approval is claimed.

## Result

- Three substantive legal-backed authored cards and two distinct source revisions added. New offline corpus: **57 documents, 80 chunks**, manifest SHA256 **`f5e14a3b96c14c8aed2ba3d144d29e680c52132861b18c470185a07e8343ffe8`**.
- The earlier corpus `kb-20261109-06` and its digest `95435827eccd150b77734f2a58a8c3fe03c7b684ece93d6cbc226fee49ed3eed` remain historical evidence. Existing source/card bytes and IDs were not edited. The root agent owns any new-version embedding, storage, publication and retrieval-quality measurements.
- A new forward-only migration removes the unused runtime write capability on `knowledge.source_confidential`; admin ingestion and authenticated corpus reads retain their existing paths. The historic schema migration is unchanged.
- A page-level human review queue exists, with every human field **PENDING**. No human proofreading, independent legal review or independent safety validation is claimed.

## Source audit and substantive additions

Full primary links, preserved-original hashes and limitations: [`agent/ingestion/legal/LEGAL-AUDIT-2026-11-09.md`](../../../agent/ingestion/legal/LEGAL-AUDIT-2026-11-09.md). Five additional official PDFs were downloaded without changing their bytes; the existing ND80 original was retained. No commercial mirror text was embedded.

The official [Child Law consolidation 108/VBHN-VPQH](https://vanban.chinhphu.vn/?docid=215227&pageid=27160) is now readable. Its first page identifies amendments including one effective 1 January 2026. Article 1 uses **under 16**; the new privacy/reporting cards do not extend that rule to all under-18 learners. The source is a distinct revision `vn-luat-tre-em-vbhn108-2025`, preserving the old excluded candidate ID.

The official signed [TT03/2026 text linked by the Government portal](https://xaydungchinhsach.chinhphu.vn/toan-van-thong-tu-03-2026-tt-bgddt-quy-dinh-quy-tac-ung-xu-cua-nha-giao-119260205093856491.htm) was visually read at PDF p3, Article 5(3)-(4), and p7, Article 15(1)-(2). It takes effect on 30 January 2026 and ends **Article 6 of TT06/2019**, not the entire circular. `vn-tt-03-2026-bgddt` supports the new teacher-duty card.

Legal-text reuse is now supported by primary official text: [Intellectual Property Law consolidation 160/2026/VBHN-LQ-VPQH](https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-160-2026-vbhn-lq-vpqh-470657.htm), Article 15(2), PDF p14 / Gazette printed p15. The exclusion concerns legal texts; it is not a licence for government-portal commentary, photographs or third-party page layouts. An earlier primary 155/2025 copy is retained as corroborating evidence; the 2026 consolidation is the latest one checked.

ND80's identity and original effective date are confirmed by its official page and preserved original. Full current-status confirmation is still OPEN: official national-registry property pages returned 403. The [4 November 2026 government briefing](https://media.chinhphu.vn/bao-luc-hoc-duong-khong-bao-che-khong-chi-xu-ly-noi-bo-102261104142652522.htm) discusses proposed amendments; this corroborates relevance, but does not certify that no amendment/repeal exists.

| New authored card | Source/locator | Added substance |
|---|---|---|
| `kb-legal-rieng-tu-duoi16` | 108/2025 Articles 1, 6(11), 21; PDF pp2,4,8 | Under-16 privacy boundary; disclosure consent from age 7; does not purport to state every data-processing rule |
| `kb-legal-bao-tin-xam-hai` | Articles 1, 51(1)-(3); PDF pp2,15-16 | Adult/organization reporting responsibilities, reception/verification and statutory national hotline; no invented number or deadline |
| `kb-school-nha-giao-tt03-2026` | TT03 Articles 5(3)-(4), 15(1)-(2); PDF pp3,7 | Teacher listening/support/reporting duties, unlawful disclosure prohibition and precise partial repeal of TT06 |

Each card separates statutory summary from MoodPrint practical suggestions. Each has an agent-only claim/source `_review` note; human and professional review remain pending. No padding, repeated paragraphs, invented endorsements, named-school rules, sanctions, legal-case conclusions or guaranteed outcomes were added.

Registry now has **15 candidates**: 3 `open_reuse`, 1 `authored`, 4 `reference_only`, 7 `unverified`. Thus **four usable sources still miss the six-source target**. Eighty chunks still miss 350. Existing excluded sources remain excluded. Source status, copyright permission, transcription fidelity and independent safety review are distinct checks.

## Database root cause and change

The historical `20261108190000_kb_schema.sql` granted `moodprint_api` INSERT/UPDATE/DELETE on the private-note table and installed unrestricted `ingest_writer`. Runtime retrieval switches explicitly to `authenticated`; it never reads or writes licence notes. Actual ingestion uses the loopback admin connection selected from `TEST_ADMIN_DATABASE_URL` in `knowledge/ingest/runtime.py`. Therefore the runtime write grants were unnecessary.

Created through pinned Supabase CLI 2.122.1 after discovering `migration new --help`:

`supabase/migrations/20261109132352_kb_fix_private_ingestion_privileges.sql`

The migration revokes every table and column privilege on this single table from PUBLIC, anon, authenticated, service_role and moodprint_api. It replaces `ingest_writer` with explicit deny policy `no_runtime_access` for moodprint_api. RLS stays enabled, the exact private-ingestion marker remains, and table ownership does not change. No new role, elevated function, schema exposure, broad grant, baseline-table change or destructive data mutation is introduced.

`14_schema_policy_manifest.sql` previously required an unused non-admin writer role. It now checks the actual ingestion architecture: owner/admin retains mutations, the owner is distinct from application/client roles, and no runtime/client table **or column** mutation grants exist. Its existing RLS/policy and no-client-policy requirements remain. The new pgTAP file also exercises allowed admin CRUD, denied runtime/client operations, unaffected public-source reads, and unchanged data after denial.

## Verification evidence

All local commands used synthetic data or public legal documents. This agent made no Voyage/OpenAI call, hosted migration, hosted publication, branch/worktree creation, commit or push. `.gitignore` was not changed.

| Check | Result |
|---|---|
| New `kb_02_runtime_privileges.sql` against pre-fix int schema, run by root before migration | **RED: 2 of 19 TAP assertions failed** (runtime catalog privileges; runtime INSERT got duplicate-key instead of permission denial). psql exit was 0, so TAP failures rather than process exit establish the regression. Other existing access/admin checks passed. |
| Source registry, repository licence/provenance/boilerplate and manifest digest tests | 7 passed |
| Affected offline suite: `uv run pytest agent/tests/knowledge backend/tests/knowledge scripts/tests/test_migration_scope_check.py scripts/tests/test_migration_order_check.py scripts/db/tests/test_migration_versions.py -q` | **204 passed, 21 deselected**, 8.57 seconds |
| `uv run python scripts/dev/migration_scope_check.py` | Exit 0, VERIFIED **7 phase migrations** |
| Scope/version tests separately | 83 passed |
| ruff check + ruff format check for new integration file | Exit 0; formatted |
| `uv run pyright agent/tests/knowledge/test_privileges_pg.py` | Exit 0, 0 errors / warnings |
| Two final offline `ingest build` runs | Exit 0; 57 documents / 80 chunks each; no serializer warning |
| Repeat-build byte comparison | `documents.jsonl`, `chunks.jsonl`, `report.json` all byte-identical |
| `git diff --check` on owned paths | Exit 0; checkout line-ending notices only |
| Final database pgTAP | Exit0:21files/479assertions PASS, including new19; clean final source chronology after the order checker reset |
| Migration order | Exit0:VERIFIED kb-first and ag-first, each reset from empty; source migration bytes unchanged |
| Full combined integration | Exit0:149passed/1563deselected;13new permission cases included |

The first corpus build exposed a quoted date in new card front matter, causing a Pydantic serializer warning. It was corrected to a TOML date before the final digest was frozen, and both final builds were warning-free. The official TT03 PDF reports duplicate `/Info` keys in pypdf; the cited pages were checked visually and the signed original was preserved unchanged.

Final build artifacts: `.local/corpus/quality-closure-build-1` and `-2` (untracked). `documents.jsonl` SHA256 `05b2cb8d01d6d84a0eb4bc252e56e8616863d7b4c5cf9c52d8264342f6cf467e`; `chunks.jsonl` SHA256 `8a76c03a773d231acd49f9162b7228b42230f8dbf7fe7cb2b214c147e2ac8d01`; report SHA256 `9955299899f2e13257c810cf8f72949e4f152db6b4a368f5041cb489b6a19076`.

## Remaining gates

- Clean-init, both migration orders, pgTAP479 and integration149 are now measured. Overall final-SHA regression/CI are recorded by root in the main closure report.
- The new corpus has not been given a retrieval-quality pass in this report. The old no-result failure remains historical evidence; root owns new-version measurements on its frozen dataset.
- ND80 current legal status and human proofreading remain unresolved; all older card wording and benchmark labels still need independent review.
- Six-source and 350-chunk targets remain unmet, without padding.
- Independent urgency dataset/safety review, live repeats/budgets, Voyage opt-out and real-student data approvals are outside this workstream and remain explicit gates. Nothing here changes PHASE_2, PHASE_3 or G_INTEGRATION to VERIFIED.

Integration setup correction: the first combined run had145passes/4failures because the new anon tests attempted SETROLEanon through moodprint_api, which correctly lacks that membership. The tests now switch the admin test session to anon, while runtime/authenticated checks still use actual runtime credentials. No role membership or grant was broadened. The complete suite was re-run,149passed.
