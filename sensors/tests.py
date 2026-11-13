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
