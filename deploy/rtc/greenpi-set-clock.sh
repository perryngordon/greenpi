#!/bin/sh
# greenpi-set-clock "YYYY-MM-DD HH:MM:SS" (UTC): called by onsite-update.ps1 with
# the laptop's time. Only acts when the Pi has no network time and is off by more
# than a minute; then also saves the time into the battery-backed RTC.
set -eu
[ "$(timedatectl show -p NTPSynchronized --value)" = yes ] && { echo "clock: network time OK"; exit 0; }
want=$(date -u -d "$1" +%s)
diff=$(( $(date +%s) - want )); [ "$diff" -lt 0 ] && diff=$(( -diff ))
if [ "$diff" -le 60 ]; then echo "clock: within ${diff}s of the laptop"; exit 0; fi
date -u -s "$1" >/dev/null
[ -e /dev/rtc0 ] && hwclock --rtc=/dev/rtc0 --systohc --utc
fake-hwclock save 2>/dev/null || true
echo "clock: was off by ${diff}s, set from the laptop"
