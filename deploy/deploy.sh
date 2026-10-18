#!/usr/bin/env bash
# =============================================================================
# Deploys one commit to one environment. Runs ON THE SERVER as the `deploy` user.
#
# GitHub Actions streams this file over SSH, so the script that runs is always
# the version from the commit being deployed:
#   ssh deploy@server "bash -s -- <env> <git-sha> <repo-url>" < deploy/deploy.sh
#
# Layout on the server (one folder per environment):
#   /opt/fastapi_001/<env>/
#     .env                  <- environment config (APP_ENV, PORT, later DB URL)
#     releases/<sha>/       <- one folder per deployed commit, each with its own .venv
#     current -> releases/<sha>   <- symlink systemd runs from
#
# Switching the `current` symlink makes deploys atomic and rollbacks instant.
# =============================================================================
set -euo pipefail

ENV_NAME="$1"
SHA="$2"
REPO_URL="$3"
SHORT_SHA="${SHA:0:7}"
KEEP_RELEASES=5

case "$ENV_NAME" in
  uat|prod) ;;
  *) echo "Unknown environment: $ENV_NAME" >&2; exit 1 ;;
esac

BASE="/opt/fastapi_001/$ENV_NAME"
RELEASE="$BASE/releases/$SHA"
SERVICE="fastapi_001@$ENV_NAME"

# Loads PORT (and APP_ENV) for the health check below.
set -a; source "$BASE/.env"; set +a

echo "==> [$ENV_NAME] Fetching commit $SHORT_SHA"
rm -rf "$RELEASE"
mkdir -p "$RELEASE"
git -C "$RELEASE" init -q
git -C "$RELEASE" fetch -q --depth 1 "$REPO_URL" "$SHA"
git -C "$RELEASE" checkout -q FETCH_HEAD

echo "==> [$ENV_NAME] Installing dependencies"
python3.12 -m venv "$RELEASE/.venv"
"$RELEASE/.venv/bin/pip" install -q --upgrade pip
"$RELEASE/.venv/bin/pip" install -q -r "$RELEASE/requirements.txt"

# systemd reads this file too, so /health reports which commit is live.
echo "APP_VERSION=$SHORT_SHA" > "$RELEASE/.release"

PREVIOUS="$(readlink -f "$BASE/current" 2>/dev/null || true)"

echo "==> [$ENV_NAME] Switching to new release and restarting"
ln -sfn "$RELEASE" "$BASE/current"
sudo /usr/bin/systemctl restart "$SERVICE"

echo "==> [$ENV_NAME] Health check on port $PORT"
for _ in $(seq 1 20); do
  if curl -fsS "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q "\"version\":\"$SHORT_SHA\""; then
    echo "==> [$ENV_NAME] Healthy, running $SHORT_SHA"
    # Delete old releases, keeping the newest few for rollback.
    ls -1dt "$BASE"/releases/*/ | tail -n +$((KEEP_RELEASES + 1)) | xargs -r rm -rf
    exit 0
  fi
  sleep 1
done

echo "!!! [$ENV_NAME] Health check failed" >&2
sudo /usr/bin/systemctl status "$SERVICE" --no-pager -n 20 >&2 || true
if [ -n "$PREVIOUS" ] && [ "$PREVIOUS" != "$RELEASE" ]; then
  echo "!!! [$ENV_NAME] Rolling back to $(basename "$PREVIOUS")" >&2
  ln -sfn "$PREVIOUS" "$BASE/current"
  sudo /usr/bin/systemctl restart "$SERVICE"
fi
exit 1
