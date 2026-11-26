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


# --- Bosch BME680 / BME688 (temperature, humidity, pressure; gas unused) ---

_BME68X_CHIP_ID = 0x61          # same for BME680 and BME688 (register 0xD0)
_BME68X_REG_CHIP_ID = 0xD0
_BME68X_REG_COEFF1 = 0x8A       # 23 bytes of calibration data
_BME68X_REG_COEFF2 = 0xE1       # 14 bytes of calibration data
_BME68X_REG_CTRL_GAS_0 = 0x70   # bit 3 heat_off
_BME68X_REG_CTRL_GAS_1 = 0x71   # run_gas bits
_BME68X_REG_CTRL_HUM = 0x72
_BME68X_REG_STATUS = 0x1D       # bit 7 new_data_0
_BME68X_REG_CTRL_MEAS = 0x74
_BME68X_REG_CONFIG = 0x75
_BME68X_REG_FIELD0 = 0x1F       # press(3) temp(3) hum(2)
_BME68X_OS_2X, _BME68X_OS_4X, _BME68X_OS_8X = 2, 3, 4
_BME68X_FILTER_3 = 2
_BME68X_FORCED_MODE = 1


def _s8(v):
    return v - 256 if v > 127 else v


def _s16(v):
    return v - 65536 if v > 32767 else v


class BME688Driver:
    """
    Driver for the SparkFun BME688 (Qwiic) environmental sensor; also fits
    the BME680. Address 0x77 by default, 0x76 with the ADR jumper changed.

    Takes one forced-mode measurement of temperature, humidity and pressure.
    The gas heater is kept OFF: it warms the chip and would make the
    temperature read high, and we do not use the gas (VOC) reading.
    Compensation uses the floating-point formulas from Bosch's BME68x API.
    """

    def __init__(self, bus_number: int = 1, address: int = 0x77):
        self.bus_number = bus_number
        self.address = address
        self.bus = smbus2.SMBus(bus_number)

    def _read(self, register: int, length: int):
        return self.bus.read_i2c_block_data(self.address, register, length)

    def _write(self, register: int, value: int):
        self.bus.write_byte_data(self.address, register, value)

    def read_id(self) -> int:
        return self.bus.read_byte_data(self.address, _BME68X_REG_CHIP_ID)

    def _read_calibration(self) -> Dict[str, int]:
        c = self._read(_BME68X_REG_COEFF1, 23) + self._read(_BME68X_REG_COEFF2, 14)
        return {
            "t1": (c[32] << 8) | c[31], "t2": _s16((c[1] << 8) | c[0]), "t3": _s8(c[2]),
            "p1": (c[5] << 8) | c[4], "p2": _s16((c[7] << 8) | c[6]), "p3": _s8(c[8]),
            "p4": _s16((c[11] << 8) | c[10]), "p5": _s16((c[13] << 8) | c[12]),
            "p6": _s8(c[15]), "p7": _s8(c[14]), "p8": _s16((c[19] << 8) | c[18]),
            "p9": _s16((c[21] << 8) | c[20]), "p10": c[22],
            "h1": (c[25] << 4) | (c[24] & 0x0F), "h2": (c[23] << 4) | (c[24] >> 4),
            "h3": _s8(c[26]), "h4": _s8(c[27]), "h5": _s8(c[28]), "h6": c[29], "h7": _s8(c[30]),
        }

    def read_raw_data(self) -> Optional[Dict[str, float]]:
        """One forced-mode measurement: raw ADC counts plus the chip's calibration."""
        try:
            if self.read_id() != _BME68X_CHIP_ID:
                return None
            calib = self._read_calibration()
            self._write(_BME68X_REG_CTRL_GAS_1, 0x00)   # no gas conversion
            self._write(_BME68X_REG_CTRL_GAS_0, 0x08)   # heater off
            self._write(_BME68X_REG_CTRL_HUM, _BME68X_OS_2X)
            self._write(_BME68X_REG_CONFIG, _BME68X_FILTER_3 << 2)
            self._write(_BME68X_REG_CTRL_MEAS,
                        (_BME68X_OS_8X << 5) | (_BME68X_OS_4X << 2) | _BME68X_FORCED_MODE)
            for _ in range(20):                          # typically ~25 ms
                time.sleep(0.01)
                if self.bus.read_byte_data(self.address, _BME68X_REG_STATUS) & 0x80:
                    break
            else:
                return None
            d = self._read(_BME68X_REG_FIELD0, 8)
            return {
                "pres_adc": float((d[0] << 12) | (d[1] << 4) | (d[2] >> 4)),
                "temp_adc": float((d[3] << 12) | (d[4] << 4) | (d[5] >> 4)),
                "hum_adc": float((d[6] << 8) | d[7]),
                **{f"cal_{k}": float(v) for k, v in calib.items()},
            }
        except OSError as e:
            print(f"Error reading BME688: {e}")
            return None

    @staticmethod
    def compensate(raw: Dict[str, float]) -> Dict[str, float]:
        """Returns temperature_c, humidity_pct, pressure_hpa (Bosch float formulas)."""
        k = {key[4:]: v for key, v in raw.items() if key.startswith("cal_")}
        t_adc, p_adc, h_adc = raw["temp_adc"], raw["pres_adc"], raw["hum_adc"]

        var1 = ((t_adc / 16384.0) - (k["t1"] / 1024.0)) * k["t2"]
        var2 = ((t_adc / 131072.0) - (k["t1"] / 8192.0)) ** 2 * (k["t3"] * 16.0)
        t_fine = var1 + var2
        temp_c = t_fine / 5120.0

        var1 = (t_fine / 2.0) - 64000.0
        var2 = var1 * var1 * (k["p6"] / 131072.0)
        var2 = var2 + var1 * k["p5"] * 2.0
        var2 = (var2 / 4.0) + (k["p4"] * 65536.0)
        var1 = (((k["p3"] * var1 * var1) / 16384.0) + (k["p2"] * var1)) / 524288.0
        var1 = (1.0 + (var1 / 32768.0)) * k["p1"]
        pres = 1048576.0 - p_adc
        if var1 != 0:
            pres = ((pres - (var2 / 4096.0)) * 6250.0) / var1
            var1 = (k["p9"] * pres * pres) / 2147483648.0
            var2 = pres * (k["p8"] / 32768.0)
            var3 = (pres / 256.0) ** 3 * (k["p10"] / 131072.0)
            pres = pres + (var1 + var2 + var3 + (k["p7"] * 128.0)) / 16.0
        else:
            pres = 0.0

        var1 = h_adc - ((k["h1"] * 16.0) + ((k["h3"] / 2.0) * temp_c))
        var2 = var1 * ((k["h2"] / 262144.0) * (1.0 + ((k["h4"] / 16384.0) * temp_c)
                                               + ((k["h5"] / 1048576.0) * temp_c * temp_c)))
        var3 = k["h6"] / 16384.0
        var4 = k["h7"] / 2097152.0
        hum = var2 + ((var3 + (var4 * temp_c)) * var2 * var2)
        hum = max(0.0, min(100.0, hum))
        return {"temperature_c": temp_c, "humidity_pct": hum, "pressure_hpa": pres / 100.0}

    def calibrate(self, raw: Dict[str, float]) -> Dict[str, float]:
        """Converts raw counts into temperature (degF), humidity (%) and pressure (hPa)."""
        v = self.compensate(raw)
        return {
            "temperature_f": round(v["temperature_c"] * 9.0 / 5.0 + 32.0, 2),
            "humidity_pct": round(v["humidity_pct"], 2),
            "pressure_hpa": round(v["pressure_hpa"], 1),
        }

    def close(self):
        self.bus.close()
