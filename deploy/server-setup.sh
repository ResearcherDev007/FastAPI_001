#!/usr/bin/env bash
# =============================================================================
# ONE-TIME server preparation. Run as root on the VPS. Safe to re-run.
#
#   scp deploy/fastapi_001@.service root@server:/etc/systemd/system/
#   ssh root@server "bash -s -- '<github-actions-public-key>'" < deploy/server-setup.sh
#
# What it does:
#   1. Installs Python 3.12 (alongside the system Python 3.9, which stays untouched)
#   2. Creates a limited `deploy` user that GitHub Actions logs in as
#   3. Creates /opt/fastapi_001/{uat,prod} with their .env config
#   4. Enables the systemd service template
#   5. Lets `deploy` restart ONLY these services via sudo (nothing else)
# =============================================================================
set -euo pipefail

DEPLOY_PUBKEY="$1"
APP_ROOT=/opt/fastapi_001

echo "==> Installing Python 3.12"
dnf install -y -q python3.12

echo "==> Creating deploy user"
id deploy &>/dev/null || useradd --create-home --shell /bin/bash deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
echo "$DEPLOY_PUBKEY" > /home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys

echo "==> Creating environment folders"
declare -A PORTS=([uat]=8002 [prod]=8003)
for env in uat prod; do
  # deploy must own the env folder itself, to swap the `current` symlink.
  install -d -o deploy -g deploy "$APP_ROOT/$env" "$APP_ROOT/$env/releases"
  if [ ! -f "$APP_ROOT/$env/.env" ]; then
    printf 'APP_ENV=%s\nPORT=%s\n' "$env" "${PORTS[$env]}" > "$APP_ROOT/$env/.env"
  fi
  chown root:deploy "$APP_ROOT/$env/.env"
  chmod 640 "$APP_ROOT/$env/.env"
done

echo "==> Enabling systemd unit (copied beforehand to /etc/systemd/system/)"
systemctl daemon-reload
systemctl enable fastapi_001@uat fastapi_001@prod

echo "==> Allowing deploy to restart only these services"
cat > /tmp/fastapi_001-deploy <<'SUDO'
Cmnd_Alias FASTAPI_001 = \
    /usr/bin/systemctl restart fastapi_001@uat, \
    /usr/bin/systemctl restart fastapi_001@prod, \
    /usr/bin/systemctl status fastapi_001@uat --no-pager -n 20, \
    /usr/bin/systemctl status fastapi_001@prod --no-pager -n 20
deploy ALL=(root) NOPASSWD: FASTAPI_001
SUDO
# Check syntax BEFORE installing: a broken sudoers file can break sudo.
visudo -cf /tmp/fastapi_001-deploy
install -m 440 -o root -g root /tmp/fastapi_001-deploy /etc/sudoers.d/fastapi_001-deploy
rm -f /tmp/fastapi_001-deploy

echo "==> Done"
