from django.db import models

class Sensor(models.Model):
    STATUS_CHOICES = [
        ('unconfigured', 'Unconfigured'),
        ('accepted', 'Accepted'),
        ('configured', 'Configured'),
    ]

    name = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    sensor_type = models.CharField(max_length=50)  # e.g., 'i2c', 'usb_modbus'
    address = models.CharField(max_length=50)      # e.g., '0x74'
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unconfigured')
    metadata = models.JSONField(default=dict, blank=True)
    # How often this sensor should be sampled and stored, in seconds.
    sample_interval_seconds = models.PositiveIntegerField(default=60)
    # When the sampler last stored a reading for this sensor (None = never).
    last_sampled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_sampling_due(self, now):
        """True if this sensor is due for a new stored reading at time `now`."""
        if self.last_sampled_at is None:
            return True
        elapsed = (now - self.last_sampled_at).total_seconds()
        return elapsed >= self.sample_interval_seconds

    def __str__(self):
        return f"{self.name} ({self.address})"


class SensorReading(models.Model):
    """A single stored data point read from a sensor at a point in time."""

    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name='readings')
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    # Calibrated, human-readable values, e.g. {"temperature_f": 71.2, "humidity_pct": 44.1}.
    values = models.JSONField(default=dict)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.sensor} @ {self.timestamp:%Y-%m-%d %H:%M:%S}"
