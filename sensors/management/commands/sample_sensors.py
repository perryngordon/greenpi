import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from sensors.models import Sensor, SensorReading
from sensors.services import DRIVERS, read_calibrated


class Command(BaseCommand):
    help = (
        "Reads every configured sensor that is due for sampling and stores the "
        "measurement as a SensorReading. Each sensor is sampled no more often "
        "than its sample_interval_seconds. Run once (e.g. from a cron/systemd "
        "timer every minute) or continuously with --loop."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--loop",
            action="store_true",
            help="Keep running, sampling due sensors every --tick seconds.",
        )
        parser.add_argument(
            "--tick",
            type=int,
            default=10,
            help="Seconds to sleep between passes when using --loop (default: 10).",
        )

    def handle(self, *args, **options):
        if options["loop"]:
            tick = max(1, options["tick"])
            self.stdout.write(f"Sampling loop started (tick={tick}s). Ctrl-C to stop.")
            try:
                while True:
                    self.sample_due()
                    time.sleep(tick)
            except KeyboardInterrupt:
                self.stdout.write("Sampling loop stopped.")
        else:
            self.sample_due()

    def sample_due(self):
        now = timezone.now()
        sensors = Sensor.objects.filter(status='configured', address__in=DRIVERS.keys())
        for sensor in sensors:
            if not sensor.is_sampling_due(now):
                continue
            try:
                values = read_calibrated(sensor.address)
            except OSError as exc:
                # One flaky sensor or a disturbed I2C bus must not stop the
                # others from being logged; retry it on the next pass.
                self.stderr.write(f"Read error on {sensor}: {exc}; skipping.")
                continue
            if values is None:
                self.stderr.write(f"Failed to read {sensor}; skipping.")
                continue
            SensorReading.objects.create(sensor=sensor, values=values)
            # Refresh timestamp so the next pass respects the interval.
            sensor.last_sampled_at = timezone.now()
            sensor.save(update_fields=["last_sampled_at"])
            self.stdout.write(f"Stored reading for {sensor}: {values}")
