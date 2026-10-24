#!/usr/bin/env bash
set -euo pipefail
umask 077

# Installed by the one-time EC2 bootstrap; this file and its parent must be root-owned.
readonly base=/opt/moodprint
readonly config="$base/deployment.conf"
readonly active="$base/staging.env"
readonly previous="$base/staging.previous.env"
readonly runtime=/run/moodprint/runtime.env

[[ $(id -u) -eq 0 ]] || { echo 'Run as root' >&2; exit 2; }
[[ -f "$config" && ! -L "$config" ]] || { echo 'Missing deployment.conf' >&2; exit 2; }
# deployment.conf is an operator-reviewed, root-owned static file, never SSM input.
[[ $(stat -c %u "$config") -eq 0 ]] || { echo 'Configuration owner is invalid' >&2; exit 2; }
if [[ -n $(find "$config" -perm /022 -print -quit) ]]; then
  echo 'Configuration is writable by group or others' >&2
  exit 2
fi
# shellcheck source=/dev/null
source "$config"

[[ ${AWS_ACCOUNT_ID:-} =~ ^[0-9]{12}$ ]] || exit 2
[[ ${AWS_REGION:-} =~ ^[a-z]{2}-[a-z]+-[0-9]$ ]] || exit 2
[[ ${ECR_API_REPO:-} =~ ^[a-z0-9][a-z0-9._/-]*$ ]] || exit 2
[[ ${ECR_WEB_REPO:-} =~ ^[a-z0-9][a-z0-9._/-]*$ ]] || exit 2
[[ ${APP_DOMAIN:-} =~ ^[a-z0-9][a-z0-9.-]*[a-z0-9]$ ]] || exit 2
[[ ${PARAMETER_NAME:-} =~ ^/[a-zA-Z0-9/_-]+$ ]] || exit 2
[[ ${SSM_apiDigest:-} =~ ^sha256:[a-f0-9]{64}$ ]] || { echo 'Invalid API digest' >&2; exit 2; }
[[ ${SSM_webDigest:-} =~ ^sha256:[a-f0-9]{64}$ ]] || { echo 'Invalid web digest' >&2; exit 2; }

registry="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
mkdir -p /run/moodprint
chmod 700 /run/moodprint
runtime_tmp=$(mktemp /run/moodprint/runtime.XXXXXX)
candidate=$(mktemp "$base/staging.XXXXXX")
trap 'rm -f "$runtime_tmp" "$candidate"' EXIT

# The SecureString contains a backend-only env file. It never appears in SSM commands or logs.
aws ssm get-parameter --region "$AWS_REGION" --name "$PARAMETER_NAME" \
  --with-decryption --query Parameter.Value --output text > "$runtime_tmp"
[[ -s "$runtime_tmp" ]] || { echo 'Runtime configuration is empty' >&2; exit 2; }
if [[ $(grep -c '^APP_ENV=' "$runtime_tmp") -ne 1 ]] ||
  ! grep -qx 'APP_ENV=production' "$runtime_tmp"; then
  echo 'APP_ENV must be production exactly once' >&2
  exit 2
fi
install -m 600 "$runtime_tmp" "$runtime"

aws ecr get-login-password --region "$AWS_REGION" |
  docker login --username AWS --password-stdin "$registry" >/dev/null
printf 'API_IMAGE=%s/%s@%s\nWEB_IMAGE=%s/%s@%s\nAPP_DOMAIN=%s\nAPI_ENV_FILE=%s\n' \
  "$registry" "$ECR_API_REPO" "$SSM_apiDigest" \
  "$registry" "$ECR_WEB_REPO" "$SSM_webDigest" "$APP_DOMAIN" "$runtime" > "$candidate"
chmod 600 "$candidate"

compose=(docker compose --project-directory "$base" -f "$base/compose.staging.yml")
"${compose[@]}" --env-file "$candidate" pull
if [[ -f "$active" ]]; then cp -p "$active" "$previous"; fi
install -m 600 "$candidate" "$active"

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
  echo 'Staging deployment healthy'
  exit 0
fi

echo 'Health verification failed; attempting image rollback' >&2
if [[ -f "$previous" ]]; then
  install -m 600 "$previous" "$active"
  "${compose[@]}" --env-file "$active" up -d --no-build
  if check_health; then
    echo 'Previous image pair restored' >&2
  else
    echo 'Rollback also failed; operator intervention required' >&2
  fi
else
  echo 'No previous image pair exists; operator intervention required' >&2
fi
exit 1
