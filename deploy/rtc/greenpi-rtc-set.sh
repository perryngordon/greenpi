#!/bin/sh
# Called by udev when the battery-backed RTC appears at boot (90-greenpi-rtc.rules).
# The PCF85063A driver is a module, so the kernel's own boot-time RTC read doesn't
# apply, and Debian's hwclock-set does nothing under systemd. Set the clock from the
# RTC, but only forwards: fake-hwclock has already restored the last saved time,
# and a dead coin cell would make the RTC read ~2000 and drag the clock backwards.
rtc=$(/sbin/hwclock --rtc=/dev/rtc0 --get --utc 2>/dev/null) || exit 0
rtc_s=$(date -d "$rtc" +%s 2>/dev/null) || exit 0
now_s=$(date +%s)
if [ "$rtc_s" -gt "$now_s" ]; then
  /sbin/hwclock --rtc=/dev/rtc0 --hctosys --utc
  logger -t greenpi-rtc "system clock set from RTC: $rtc"
else
  logger -t greenpi-rtc "RTC ($rtc) not ahead of system clock; left as is"
fi
