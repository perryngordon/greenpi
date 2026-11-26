#!/bin/bash
# Load greenhouse data (brought home by onsite-update.sh) into THIS laptop's
# development copy, so local work uses the real readings, photos and journal.
#
#   deploy/load-local.sh                       # newest folder in ~/greenpi-snapshots
#   deploy/load-local.sh ~/greenpi-snapshots/20261120-1430
#
# Replaces the local db.sqlite3 (never the Pi's). Runs in staging mode:
# simulated sensors, network changes saved but never applied, Wi-Fi
# passwords blanked. Then start the app with deploy/run-local.sh.
set -euo pipefail
cd "$(dirname "$0")/.."

folder="${1:-$(ls -1d "$HOME"/greenpi-snapshots/*/ 2>/dev/null | sort | tail -1)}"
folder="${folder%/}"
[ -n "$folder" ] && [ -d "$folder/backups/db" ] \
    || { echo "No snapshot folder found (run deploy/onsite-update.sh at the greenhouse first)." >&2; exit 1; }
db="$(ls -1 "$folder"/backups/db/greenpi-*.sqlite3 | sort | tail -1)"

args=("$db" --source "laptop copy $(basename "$folder")")
[ -d "$folder/media" ] && args+=(--media "$folder/media")
[ -d "$folder/surveys" ] && args+=(--surveys "$folder/surveys")

GREENPI_STAGING=1 venv/bin/python manage.py load_snapshot "${args[@]}"
echo "Loaded $(basename "$folder"). Start the app with: deploy/run-local.sh"
