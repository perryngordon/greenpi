#!/usr/bin/env bash
# STAGING ONLY. Load data copied from the greenhouse Pi into the staging copy.
#   greenpi-load-snapshot <folder> [source label]
# <folder> holds what the Pi keeps under /srv/greenpi-data:
#   backups/db/greenpi-YYYY-MM-DD.sqlite3 (newest is used), media/, surveys/
# or is a single .sqlite3 file.
set -euo pipefail
SRC=${1:?usage: greenpi-load-snapshot <folder-or-sqlite3> [source label]}
LABEL=${2:-the greenhouse Pi}
REPO=/home/admin/greenpi
ENV=/etc/greenpi/greenpi.env
grep -q '^GREENPI_STAGING=1' "$ENV" || { echo "not a staging copy: refusing"; exit 1; }

if [ -f "$SRC" ]; then DB=$SRC; DIR=$(dirname "$SRC"); else
  DIR=$SRC
  DB=$(ls -1 "$DIR"/backups/db/greenpi-*.sqlite3 "$DIR"/greenpi-*.sqlite3 2>/dev/null | sort | tail -1 || true)
fi
[ -n "${DB:-}" ] && [ -f "$DB" ] || { echo "no greenpi-*.sqlite3 snapshot in $SRC"; exit 1; }
ARGS=("$DB" --source "$LABEL")
[ -d "$DIR/media" ] && ARGS+=(--media "$DIR/media")
[ -d "$DIR/surveys" ] && ARGS+=(--surveys "$DIR/surveys")

systemctl stop greenpi-sampler greenpi-web
trap 'systemctl start greenpi-web greenpi-sampler' EXIT
cd "$REPO"
sudo -u admin bash -c 'set -a; . '"$ENV"'; set +a; exec venv/bin/python manage.py load_snapshot "$@"' _ "${ARGS[@]}"
