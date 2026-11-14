# Deploying GreenPi on the greenhouse Pi

Target: Raspberry Pi CM4 (Debian 12), user `admin`, repo at `/home/admin/greenpi`,
venv at `venv/`, system on eMMC, app data drive (USB) at `/srv/greenpi-data`
(fstab `nofail`, so the Pi boots without it).

```bash
cd ~/greenpi && git pull && deploy/install.sh   # idempotent
```

## Secrets: `/etc/greenpi/greenpi.env` (root:admin 0640, never committed)

```
GREENPI_AP_PASSWORD=...      # hotspot WPA2 password (first install only; then it lives in the DB)
DJANGO_SECRET_KEY=...
GREENPI_ADMIN_PASSWORD=...   # web admin user "admin" (first install only)
DJANGO_DEBUG=0
GREENPI_DATA_DIR=/srv/greenpi-data
GREENPI_AP_INTERFACE=wlap0
GREENPI_STA_INTERFACE=wlsta0
```

## What runs

| Unit | What |
|---|---|
| `greenpi-web` | gunicorn on :80 (static files via whitenoise; works offline) |
| `greenpi-sampler` | `manage.py sample_sensors --loop` stores configured sensors (default 1/min) |
| `greenpi-backup.timer` | 02:30 nightly SQLite snapshot to `/srv/greenpi-data/backups/db` (keeps 30) |
| `hostapd` + `dnsmasq` + `greenpi-ap-ip` | hotspot `GreenPi_WiFi` on `wlap0`, 10.42.0.1/24, no default route handed out |

## Radios

| Name | Hardware | Role |
|---|---|---|
| `wlap0` | Linksys AE1200 (brcmfmac) | hotspot, unmanaged by NetworkManager |
| `wlsta0` | Comfast RTL8188EUS (in-kernel rtl8xxxu) | Wi-Fi client uplink via NetworkManager (`nmcli`) |

Names are pinned by MAC in `deploy/network/*.link`; update the MACs there if a dongle is swapped.

Hotspot users browse to `http://10.42.0.1/` (or `http://greenhouse/`). Network settings
in the Config tab need the web admin login (`/admin/`).
