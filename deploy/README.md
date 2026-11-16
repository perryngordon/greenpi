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
GREENPI_LATITUDE=...         # optional: greenhouse location for almanac sunrise/sunset
GREENPI_LONGITUDE=...        # (decimal degrees, west is negative)
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

## Updating

- **Pi has internet:** `ssh admin@10.8.0.21 'cd ~/greenpi && git pull --ff-only && deploy/install.sh'`
- **On site, no internet (Windows laptop):** one-time setup:
  `winget install Git.Git`, then `git clone https://github.com/perryngordon/greenpi.git` and
  `git checkout step1-services` (at home, while online; `git pull` to refresh before a visit).
  At the greenhouse: join **GreenPi_WiFi**, then from the repo folder in PowerShell:
  `.\deploy\onsite-update.ps1`. It pushes the branch straight to the Pi (the Pi's repo accepts
  pushes to its checked-out branch: `receive.denyCurrentBranch updateInstead`) and runs `install.sh`.
  Same script over the VPN from anywhere: `.\deploy\onsite-update.ps1 -PiHost 10.8.0.21`.

## Remote access (VPN)

The Pi is a WireGuard peer on wg-hub (`108.61.151.131:51820`) at **10.8.0.21**, so it can be
reached from anywhere on the VPN regardless of its uplink (home Ethernet, neighbour Wi-Fi, LTE):
`ssh admin@10.8.0.21`, `http://10.8.0.21/`.

- `/etc/wireguard/wg0.conf` + `greenpi.key` live only on the device (never committed).
  `AllowedIPs = 10.8.0.0/24` (only VPN traffic uses the tunnel), `PersistentKeepalive = 25`.
- `greenpi-vpn-watchdog.timer` (every 2 min) restarts `wg-quick@wg0` if there has been no
  handshake for 3 min and the hub doesn't answer ping.
- Hub side: infra peer (free access from other infra peers); owner devices
  (10.8.0.100-119) may reach it on 22/80 (wg-hub `/etc/nftables.conf`).

Hotspot users browse to `http://10.42.0.1/` (or `http://greenhouse/`). Network settings
in the Config tab need the web admin login (`/admin/`).
