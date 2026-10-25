#!/usr/bin/env bash
set -euo pipefail
umask 077

readonly base=/opt/moodprint
readonly config="$base/deployment.conf"
readonly active="$base/staging.env"
readonly previous="$base/staging.previous.env"
readonly runtime_dir=/run/moodprint

[[ $(id -u) -eq 0 ]] || { echo 'Run as root' >&2; exit 2; }
[[ $# -eq 3 ]] || { echo 'Usage: deploy.sh API_IMAGE_REF WEB_IMAGE_REF RELEASE_SHA' >&2; exit 2; }
[[ -f "$config" && ! -L "$config" ]] || { echo 'Missing deployment.conf' >&2; exit 2; }
[[ $(stat -c %u "$config") -eq 0 ]] || { echo 'Configuration owner is invalid' >&2; exit 2; }
for state_file in "$active" "$previous"; do
  if [[ -L "$state_file" ]]; then
    echo 'Deployment state must not be a symbolic link' >&2
    exit 2
  fi
  if [[ -f "$state_file" ]] && { [[ $(stat -c %u "$state_file") -ne 0 ]] || [[ -n $(find "$state_file" -perm /022 -print -quit) ]]; }; then
    echo 'Deployment state ownership or mode is invalid' >&2
    exit 2
  fi
done
if [[ -n $(find "$config" -perm /022 -print -quit) ]]; then
  echo 'Configuration is writable by group or others' >&2
  exit 2
fi
# deployment.conf is an operator-reviewed, root-owned static file; it is never SSM input.
# shellcheck source=/dev/null
source "$config"

api_ref="$1"
web_ref="$2"
release_sha="$3"
[[ ${AWS_REGION:-} =~ ^[a-z]{2}-[a-z]+-[0-9]$ ]] || exit 2
[[ ${GHCR_API_IMAGE:-} =~ ^ghcr\.io/[a-z0-9][a-z0-9._/-]*$ ]] || exit 2
[[ ${GHCR_WEB_IMAGE:-} =~ ^ghcr\.io/[a-z0-9][a-z0-9._/-]*$ ]] || exit 2
[[ ${APP_DOMAIN:-} =~ ^[a-z0-9][a-z0-9.-]*[a-z0-9]$ ]] || exit 2
[[ ${PARAMETER_NAME:-} =~ ^/[a-zA-Z0-9/_-]+$ ]] || exit 2
[[ "$release_sha" =~ ^[a-f0-9]{40}$ ]] || { echo 'Invalid release SHA' >&2; exit 2; }
[[ "$api_ref" =~ ^ghcr\.io/[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$ ]] || { echo 'Invalid API image reference' >&2; exit 2; }
[[ "$web_ref" =~ ^ghcr\.io/[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$ ]] || { echo 'Invalid web image reference' >&2; exit 2; }
[[ "$api_ref" == "$GHCR_API_IMAGE@sha256:"* ]] || { echo 'Unexpected API image repository' >&2; exit 2; }
[[ "$web_ref" == "$GHCR_WEB_IMAGE@sha256:"* ]] || { echo 'Unexpected web image repository' >&2; exit 2; }

mkdir -p "$runtime_dir"
chmod 700 "$runtime_dir"
runtime_file=$(mktemp "$runtime_dir/runtime.env.XXXXXX")
candidate=$(mktemp "$base/staging.XXXXXX")
keep_runtime=0
cleanup() {
  rm -f "$candidate"
  if [[ "$keep_runtime" -ne 1 ]]; then rm -f "$runtime_file"; fi
}
trap cleanup EXIT

# The SecureString contains backend-only variables. It never appears in SSM commands or logs.
aws ssm get-parameter --region "$AWS_REGION" --name "$PARAMETER_NAME" \
  --with-decryption --query Parameter.Value --output text > "$runtime_file"
[[ -s "$runtime_file" ]] || { echo 'Runtime configuration is empty' >&2; exit 2; }
if [[ $(grep -c '^APP_ENV=' "$runtime_file") -ne 1 ]] ||
  ! grep -qx 'APP_ENV=production' "$runtime_file"; then
  echo 'APP_ENV must be production exactly once' >&2
  exit 2
fi
chmod 600 "$runtime_file"

printf 'API_IMAGE=%s\nWEB_IMAGE=%s\nAPP_DOMAIN=%s\nAPI_ENV_FILE=%s\nRELEASE_SHA=%s\n' \
  "$api_ref" "$web_ref" "$APP_DOMAIN" "$runtime_file" "$release_sha" > "$candidate"
chmod 600 "$candidate"

compose=(docker compose --project-directory "$base" -f "$base/compose.staging.yml")
"${compose[@]}" --env-file "$candidate" pull

had_active=0
if [[ -f "$active" && ! -L "$active" ]]; then
  cp -p "$active" "$previous"
  had_active=1
fi
install -o root -g root -m 600 "$candidate" "$active"

check_health() {
  local id state attempt
  for ((attempt=0; attempt<30; attempt++)); do
    state=healthy
    for service in api web; do
      id=$("${compose[@]}" --env-file "$active" ps -q "$service")
      if [[ -z "$id" || $(docker inspect -f '{{.State.Health.Status}}' "$id" 2>/dev/null) != healthy ]]; then
        state=waiting
      fi
    done
    if [[ "$state" == healthy ]] && curl --fail --silent --show-error --output /dev/null \
      --max-time 10 "https://${APP_DOMAIN}/api/v1/health/ready"; then
      return 0
    fi
    sleep 5
  done
  return 1
}

if "${compose[@]}" --env-file "$active" up -d --no-build && check_health; then
  keep_runtime=1
  active_runtime=$(sed -n 's/^API_ENV_FILE=//p' "$active")
  previous_runtime=''
  if [[ -f "$previous" && ! -L "$previous" ]]; then
    previous_runtime=$(sed -n 's/^API_ENV_FILE=//p' "$previous")
  fi
  for old_runtime in "$runtime_dir"/runtime.env.*; do
    [[ -f "$old_runtime" ]] || continue
    if [[ "$old_runtime" != "$active_runtime" && "$old_runtime" != "$previous_runtime" ]]; then
      rm -f "$old_runtime"
    fi
  done
  echo "Staging deployment healthy: $release_sha"
  exit 0
fi

echo 'Health verification failed; attempting image rollback' >&2
if [[ "$had_active" -eq 1 && -f "$previous" ]]; then
  install -o root -g root -m 600 "$previous" "$active"
  if "${compose[@]}" --env-file "$active" up -d --no-build && check_health; then
    echo 'Previous image pair restored' >&2
  else
    echo 'Rollback also failed; operator intervention required' >&2
  fi
else
  rm -f "$active"
  "${compose[@]}" --env-file "$candidate" down --remove-orphans >/dev/null 2>&1 || true
  echo 'No previous image pair exists; failed first deployment was stopped' >&2
fi
exit 1
