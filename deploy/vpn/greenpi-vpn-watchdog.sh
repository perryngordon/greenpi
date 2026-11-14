#!/usr/bin/env bash
# Restart the WireGuard tunnel if it has gone stale (no handshake for >3 min
# and the hub doesn't answer ping). Keeps remote access alive after Wi-Fi
# drops / uplink changes at the greenhouse. Run by greenpi-vpn-watchdog.timer.
set -u
HUB=10.8.0.1
last=$(wg show wg0 latest-handshakes 2>/dev/null | awk '{print $2}' | sort -n | tail -1)
now=$(date +%s)
if [ -n "${last:-}" ] && [ "$last" -gt 0 ] && [ $((now - last)) -lt 180 ]; then
  exit 0
fi
if ping -c 3 -W 3 -q "$HUB" >/dev/null 2>&1; then
  exit 0
fi
echo "wg0 stale (last handshake ${last:-none}, now $now); restarting wg-quick@wg0"
systemctl restart wg-quick@wg0
