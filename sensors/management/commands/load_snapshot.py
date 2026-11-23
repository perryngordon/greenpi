import json
import shutil
import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "STAGING ONLY. Replaces this copy's database with a snapshot from the "
        "greenhouse Pi (a nightly greenpi-YYYY-MM-DD.sqlite3 backup) and copies "
        "its photos and Wi-Fi surveys. Stored Wi-Fi passwords are blanked. "
        "Stop greenpi-web/greenpi-sampler first (deploy/staging/load-snapshot.sh does)."
    )

    def add_arguments(self, parser):
        parser.add_argument("db", help="Snapshot .sqlite3 file from the Pi.")
        parser.add_argument("--media", help="Pi's media/ folder (photos) to merge in.")
        parser.add_argument("--surveys", help="Pi's surveys/ folder to merge in.")
        parser.add_argument("--source", default="the greenhouse Pi", help="Where it came from (shown in the banner).")

    def handle(self, *args, **opts):
        if not settings.GREENPI_STAGING:
            raise CommandError("Refusing: GREENPI_STAGING is not set. This would overwrite the real database.")
        snap = Path(opts["db"])
        if not snap.is_file():
            raise CommandError(f"{snap} not found")

        # immutable: read without creating -wal/-shm files next to the snapshot.
        src = sqlite3.connect(f"file:{snap}?mode=ro&immutable=1", uri=True)
        try:
            ok = src.execute("PRAGMA integrity_check").fetchone()[0]
            if ok != "ok":
                raise CommandError(f"Snapshot failed integrity_check: {ok}")
            last = src.execute("SELECT MAX(timestamp) FROM sensors_sensorreading").fetchone()[0]
            connections.close_all()
            dst = sqlite3.connect(settings.DATABASES["default"]["NAME"], timeout=30)
            try:
                src.backup(dst)  # page-level copy: replaces the whole database
            finally:
                dst.close()
        finally:
            src.close()
        self.stdout.write(f"Loaded {snap.name} (last reading {last})")

        call_command("migrate", interactive=False, verbosity=0)

        # The Pi's DB holds real Wi-Fi passwords; staging never needs them.
        from network.models import NetworkConfig
        n = NetworkConfig.objects.update(wifi_password="", wifi_client_password="")
        self.stdout.write(f"Blanked Wi-Fi passwords in {n} network config row(s)")

        for key, sub in (("media", "media"), ("surveys", "surveys")):
            if opts[key]:
                s = Path(opts[key])
                if s.is_dir():
                    shutil.copytree(s, settings.DATA_DIR / sub, dirs_exist_ok=True)
                    self.stdout.write(f"Copied {sub}/ from {s}")

        last_iso = None
        if last:
            # SQLite stores 'YYYY-MM-DD HH:MM:SS[.ffffff]' in UTC (USE_TZ).
            last_iso = last.replace(" ", "T") + ("" if "+" in last else "+00:00")
        info = {
            "file": snap.name,
            "source": opts["source"],
            "last_reading_at": last_iso,
            "loaded_at": timezone.now().isoformat(),
        }
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        (settings.DATA_DIR / "staging-snapshot.json").write_text(json.dumps(info, indent=1))
        self.stdout.write("Done.")
