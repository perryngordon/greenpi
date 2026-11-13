from django.contrib import admin

from .models import Sensor, SensorReading


@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'status', 'sample_interval_seconds', 'last_sampled_at')
    list_filter = ('status', 'sensor_type')


@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    list_display = ('sensor', 'timestamp', 'values')
    list_filter = ('sensor',)
    date_hierarchy = 'timestamp'
