"""
step5_combined.py -- STEP 5: Both sensors, one bus, one loop

This is the shape of a real flight controller's sensor layer: read
everything on a fixed schedule, fast enough to stabilise on.

Run:  import step5_combined
"""

import time
from machine import Pin, I2C

import config
from mpu6050 import MPU6050
from bmp280 import BMP280


def make_sensors():
    """ONE bus object, shared by both sensors. This is the point of I2C."""
    i2c = I2C(config.I2C_ID,
              sda=Pin(config.I2C_SDA),
              scl=Pin(config.I2C_SCL),
              freq=config.I2C_FREQ)

    imu = MPU6050(i2c, addr=config.MPU6050_ADDR)
    baro = BMP280(i2c, addr=config.BMP280_ADDR)
    return i2c, imu, baro


def tilt_angles(ax, ay, az):
    """
    Roll and pitch from gravity alone.

    Good enough while stationary. In flight this drifts badly under
    acceleration, which is why real firmware fuses it with the gyro.
    """
    import math
    roll = math.atan2(ay, az) * 57.2958
    pitch = math.atan2(-ax, math.sqrt(ay * ay + az * az)) * 57.2958
    return roll, pitch


def stream(imu, baro, seconds=30, hz=10):
    period = 1000 // hz
    print()
    print("-- Combined stream, {}s @ {}Hz --".format(seconds, hz))
    print("{:>7} {:>7} | {:>8} {:>8} {:>8} | {:>9} {:>7}".format(
        "roll", "pitch", "gx", "gy", "gz", "hPa", "alt(m)"))
    print("-" * 68)

    end = time.ticks_add(time.ticks_ms(), seconds * 1000)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        t0 = time.ticks_ms()

        d = imu.read_all()
        ax, ay, az = d["accel"]
        gx, gy, gz = d["gyro"]
        roll, pitch = tilt_angles(ax, ay, az)

        temp_c, p = baro.read()
        alt = baro.altitude(config.SEA_LEVEL_HPA)

        print("{:7.1f} {:7.1f} | {:8.1f} {:8.1f} {:8.1f} | {:9.2f} {:7.2f}".format(
            roll, pitch, gx, gy, gz, p / 100.0, alt))

        elapsed = time.ticks_diff(time.ticks_ms(), t0)
        if elapsed < period:
            time.sleep_ms(period - elapsed)


def loop_rate(imu, baro, samples=200):
    """
    How fast can we actually read both sensors?

    ESP-Drone runs its stabilisation loop at 500-1000 Hz. MicroPython
    won't get near that -- and even if the average looked fine, garbage
    collection pauses mean it can't guarantee CONSISTENT timing. That
    inconsistency is why flight firmware is C, not Python.
    """
    print()
    print("-- Loop rate benchmark --")

    t0 = time.ticks_ms()
    for _ in range(samples):
        imu.read_raw()
        baro.read()
    elapsed = time.ticks_diff(time.ticks_ms(), t0)

    rate = samples * 1000 / elapsed
    print("  {} full reads in {} ms".format(samples, elapsed))
    print("  ~{:.0f} Hz sustained".format(rate))
    print()
    print("  Fine for logging and learning. Not a flight loop --")
    print("  that's ESP-Drone's job next session.")


def run():
    print("=" * 46)
    print("  ESP-FLY  --  Step 5: Combined")
    print("=" * 46)

    i2c, imu, baro = make_sensors()

    devs = i2c.scan()
    print("Bus has {} device(s): {}".format(
        len(devs), ", ".join("0x{:02X}".format(d) for d in sorted(devs))))
    print("IMU  : MPU-6050 @ 0x{:02X}".format(config.MPU6050_ADDR))
    print("Baro : {} @ 0x{:02X}".format(baro.chip_name, config.BMP280_ADDR))
    print()

    print("Calibrating gyro -- KEEP STILL...")
    imu.calibrate_gyro()
    print("Done.")

    stream(imu, baro, seconds=20)
    loop_rate(imu, baro)

    print()
    print("=" * 46)
    print("  If roll/pitch track the board and altitude responds")
    print("  to lifting it -- the flight controller can sense the")
    print("  world. That's tonight's goal met.")
    print("=" * 46)


run()
