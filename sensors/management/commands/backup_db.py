import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Writes a consistent snapshot of the SQLite database (safe while the "
        "sampler is running) to <DATA_DIR>/backups/db/greenpi-YYYY-MM-DD.sqlite3 "
        "and deletes all but the newest --keep snapshots. Run nightly."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dest", default=None, help="Directory for snapshots (default: DATA_DIR/backups/db).")
        parser.add_argument("--keep", type=int, default=30, help="Number of snapshots to keep (default 30).")

    def handle(self, *args, **opts):
        dest = Path(opts["dest"] or settings.DATA_DIR / "backups" / "db")
        if not dest.parent.exists():
            # Data drive not mounted: fail loudly rather than filling the eMMC.
            raise CommandError(f"{dest.parent} does not exist (is the data drive mounted?)")
        dest.mkdir(parents=True, exist_ok=True)

        target = dest / f"greenpi-{timezone.localdate().isoformat()}.sqlite3"
        tmp = target.with_suffix(".tmp")
        src = sqlite3.connect(settings.DATABASES["default"]["NAME"], timeout=30)
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        tmp.replace(target)
        self.stdout.write(f"Wrote {target} ({target.stat().st_size // 1024} KiB)")

        snapshots = sorted(dest.glob("greenpi-*.sqlite3"))
        for old in snapshots[: max(0, len(snapshots) - opts["keep"])]:
            old.unlink()
            self.stdout.write(f"Removed old snapshot {old.name}")
