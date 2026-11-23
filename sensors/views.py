from datetime import datetime, timedelta

from django.http import JsonResponse
from django.utils import timezone
import json
from .models import Sensor, SensorReading
from .services import SensorDiscoveryService, read_calibrated, DRIVERS

# Mapping of common I2C addresses to sensor types/metadata
SENSOR_METADATA = {
    '0x74': {
        'type': 'i2c',
        'name': 'SparkFun Spectral UV Sensor (AS7331)',
        'metadata': {'manufacturer': 'SparkFun', 'model': 'AS7331'}
    },
    '0x70': {
        'type': 'i2c',
        'name': 'SparkFun Humidity Sensor (SHTC3)',
        'metadata': {'manufacturer': 'SparkFun', 'model': 'SHTC3'}
    },
    # Add more as needed
}

def get_sensor_list(request):
    db_sensors = Sensor.objects.all()
    sensors = []
    
    for s in db_sensors:
        sensors.append({
            "id": str(s.id),
            "type": s.sensor_type,
            "name": s.name,
            "address": s.address,
            "status": s.status,
            "description": s.description,
            "metadata": s.metadata,
            "sample_interval_seconds": s.sample_interval_seconds,
            "last_sampled_at": s.last_sampled_at.isoformat() if s.last_sampled_at else None,
        })

    i2c_addresses = SensorDiscoveryService.scan_i2c(bus_number=1)
    for addr in i2c_addresses:
        if not Sensor.objects.filter(address=addr).exists():
            meta = SENSOR_METADATA.get(addr, {'type': 'i2c', 'name': 'Unknown I2C Sensor', 'metadata': {}})
            sensors.append({
                "id": f"discovered_{addr}",
                "type": meta['type'],
                "name": meta['name'],
                "address": addr,
                "status": "unconfigured",
                "description": "",
                "metadata": meta['metadata']
            })

    return JsonResponse({"sensors": sensors})

def mock_sensor_list(request):
    return JsonResponse({"sensors": get_sensor_list(request)})

def configure_sensor(request):
    from config.api import staff_only
    denied = staff_only(request)
    if denied:
        return denied
    if request.method == "POST":
        data = json.loads(request.body)
        sensor_id = data.get("id")
        name = data.get("name")
        description = data.get("description")
        address = data.get("address")
        sensor_type = data.get("type")
        sample_interval = data.get("sample_interval_seconds")

        if sensor_id.startswith("discovered_"):
            sensor = Sensor(
                name=name,
                description=description,
                sensor_type=sensor_type,
                address=address,
                status='configured'
            )
            if sample_interval is not None:
                sensor.sample_interval_seconds = int(sample_interval)
            sensor.save()
            return JsonResponse({"status": "success", "message": "Sensor configured"})
        else:
            sensor = Sensor.objects.get(id=sensor_id)
            sensor.name = name
            sensor.description = description
            sensor.status = 'configured'
            if sample_interval is not None:
                sensor.sample_interval_seconds = int(sample_interval)
            sensor.save()
            return JsonResponse({"status": "success", "message": "Sensor updated"})

def get_sensor_readings(request, sensor_id):
    if sensor_id.startswith("discovered_"):
        address = sensor_id[len("discovered_"):]
    else:
        sensor = Sensor.objects.get(id=sensor_id)
        address = sensor.address

    if address not in DRIVERS:
        return JsonResponse({"error": "Sensor driver not implemented"}, status=404)

    # Always return calibrated, human-readable values (with units),
    # whether or not the sensor has been configured yet.
    readings = read_calibrated(address)
    if readings is None:
        return JsonResponse({"error": "Could not read from sensor"}, status=500)
    return JsonResponse({"sensor_id": sensor_id, "readings": readings})

def mock_sensor_readings(request, sensor_id):
    return get_sensor_readings(request, sensor_id)

def get_sensor_history(request, sensor_id):
    """Returns the stored data points for a configured sensor, newest first."""
    try:
        sensor = Sensor.objects.get(id=sensor_id)
    except (Sensor.DoesNotExist, ValueError):
        return JsonResponse({"error": "Sensor not found"}, status=404)

    try:
        limit = min(int(request.GET.get("limit", 500)), 5000)
    except ValueError:
        limit = 500

    readings = sensor.readings.all()[:limit]
    return JsonResponse({
        "sensor_id": str(sensor.id),
        "readings": [
            {"timestamp": r.timestamp.isoformat(), "values": r.values}
            for r in readings
        ],
    })


# Values the climate dashboard charts and summarises, in display order.
CLIMATE_KEYS = ("temperature_f", "humidity_pct")
MAX_CHART_POINTS = 400


def climate(request):
    """
    Climate dashboard data for every configured sensor that reports
    temperature and/or humidity:
      * latest  - most recent stored values
      * series  - bucket-averaged values over the last `hours` (<= ~400 points)
      * daily   - per local day min/max/avg over the last `days`
    """
    try:
        hours = max(1, min(int(request.GET.get("hours", 24)), 24 * 366))
        days = max(1, min(int(request.GET.get("days", 14)), 366))
    except ValueError:
        return JsonResponse({"error": "hours and days must be integers"}, status=400)

    now = timezone.now()
    series_start = now - timedelta(hours=hours)
    local_today = timezone.localdate(now)
    daily_start = timezone.make_aware(
        datetime.combine(local_today - timedelta(days=days - 1), datetime.min.time())
    )
    since = min(series_start, daily_start)
    bucket_s = max(60, int(hours * 3600 / MAX_CHART_POINTS))

    out = []
    for sensor in Sensor.objects.filter(status="configured").order_by("id"):
        # e.g. the AS7331 reports its die temperature, which isn't air climate.
        if (sensor.metadata or {}).get("climate") is False:
            continue
        rows = list(
            sensor.readings.filter(timestamp__gte=since)
            .order_by("timestamp")
            .values_list("timestamp", "values")
        )
        keys = [k for k in CLIMATE_KEYS if any(k in v for _, v in rows)]
        latest = sensor.readings.order_by("-timestamp").first()
        if not keys and not (latest and any(k in latest.values for k in CLIMATE_KEYS)):
            continue

        # Bucketed chart series.
        buckets = {}
        for ts, vals in rows:
            if ts < series_start:
                continue
            b = int(ts.timestamp()) // bucket_s
            acc = buckets.setdefault(b, {})
            for k in keys:
                if isinstance(vals.get(k), (int, float)):
                    acc.setdefault(k, []).append(vals[k])
        series = [
            {"t": (b * bucket_s + bucket_s // 2) * 1000,
             **{k: round(sum(v) / len(v), 2) for k, v in acc.items()}}
            for b, acc in sorted(buckets.items())
        ]

        # Daily min / max / avg by local calendar day.
        per_day = {}
        for ts, vals in rows:
            if ts < daily_start:
                continue
            d = timezone.localtime(ts).date().isoformat()
            for k in keys:
                if isinstance(vals.get(k), (int, float)):
                    per_day.setdefault(d, {}).setdefault(k, []).append(vals[k])
        daily = [
            {"date": d, **{
                k: {"min": round(min(v), 1), "max": round(max(v), 1),
                    "avg": round(sum(v) / len(v), 1), "n": len(v)}
                for k, v in ks.items()}}
            for d, ks in sorted(per_day.items(), reverse=True)
        ]

        out.append({
            "id": sensor.id,
            "name": sensor.name or sensor.address,
            "description": sensor.description or "",
            "keys": keys,
            "latest": ({"timestamp": latest.timestamp.isoformat(), "values": latest.values}
                       if latest else None),
            "series": series,
            "daily": daily,
        })

    return JsonResponse({
        "now": now.isoformat(),
        "timezone": timezone.get_current_timezone_name(),
        "hours": hours,
        "bucket_seconds": bucket_s,
        "sensors": out,
    })
