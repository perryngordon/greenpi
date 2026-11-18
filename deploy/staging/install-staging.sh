#!/usr/bin/env bash
# Idempotent installer for the STAGING copy (pve container, no sensors, no radios).
# Run as `admin` from the repo:  cd ~/greenpi && deploy/staging/install-staging.sh
# Needs /etc/greenpi/greenpi.env with GREENPI_STAGING=1 - see deploy/staging/README.md.
set -euo pipefail
cd "$(dirname "$0")/../.."
ENV=/etc/greenpi/greenpi.env
sudo test -f "$ENV" || { echo "missing $ENV"; exit 1; }
set -a; eval "$(sudo cat "$ENV")"; set +a
[ "${GREENPI_STAGING:-0}" = 1 ] || { echo "GREENPI_STAGING=1 missing from $ENV: refusing (is this the real Pi?)"; exit 1; }

echo "== python deps"
[ -x venv/bin/python ] || python3 -m venv venv
venv/bin/pip install -q -r requirements.txt

echo "== data dir"
sudo install -d -o admin -g admin "${GREENPI_DATA_DIR:-/srv/greenpi-data}"

echo "== database, static files, admin user, simulated sensors"
M="venv/bin/python manage.py"
$M migrate --noinput
$M collectstatic --noinput -v 0
$M seed_defaults

echo "== systemd units (web, sampler, nightly backup, nightly pull from the Pi)"
sudo install -m 644 deploy/systemd/greenpi-web.service deploy/systemd/greenpi-sampler.service \
  deploy/systemd/greenpi-backup.service deploy/systemd/greenpi-backup.timer \
  deploy/staging/greenpi-stage-sync.service deploy/staging/greenpi-stage-sync.timer /etc/systemd/system/
sudo install -m 755 deploy/staging/load-snapshot.sh /usr/local/sbin/greenpi-load-snapshot
sudo install -m 755 deploy/staging/stage-sync.sh /usr/local/sbin/greenpi-stage-sync
sudo systemctl daemon-reload
sudo systemctl enable -q --now greenpi-web greenpi-sampler greenpi-backup.timer greenpi-stage-sync.timer
sudo systemctl restart greenpi-web greenpi-sampler
sleep 3
systemctl is-active greenpi-web greenpi-sampler | paste -sd' '
echo "done: http://$(hostname -I | awk '{print $1}')/"
