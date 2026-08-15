"""
bmp280.py -- minimal BMP280 driver (library, not a test)

Imported by step4_baro.py and step5_combined.py.

The raw ADC values from this chip are meaningless on their own. Every
BMP280 ships with per-chip calibration coefficients burned into ROM,
which you read once and then apply with Bosch's compensation formulas.
That's what most of this file is.
"""

import struct
import time

_CHIP_ID   = 0xD0
_RESET     = 0xE0
_STATUS    = 0xF3
_CTRL_MEAS = 0xF4
_CONFIG    = 0xF5
_PRESS_MSB = 0xF7
_CALIB     = 0x88

CHIP_BMP280 = 0x58
CHIP_BME280 = 0x60


class BMP280:

    def __init__(self, i2c, addr=0x76):
        self.i2c = i2c
        self.addr = addr
        self.t_fine = 0

        self.chip_id = self._r8(_CHIP_ID)
        if self.chip_id == CHIP_BME280:
            self.chip_name = "BME280 (has humidity)"
        elif self.chip_id in (CHIP_BMP280, 0x56, 0x57):
            self.chip_name = "BMP280"
        else:
            raise OSError(
                "Unknown chip ID 0x{:02X} at 0x{:02X}".format(self.chip_id, addr))

        self._w8(_RESET, 0xB6)
        time.sleep_ms(10)
        self._read_calibration()

        # osrs_t=x2 (010), osrs_p=x16 (101), mode=normal (11)
        self._w8(_CTRL_MEAS, (0b010 << 5) | (0b101 << 2) | 0b11)
        # t_sb=0.5ms (000), filter=x16 (100) -- heavy filtering, low noise
        self._w8(_CONFIG, (0b000 << 5) | (0b100 << 2))
        time.sleep_ms(100)

    # ---- low level ----
    def _r8(self, reg):
        return self.i2c.readfrom_mem(self.addr, reg, 1)[0]

    def _w8(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes([val]))

    def _read_calibration(self):
        d = self.i2c.readfrom_mem(self.addr, _CALIB, 24)
        # T1 and P1 unsigned, the rest signed, all little-endian
        (self.dig_T1, self.dig_T2, self.dig_T3,
         self.dig_P1, self.dig_P2, self.dig_P3, self.dig_P4,
         self.dig_P5, self.dig_P6, self.dig_P7, self.dig_P8,
         self.dig_P9) = struct.unpack("<HhhHhhhhhhhh", d)

    # ---- readings ----
    def _read_raw(self):
        d = self.i2c.readfrom_mem(self.addr, _PRESS_MSB, 6)
        raw_p = (d[0] << 12) | (d[1] << 4) | (d[2] >> 4)
        raw_t = (d[3] << 12) | (d[4] << 4) | (d[5] >> 4)
        return raw_t, raw_p

    def read(self):
        """Returns (temperature_C, pressure_Pa)."""
        raw_t, raw_p = self._read_raw()

        # --- temperature (Bosch datasheet, float variant) ---
        v1 = (raw_t / 16384.0 - self.dig_T1 / 1024.0) * self.dig_T2
        v2 = ((raw_t / 131072.0 - self.dig_T1 / 8192.0) ** 2) * self.dig_T3
        self.t_fine = v1 + v2
        temp_c = self.t_fine / 5120.0

        # --- pressure (needs t_fine, so temperature must come first) ---
        v1 = self.t_fine / 2.0 - 64000.0
        v2 = v1 * v1 * self.dig_P6 / 32768.0
        v2 = v2 + v1 * self.dig_P5 * 2.0
        v2 = v2 / 4.0 + self.dig_P4 * 65536.0
        v1 = (self.dig_P3 * v1 * v1 / 524288.0 + self.dig_P2 * v1) / 524288.0
        v1 = (1.0 + v1 / 32768.0) * self.dig_P1

        if v1 == 0.0:
            return temp_c, 0.0          # avoid divide-by-zero

        p = 1048576.0 - raw_p
        p = (p - v2 / 4096.0) * 6250.0 / v1
        v1 = self.dig_P9 * p * p / 2147483648.0
        v2 = p * self.dig_P8 / 32768.0
        p = p + (v1 + v2 + self.dig_P7) / 16.0

        return temp_c, p

    def temperature(self):
        return self.read()[0]

    def pressure(self):
        return self.read()[1]

    def pressure_hpa(self):
        return self.read()[1] / 100.0

    def altitude(self, sea_level_hpa=1013.25):
        """
        Altitude in metres via the barometric formula.

        ABSOLUTE altitude is only as good as your sea_level_hpa guess.
        RELATIVE altitude -- the change as you lift the board -- is
        accurate regardless. Relative is what a drone actually uses.
        """
        p_hpa = self.pressure() / 100.0
        if p_hpa <= 0:
            return 0.0
        return 44330.0 * (1.0 - (p_hpa / sea_level_hpa) ** (1.0 / 5.255))
