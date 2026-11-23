import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from sensors.models import Sensor

# The sensors physically on the greenhouse box (and simulated on staging).
SEED = [
    ('0x70', 'Air temp & humidity (SHTC3)', 'SparkFun SHTC3', 60),
    ('0x74', 'UV light (AS7331)', 'SparkFun AS7331', 300),
]


class Command(BaseCommand):
    help = ("Idempotent first-install defaults: web admin user 'admin' (password from "
            "GREENPI_ADMIN_PASSWORD) and the box's known sensors. Never changes existing rows "
            "except keeping the UV sensor off the climate view.")

    def handle(self, *args, **opts):
        U = get_user_model()
        pw = os.environ.get('GREENPI_ADMIN_PASSWORD')
        if pw and not U.objects.filter(username='admin').exists():
            U.objects.create_superuser('admin', '', pw)
            self.stdout.write('created web admin user')
        for addr, name, desc, every in SEED:
            _, new = Sensor.objects.get_or_create(address=addr, defaults=dict(
                name=name, description=desc, sensor_type='i2c', status='configured',
                sample_interval_seconds=every))
            if new:
                self.stdout.write(f'configured sensor {addr} {name}')
        # The AS7331's temperature is its die temperature: keep it off the climate view.
        uv = Sensor.objects.filter(address='0x74').first()
        if uv and (uv.metadata or {}).get('climate') is not False:
            uv.metadata = {**(uv.metadata or {}), 'climate': False}
            uv.save()
            self.stdout.write('UV sensor excluded from climate view')
