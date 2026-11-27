# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

GreenPi is a Django web app for monitoring/controlling a greenhouse from a single-board computer (Raspberry Pi 4, Orange Pi PC Plus). It discovers and reads sensors over I2C and USB-Modbus, and configures the SBC's networking (Wi-Fi AP mode for a local "greenhouse" network, or Wi-Fi client mode, plus the primary Ethernet interface) by templating and restarting `hostapd`/`dnsmasq`/`wpa_supplicant` on the host. The `ai/` directory contains the owner's informal planning notes (`persona.md`, `system_architecture.md`, `target_platforms.md`, `webapp.md`, `sensors_i2c.md`, `sensors_usb_modbus.md`) — useful for intent, not authoritative specs.

## Commands

A virtualenv exists at `venv/`; dependencies are pinned in `requirements.txt`. On the device the app runs as systemd services — see `deploy/README.md` (`deploy/install.sh` is the idempotent installer).

**Developing on a laptop (Mac/Linux)** — see `docs/DEVELOPING.md`: `deploy/setup-local.sh` (one-time), `deploy/run-local.sh` (app + sampler with simulated sensors at :8000), `deploy/onsite-update.sh` (on site via the `Ward_Greenhouse` hotspot: push code, install, fetch data to `~/greenpi-snapshots/`), `deploy/load-local.sh` (load that data locally). Windows equivalents: `deploy/*.ps1`. Always set `GREENPI_STAGING=1` off-device (the scripts do).

```bash
source venv/bin/activate

GREENPI_STAGING=1 python manage.py runserver 0.0.0.0:8000   # dev server (simulated sensors)
python manage.py makemigrations <app>     # after changing a model
python manage.py migrate
python manage.py test                     # all apps
python manage.py test sensors             # single app
python manage.py test sensors.tests.SomeTestCase  # single test case
python manage.py createsuperuser          # for /admin/
```

Off-device, use staging mode: real I2C calls fail without a bus (`smbus2` isn't even importable on Windows; the import is optional).

## Architecture

- **`config/`** — Django project (settings, urls, wsgi/asgi). `config/views.py:home` serves `client/index.html` as a raw `HttpResponse` (file read off disk), not via Django's template engine — it's the single entry point for the whole frontend.
- **`client/index.html`** — the entire frontend: one HTML file, vanilla JS, Tailwind + Chart.js vendored under `client/static/vendor/` (served by whitenoise so it works on the offline hotspot — never switch back to CDN links). No build step, no bundler. Home = climate dashboard (`/api/climate/`). Sections (Home/Sensors/Wiki/Config) are plain `<section>` elements toggled by `showSection()`; data comes from `fetch()` calls to the `/api/...` endpoints.
- **`sensors/`** — `models.py` defines `Sensor` (status: `unconfigured` → `accepted`/`configured`, with a free-form `metadata` JSONField). `drivers.py` holds one driver class per physical sensor chip (e.g. `AS7331Driver`, talking I2C via `smbus2`). `services.py:SensorDiscoveryService` scans the I2C bus for live addresses and has a stubbed-out USB-Modbus scan. `views.py:get_sensor_list` merges DB-known sensors with a live I2C scan (anything found on the bus but not in the DB is reported as `unconfigured`); `configure_sensor` accepts/names a discovered sensor or edits an existing one; `get_sensor_readings`/`mock_sensor_readings` pick a driver by `sensor.address` and return raw channel data for unconfigured sensors vs. curated fields for configured ones.
- **`network/`** — `models.py:NetworkConfig` is a singleton-style row holding AP + Wi-Fi-client + Ethernet settings. `views.py:network_config` (GET/POST, staff login + CSRF required) writes `/etc/hostapd/hostapd.conf` + `/etc/dnsmasq.d/greenpi-ap.conf` for the hotspot radio (`settings.GREENPI_AP_INTERFACE`, wlap0) and joins Wi-Fi networks with `nmcli` on the client radio (`GREENPI_STA_INTERFACE`, wlsta0). `manage.py apply_network` re-applies the stored config. Only works on the device (sudo, hostapd, NetworkManager).
- **`wiki/`** — `WikiPage` + `WikiRevision` (previous version kept on every save). Markdown with `[[Page name]]` links; `/api/wiki/<slug>/` returns rendered HTML plus backlinks (pages and blog posts linking to it).
- **`blog/`** — `Post` (dated journal entry; `date` = the greenhouse day it's about, drafts via `published`) and `Photo` (uploads resized to ≤2000 px JPEG under `MEDIA_ROOT/photos/YYYY/MM/` on the USB data drive; served by Django at `/media/`).
- **`almanac/`** — `AlmanacEvent` (one-off or `yearly`; kinds frost/planting/harvest/task/note). `/api/almanac/month/` and `/day/<date>/` combine daily greenhouse min/max/avg (DB-side aggregation by local day over the primary climate sensor), sun times (`astral`, needs `GREENPI_LATITUDE`/`GREENPI_LONGITUDE`), moon phase, events and that day's posts.
- **`config/markup.py`** — the one Markdown renderer (wiki links + `nh3` sanitising). Always render user text through it; never put raw user HTML in the page. **`config/api.py`** — permission helpers: reads are public; `editor_only`/`can_edit` = any active account that has replaced its temporary password (journal, wiki, almanac, photos); `staff_only`/`is_staff` = admins (network, sensors, people). All writes also need CSRF.
- **`client/static/js/content.js`** — hash router (`#/almanac/2026-11-16`, `#/blog/5`, `#/wiki/slug`) plus the almanac/blog/wiki UI and the shared editor overlay (photo upload, server-side preview via `/api/preview/`).
- **Staging copy** — `GREENPI_STAGING=1`, either a developer's laptop (`deploy/run-local.sh`) or the owner's always-on copy (pve CT 219, http://10.8.0.22/, VPN only): `sensors/simulated.py` replaces the I2C drivers (`services.DRIVERS`), network views save but never apply, the survey shows the Pi's last saved scan, `/api/me` returns `staging` info for the banner. `manage.py load_snapshot` (refuses unless staging) swaps in a Pi backup and blanks Wi-Fi passwords. Develop and click-test there first; see `docs/DEVELOPING.md` and `deploy/staging/README.md`. `manage.py seed_defaults` creates the admin user + known sensors on both.
- **`accounts/`** — `Profile` (display name, avatar slug, `must_change_password`) per Django user; role = `User.is_staff` (admin) or not (gardener). JSON API: `/api/login/`, `/api/logout/`, `/api/me/` (GET/PUT), `/api/me/password/`, admin-only `/api/people/`. No self-signup: admins add people and get a one-time temporary password. Wrong passwords lock a login name for 15 min (file cache in `DATA_DIR/cache`). Avatars are original SVGs in `client/static/avatars/` (list in `accounts/avatars.py`).
- **`dashboard/`** — scaffolded stub app, not in `INSTALLED_APPS`.
- **`rtl8188eu/`** (on the device only, git-ignored) — old out-of-tree driver source for the Comfast RTL8188EUS dongle. No longer needed: kernel 6.12's in-tree `rtl8xxxu` drives it.

## The hardware (greenhouse box)

- **Pi:** Raspberry Pi CM4 on the official CM4 IO Board, boots from eMMC, hostname `greenhouse`, user `admin`. Data (backups, photos, surveys, cache) on a USB stick at `/srv/greenpi-data` (`GREENPI_DATA_DIR`). Services: `greenpi-web` (gunicorn :80), `greenpi-sampler` (reads due sensors every 10 s tick), `greenpi-backup.timer` (02:30 DB snapshot), `hostapd` + `dnsmasq`.
- **Clock:** no internet on site, so the IO Board's PCF85063A RTC (CR2032; `i2c-10` @0x51, enabled by `deploy/install.sh` in `config.txt`) sets the time at boot; `onsite-update` also sets it from the laptop. `fake-hwclock` is the fallback.
- **Radios:** no onboard Wi-Fi on this CM4. `wlap0` = Linksys AE1200 USB, the `Ward_Greenhouse` hotspot at 10.42.0.1 (name and password live in the DB, set on the Config page; `GreenPi_WiFi` in the code is only the fresh-install default; the QR sign encodes the name, so reprint it after a rename; dnsmasq answers `greenhouse` / `greenhouse.lan`, no default route so phones keep mobile data). `wlsta0` = Comfast RTL8188EUS USB, Wi-Fi client via NetworkManager for an uplink. Both pinned by MAC. `wg0` is the owner's remote-access VPN — don't touch.
- **Sensors (I2C bus 1, Qwiic, some via SparkFun QwiicBus Ethernet extenders):**

  | Addr | Board | Driver | Notes |
  |---|---|---|---|
  | 0x70 | SparkFun SHTC3 | `SHTC3Driver` | temp/RH, inside air; fixed address |
  | 0x74 | SparkFun AS7331 | `AS7331Driver` | UV A/B/C; its temperature is the die temp (kept off the climate view); reads ~0 indoors |
  | 0x76 | SparkFun BME688 (ADR jumper; 0x77 default) | `BME688Driver` | temp/RH/pressure, planned outside sensor; gas heater kept OFF |
  | 0x37 | SparkFun capacitive soil (SEN-30480, CY8CMBR3102) | `SoilCapacitiveDriver` | sleeps and NAKs the first transaction (driver + bus scan retry); `capacitance_pf` is absolute (7 pF dry), `raw_count` re-tunes on every chip power-up; moisture % not calibrated yet |

  A bad/miswired board can hold SDA low and make every address answer in `i2cdetect` — unplug things one by one. The sampler skips a sensor that throws `OSError` so one bad board can't stop logging. New driver = real class in `drivers.py`, register its address in `services.DRIVERS`, a simulated twin in `simulated.py`, and a test built from one real raw reading.
- **Also on the box:** CH340 USB-RS485 adapter for the solar charge controller (Modbus, model not identified yet, no driver). Printable sensor shield: `hardware/sensor-shield/`.

## Known gotchas

- Secrets come from `/etc/greenpi/greenpi.env` (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, ...). Off-device the settings fall back to an insecure dev key with DEBUG on.
- SQLite runs in WAL mode with IMMEDIATE transactions because the sampler and web app write concurrently.
- `TIME_ZONE` is America/Denver; daily highs/lows in `/api/climate/` are by local calendar day.
- `venv/`, `db.sqlite3`, `staticfiles/` and `rtl8188eu/` are git-ignored — never commit the DB (it holds Wi-Fi passwords).
