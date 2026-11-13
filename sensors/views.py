from django.shortcuts import render
from django.http import JsonResponse
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

# Create your views here.
