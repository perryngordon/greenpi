# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

GreenPi is a Django web app for monitoring/controlling a greenhouse from a single-board computer (Raspberry Pi 4, Orange Pi PC Plus). It discovers and reads sensors over I2C and USB-Modbus, and configures the SBC's networking (Wi-Fi AP mode for a local "greenhouse" network, or Wi-Fi client mode, plus the primary Ethernet interface) by templating and restarting `hostapd`/`dnsmasq`/`wpa_supplicant` on the host. The `ai/` directory contains the owner's informal planning notes (`persona.md`, `system_architecture.md`, `target_platforms.md`, `webapp.md`, `sensors_i2c.md`, `sensors_usb_modbus.md`) — useful for intent, not authoritative specs.

## Commands

A virtualenv exists at `venv/`; dependencies are pinned in `requirements.txt`. On the device the app runs as systemd services — see `deploy/README.md` (`deploy/install.sh` is the idempotent installer).

```bash
source venv/bin/activate

python manage.py runserver 0.0.0.0:8000   # dev server
python manage.py makemigrations <app>     # after changing a model
python manage.py migrate
python manage.py test                     # all apps
python manage.py test sensors             # single app
python manage.py test sensors.tests.SomeTestCase  # single test case
python manage.py createsuperuser          # for /admin/
```

`smbus2` (I2C) calls in `sensors/drivers.py` and `sensors/services.py` will fail outside of an SBC with an I2C bus present — expect `OSError`s when running the dev server off-device.

## Architecture

- **`config/`** — Django project (settings, urls, wsgi/asgi). `config/views.py:home` serves `client/index.html` as a raw `HttpResponse` (file read off disk), not via Django's template engine — it's the single entry point for the whole frontend.
- **`client/index.html`** — the entire frontend: one HTML file, vanilla JS, Tailwind + Chart.js vendored under `client/static/vendor/` (served by whitenoise so it works on the offline hotspot — never switch back to CDN links). No build step, no bundler. Home = climate dashboard (`/api/climate/`). Sections (Home/Sensors/Wiki/Config) are plain `<section>` elements toggled by `showSection()`; data comes from `fetch()` calls to the `/api/...` endpoints.
- **`sensors/`** — `models.py` defines `Sensor` (status: `unconfigured` → `accepted`/`configured`, with a free-form `metadata` JSONField). `drivers.py` holds one driver class per physical sensor chip (e.g. `AS7331Driver`, talking I2C via `smbus2`). `services.py:SensorDiscoveryService` scans the I2C bus for live addresses and has a stubbed-out USB-Modbus scan. `views.py:get_sensor_list` merges DB-known sensors with a live I2C scan (anything found on the bus but not in the DB is reported as `unconfigured`); `configure_sensor` accepts/names a discovered sensor or edits an existing one; `get_sensor_readings`/`mock_sensor_readings` pick a driver by `sensor.address` and return raw channel data for unconfigured sensors vs. curated fields for configured ones.
- **`network/`** — `models.py:NetworkConfig` is a singleton-style row holding AP + Wi-Fi-client + Ethernet settings. `views.py:network_config` (GET/POST, staff login + CSRF required) writes `/etc/hostapd/hostapd.conf` + `/etc/dnsmasq.d/greenpi-ap.conf` for the hotspot radio (`settings.GREENPI_AP_INTERFACE`, wlap0) and joins Wi-Fi networks with `nmcli` on the client radio (`GREENPI_STA_INTERFACE`, wlsta0). `manage.py apply_network` re-applies the stored config. Only works on the device (sudo, hostapd, NetworkManager).
- **`dashboard/`** and **`wiki/`** — scaffolded Django apps (stock `startapp` stubs only, no real models/views yet) that exist on disk but are **not** in `INSTALLED_APPS` in `config/settings.py`, so they currently have zero effect on the running app.
- **`rtl8188eu/`** (on the device only, git-ignored) — old out-of-tree driver source for the Comfast RTL8188EUS dongle. No longer needed: kernel 6.12's in-tree `rtl8xxxu` drives it.

## Known gotchas

- Secrets come from `/etc/greenpi/greenpi.env` (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, ...). Off-device the settings fall back to an insecure dev key with DEBUG on.
- SQLite runs in WAL mode with IMMEDIATE transactions because the sampler and web app write concurrently.
- `TIME_ZONE` is America/Denver; daily highs/lows in `/api/climate/` are by local calendar day.
- `venv/`, `db.sqlite3`, `staticfiles/` and `rtl8188eu/` are git-ignored — never commit the DB (it holds Wi-Fi passwords).
