# GreenPi staging copy

A second GreenPi that runs **without the greenhouse hardware**, so development can
carry on while the real box sits in the greenhouse with no internet.

| | |
|---|---|
| Where | pve **CT 219 `greenpi-stage`** (Debian 12, like the Pi), LAN 172.18.0.219 |
| VPN | **http://10.8.0.22/** (wg-hub infra peer; owner devices may use 22 + 80) |
| Login | web and SSH user `admin`, password = the greenpi web admin password (`GREENPI_ADMIN_PASSWORD`) |
| Repo | `/home/admin/greenpi`, branch `step1-services` (`git pull` + `deploy/staging/install-staging.sh`) |
| Data | `/srv/greenpi-data` (same layout as the Pi's USB drive) |

`/etc/greenpi/greenpi.env` has **`GREENPI_STAGING=1`**, which:

- replaces the I2C drivers with simulated SHTC3/AS7331 sensors (`sensors/simulated.py`:
  Ward winter nights, solar-gain afternoons, cloudy days, UV following the sun);
- saves network settings but never touches a radio; the Wi-Fi survey shows the Pi's
  last saved scan;
- shows a yellow **STAGING COPY** banner with how fresh the real data is;
- allows `manage.py load_snapshot` (refuses to run anywhere else).

## Getting the greenhouse's real data onto staging

Either way, `load_snapshot` swaps in the Pi's database (newest nightly backup), merges
`media/` (photos) and `surveys/`, and **blanks the stored Wi-Fi passwords**. Sensor readings
after the snapshot are simulated, and the climate chart shows the gap as a break.

1. **Pi online (VPN up):** automatic. `greenpi-stage-sync.timer` runs at 03:30, after the
   Pi's 02:30 backup. It rsyncs `backups/db`, `media` and `surveys` into `/srv/greenpi-data/pi-mirror`
   and loads the newest snapshot if it changed. The pull key `/root/.ssh/greenpi-pull` is
   locked on the Pi to read-only rsync of `/srv/greenpi-data`, from 10.8.0.22 only
   (`command="/usr/bin/rrsync -ro /srv/greenpi-data/",restrict,from="10.8.0.22"` in
   `~admin/.ssh/authorized_keys`). Run now: `sudo systemctl start greenpi-stage-sync`.
2. **Pi offline (sneakernet with the Windows laptop):**
   - at the greenhouse, `.\deploy\onsite-update.ps1` updates the code *and* takes a fresh
     snapshot into `~\greenpi-snapshots\<date-time>\` (`-DataOnly` to skip the code update);
   - back home on the VPN, `.\deploy\push-snapshot.ps1` uploads the newest folder and loads it.

   Both scripts add the laptop's SSH key on first use, so later runs don't ask for passwords.
3. **By hand:** `sudo greenpi-load-snapshot <folder-or-.sqlite3> ["label"]`.

## Rebuilding it

```bash
# on pve: Debian 12 CT, unprivileged, nesting+keyctl, firewall 219.fw (GROUP base + +admin tcp/80)
apt install git python3-venv rsync wireguard-tools sudo sqlite3
useradd -m -s /bin/bash admin          # NOPASSWD sudo, like the Pi
git clone -b step1-services https://github.com/perryngordon/greenpi.git ~admin/greenpi
# /etc/greenpi/greenpi.env (root:admin 0640):
#   GREENPI_STAGING=1, DJANGO_SECRET_KEY, DJANGO_DEBUG=0, GREENPI_DATA_DIR=/srv/greenpi-data,
#   GREENPI_LATITUDE/LONGITUDE, GREENPI_ADMIN_PASSWORD
# /etc/wireguard/wg0.conf: Address 10.8.0.22/24, AllowedIPs 10.8.0.0/24, keepalive 25
sudo -u admin ~admin/greenpi/deploy/staging/install-staging.sh
```
