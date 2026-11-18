#!/usr/bin/env bash
# STAGING ONLY. Nightly: copy the greenhouse Pi's data over the VPN (read-only
# rrsync login, see README) and load it if there's a newer database snapshot.
# Quietly does nothing when the Pi is offline (no uplink at the greenhouse yet).
set -uo pipefail
PI=${GREENPI_PI_HOST:-admin@10.8.0.21}
KEY=/root/.ssh/greenpi-pull
MIRROR=/srv/greenpi-data/pi-mirror
SSH="ssh -i $KEY -o BatchMode=yes -o ConnectTimeout=15"

# The Pi's key is locked to read-only rrsync, so probe with an rsync listing.
if ! rsync -e "$SSH" --list-only "$PI:backups/db/" >/dev/null 2>&1; then
  echo "Pi not reachable; nothing to do"; exit 0
fi
install -d -o admin -g admin "$MIRROR"
for d in backups/db media surveys; do
  install -d -o admin -g admin "$MIRROR/$d"
  rsync -a -e "$SSH" "$PI:$d/" "$MIRROR/$d/" || echo "warning: could not copy $d"
done
chown -R admin:admin "$MIRROR"

NEWEST=$(ls -1 "$MIRROR"/backups/db/greenpi-*.sqlite3 2>/dev/null | sort | tail -1)
[ -n "$NEWEST" ] || { echo "no snapshot on the Pi yet"; exit 0; }
STAMP=/srv/greenpi-data/.last-loaded
SIG="$(basename "$NEWEST") $(stat -c %Y "$NEWEST")"
if [ "$(cat "$STAMP" 2>/dev/null)" = "$SIG" ]; then echo "already loaded $SIG"; exit 0; fi
/usr/local/sbin/greenpi-load-snapshot "$MIRROR" "the Pi over the VPN" && echo "$SIG" > "$STAMP"
