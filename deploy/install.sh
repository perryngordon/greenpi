#!/usr/bin/env bash
# Idempotent installer for the greenhouse Pi. Run as `admin` from the repo:
#   cd ~/greenpi && deploy/install.sh
# Needs /etc/greenpi/greenpi.env (secrets; never committed) - see deploy/README.md.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO=$(pwd)
ENV=/etc/greenpi/greenpi.env
sudo test -f "$ENV" || { echo "missing $ENV"; exit 1; }
set -a; eval "$(sudo cat "$ENV")"; set +a
if [ "${GREENPI_STAGING:-0}" = 1 ]; then echo "this is the staging copy: use deploy/staging/install-staging.sh"; exit 1; fi

echo "== git: accept pushes to the checked-out branch (on-site updates from a laptop)"
git config receive.denyCurrentBranch updateInstead

echo "== python deps"
# On site there may be no internet; already-installed pins don't need it.
venv/bin/pip install -q -r requirements.txt || echo "WARNING: pip install failed (offline?); continuing with installed packages"

echo "== wifi interface names (persist via .link files, applied live now)"
sudo install -m 644 deploy/network/*.link /etc/systemd/network/
sudo install -m 644 deploy/network/90-greenpi.conf /etc/NetworkManager/conf.d/
rename_by_mac() {  # mac newname
  local cur; cur=$(ip -o link | awk -v m="$1" '$0 ~ m {sub(":","",$2); print $2}')
  if [ -n "$cur" ] && [ "$cur" != "$2" ]; then
    sudo systemctl stop hostapd || true
    sudo ip link set dev "$cur" down
    sudo ip link set dev "$cur" name "$2"
    sudo ip link set dev "$2" up
    echo "renamed $cur -> $2"
  fi
}
rename_by_mac 60:38:e0:09:cc:9c wlap0
rename_by_mac e0:e1:a9:93:c8:e1 wlsta0
sudo systemctl reload NetworkManager

echo "== battery-backed clock (CM4 IO Board PCF85063A + CR2032): no internet at the greenhouse"
CFG=/boot/firmware/config.txt
if ! grep -q "^dtoverlay=i2c-rtc,pcf85063a" "$CFG"; then
  # Appended at the end = inside the final [all] section.
  printf '\n# greenpi: CM4 IO Board RTC (needs a reboot)\n[all]\ndtparam=i2c_vc=on\ndtoverlay=i2c-rtc,pcf85063a,i2c_csi_dsi\n' | sudo tee -a "$CFG" >/dev/null
  echo "RTC enabled in $CFG: REBOOT to activate"
fi
sudo install -m 755 deploy/rtc/greenpi-rtc-set.sh /usr/local/sbin/greenpi-rtc-set
sudo install -m 755 deploy/rtc/greenpi-set-clock.sh /usr/local/sbin/greenpi-set-clock
sudo install -m 644 deploy/rtc/90-greenpi-rtc.rules /etc/udev/rules.d/
if [ -e /dev/rtc0 ] && [ "$(timedatectl show -p NTPSynchronized --value)" = yes ]; then
  sudo hwclock --rtc=/dev/rtc0 --systohc --utc && echo "RTC set from network time"
fi

echo "== systemd units"
sudo install -m 644 deploy/systemd/*.service deploy/systemd/*.timer /etc/systemd/system/
sudo install -d /etc/systemd/system/hostapd.service.d
sudo install -m 644 deploy/systemd/hostapd.service.d/greenpi.conf /etc/systemd/system/hostapd.service.d/
sudo rm -f /etc/dnsmasq.d/django-dhcp.conf   # replaced by greenpi-ap.conf
sudo systemctl daemon-reload
sudo systemctl unmask hostapd 2>/dev/null || true
sudo systemctl enable -q hostapd dnsmasq greenpi-ap-ip.service
sudo systemctl restart greenpi-ap-ip.service

echo "== database, static files, admin user, sensors"
M="venv/bin/python manage.py"
$M migrate --noinput
$M collectstatic --noinput -v 0
$M seed_defaults

echo "== hotspot config (from DB; first run takes the password from $ENV)"
$M apply_network --from-env

echo "== VPN (wg-hub) watchdog, only if the tunnel is configured on this device"
if sudo test -f /etc/wireguard/wg0.conf; then
  sudo install -m 755 deploy/vpn/greenpi-vpn-watchdog.sh /usr/local/sbin/greenpi-vpn-watchdog
  sudo install -m 644 deploy/vpn/greenpi-vpn-watchdog.service deploy/vpn/greenpi-vpn-watchdog.timer /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable -q --now wg-quick@wg0 greenpi-vpn-watchdog.timer
else
  echo "no /etc/wireguard/wg0.conf - skipping (see deploy/README.md)"
fi

echo "== app services"
sudo systemctl enable -q --now greenpi-web greenpi-sampler greenpi-backup.timer
sudo systemctl restart greenpi-web greenpi-sampler
sleep 3
systemctl is-active hostapd dnsmasq greenpi-ap-ip greenpi-web greenpi-sampler | paste -sd' '
echo "done: http://$(hostname -I | awk '{print $1}')/  hotspot: 10.42.0.1"
