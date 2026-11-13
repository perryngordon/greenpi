# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

GreenPi is a Django web app for monitoring/controlling a greenhouse from a single-board computer (Raspberry Pi 4, Orange Pi PC Plus). It discovers and reads sensors over I2C and USB-Modbus, and configures the SBC's networking (Wi-Fi AP mode for a local "greenhouse" network, or Wi-Fi client mode, plus the primary Ethernet interface) by templating and restarting `hostapd`/`dnsmasq`/`wpa_supplicant` on the host. The `ai/` directory contains the owner's informal planning notes (`persona.md`, `system_architecture.md`, `target_platforms.md`, `webapp.md`, `sensors_i2c.md`, `sensors_usb_modbus.md`) — useful for intent, not authoritative specs.

## Commands

A virtualenv already exists at `venv/` with dependencies installed (Django 5.2.15, djangorestframework 3.17.1, smbus2 0.6.1). There is no `requirements.txt`/`pyproject.toml` — if recreating the env, install those packages directly.

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
- **`client/index.html`** — the entire frontend: one HTML file, Tailwind via CDN, vanilla JS. No build step, no bundler. Sections (Home/Sensors/Wiki/Config) are plain `<section>` elements toggled by `showSection()`; data comes from `fetch()` calls to the `/api/...` endpoints.
- **`sensors/`** — `models.py` defines `Sensor` (status: `unconfigured` → `accepted`/`configured`, with a free-form `metadata` JSONField). `drivers.py` holds one driver class per physical sensor chip (e.g. `AS7331Driver`, talking I2C via `smbus2`). `services.py:SensorDiscoveryService` scans the I2C bus for live addresses and has a stubbed-out USB-Modbus scan. `views.py:get_sensor_list` merges DB-known sensors with a live I2C scan (anything found on the bus but not in the DB is reported as `unconfigured`); `configure_sensor` accepts/names a discovered sensor or edits an existing one; `get_sensor_readings`/`mock_sensor_readings` pick a driver by `sensor.address` and return raw channel data for unconfigured sensors vs. curated fields for configured ones.
- **`network/`** — `models.py:NetworkConfig` is a singleton-style row holding AP + Wi-Fi-client + Ethernet settings. `views.py:network_config` (GET/POST) is the only API; on POST it writes `/etc/hostapd/hostapd.conf` and `/etc/dnsmasq.d/django-dhcp.conf` and shells out to `sudo systemctl restart hostapd`/`dnsmasq`. This only works on the actual SBC with those services installed and passwordless sudo for them — off-device it will throw/print errors (hostapd path catches exceptions; the dnsmasq path returns an HTTP 500 on failure).
- **`dashboard/`** and **`wiki/`** — scaffolded Django apps (stock `startapp` stubs only, no real models/views yet) that exist on disk but are **not** in `INSTALLED_APPS` in `config/settings.py`, so they currently have zero effect on the running app.
- **`rtl8188eu/`** — vendored upstream driver source for the Realtek RTL8188EU USB Wi-Fi chipset, as its own nested git repo with unrelated history. It's the out-of-tree kernel module + bundled `hostapd-2.9` source that `network/`'s AP-mode feature depends on at the OS level on real hardware. It's C/kernel code built via its own `Makefile`/`dkms.conf`, not via Django tooling — don't treat it as part of the Python app.

## Known gotchas

- This repo currently has no commits (`git log` is empty) and no root `.gitignore` — `venv/`, `db.sqlite3`, and `__pycache__/` directories are all untracked. Don't bulk-`git add` without checking what's staged.
- `config/settings.py` has `DEBUG = True` and a hardcoded `SECRET_KEY` — fine for this prototype stage, but flag before any real deployment.
- `client/index.html`'s JS expects a sensor JSON shape (`sensor_id`, `location`, `status: 'CONFIGURED'`, readings as a list of `{temp, humidity}`) that doesn't match what `sensors/views.py` actually returns (`id`, `address`, `status: 'configured'`, `metadata`, readings as a single dict) — the Sensors panel in the UI is not currently wired correctly to the live API.
