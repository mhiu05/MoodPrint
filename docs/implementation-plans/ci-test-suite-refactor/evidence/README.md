# Evidence scope

Snapshot source: branch `test/11-2`, commit `a3af3d4cef1c7de75b2ec2b65ea5743640fbb853`, 2026-11-02 (Asia/Bangkok).

GitHub JSON contains public run/job metadata and step timestamps, not secrets or full logs. Local collectors list tests without running browser flows or database fixtures. Playwright list reports use `skipped` for unexecuted tests; those values are collection counts, not evidence of CI skips. Source heuristics in the inventory are explicitly separated from collected node IDs and measured runtime.

Generated files can be refreshed with the commands in [validation](../07-validation-and-benchmark-plan.md). These tools read tracked source and write only explicitly selected audit outputs. No production writes, migrations, deployments or live AI calls belong to this audit.
