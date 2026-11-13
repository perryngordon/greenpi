from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta

from sensors.models import SensorReading


class Command(BaseCommand):
    help = (
        "Deletes stored SensorReading data points to keep the database bounded. "
        "Choose one strategy: --older-than-days N deletes readings older than N "
        "days; --keep-per-sensor N keeps only the N newest readings per sensor. "
        "Run from a daily cron/systemd timer."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--older-than-days",
            type=int,
            default=None,
            help="Delete readings whose timestamp is older than this many days.",
        )
        parser.add_argument(
            "--keep-per-sensor",
            type=int,
            default=None,
            help="Keep only the N most recent readings per sensor; delete the rest.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be deleted without deleting anything.",
        )

    def handle(self, *args, **options):
        older_than = options["older_than_days"]
        keep = options["keep_per_sensor"]
        dry_run = options["dry_run"]

        if (older_than is None) == (keep is None):
            raise CommandError(
                "Specify exactly one of --older-than-days or --keep-per-sensor."
            )

        if older_than is not None:
            if older_than < 0:
                raise CommandError("--older-than-days must be >= 0.")
            cutoff = timezone.now() - timedelta(days=older_than)
            qs = SensorReading.objects.filter(timestamp__lt=cutoff)
            count = qs.count()
            if not dry_run:
                qs.delete()
            self.stdout.write(
                f"{'Would delete' if dry_run else 'Deleted'} {count} reading(s) "
                f"older than {older_than} day(s)."
            )
            return

        # --keep-per-sensor
        if keep < 0:
            raise CommandError("--keep-per-sensor must be >= 0.")
        total = 0
        sensor_ids = SensorReading.objects.values_list("sensor_id", flat=True).distinct()
        for sensor_id in sensor_ids:
            # ids of the readings to KEEP (newest first), then delete everything else.
            keep_ids = list(
                SensorReading.objects.filter(sensor_id=sensor_id)
                .values_list("id", flat=True)[:keep]
            )
            qs = SensorReading.objects.filter(sensor_id=sensor_id).exclude(id__in=keep_ids)
            count = qs.count()
            if not dry_run:
                qs.delete()
            total += count
        self.stdout.write(
            f"{'Would delete' if dry_run else 'Deleted'} {total} reading(s), "
            f"keeping the {keep} newest per sensor."
        )
