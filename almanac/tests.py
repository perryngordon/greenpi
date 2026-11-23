import json
from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from blog.models import Post
from sensors.models import Sensor, SensorReading

from .models import AlmanacEvent


def reading(sensor, local_dt, temp, rh):
    r = SensorReading.objects.create(sensor=sensor, values={"temperature_f": temp, "humidity_pct": rh})
    # timestamp is auto_now_add; set it explicitly afterwards.
    SensorReading.objects.filter(id=r.id).update(timestamp=timezone.make_aware(local_dt))


class AlmanacTests(TestCase):
    def setUp(self):
        air = Sensor.objects.create(name="Air", sensor_type="i2c", address="0x70", status="configured")
        uv = Sensor.objects.create(name="UV", sensor_type="i2c", address="0x74", status="configured",
                                   metadata={"climate": False})
        # 16 Nov local: 38..71 °F; the late-evening reading must stay on the 16th
        # (UTC would put it on the 17th).
        reading(air, datetime(2026, 11, 16, 6, 0), 38.0, 80)
        reading(air, datetime(2026, 11, 16, 14, 0), 71.0, 30)
        reading(air, datetime(2026, 11, 16, 23, 30), 45.0, 60)
        reading(air, datetime(2026, 11, 17, 3, 0), 33.5, 85)
        reading(uv, datetime(2026, 11, 16, 14, 0), 99.0, 0)  # die temp: must be ignored
        AlmanacEvent.objects.create(title="Avg first frost", date=date(2020, 11, 16), yearly=True, kind="frost")
        Post.objects.create(title="Moved the probe", date=date(2026, 11, 16))
        Post.objects.create(title="Draft", date=date(2026, 11, 16), published=False)

    def test_month_daily_highs_lows_local_days(self):
        d = self.client.get("/api/almanac/month/?month=2026-11").json()
        self.assertEqual(len(d["days"]), 30)
        day16 = d["days"][15]
        self.assertEqual(day16["climate"]["temp_min"], 38.0)
        self.assertEqual(day16["climate"]["temp_max"], 71.0)
        self.assertEqual(day16["climate"]["readings"], 3)
        self.assertEqual(d["days"][16]["climate"]["temp_min"], 33.5)
        self.assertEqual([e["title"] for e in day16["events"]], ["Avg first frost"])
        self.assertEqual([p["title"] for p in day16["posts"]], ["Moved the probe"])
        self.assertIsNone(day16["sunrise"])  # no location configured
        self.assertIn("emoji", day16["moon"])

    @override_settings(GREENPI_LATITUDE=39.74, GREENPI_LONGITUDE=-104.99)
    def test_day_has_sun_times_when_location_set(self):
        d = self.client.get("/api/almanac/day/2026-11-16/").json()
        self.assertTrue(d["location_set"])
        self.assertTrue(d["sun"]["sunrise"].startswith(("06:", "07:")))
        self.assertTrue(d["sun"]["sunset"].startswith(("16:", "17:")))
        self.assertLess(d["sun"]["daylight_change_minutes"], 0)  # days shortening in November

    def test_events_editing_requires_staff(self):
        body = json.dumps({"title": "Plant garlic", "date": "2026-10-15", "kind": "planting"})
        self.assertEqual(self.client.post("/api/almanac/events/", body, content_type="application/json").status_code, 403)
        self.client.force_login(get_user_model().objects.create_superuser("admin", "", "pw"))
        self.assertEqual(self.client.post("/api/almanac/events/", body, content_type="application/json").status_code, 201)
