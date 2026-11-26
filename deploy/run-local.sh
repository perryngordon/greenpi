#!/bin/bash
# Run the app on this laptop for development: simulated sensors, the sampler
# filling in readings once a minute, and the web app at http://127.0.0.1:8000/
# (also reachable from a phone on the same Wi-Fi at http://<laptop-ip>:8000/).
# First time: deploy/setup-local.sh. Ctrl-C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."
export GREENPI_STAGING=1

venv/bin/python manage.py migrate --noinput
venv/bin/python manage.py sample_sensors --loop --tick 10 &
sampler=$!
trap 'kill $sampler 2>/dev/null' EXIT
venv/bin/python manage.py runserver 0.0.0.0:8000
