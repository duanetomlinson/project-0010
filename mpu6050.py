"""
mpu6050.py -- minimal MPU-6050 driver (library, not a test)

Imported by step3_imu.py and step5_combined.py.
Nothing runs when you import this.
"""

import struct
import time

# Registers
_SMPLRT_DIV   = 0x19
_CONFIG       = 0x1A
_GYRO_CONFIG  = 0x1B
_ACCEL_CONFIG = 0x1C
_ACCEL_XOUT_H = 0x3B
_PWR_MGMT_1   = 0x6B
_WHO_AM_I     = 0x75

# Full-scale ranges -> LSB per unit
_ACCEL_SCALE = {0: 16384.0, 1: 8192.0, 2: 4096.0, 3: 2048.0}   # LSB/g
_GYRO_SCALE  = {0: 131.0,   1: 65.5,   2: 32.8,   3: 16.4}     # LSB/(deg/s)


class MPU6050:

    def __init__(self, i2c, addr=0x68, accel_range=0, gyro_range=0):
        self.i2c = i2c
        self.addr = addr
        self._a_scale = _ACCEL_SCALE[accel_range]
        self._g_scale = _GYRO_SCALE[gyro_range]

        self.gyro_offset = (0.0, 0.0, 0.0)

        who = self._r8(_WHO_AM_I)
        if who not in (0x68, 0x70, 0x72, 0x73, 0x98):
            raise OSError(
                "Unexpected WHO_AM_I 0x{:02X} at 0x{:02X} -- "
                "is this really an MPU-6050?".format(who, addr))
        self.who_am_i = who

        # The MPU-6050 boots ASLEEP. Clear the sleep bit or you read zeros.
        self._w8(_PWR_MGMT_1, 0x00)
        time.sleep_ms(100)
        self._w8(_PWR_MGMT_1, 0x01)      # clock from gyro X -- more stable
        self._w8(_SMPLRT_DIV, 0x00)      # 1 kHz sample rate
        self._w8(_CONFIG, 0x03)          # DLPF ~44 Hz -- kills prop vibration
        self._w8(_ACCEL_CONFIG, accel_range << 3)
        self._w8(_GYRO_CONFIG, gyro_range << 3)
        time.sleep_ms(50)

    # ---- low level ----
    def _r8(self, reg):
        return self.i2c.readfrom_mem(self.addr, reg, 1)[0]

    def _w8(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes([val]))

    # ---- readings ----
    def read_raw(self):
        """All 14 bytes in one burst: accel, temp, gyro."""
        d = self.i2c.readfrom_mem(self.addr, _ACCEL_XOUT_H, 14)
        ax, ay, az, temp, gx, gy, gz = struct.unpack(">hhhhhhh", d)
        return ax, ay, az, temp, gx, gy, gz

    def accel(self):
        """Acceleration in g."""
        ax, ay, az, _, _, _, _ = self.read_raw()
        return (ax / self._a_scale, ay / self._a_scale, az / self._a_scale)

    def gyro(self):
        """Angular rate in deg/s, offset-corrected."""
        _, _, _, _, gx, gy, gz = self.read_raw()
        ox, oy, oz = self.gyro_offset
        return (gx / self._g_scale - ox,
                gy / self._g_scale - oy,
                gz / self._g_scale - oz)

    def temperature(self):
        """Die temperature in C. Not ambient -- it runs warm."""
        _, _, _, t, _, _, _ = self.read_raw()
        return t / 340.0 + 36.53

    def read_all(self):
        ax, ay, az, t, gx, gy, gz = self.read_raw()
        ox, oy, oz = self.gyro_offset
        return {
            "accel": (ax / self._a_scale, ay / self._a_scale, az / self._a_scale),
            "gyro":  (gx / self._g_scale - ox,
                      gy / self._g_scale - oy,
                      gz / self._g_scale - oz),
            "temp":  t / 340.0 + 36.53,
        }

    # ---- calibration ----
    def calibrate_gyro(self, samples=200, delay_ms=5):
        """
        Learn the gyro's resting bias. The board MUST be still.

        Every MPU-6050 reads slightly non-zero when stationary. ESP-Drone
        does this on boot -- if the drone moves during that window it
        learns the wrong zero and drifts in flight.
        """
        sx = sy = sz = 0
        for _ in range(samples):
            _, _, _, _, gx, gy, gz = self.read_raw()
            sx += gx
            sy += gy
            sz += gz
            time.sleep_ms(delay_ms)

        self.gyro_offset = (
            sx / samples / self._g_scale,
            sy / samples / self._g_scale,
            sz / samples / self._g_scale,
        )
        return self.gyro_offset
