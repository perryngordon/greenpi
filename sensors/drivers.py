import smbus2
import time
from typing import Dict, Optional

# Register addresses, bit fields, and conversion formulas below are from the
# ams OSRAM AS7331 datasheet (DS001047 v4-00, 2023-Mar-24), sections 7.4-7.7 and 8.

# Configuration-state register addresses
_REG_OSR = 0x00
_REG_CREG1 = 0x06
_REG_CREG2 = 0x07
_REG_CREG3 = 0x08

# OSR (Operational State Register) values, see Figure 46
_OSR_SW_RESET = 0x0A          # DOS=config, SW_RES=1
_OSR_CONFIG_POWERED = 0x02    # DOS=config, PD=0
_OSR_MEASURE_START = 0x83     # DOS=measurement, PD=0, SS=1

# CREG1: GAIN (bits 7:4) and TIME (bits 3:0). Defaults match chip power-on-reset values.
GAIN_2X = 0x0A     # CREG1:GAIN = 1010b -> 2x irradiance responsivity
TIME_64MS = 0x06   # CREG1:TIME = 0110b -> 64 ms conversion time, 16-bit resolution

_CREG2_EN_TM = 0x40   # enable temperature measurement
_CREG3_MMODE_CONT = 0x00  # continuous measurement mode

# Measurement-state register address of TEMP; MRES1/2/3 follow immediately after.
_REG_TEMP = 0x01

# Base LSB (nW/cm^2 per count) at GAIN=2048x, TIME=1ms (10-bit resolution) - Figures 27/29/31.
_BASE_LSB_NW_CM2 = {
    "uva": 170000.0 / 1024,  # ~166.02
    "uvb": 189000.0 / 1024,  # ~184.57
    "uvc": 83000.0 / 1024,   # ~81.05
}

_TSTARTPD_MAX_S = 0.002  # startup time after leaving power-down (datasheet: typ 1.2ms, max 2ms)


class AS7331Driver:
    """
    Driver for the SparkFun Spectral UV Sensor (AS7331) over I2C.

    Configures the sensor for continuous measurement (CONT mode) at the given
    gain/conversion-time and exposes both raw register counts and the
    irradiance/temperature values calibrated from them.
    """

    def __init__(self, bus_number: int = 1, address: int = 0x74, gain_reg: int = GAIN_2X, time_reg: int = TIME_64MS):
        self.bus_number = bus_number
        self.address = address
        self.gain_reg = gain_reg
        self.time_reg = time_reg
        self.bus = smbus2.SMBus(bus_number)
        self._initialize_sensor()

    def _write_register(self, register: int, value: int):
        self.bus.write_byte_data(self.address, register, value)

    def _conversion_time_seconds(self) -> float:
        # NCLK = 1024 * 2^TIME clock cycles at the default 1.024 MHz internal clock (CREG3:CCLK = 00b).
        return (1024 << self.time_reg) / 1_024_000.0

    def _initialize_sensor(self):
        self._write_register(_REG_OSR, _OSR_SW_RESET)
        time.sleep(0.001)
        self._write_register(_REG_OSR, _OSR_CONFIG_POWERED)

        self._write_register(_REG_CREG1, (self.gain_reg << 4) | self.time_reg)
        self._write_register(_REG_CREG2, _CREG2_EN_TM)
        self._write_register(_REG_CREG3, _CREG3_MMODE_CONT)

        self._write_register(_REG_OSR, _OSR_MEASURE_START)
        # Wait for the startup delay plus one full conversion before the first read.
        time.sleep(_TSTARTPD_MAX_S + self._conversion_time_seconds())

    def _lsb_nw_cm2(self, channel: str) -> float:
        return _BASE_LSB_NW_CM2[channel] * (1 << self.gain_reg) / (1 << self.time_reg)

    def read_raw_data(self) -> Optional[Dict[str, float]]:
        """
        Reads the uncalibrated register counts: temp_raw (12-bit) and
        uva_raw/uvb_raw/uvc_raw (16-bit), straight off the sensor.
        """
        try:
            data = self.bus.read_i2c_block_data(self.address, _REG_TEMP, 8)
            return {
                "temp_raw": (data[0] | (data[1] << 8)) & 0x0FFF,
                "uva_raw": float(data[2] | (data[3] << 8)),
                "uvb_raw": float(data[4] | (data[5] << 8)),
                "uvc_raw": float(data[6] | (data[7] << 8)),
            }
        except Exception as e:
            print(f"Error reading AS7331: {e}")
            return None

    def calibrate(self, raw: Dict[str, float]) -> Dict[str, float]:
        """Converts raw register counts into UV irradiance (uW/cm^2) and temperature (degF)."""
        temperature_c = raw["temp_raw"] * 0.05 - 66.9
        temperature_f = temperature_c * 9.0 / 5.0 + 32.0
        return {
            "uva_uw_cm2": round(raw["uva_raw"] * self._lsb_nw_cm2("uva") / 1000.0, 2),
            "uvb_uw_cm2": round(raw["uvb_raw"] * self._lsb_nw_cm2("uvb") / 1000.0, 2),
            "uvc_uw_cm2": round(raw["uvc_raw"] * self._lsb_nw_cm2("uvc") / 1000.0, 2),
            "temperature_f": round(temperature_f, 2),
        }

    def close(self):
        self.bus.close()


# Register commands and conversion formulas below are from the Sensirion SHTC3
# datasheet (Version 2 - January 2020), sections 3.4-3.6 and 5.

# 16-bit I2C commands (MSB first). Names follow the datasheet command table.
_SHTC3_WAKEUP = 0x3517
_SHTC3_SLEEP = 0xB098
_SHTC3_READ_ID = 0xEFC8
# Normal-mode measurement, clock stretching disabled, temperature returned first.
_SHTC3_MEASURE_T_FIRST = 0x7866

_SHTC3_ID_MASK = 0x083F   # bits that are fixed across all SHTC3 parts
_SHTC3_ID_VALUE = 0x0807  # expected value of (id & mask) for the SHTC3


class SHTC3Driver:
    """
    Driver for the SparkFun Humidity Sensor (SHTC3) over I2C.

    The SHTC3 powers up in a low-power sleep state and only acknowledges its
    address until woken, so each read wakes the sensor, performs one normal-mode
    measurement (temperature first, clock stretching disabled), then returns it
    to sleep. Returned register words are validated against the datasheet CRC-8.
    """

    def __init__(self, bus_number: int = 1, address: int = 0x70):
        self.bus_number = bus_number
        self.address = address
        self.bus = smbus2.SMBus(bus_number)

    def _send_command(self, command: int):
        msg = smbus2.i2c_msg.write(self.address, [(command >> 8) & 0xFF, command & 0xFF])
        self.bus.i2c_rdwr(msg)

    def _read_bytes(self, length: int):
        msg = smbus2.i2c_msg.read(self.address, length)
        self.bus.i2c_rdwr(msg)
        return list(msg)

    @staticmethod
    def _crc8(data) -> int:
        # CRC-8, polynomial 0x31 (x^8 + x^5 + x^4 + 1), init 0xFF - datasheet section 5.10.
        crc = 0xFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
        return crc

    def wake(self):
        self._send_command(_SHTC3_WAKEUP)
        time.sleep(0.001)  # tWU: wake-up time, max 240 us; pad generously

    def sleep(self):
        self._send_command(_SHTC3_SLEEP)

    def read_id(self) -> Optional[int]:
        """Returns the raw 16-bit ID register, or None on CRC failure / I/O error."""
        try:
            self.wake()
            self._send_command(_SHTC3_READ_ID)
            data = self._read_bytes(3)
            self.sleep()
            if self._crc8(data[0:2]) != data[2]:
                return None
            return (data[0] << 8) | data[1]
        except OSError as e:
            print(f"Error reading SHTC3 ID: {e}")
            return None

    def read_raw_data(self) -> Optional[Dict[str, float]]:
        """
        Wakes the sensor, takes one measurement, and returns the uncalibrated
        16-bit temperature and humidity register counts. Returns None if the
        CRC check fails or the bus errors.
        """
        try:
            self.wake()
            self._send_command(_SHTC3_MEASURE_T_FIRST)
            time.sleep(0.013)  # tMEAS: normal-mode measurement, max 12.1 ms
            data = self._read_bytes(6)
            self.sleep()
            if self._crc8(data[0:2]) != data[2] or self._crc8(data[3:5]) != data[5]:
                return None
            return {
                "temp_raw": float((data[0] << 8) | data[1]),
                "humidity_raw": float((data[3] << 8) | data[4]),
            }
        except OSError as e:
            print(f"Error reading SHTC3: {e}")
            return None

    def calibrate(self, raw: Dict[str, float]) -> Dict[str, float]:
        """Converts raw register counts into temperature (degF) and relative humidity (%)."""
        temperature_c = -45.0 + 175.0 * (raw["temp_raw"] / 65536.0)
        temperature_f = temperature_c * 9.0 / 5.0 + 32.0
        humidity_pct = 100.0 * (raw["humidity_raw"] / 65536.0)
        return {
            "temperature_f": round(temperature_f, 2),
            "humidity_pct": round(humidity_pct, 2),
        }

    def close(self):
        self.bus.close()
