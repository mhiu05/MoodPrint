# Retrieval quality closure

Code delivery SHA: `e831a31d935aeb363f9e7689e21b31782e072568`; measurements identify their source SHA plus normalized source hashes. Branch `mhiu05/feat-refactor`. No original result or label was overwritten.

## Root cause and architecture

Query normalization uses NFC, redaction and a 300-character embedding cut; lexical queries use safe folded tokens and IDF coverage. Voyage cosine normalization, vector/lexical candidate counts 40, RRF/blend, query-level relevance gate, lower candidate floors and per-document cap 1 were inspected. The v2 locked gate lets a single high topical candidate open the query and retains lower-floor neighbours. This cannot establish whether a document states a requested penalty, local procedure, directory entry or foreign law. Source/citation integrity only proves provenance, not answer support.

Baseline reproduced on the exact original corpus06 (54 documents/74 chunks, manifest 95435827...): v2 test Recall@5 = 0.869444 and no-result 10/18, matching the historical report. The same embeddings were reused, with zero query calls for that reproduction. Existing source bytes, model voyage-4, lexical/vector thresholds and scoring configuration were preserved.

`shared/knowledge_support.py` is a versioned, deterministic requirement catalogue (`evidence-support-v2`), shared through a data-only Evidence protocol. It evaluates the complete original question before the embedding cut and filters candidates before ranking. It requires a positive same-chunk statement for requested monetary amounts, criminal age, transfer procedure, workplace scope and legal deadlines; rejects unverified current legal status, unsupported institution/directory/clinical scope and incompatible jurisdiction metadata; distinguishes national hotlines from a local directory. Negative coverage disclaimers and unrelated dates/hotline numbers are not numerical evidence. General safety advice retains the calibrated relevance gate. No benchmark IDs, new judge, network pipeline, threshold increase or reranking service was introduced.

Companion checks the original user question even if the model generalizes the search query. Masked requirements survive private approval checkpoints. `knowledge_search` policy version 2 invalidates older private checkpoints that lacked that binding. Unsupported/empty retrieval and provider failures yield an empty citation ledger and a fixed insufficient-information answer with an official-source/trusted-authority next step. Exact-fact SSE text is buffered until final resolution. The frozen KnowledgeRetriever and API contracts are unchanged. Hub empty-state copy explains insufficient evidence. Unit, vertical-slice and browser tests cover missing penalties, foreign law, no source, forged markers and no-search fabrication.

## Every previously failing no-result test query

Top candidate below; the JSON artifact `agent/evals/knowledge/results/closure-regression-v2-corpus06.json` preserves all five ranked candidates, full chunk text, vector/lexical/rank scores and support decisions for every no-result query. Expected=no_results; actual old gate=ok in each row. None of these chunks states the requested answer. Ranking/gating is the failure layer; corpus absence is the underlying coverage limit.

| ID / query | Retrieved document / chunk | cosine / lexical | Correction |
|---|---|---|---|
|N006 — cách xóa tin nhắn rác cho đỡ đầy bộ nhớ điện thoại|`kb-evid-luu-truoc-khi-chan` / `kb-evid-luu-truoc-khi-chan#000-10d2cae1`|0.4729 / 0.4053|unsupported_task; reject unsupported scope, retain general guidance for answerable requests|
|N007 — xem phim hành động mới nhất|`kb-cyber-anh-rieng-tong-tien` / `kb-cyber-anh-rieng-tong-tien#000-2250845f`|0.1438 / 0.4593|unsupported_task; reject unsupported scope, retain general guidance for answerable requests|
|N020 — dịch câu này sang tiếng anh giúp mình|`kb-excl-ep-lam-theo-nhom` / `kb-excl-ep-lam-theo-nhom#000-297b2c6d`|0.2447 / 0.2316|unsupported_task; reject unsupported scope, retain general guidance for answerable requests|
|N021 — mức phạt tiền cho học sinh đánh bạn là bao nhiêu|`kb-legal-khi-nao-bao-cong-an` / `kb-legal-khi-nao-bao-cong-an#001-0e5ff567`|0.5243 / absent|monetary_amount_missing; reject unsupported scope, retain general guidance for answerable requests|
|N024 — thủ tục chuyển trường khi bị bắt nạt|`kb-legal-khi-nao-bao-cong-an` / `kb-legal-khi-nao-bao-cong-an#000-5a6f63e3`|0.5868 / 0.0525|transfer_procedure_missing; reject unsupported scope, retain general guidance for answerable requests|
|N025 — bắt nạt ở nơi làm việc thì xử lý thế nào|`legacy-bat-nat-la-gi` / `legacy-bat-nat-la-gi#000-50deb720`|0.5018 / absent|workplace_missing; reject unsupported scope, retain general guidance for answerable requests|
|N027 — luật chống bắt nạt học đường ở Mỹ quy định gì|`kb-def-ba-dau-hieu` / `kb-def-ba-dau-hieu#001-bb17eea8`|0.5380 / 0.3024|jurisdiction_mismatch; reject unsupported scope, retain general guidance for answerable requests|
|N028 — số điện thoại hiệu trưởng trường mình|`kb-help-chon-nguoi-nao` / `kb-help-chon-nguoi-nao#000-6e5f0e30`|0.4325 / 0.0000|local_directory_unavailable; reject unsupported scope, retain general guidance for answerable requests|

## Development and final protocol

Only the already inspected v2 development 72 queries were used for tuning. Initial support code caused two false negatives: `theo phap luat` accidentally matched the country France without a word boundary, and an emergency-number query was confused with a local directory. Paired counterexamples corrected both before final evaluation. Dev Recall@5 returned to 0.8611 with no-result 12/12. Reviewer-authored hotline and checkpoint tests were added before final evaluation; they are another AI review, not independent human validation.

V3 was frozen in commits 478ae301/c1a71fc0 before its first evaluation; the second commit corrects a Windows CRLF-vs-LF hash error without changing any case/label. LF hash `ad457c367dd883eefe10b0b98e8efcbd69969a3ff59d73f03222432a18f8dc84`. There are 120 queries: 90 answerable from 30 seed situations×3 correlated styles and 30 no-result (20 in-domain / 10 out-of-domain). Labels name one primary answer-bearing document, not an exhaustive pooled set. The same coding agent authored labels and support rules. It is not independent validation or a newly unseen test authored elsewhere. Existing v2 test is openly regression data. No labels changed after final results.

Corpus07 is 57 documents/80 chunks, manifest `f5e14a3b96c14c8aed2ba3d144d29e680c52132861b18c470185a07e8343ffe8`. The pre-registered methods were evaluated once. Production selection stayed locked vector-led ranking plus evidence support; final results did not select a new method. Rerank-3 and alternate embedding models remain NOT_RUN because authorization names only voyage-4.

| V3 method | Recall@5 | Recall@10 | MRR@10 | nDCG@10 | P@1 | no-result | false-no-result | citation integrity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|topic_only|0.9889|0.9889|0.8861|0.9126|0.8000|14/30|0.0111|1.0000|
|locked|0.9889|0.9889|0.8861|0.9126|0.8000|30/30|0.0111|1.0000|
|A_lexical_only|0.2556|0.5222|0.1366|0.2246|0.0333|30/30|0.1667|1.0000|
|B_vector_only|0.9889|0.9889|0.8861|0.9126|0.8000|30/30|0.0111|1.0000|
|C_hybrid_rrf|0.9444|0.9778|0.7762|0.8268|0.6333|30/30|0.0111|1.0000|
|Cprime_blend|0.9444|0.9889|0.8221|0.8636|0.7111|30/30|0.0111|1.0000|

Locked result: Recall@5 = 0.9889 (89/90), no-result 30/30, false-result rate 0/30, binary precision among returned queries 89/89; P@1 = 0.8000 is document precision, not the binary measure. Citation integrity 889/889 checks. One false negative remains `V3A22-3` (unaccented property-damage/cap-sac question), recorded without retuning. No false positive observed on the 30 negatives. All required point-estimate targets pass.

Bootstrap 95% Recall@5 [0.967, 1.000]; no-result bootstrap [1, 1] is degenerate at 30/30, so Wilson 95% [0.8865, 1.000] is also reported. Correlated positive variants and self-authored labels make these optimistic descriptive intervals, not population assurance.

Historical v2 test, exact corpus06: topical-only Recall@5 = 0.869444/no-result 10/18; supported Recall@5 = 0.869444/no-result 18/18. V2 test on new corpus07: topical-only Recall@5 = 0.875/no-result 10/18; supported Recall@5 = 0.875/no-result 18/18. Full 180-query corpus07 regression: Recall@5 = 0.8661, Recall@10 = 0.9028, P@1 = 0.8000, false-no-result 0.0533, no-result 30/30, citation integrity 1387/1387. Full results for every method and all errors are preserved separately.

## Supplemental full-distribution V4 (no retuning)

V3 actual primary-topic coverage was 13, not the 14 intended in its original registration (missing `verbal-social`); its labels and outputs are preserved. V4 was designed after seeing V3 coverage/results, then frozen in commit `040816f8ec38c68dc2eb7d45ac5ac4d5653e80c7` before its first retrieval. It is not an untouched holdout. LF SHA256 `1f114eaf6408525c4046e2e8a01435abe9cba44426d5367f19ad833f18b0aafa`. There are 180 queries: 150 positives from 30 situations x 5 correlated variants, and 30 negatives (10 in-domain gaps / 20 out of scope). All 14 topics and original positive style counts are represented: standard 50, nodiac 35, slang 30, narrative 25, English 10. Four groups have pre-labelled secondary evidence; labels are not exhaustive independent pooled judgements. Same coding agent authored cases/labels.

Production remained locked; neither labels, thresholds, support code nor method selection changed after V4 results. The complete artifact `agent/evals/knowledge/results/closure-final-v4.json` pins source SHA `040816f8`, normalized source tree, corpus and dataset. All six methods completed all 180 cases. The original process handle expired across session continuation, so its final shell exit receipt is unavailable; the complete parseable report and settled original ledger are preserved. A later cache-only reproducibility attempt exited 1 before evaluation because Docker was off (`ConnectionRefusedError`); it made zero provider calls and did not overwrite results.

| V4 method | Recall@5 | Recall@10 | MRR@10 | nDCG@10 | P@1 | no-result | false-no-result | citations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|topic_only|0.9600|0.9667|0.9089|0.9221|0.8600|20/30|0.0333|1.0000|
|locked|0.9600|0.9667|0.9089|0.9221|0.8600|28/30|0.0333|1.0000|
|A_lexical_only|0.1733|0.3700|0.0945|0.1596|0.0267|29/30|0.3533|1.0000|
|B_vector_only|0.9333|0.9400|0.8822|0.8954|0.8333|29/30|0.0600|1.0000|
|C_hybrid_rrf|0.9267|0.9600|0.8786|0.8844|0.8200|28/30|0.0267|1.0000|
|Cprime_blend|0.9567|0.9667|0.9156|0.9187|0.8667|28/30|0.0333|1.0000|

Locked V4: 144/150 positive queries have a labelled document in top 5, 145/150 in top 10; five return no results (3.33%), and one returns related documents with the expected evidence at rank 6. No-result accuracy is 28/30 = 0.9333, in-domain 9/10, OOS 19/20; false-result rate is 2/30 = 0.0667. Binary answerable-query precision among returned queries is 145/147 = 0.9864; the more demanding top-5 evidence precision is 144/147 = 0.9796. P@1 = 0.86 is a document-ranking metric. Citation integrity is 1461/1461. Required point targets pass without rejecting most positives, but the errors below remain real gaps.

Seeded per-query bootstrap 95% Recall@5 [0.927, 0.987], no-result [0.833, 1.0]; a supplementary 10,000-resample bootstrap of the 30 positive seed means (seed 20261110) gives [0.9267, 0.9867]. Wilson no-result 95% [0.7868, 0.9815]. Correlated template variants, only 30 negatives and same-author labels limit inference; point-estimate success is not population assurance.

| V4 error | Query | Actual / failure class |
|---|---|---|
|V4A12-3|thấy post bêu bạn, giúp sao mà ko làm nó viral thêm?|no_results; positive false abstention|
|V4A15-3|định block nick dọa t, lưu trước hay block trước, backup đâu?|no_results; positive false abstention|
|V4A16-3|muốn up phốt bằng chứng với nhờ bạn đoán pass nó, ổn ko?|no_results; positive false abstention|
|V4A21-3|an toàn r mà vẫn run, thở sao với tập trung hiện tại kiểu j?|no_results; positive false abstention|
|V4A22-4|Mình đang tìm cách xử lý chuyện này và chưa biết bắt đầu từ đâu. Sau chuyện bắt nạt em nhiều ngày không ăn ngủ và sợ ở một mình; lúc nào phải nhờ giúp ngay?|Expected evidence at rank 6; top-5 ranking miss|
|V4A30-3|đứa hay chặn t đang chờ cổng, ở đâu với về sao cho an toàn?|no_results; positive false abstention|
|V4N05|Trường THCS Ánh Sao quy định đình chỉ học mấy ngày cho việc đánh nhau?|ok with unsupported related documents; false result|
|V4N29|Tối ưu pin điện thoại khi học trực tuyến bằng cách nào?|ok with unsupported related documents; false result|

The named-school false positive exposes order-sensitive institution recognition (school name precedes `quy định`), and the battery request is outside the bounded task catalogue; high lexical coverage can still open the gate. Its top battery result has cosine 0.4010, while a lower family-plan candidate has lexical 0.6474. The school top chunk explicitly disclaims school-specific rules (cosine 0.5558) but receives `supported_scope` because the requirement was not recognized. Neither provides the requested fact. Original candidate text/scores/reasons remain in `no_result_diagnosis`. These failures can also escape the precise-question buffer in Companion; generic answerability is not solved. Future correction needs new development data and another pre-registered final evaluation, not relabelling this final set.

Five slang no-result errors and one narrative rank-6 miss remain. All six also fail top 5 under the topic-only comparator, so support filtering did not cause these answer-preservation losses. Slang Recall@5 is 25/30 = 0.8333; standard, nodiac and English are 1.0; narrative is 24/25 = 0.96. Cached locked timing is p50 52.4 / p95 85.5 ms. Topic-only timing includes first-time provider misses and is not a cache-only comparison.

## Latency, spend and limits

Fresh-provider timing used every sixth frozen V3 case (20 queries, 5 warmups, 3 repetitions=60 measurements): p50 355.7 ms/p95 759.6 ms, 65 Voyage calls including warmups, 1200 tokens. This measures authenticated PostgreSQL, live embedding and evidence support. Locked cached timing in the final comparison was 65.6/116.8 ms; the first topic-only method populated 120 query embeddings and its mislabeled cached fields include provider misses (302.8/357.7 ms), so do not compare those fields as like-for-like cached timings. The separate live latency artifact is the appropriate end-to-end evidence.

Existing cumulative Voyage ledger is unchanged in cap/model/scope; recorded spend before V4 $0.00758214/$1.00, reserved 0. Corpus embedding reused 74 vectors and embedded 6 new chunks in one call (1065 tokens,$0.00006390). V3 query embeddings 120 calls/2369 tokens; live timing 65 calls/1200 tokens; v2 corpus07 restorer cache required 2 additional query embeddings (19 tokens). No OpenAI judge/call was used. After the supplemental V4 run, cumulative spend is $0.00784422/$1.00, with zero reserved; V4 added 180 embedding calls / 4368 tokens / $0.00026208. This task totals 368 Voyage calls / 9021 tokens / $0.00054126 above the actual starting ledger.

Remaining limits: this bounded catalogue is not a general semantic-entailment proof. Unknown jurisdictions/institutions, ambiguous references, multi-chunk evidence and future numerical claims need further labelled coverage. General advice still uses topical ranking. A valid citation does not guarantee every sentence the model generates is entailed. No new expert/human corpus or label review occurred. Six usable sources, 350 chunks and legal/human-review conditions remain unmet, so PHASE_2 stays NOT_VERIFIED despite these measured retrieval targets.
