#!/bin/bash
# macOS / Linux version of onsite-update.ps1.
#
# Push this repo's current branch to the greenhouse Pi, run the installer, and
# bring the Pi's data home (database snapshot, photos, Wi-Fi surveys).
# Works without internet: the laptop talks straight to the Pi.
#
#   On site (laptop joined to Ward_Greenhouse):  deploy/onsite-update.sh
#   Another address (e.g. over a VPN):        deploy/onsite-update.sh --host 10.8.0.21
#   Only fetch data, no code update:          deploy/onsite-update.sh --data-only
#   Code only, no data:                       deploy/onsite-update.sh --no-data
#
# The first run adds this laptop's SSH key to the Pi (asks for the Pi's admin
# password once). Data lands in ~/greenpi-snapshots/<date-time>/.
set -euo pipefail
cd "$(dirname "$0")/.."
. deploy/ssh-key.sh

PI=10.42.0.1
BRANCH=""
DATA=1
CODE=1
while [ $# -gt 0 ]; do
    case "$1" in
        --host) PI="$2"; shift 2 ;;
        --branch) BRANCH="$2"; shift 2 ;;
        --data-only) CODE=0; shift ;;
        --no-data) DATA=0; shift ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

ensure_greenpi_key "$PI"

# No internet at the greenhouse: if the Pi's clock isn't network-synced, set it
# from this laptop (it also updates the battery-backed clock).
ssh "admin@$PI" "sudo /usr/local/sbin/greenpi-set-clock '$(date -u '+%Y-%m-%d %H:%M:%S')'"

if [ "$CODE" = 1 ]; then
    [ -n "$BRANCH" ] || BRANCH="$(git rev-parse --abbrev-ref HEAD)"
    if [ -n "$(git status --porcelain)" ]; then
        echo "WARNING: uncommitted changes are NOT sent; commit them first if you want them on the Pi." >&2
    fi
    echo "Pushing $BRANCH to admin@$PI:greenpi ..."
    git push "admin@$PI:greenpi" "$BRANCH:$BRANCH" \
        || { echo "git push failed (on site? check you're joined to Ward_Greenhouse)" >&2; exit 1; }
    echo "Running the installer on the Pi ..."
    ssh "admin@$PI" "cd ~/greenpi && git checkout -q $BRANCH && deploy/install.sh"
fi

if [ "$DATA" = 1 ]; then
    echo "Taking a fresh database snapshot on the Pi ..."
    ssh "admin@$PI" "sudo systemctl start greenpi-backup.service"
    db="$(ssh "admin@$PI" 'ls -1 /srv/greenpi-data/backups/db/greenpi-*.sqlite3 | sort | tail -1')"
    [ -n "$db" ] || { echo "no database snapshot found on the Pi" >&2; exit 1; }

    dest="$HOME/greenpi-snapshots/$(date '+%Y%m%d-%H%M')"
    mkdir -p "$dest/backups/db"
    echo "Copying data to $dest ..."
    scp -q "admin@$PI:$db" "$dest/backups/db/"
    scp -q -r "admin@$PI:/srv/greenpi-data/media" "$dest/" || echo "WARNING: photos were not copied" >&2
    scp -q -r "admin@$PI:/srv/greenpi-data/surveys" "$dest/" || echo "WARNING: no Wi-Fi surveys copied (none saved yet?)" >&2
    echo "Saved $(du -sh "$dest" | cut -f1). Load it into this laptop's development copy with:"
    echo "  deploy/load-local.sh"
fi
echo "Done. Open http://$PI/"
