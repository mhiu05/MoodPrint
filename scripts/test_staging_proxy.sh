#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
host_root=$(pwd -W 2>/dev/null || pwd)
name="moodprint-proxy-smoke-$$"
network="$name"
api="$name-api"
web="$name-web"
cleanup() {
  docker rm -f "$web" "$api" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker network create "$network" >/dev/null
docker run -d --rm --name "$api" --network "$network" --network-alias api \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --cap-drop ALL \
  -e APP_ENV=development moodprint-api:ci >/dev/null
MSYS_NO_PATHCONV=1 docker run -d --rm --name "$web" --network "$network" \
  --read-only --tmpfs /data:rw,size=16m --tmpfs /config:rw,size=16m \
  --cap-drop ALL --cap-add NET_BIND_SERVICE \
  -p 127.0.0.1::80 -e APP_DOMAIN=:80 \
  -v "$host_root/deploy/Caddyfile:/etc/caddy/Caddyfile:ro" moodprint-web:ci >/dev/null
port=$(docker port "$web" 80/tcp | sed 's/.*://')
base="http://127.0.0.1:$port"
for ((attempt=0; attempt<60; attempt++)); do
  if [[ $(curl -sS -o /dev/null -w '%{http_code}' "$base/api/v1/health/live" 2>/dev/null) == 200 ]]; then
    break
  fi
  sleep 2
done
check() {
  local path="$1" expected="$2" actual
  actual=$(curl -sS -o /dev/null -w '%{http_code}' "$base$path")
  [[ "$actual" == "$expected" ]] || { echo "$path: expected $expected, got $actual" >&2; exit 1; }
  echo "$path: $actual"
}
check / 200
check /auth/callback 200
header() {
  curl -sSI "$base$1" | tr -d '\r' | awk -v name="$2" 'tolower($1) == tolower(name ":") { $1 = ""; sub(/^ /, ""); print }'
}
csp=$(header / Content-Security-Policy)
[[ "$csp" == *"default-src 'self'"* && "$csp" == *"frame-ancestors 'none'"* ]] \
  || { echo "/: missing strict Content-Security-Policy" >&2; exit 1; }
[[ "$csp" != *"unsafe-inline"* && "$csp" != *"unsafe-eval"* && "$csp" != *"challenges.cloudflare.com"* ]] \
  || { echo "/: CSP must stay same-origin while the CAPTCHA origin is unset" >&2; exit 1; }
[[ "$(header /auth/callback X-Robots-Tag)" == "noindex, nofollow" ]] \
  || { echo "/auth/callback: expected noindex" >&2; exit 1; }
[[ "$(header /auth/callback Cache-Control)" == "no-store" ]] \
  || { echo "/auth/callback: expected no-store" >&2; exit 1; }
[[ -z "$(header /api/v1/health/live Content-Security-Policy)" ]] \
  || { echo "/api: JSON responses carry no document CSP" >&2; exit 1; }
echo "shell headers: ok"
check /api/v1/health/live 200
check /api/v1/health/ready 503
check /api/v1/session 401

# Replace only the test-owned API container with a synthetic two-event stream.
docker rm -f "$api" >/dev/null
MSYS_NO_PATHCONV=1 docker run -d --rm --name "$api" --network "$network" --network-alias api \
  --read-only --cap-drop ALL \
  -v "$host_root/scripts/fixtures/sse_server.py:/tmp/sse_server.py:ro" \
  --entrypoint /srv/moodprint/.venv/bin/python moodprint-api:ci \
  -u /tmp/sse_server.py >/dev/null
sleep 2
python scripts/check_sse_timing.py "$base/api/v1/sse-smoke"
