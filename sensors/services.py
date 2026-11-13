import smbus2
import json

from .drivers import AS7331Driver, SHTC3Driver

# Maps an I2C address to the driver class that knows how to read it.
DRIVERS = {
    '0x74': AS7331Driver,
    '0x70': SHTC3Driver,
}


def read_calibrated(address):
    """
    Reads one calibrated, human-readable measurement from the sensor at the
    given I2C address (e.g. '0x70'). Returns a dict of values, or None if no
    driver is registered for the address or the read failed.
    """
    driver_class = DRIVERS.get(address)
    if driver_class is None:
        return None
    driver = driver_class(address=int(address, 16))
    try:
        raw = driver.read_raw_data()
        return driver.calibrate(raw) if raw else None
    finally:
        driver.close()


class SensorDiscoveryService:
    """Service to scan I2C and USB buses for available sensors."""

    @staticmethod
    def scan_i2c(bus_number: int = 1):
        """Scans the specified I2C bus and returns a list of device addresses."""
        devices = []
        try:
            with smbus2.SMBus(bus_number) as bus:
                for address in range(0x03, 0x78):
                    try:
                        bus.write_quick(address, 0)
                        devices.append(hex(address))
                    except OSError:
                        pass
        except Exception as e:
            print(f"Error scanning I2C bus {bus_number}: {e}")
        return devices

    @staticmethod
    def scan_usb_modbus():
        """
        Placeholder for USB Modbus discovery.
        In a real implementation, this would scan USB ports for serial/modbus devices.
        """
        # For now, return a mock discovered device
        return [{"address": "USB_0", "type": "usb_modbus"}]
