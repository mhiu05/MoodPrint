#!/usr/bin/env bash
set -euo pipefail
umask 077

[[ $(id -u) -eq 0 ]] || { echo 'Run as root' >&2; exit 2; }
readonly source_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
readonly base=/opt/moodprint
readonly config="$base/deployment.conf"

if [[ -L "$config" ]]; then
  echo 'Refusing to use a symbolic-link deployment.conf' >&2
  exit 2
fi

for required in python3 aws docker; do
  command -v "$required" >/dev/null || { echo "Missing required command: $required" >&2; exit 2; }
done
docker compose version >/dev/null

if ! command -v gh >/dev/null || ! dpkg --compare-versions "$(gh version | awk 'NR == 1 {print $3}')" ge 2.102.0; then
  apt-get update
  apt-get install -y ca-certificates curl gnupg
  install -d -m 755 /usr/share/keyrings
  curl --fail --silent --show-error --location \
    https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    --output /usr/share/keyrings/githubcli-archive-keyring.gpg
  chmod 644 /usr/share/keyrings/githubcli-archive-keyring.gpg
  printf 'deb [arch=%s signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main\n' \
    "$(dpkg --print-architecture)" > /etc/apt/sources.list.d/github-cli.list
  apt-get update
  apt-get install -y gh
fi
installed_gh_version=$(gh version | awk 'NR == 1 {print $3}')
dpkg --compare-versions "$installed_gh_version" ge 2.102.0 || {
  echo 'GitHub CLI 2.102.0 or newer is required for safe attestation verification' >&2
  exit 2
}
gh attestation verify --help >/dev/null

install -d -o root -g root -m 750 "$base"
if [[ ! -f "$config" ]] || grep -q '^ECR_API_REPO=' "$config" || ! grep -q '^GITHUB_REPOSITORY=' "$config"; then
  install -o root -g root -m 600 "$source_dir/deployment.conf.example" "$config"
else
  chown root:root "$config"
  chmod 600 "$config"
fi

install -o root -g root -m 750 "$source_dir/poll_release.py" "$base/poll_release.py"
install -o root -g root -m 750 "$source_dir/deploy.sh" "$base/deploy.sh"
install -o root -g root -m 640 "$source_dir/../compose.staging.yml" "$base/compose.staging.yml"
install -o root -g root -m 640 "$source_dir/../Caddyfile" "$base/Caddyfile"
install -o root -g root -m 644 "$source_dir/moodprint-release-poll.service" \
  /etc/systemd/system/moodprint-release-poll.service
install -o root -g root -m 644 "$source_dir/moodprint-release-poll.timer" \
  /etc/systemd/system/moodprint-release-poll.timer
install -d -o root -g root -m 700 /run/moodprint

systemctl daemon-reload
systemctl enable --now moodprint-release-poll.timer
systemctl start moodprint-release-poll.service
echo 'MoodPrint release poller installed. Check: systemctl status moodprint-release-poll.timer'
