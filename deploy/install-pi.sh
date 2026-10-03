#!/usr/bin/env bash
# Install (or re-install) the Hive monitor on the Pi. Run it ON the Pi:
#
#   cd ~/hive-monitor && ./deploy/install-pi.sh
#
# Safe to re-run: never touches the database or backend/.env. It does not build the
# frontend (that happens on the laptop, via `scripts/hive rebuild`) and it does not
# configure Caddy: one Caddyfile serves every app and it lives in the recipe-for-disaster repo.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ "$(id -un)" = root ] && { echo "run this as your normal user, not root" >&2; exit 1; }

echo "==> backend dependencies"
"$HOME/.local/bin/uv" --version >/dev/null 2>&1 || { echo "uv is not installed: https://astral.sh/uv" >&2; exit 1; }
(cd "$ROOT/backend" && "$HOME/.local/bin/uv" sync -q --no-dev)

if [ ! -f "$ROOT/backend/.env" ]; then
	cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"
	echo "    created backend/.env from the example: fill it in, then run setup"
fi
chmod 600 "$ROOT/backend/.env"

echo "==> systemd units"
sudo cp "$ROOT/deploy/hive.service" /etc/systemd/system/hive.service
sudo cp "$ROOT/deploy/hive-backup.service" /etc/systemd/system/hive-backup.service
sudo cp "$ROOT/deploy/hive-backup.timer" /etc/systemd/system/hive-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now hive.service >/dev/null
sudo systemctl enable --now hive-backup.timer >/dev/null

echo "==> waiting for the app"
for _ in $(seq 1 40); do
	curl -sf -m 1 http://127.0.0.1:8030/api/health >/dev/null && break
	sleep 0.5
done
curl -sf -m 3 http://127.0.0.1:8030/api/health >/dev/null \
	|| { echo "the app did not come up; see: sudo journalctl -u hive -n 50" >&2; exit 1; }

echo
echo "installed."
printf "  app        : %s\n" "$(systemctl is-active hive)"
printf "  next backup: %s\n" "$(systemctl list-timers hive-backup --no-pager 2>/dev/null | awk 'NR==2 {print $1, $2, $3}')"
