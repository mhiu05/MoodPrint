# Global 18+ implementation and release plan

The approved owner request is the specification for this execution. MoodPrint
requires self-declared adult eligibility throughout the application. Birth year
alone does not establish the exact birthday; the eighteenth year requires an
explicit adult attestation. Existing unambiguously eligible adult declarations
remain usable. No government identity verification is implied.

## Constraints

- Preserve unrelated working files, `.gitignore`, and companion planning documents.
- Preserve Friendship Discovery behavior, data, separate publication consent and legacy clients.
- Never deploy, create a PR, merge, force-push, or rewrite published commits.
- Hosted 0020 requires verified identity, backup/restore, rehearsal and compatible traffic.
- Keep secure export, withdrawal, reauthentication, logout and deletion available.

## Execution checklist

- [x] Fetch remote, verify unpublished ancestry, snapshot unrelated files and create backup ref.
- [x] Create a review branch while preserving the original branch and working tree.
- [x] Backend: observe failing adult/session/guest/privacy tests, enforce persisted declaration checks, then pass.
- [x] Frontend: update signup, guest and eligibility copy/guards, preserving existing unrelated edits; test denial recovery.
- [x] Social and AI background work: validate both actors and peers against declarations; test missing/invalid declarations.
- [x] Rehearse real 0019 to 0020 with PostgreSQL and inspect hosted identity/schema/ACL/traffic read-only.
- [x] Run full applicable pytest, frontend, browser, fullstack v1/v2, contracts and quality checks.
- [x] Independently review security, compatibility and final diff; resolve important defects.
- [x] Split unpublished Friendship changes and new policy changes into coherent commits.
- [x] Record evidence and rollout dependency; prepare branch push, remote-SHA and CI checks.
- Delivery SHA and CI outcome are recorded in the final response after the remote operations.

## Review focus

Stale teen sessions must not open personal APIs. A fabricated adult band without
a valid declaration must fail closed. Ambiguous eighteenth-year declarations must
require confirmation. Ineligible published peers must disappear without deleting
their profile. Privacy operations must remain owner/session protected and usable.

## Coordination

The primary agent owns backend auth/security/contracts/guest and privacy changes,
integration testing, Git and the rollout document. Independent agents own frontend,
social/background eligibility and hosted migration audit/rehearsal. Only the primary
agent stages, commits or changes branches. Scratch evidence lives outside Git in
`.tmp/18plus-release`; test databases are individually owned loopback containers.
