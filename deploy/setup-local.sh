#!/bin/bash
# One-time setup of a development copy on a Mac (or Linux) laptop.
# Needs Python 3.11+ (macOS: `brew install python@3.12` or python.org).
#
#   deploy/setup-local.sh
#
# Creates venv/, installs the pinned packages, builds the database with the
# default admin user + known sensors, and runs the tests.
set -euo pipefail
cd "$(dirname "$0")/.."
export GREENPI_STAGING=1

py=""
for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
        py="$candidate"; break
    fi
done
[ -n "$py" ] || { echo "Need Python 3.11 or newer (macOS: brew install python@3.12)" >&2; exit 1; }

[ -d venv ] || "$py" -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt
venv/bin/python manage.py migrate --noinput
venv/bin/python manage.py collectstatic --noinput -v 0
if [ -z "${GREENPI_ADMIN_PASSWORD:-}" ]; then
    read -r -s -p "Choose a password for the local 'admin' web account: " GREENPI_ADMIN_PASSWORD; echo
    export GREENPI_ADMIN_PASSWORD
fi
venv/bin/python manage.py seed_defaults
venv/bin/python manage.py test
echo
echo "Ready. Start it with: deploy/run-local.sh   (then open http://127.0.0.1:8000/)"
echo "Real greenhouse data: deploy/onsite-update.sh at the greenhouse, then deploy/load-local.sh"
