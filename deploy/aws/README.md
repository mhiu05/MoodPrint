# AWS staging release poller

The workflow in `.github/workflows/deploy-staging.yml` publishes a prerelease only after the exact current `main` commit has a successful push run of `Verify local application`. It publishes digest-pinned GHCR images and GitHub attestations. This EC2 poller checks the current `main` SHA, release manifest attestation, CI run, publish run, and both image attestations before calling `deploy.sh`.

The EC2 instance needs Docker Compose, AWS CLI, Python 3, GitHub CLI 2.102.0 or newer, and its existing SSM managed-instance role. For the public repository, the poller reads attestation bundles from GitHub's unauthenticated REST API and verifies them offline with the GitHub CLI and a fresh Sigstore trusted root; it does not need a GitHub token. It also pins the repository's numeric GitHub ID so a rename or name reuse fails closed. The poller runs as root from a five-minute systemd timer. It reads the runtime `SecureString` only during a verified deployment, writes it under `/run/moodprint` with mode `0600`, and never prints the value. It does not run database migrations.

## Configure and install

1. Keep `/moodprint/staging/runtime` as a `SecureString` containing the backend production environment. Use a Session Manager connection to verify that the instance is healthy before making any changes.
2. Attach the policy in `instance-policy.json` to the existing EC2 role after replacing `<REGION>` and `<ACCOUNT_ID>`. The policy grants `ssm:GetParameter` for only the runtime parameter. The existing `AmazonSSMManagedInstanceCore` policy remains attached.
3. Keep `GHCR_TOKEN_PARAMETER_NAME` blank if both GHCR packages are public. For private packages, store a GitHub token limited to `read:packages` as a separate `SecureString`, set the exact parameter name in `/opt/moodprint/deployment.conf`, and add only that parameter ARN to the instance policy. Never put the token in GitHub Actions or this repository.
4. Download the repository at the reviewed `main` commit, then run `sudo bash deploy/aws/install-release-poller.sh`. The installer preserves a current GHCR configuration and replaces the old ECR example when present. It enables the timer and starts one verification poll.

The GHCR packages begin private. Public packages can be pulled without an AWS or GitHub credential. GitHub does not allow a public package to be made private again, so make that visibility change only after the first images have passed the workflow's secret checks and their contents have been reviewed. The private package option uses a narrow read token stored in Parameter Store.

## Operations

```bash
sudo systemctl status moodprint-release-poll.timer
sudo systemctl start moodprint-release-poll.service
sudo journalctl -u moodprint-release-poll.service --since today --no-pager
```

Deployments are selected by the current `main` SHA. If a newer commit reaches `main` while an older release is being checked, the older release is skipped. `deploy.sh` switches both images together, waits for container health and the HTTPS readiness endpoint, and restores the last active image pair if health verification fails. The poller retains the current and previous image pair and removes older MoodPrint GHCR images after a successful deployment.

The SSM document in `ssm-document.json` is an operator recovery path. It accepts complete image references by digest and a full commit SHA; it does not grant GitHub Actions permission to invoke SSM.
