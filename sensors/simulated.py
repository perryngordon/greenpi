"""
Simulated sensors for the staging copy (settings.GREENPI_STAGING).

Same interface as the real drivers in drivers.py (read_raw_data / calibrate /
close), so the sampler and views run unchanged. Values follow a plausible Ward,
CO winter greenhouse: cold nights, a sharp solar-gain peak early afternoon,
humidity moving opposite to temperature, UV only while the sun is up.
"""
import math
import random
from datetime import datetime

from django.conf import settings
from django.utils import timezone


def _local_now():
    return timezone.localtime()


def _sun_factor(now: datetime) -> float:
    """0 at night, rising to 1 at solar noon (rough, good enough to look real)."""
    lat = settings.GREENPI_LATITUDE
    lon = settings.GREENPI_LONGITUDE
    if lat is not None and lon is not None:
        try:
            from astral import Observer
            from astral.sun import elevation
            elev = elevation(Observer(latitude=lat, longitude=lon), now)
            return max(0.0, math.sin(math.radians(max(0.0, elev))) / math.sin(math.radians(60)))
        except Exception:
            pass
    hour = now.hour + now.minute / 60
    return max(0.0, math.sin(math.pi * (hour - 7) / 10)) if 7 <= hour <= 17 else 0.0


def climate_at(now: datetime) -> dict:
    """Deterministic-ish greenhouse air temperature (degF) and humidity for a moment."""
    day = now.timetuple().tm_yday
    # Season: coldest late January, warmest late July (Ward ~9,400 ft).
    season = -math.cos(2 * math.pi * (day - 25) / 365)          # -1 winter .. +1 summer
    night_low = 30 + 18 * season                                  # ~12 F Jan .. ~48 F Jul
    sun = _sun_factor(now)
    # Day-to-day weather: some days are cloudy (less solar gain).
    rng = random.Random(now.date().toordinal())
    cloud = rng.uniform(0.35, 1.0)
    gain = 50 * sun * cloud                                       # solar gain inside glazing
    temp_f = night_low + gain + random.gauss(0, 0.4)
    humidity = 85 - 0.9 * gain - 0.25 * (night_low - 30) + random.gauss(0, 1.0)
    return {
        "temperature_f": round(temp_f, 2),
        "humidity_pct": round(min(99.0, max(8.0, humidity)), 2),
    }


class SimulatedSHTC3:
    def __init__(self, bus_number: int = 1, address: int = 0x70):
        self.address = address

    def read_raw_data(self):
        return climate_at(_local_now())

    def calibrate(self, raw):
        return dict(raw)

    def close(self):
        pass


class SimulatedAS7331:
    def __init__(self, bus_number: int = 1, address: int = 0x74):
        self.address = address

    def read_raw_data(self):
        now = _local_now()
        sun = _sun_factor(now)
        cloud = random.Random(now.date().toordinal()).uniform(0.35, 1.0)
        k = sun * cloud
        jitter = lambda: random.uniform(0.95, 1.05)  # noqa: E731
        return {
            "uva_uw_cm2": round(900 * k * jitter(), 2),
            "uvb_uw_cm2": round(40 * k * k * jitter(), 2),
            "uvc_uw_cm2": round(random.uniform(0, 0.5), 2),
            # Die temperature: a little above the box air.
            "temperature_f": round(climate_at(now)["temperature_f"] + 6, 2),
        }

    def calibrate(self, raw):
        return dict(raw)

    def close(self):
        pass


SIMULATED_DRIVERS = {
    '0x74': SimulatedAS7331,
    '0x70': SimulatedSHTC3,
}
