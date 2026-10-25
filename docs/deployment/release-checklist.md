# Release checklist staging — 25/10/2026

| Gate | Bằng chứng cần có | Trạng thái hiện tại |
| --- | --- | --- |
| Snapshot | PR #1 reviewed, changes merged to `main`, exact SHA includes app and deployment files | BLOCKED: PR #1 remains draft/open; do not merge before CI and EC2 prerequisites are ready. |
| CI | `Verify local application` succeeds on the exact main SHA; includes poller tests, workflow syntax, Compose and production image checks | IN PROGRESS on current PR head; require green run for the final branch commit and later a green `main` push run. |
| Release | GHCR images, digests, signed manifest, and source attestations exist for the current main SHA | NOT RUN: main has not received the release workflow change. |
| DB | Supabase target, backup/restore drill, revision 0010, Auth helper, grants, and migration SQL reviewed | PARTIAL: read-only probe saw revision 0010 and helper; backup/restore and privilege review remain. No DDL has been run. |
| IAM/infra | Existing EC2, SG, EIP, SSM, exact runtime access, poller install, and package access verified | PARTIAL: EC2/SSM resources exist; role still needs exact runtime `ssm:GetParameter` permission, poller is not installed, and GHCR access choice is open. Keep AWS Free Plan and ECR resources. |
| Secrets | SecureString exists; required variable names/shape validated without revealing values; no secrets in image | PARTIAL: Standard SecureString exists; EC2 retrieval permission and runtime startup have not been verified. |
| HTTPS/application | DNS, Caddy certificate, SPA refresh, readiness, auth, persistence, and release SHA verified | BLOCKED: browser HTTPS request was refused and no application containers have been deployed. DNS lookup could not be resolved from this workspace. |
| Features | Synthetic account checks for Auth, mood, matching, consent, messaging, privacy, SSE, mobile, AI/memory/Voyage/STT as enabled | NOT TESTED on staging. Keep AI/provider features off until configuration, consent, budget, and smoke tests are reviewed. |
| Operations | Poller cadence, deployment state, failed-CI behavior, rollback health, resource limits, and logs verified on EC2 | PARTIAL: code and unit tests are prepared; EC2 install, automatic release, rollback, and monitoring have not been proven live. |

After merge, each successful push to `main` starts CI; the release workflow publishes only after exact-SHA CI succeeds. EC2 detects the current verified release on its five-minute systemd timer. A failed CI run publishes no release; a failed health check makes `deploy.sh` attempt the previous healthy image pair. Do not report automatic CD as PASS until a real main release has been detected and deployed without manual intervention.

Routine deployment needs no Actions button, SSH login, or SSM command after installation. The owner-only `workflow_dispatch` path is a publication fallback, not a routine deployment step. Before the first live release, choose GHCR access, attach the narrow EC2 runtime policy, install and verify the poller, and confirm HTTPS readiness. Keep branch protection enabled if main pushes require review.

No deployment step runs Supabase migration or destructive DDL. See [CI/CD](github-cicd.md), [staging setup](staging-setup.md), [AWS poller operations](../../deploy/aws/README.md), and [rollback](rollback.md).
