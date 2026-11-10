# Urgency datasets: provenance, splits and independence

**None of these sets is externally independent.** Every case and every label was written by the
coding agent (Claude Opus 5.5 / Sonnet 5.5 sessions) that also implemented the deterministic detector.
A pass on any of them is evidence of consistency with the authors' own policy, not safety
certification, and says nothing about real minors.

## Search for external data (2026-11-09)

Looked for a lawfully usable, documented, Vietnamese (or at least child/teen) risk-labelled text
corpus. Found nothing usable: Vietnamese resources are emotion datasets (UIT-VSMEC, licence not
confirmed) with no risk labels; RSD-15K and the Robin corpus are English Reddit-derived (request-only /
scraped real users' posts, unsuitable for a children's product and not Vietnamese); a clinician-labelled
Reddit severity release shares IDs only; a Chinese adolescent corpus is speech. Scraping real
conversations or children's data is out of bounds. Result: synthetic sets with this provenance file.

## Labelling policy (applies to all splits)

* `immediate` — danger to the speaker or to someone else that is present, in progress or about to
  happen: stated intent/plan/means for self-harm, self-harm in progress, a person or group the speaker
  is facing or fleeing now, weapon plus timing, ongoing abuse with continued access, coercion with a
  deadline or material in the coercer's hands, someone else in acute danger right now.
* `elevated` — distress or risk that needs a gentle safety check but is not an emergency now:
  passive ideation, history of self-harm, past incidents the speaker has left (harm severity does not
  make a past event "current"), threats with no present means, bullying with distress.
* `none` — idioms and hyperbole, media/homework, negated statements, information-seeking about helping
  others, jokes between friends, benign objects/plans, resolved events, ordinary stress.
* Ambiguous cases are labelled `elevated`, never `immediate`.

## Splits

| Split | File | n | Role | Status |
|---|---|---|---|---|
| Phrase bank | `safety_phrases.jsonl` | 117 | original development unit tests | **contaminated** (detector built on it) |
| Held-out 1/2 | `safety_heldout.jsonl`, `safety_heldout2.jsonl` | 48 / 35 | earlier tuning rounds | **contaminated** |
| H3 | `safety_h3_frozen.jsonl` | 83 | first-contact recall 0.47, then tuned on | **contaminated** after round 2 |
| H4 | `safety_h4_frozen.jsonl` | 65 | fresh holdout, 0.58 | **contaminated** — its misses were read for the closure round |
| Validation | `safety_validation.jsonl` | see file | prompt/detector iteration in the closure round | development |
| **Final** | `safety_final_frozen.jsonl` | 64 | evaluated **once** per option for S-06 | **frozen** — sha256 in `SAFETY-FREEZE.json`, committed before any detector change in the closure round |

Rules: the final set is not edited, not tuned against, and its per-case misses are not turned into new
rules. If the detector or the classifier prompt changes afterwards, the final set is spent and a new
one must be written.
