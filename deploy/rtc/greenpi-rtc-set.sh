#!/bin/sh
# Called by udev when the battery-backed RTC appears at boot (90-greenpi-rtc.rules).
# Safety net: on this Pi the kernel already sets the clock from the RTC ~1.6 s into
# boot (CONFIG_RTC_HCTOSYS; verified 2026-11-18), and Debian's hwclock-set does
# nothing under systemd. If the kernel ever doesn't, set the clock from the RTC here,
# but only forwards: a dead coin cell would make the RTC read ~2000.
rtc=$(/sbin/hwclock --rtc=/dev/rtc0 --get --utc 2>/dev/null) || exit 0
rtc_s=$(date -d "$rtc" +%s 2>/dev/null) || exit 0
now_s=$(date +%s)
if [ "$rtc_s" -gt "$now_s" ]; then
  /sbin/hwclock --rtc=/dev/rtc0 --hctosys --utc
  logger -t greenpi-rtc "system clock set from RTC: $rtc"
else
  logger -t greenpi-rtc "RTC ($rtc) not ahead of system clock; left as is"
fi
