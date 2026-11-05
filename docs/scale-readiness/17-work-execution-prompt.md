# Prompt to paste into ChatGPT Work

Implementation commit: `ed75c4a1fbef462f33ad5389e0615b9afaa4b6da`. Normal push verified by
`git ls-remote origin refs/heads/feat/upgrade-user` returning this exact SHA.
This prompt is published in a later documentation-only commit; the branch tip is
therefore expected to differ. Verify the implementation commit remains its ancestor.

---

Continue MoodPrint execution using this shared repository:
https://github.com/mhiu05/MoodPrint/tree/feat/upgrade-user

Pinned implementation SHA: `ed75c4a1fbef462f33ad5389e0615b9afaa4b6da`
https://github.com/mhiu05/MoodPrint/commit/ed75c4a1fbef462f33ad5389e0615b9afaa4b6da

First read `docs/scale-readiness/16-work-handoff.md` on that branch, then12–15 and
18–20. Use GitHub, not the local Windows directory. Confirm the pinned implementation
commit is an ancestor of the branch tip; later documentation commits do not change
the tested application source. Record the actual branch SHA and time of your read.

Use supported connectors/APIs first, browser tools where those cannot provide the
needed configuration. Open AWS Console in ap-southeast-2, Supabase Dashboard,
OpenAI Platform, and GitHub. Verify each account/project fingerprint from16 before
reading or changing anything. Do the authorized read-only investigation across all
sites and keep progressing when one site is blocked.

Your cloud browser has a separate login session from the owner's Chrome. Ask the
owner to use secure sign-in/MFA when needed. Never ask for passwords, API keys,
SMTP credentials, database passwords or recovery codes in chat. If access to the
existing Chrome session is necessary, use a supported Chrome integration with user
permission. Do not assume your browser can access `E:\MoodPrint`, local terminals,
Docker, private vault files or unpublished artifacts.

Current facts:application URL stays https://moodprint.duckdns.org. AWS…3536/Sydney
staging instance i-0664d6ea5930452db is already running m7i-flex.large with EIP13.210.93.93;
SSM diagnostic succeeded, four containers healthy, readiness200. No Start is needed.
SES remains sandbox200recipients/day and1/s with one verified Gmail identity. Supabase
project fingerprint44a655e04517 is Pro/Tokyo; actual compute/pooler/backup/SMTP/Auth
limits require dashboard verification. OpenAI project/account limits and exact pricing
are not established by the earlier successful gpt-6-luna model lookup.

Perform16 sections1–10 in dependency order:

1. Read SES access/quotas/reputation, existing sender identity and current DMARC/provider
   policy. Prepare an honest transactional production-access request; do not submit it yet.
   Verified Gmail may satisfy SES identity authorization after production access, but
   cannot by itself prove aligned, reliable public mail. Do not buy a domain/service.
2. Read Supabase SMTP, confirmation, CAPTCHA, Auth limits, redirects and forwarding.
   Preserve confirmed signup and all abuse controls. Prepare exact config diffs only
   after sender/quota facts are known.
3. Read OpenAI staging-project model access, RPM/TPM/shared limits, billing, service tier,
   input-count access/fees and account pricing. No generation as a quota probe.
4. Prepare and obtain approval for the exact active postgres migration-password
   rotation in20. Runtime password differs; do not overwrite it. Verify new login,
   old rejection and runtime health through secure tooling; never expose either secret.
5. Read actual Supabase compute/pooler/backups and EC2 snapshots. The chosen policy
   is RPO24h/RTO8h, not achieved yet. Use18 to propose a priced encrypted independent
   backup generation and an isolated hosted recovery drill. DB backups do not include
   private Storage object bytes or all secrets/custom-role passwords.
6. Read CloudWatch metric delivery/dimensions and existing alerts. Prepare priced
   alarms/retention plus a named notification destination; do not send messages or
   activate subscriptions without approval.
7. Verify EC2 identity/type/status/EIP, aggregate traffic role, CPU/memory/cgroup/OOM,
   restart history and current billing/credits. Do not restart, resize or deploy an
   unreviewed image. M7i-flex has different CPU economics from T3.
8. Prepare the exact controlled hosted Auth/email canary manifest. Existing Gmail
   controlled tests may use only permitted verified recipients within SES restrictions;
   new hosted account/SMTP/policy/cohort writes need the explicit confirmation in16.
9. Return required coding facts to a coding environment:pooled parent/child financial
   accounting, all-paid scopes, exact-count/immutable-payload/one-wire campaign adapter,
   sustained-load, network SSE, mixed/fault and active-turn deployment tests are still
   engineering work. A browser setting cannot fix them.
10. Only after the actual safety prerequisites pass, use the already approved cumulative
    **$3** staging evaluation campaign, **gpt-6-luna only**, no additional judge API.
    Use one durable campaign ledger, preserve unknown/crash liability, never reset
    totals, and have the coding agent evaluate saved synthetic outputs directly.
    Report the tested scope if the full50concurrent/900s real profile cannot fit$3.

Read-only/local work is authorized. Named conditional Start was authorized but is
already satisfied. Before every other consequential change—including SES submission,
SMTP/Auth policy/DNS/sender changes, credential reset, DB migration, paid backup,
production deployment, budget activation or infrastructure upgrade—present the exact
target/diff/cost/downtime/verification/rollback and obtain specific owner confirmation.
Mark these **REQUIRES_OWNER_CONFIRMATION**. Prior $50/day target,50registered AI turns,
approved $3 cumulative campaign and delegated technical recovery policy do not need
to be asked again. They do not authorize production activation.

Do not merge into main, force-push, rewrite history, change `.gitignore`, disable
confirmation/CAPTCHA, delete unrelated changes, replace production data, delete
backups or pretend a blocked operation succeeded.

For every action record UTC timestamp, task ID/status, redacted account fingerprint,
exact Console navigation/API, actual result, safe evidence, cost/liability, remaining
blocker, next executable step and rollback where relevant. Read back resulting state
before marking it complete. Keep source implementation, local mock benchmark,
target-size staging, real-provider validation and production deployment separate.
Update12–16 while preserving all41IDs. Review G00–G15 and keep release **NO-GO** until
the evidence and final release authorization justify a change.

Deliver a Vietnamese report with verified facts, completed/blocked actions, specific
approval proposals, test/financial evidence and updated GitHub links. Never use a
successful push or healthy idle host as proof of scale readiness.
