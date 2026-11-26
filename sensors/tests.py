from datetime import timedelta
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from .models import Sensor, SensorReading


class SamplingDueTests(TestCase):
    def test_never_sampled_is_due(self):
        s = Sensor(address='0x70', sample_interval_seconds=60)
        self.assertTrue(s.is_sampling_due(timezone.now()))

    def test_within_interval_is_not_due(self):
        now = timezone.now()
        s = Sensor(address='0x70', sample_interval_seconds=60, last_sampled_at=now - timedelta(seconds=30))
        self.assertFalse(s.is_sampling_due(now))

    def test_past_interval_is_due(self):
        now = timezone.now()
        s = Sensor(address='0x70', sample_interval_seconds=60, last_sampled_at=now - timedelta(seconds=90))
        self.assertTrue(s.is_sampling_due(now))


class SampleSensorsCommandTests(TestCase):
    def test_stores_reading_for_due_configured_sensor(self):
        sensor = Sensor.objects.create(address='0x70', sensor_type='i2c', status='configured')

        with mock.patch('sensors.management.commands.sample_sensors.read_calibrated',
                        return_value={'temperature_f': 71.2, 'humidity_pct': 44.1}) as reader:
            call_command('sample_sensors')

        reader.assert_called_once_with('0x70')
        self.assertEqual(sensor.readings.count(), 1)
        reading = sensor.readings.get()
        self.assertEqual(reading.values['temperature_f'], 71.2)

        sensor.refresh_from_db()
        self.assertIsNotNone(sensor.last_sampled_at)

    def test_skips_sensor_not_yet_due(self):
        Sensor.objects.create(
            address='0x70', sensor_type='i2c', status='configured',
            sample_interval_seconds=60, last_sampled_at=timezone.now(),
        )
        with mock.patch('sensors.management.commands.sample_sensors.read_calibrated') as reader:
            call_command('sample_sensors')
        reader.assert_not_called()
        self.assertEqual(SensorReading.objects.count(), 0)

    def test_ignores_unconfigured_sensor(self):
        Sensor.objects.create(address='0x70', sensor_type='i2c', status='unconfigured')
        with mock.patch('sensors.management.commands.sample_sensors.read_calibrated') as reader:
            call_command('sample_sensors')
        reader.assert_not_called()

    def test_failed_read_stores_nothing(self):
        Sensor.objects.create(address='0x70', sensor_type='i2c', status='configured')
        with mock.patch('sensors.management.commands.sample_sensors.read_calibrated', return_value=None):
            call_command('sample_sensors')
        self.assertEqual(SensorReading.objects.count(), 0)

    def test_bus_error_on_one_sensor_does_not_stop_the_others(self):
        Sensor.objects.create(address='0x74', sensor_type='i2c', status='configured')
        Sensor.objects.create(address='0x70', sensor_type='i2c', status='configured')

        def read(address):
            if address == '0x74':
                raise OSError(5, 'Input/output error')
            return {'temperature_f': 70.0}

        with mock.patch('sensors.management.commands.sample_sensors.read_calibrated', side_effect=read):
            call_command('sample_sensors')
        self.assertEqual(SensorReading.objects.get().sensor.address, '0x70')


class BME688CompensationTests(TestCase):
    # One raw reading captured from the real SparkFun BME688 on the Pi
    # (2026-11-26, indoors, ~8,500 ft); a SHTC3 next to it read 69 F / 16 %.
    RAW = {'pres_adc': 494207, 'temp_adc': 491279, 'hum_adc': 13340,
           'cal_t1': 26267, 'cal_t2': 26647, 'cal_t3': 3, 'cal_p1': 35564, 'cal_p2': -10334,
           'cal_p3': 88, 'cal_p4': 8351, 'cal_p5': -124, 'cal_p6': 30, 'cal_p7': 25,
           'cal_p8': -604, 'cal_p9': -3434, 'cal_p10': 30, 'cal_h1': 652, 'cal_h2': 1033,
           'cal_h3': 0, 'cal_h4': 45, 'cal_h5': 20, 'cal_h6': 120, 'cal_h7': -100}

    def test_real_sample_converts_to_sane_values(self):
        from .drivers import BME688Driver
        with mock.patch('sensors.drivers.smbus2.SMBus'):
            values = BME688Driver(address=0x76).calibrate({k: float(v) for k, v in self.RAW.items()})
        self.assertEqual(values, {'temperature_f': 72.61, 'humidity_pct': 13.22, 'pressure_hpa': 735.6})


class SoilCapacitiveDriverTests(TestCase):
    class FakeMBR3:
        """Mimics the CY8CMBR3102: NAKs every 3rd access (wake-up), DEBUG_SENSOR_ID follows SENSOR_ID."""
        def __init__(self, *args):
            self.calls, self.sensor_id = 0, 0
            self.regs = {0x8F: 0x9A, 0xDD: 7, 0xE2: 1116}

        def _maybe_nak(self):
            self.calls += 1
            if self.calls % 3 == 1:
                raise OSError(5, 'Input/output error')

        def read_byte_data(self, addr, reg):
            self._maybe_nak()
            return self.sensor_id if reg == 0xDC else self.regs[reg]

        def read_word_data(self, addr, reg):
            self._maybe_nak()
            return self.regs[reg]

        def write_byte_data(self, addr, reg, value):
            self._maybe_nak()
            if reg == 0x82:
                self.sensor_id = value

        def close(self):
            pass

    def test_reads_capacitance_through_wakeup_naks(self):
        from .drivers import SoilCapacitiveDriver
        with mock.patch('sensors.drivers.smbus2.SMBus', self.FakeMBR3):
            d = SoilCapacitiveDriver(address=0x37)
            raw = d.read_raw_data()
        self.assertEqual(d.calibrate(raw), {'capacitance_pf': 7, 'raw_count': 1116})

    def test_wrong_chip_returns_none(self):
        from .drivers import SoilCapacitiveDriver
        with mock.patch('sensors.drivers.smbus2.SMBus', self.FakeMBR3):
            d = SoilCapacitiveDriver(address=0x37)
            d.bus.regs[0x8F] = 0x12
            self.assertIsNone(d.read_raw_data())


class PruneReadingsCommandTests(TestCase):
    def _reading(self, sensor, age_days):
        r = SensorReading.objects.create(sensor=sensor, values={'v': age_days})
        # auto_now_add ignores an explicit timestamp, so backdate after creation.
        SensorReading.objects.filter(pk=r.pk).update(
            timestamp=timezone.now() - timedelta(days=age_days)
        )
        return r

    def test_requires_exactly_one_strategy(self):
        with self.assertRaises(Exception):
            call_command('prune_readings')
        with self.assertRaises(Exception):
            call_command('prune_readings', '--older-than-days', '1', '--keep-per-sensor', '1')

    def test_older_than_days_deletes_old(self):
        sensor = Sensor.objects.create(address='0x70', sensor_type='i2c', status='configured')
        self._reading(sensor, age_days=10)
        self._reading(sensor, age_days=1)
        call_command('prune_readings', '--older-than-days', '7')
        self.assertEqual(sensor.readings.count(), 1)

    def test_older_than_days_dry_run_deletes_nothing(self):
        sensor = Sensor.objects.create(address='0x70', sensor_type='i2c', status='configured')
        self._reading(sensor, age_days=10)
        call_command('prune_readings', '--older-than-days', '7', '--dry-run')
        self.assertEqual(sensor.readings.count(), 1)

    def test_keep_per_sensor_keeps_newest(self):
        sensor = Sensor.objects.create(address='0x70', sensor_type='i2c', status='configured')
        for age in (5, 4, 3, 2, 1):
            self._reading(sensor, age_days=age)
        call_command('prune_readings', '--keep-per-sensor', '2')
        remaining = list(sensor.readings.values_list('values', flat=True))
        # Newest two are age 1 and 2 (ordering is -timestamp).
        self.assertEqual(remaining, [{'v': 1}, {'v': 2}])

    def test_keep_per_sensor_is_per_sensor(self):
        a = Sensor.objects.create(address='0x70', sensor_type='i2c', status='configured')
        b = Sensor.objects.create(address='0x74', sensor_type='i2c', status='configured')
        for age in (3, 2, 1):
            self._reading(a, age_days=age)
            self._reading(b, age_days=age)
        call_command('prune_readings', '--keep-per-sensor', '1')
        self.assertEqual(a.readings.count(), 1)
        self.assertEqual(b.readings.count(), 1)


class HistoryEndpointTests(TestCase):
    def test_returns_stored_readings_newest_first(self):
        sensor = Sensor.objects.create(address='0x70', sensor_type='i2c', status='configured')
        SensorReading.objects.create(sensor=sensor, values={'temperature_f': 70})
        SensorReading.objects.create(sensor=sensor, values={'temperature_f': 72})

        resp = self.client.get(f'/api/sensors/{sensor.id}/history/')
        self.assertEqual(resp.status_code, 200)
        readings = resp.json()['readings']
        self.assertEqual(len(readings), 2)
        self.assertEqual(readings[0]['values']['temperature_f'], 72)

    def test_missing_sensor_returns_404(self):
        resp = self.client.get('/api/sensors/999999/history/')
        self.assertEqual(resp.status_code, 404)


class StagingTests(TestCase):
    """Staging copy: simulated sensors, safe network views, guarded snapshot loader."""

    def test_simulated_climate_is_plausible(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from .simulated import climate_at
        tz = ZoneInfo("America/Denver")
        night = climate_at(datetime(2027, 1, 20, 4, 0, tzinfo=tz))
        noon = climate_at(datetime(2027, 1, 20, 13, 0, tzinfo=tz))
        self.assertLess(night["temperature_f"], noon["temperature_f"])
        self.assertTrue(0 < night["temperature_f"] < 40, night)
        self.assertTrue(8 <= noon["humidity_pct"] <= 99)

    def test_simulated_drivers_match_real_fields(self):
        from .simulated import SimulatedAS7331, SimulatedSHTC3
        sht = SimulatedSHTC3()
        self.assertEqual(set(sht.calibrate(sht.read_raw_data())), {"temperature_f", "humidity_pct"})
        uv = SimulatedAS7331()
        self.assertEqual(set(uv.calibrate(uv.read_raw_data())),
                         {"uva_uw_cm2", "uvb_uw_cm2", "uvc_uw_cm2", "temperature_f"})

    def test_load_snapshot_refuses_on_real_device(self):
        from django.core.management.base import CommandError
        from django.test import override_settings
        with override_settings(GREENPI_STAGING=False):
            with self.assertRaises(CommandError):
                call_command("load_snapshot", "/nonexistent.sqlite3")

    def test_staging_network_saves_without_applying(self):
        import json
        import tempfile
        from pathlib import Path
        from django.contrib.auth import get_user_model
        from django.test import override_settings
        from network import views as net
        get_user_model().objects.create_superuser("admin", "", "pw")
        self.client.login(username="admin", password="pw")
        with tempfile.TemporaryDirectory() as tmp, \
                override_settings(GREENPI_STAGING=True, DATA_DIR=Path(tmp)), \
                mock.patch.object(net, "apply_ap") as ap, mock.patch.object(net, "apply_client") as cl:
            r = self.client.post("/api/network/", json.dumps({"ssid": "X", "wifi_client_ssid": "Y"}),
                                 content_type="application/json")
            self.assertEqual(r.status_code, 200)
            self.assertIn("Staging", r.json()["message"])
            ap.assert_not_called()
            cl.assert_not_called()
            s = self.client.get("/api/network/survey/").json()
            self.assertEqual(s["networks"], [])
            self.assertIn("Staging", s["note"])
            # A survey copied from the Pi is shown instead of a live scan.
            (Path(tmp) / "surveys").mkdir()
            (Path(tmp) / "surveys" / "survey-20261118-120000.json").write_text(json.dumps(
                {"interface": "wlsta0", "scanned_at": "2026-11-18T12:00:00-07:00",
                 "networks": [{"ssid": "NeighbourWiFi"}]}))
            s = self.client.get("/api/network/survey/").json()
            self.assertEqual(s["networks"][0]["ssid"], "NeighbourWiFi")
            self.assertIsNotNone(self.client.get("/api/me/").json()["staging"])
        with override_settings(GREENPI_STAGING=False):   # also when run on a dev laptop in staging mode
            self.assertIsNone(self.client.get("/api/me/").json()["staging"])
