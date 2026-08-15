"""
step3_imu.py -- STEP 3: Is the IMU telling the truth?

Two tests:
  1. Live stream -- tilt the board, watch numbers move
  2. Six-orientation test -- the real acceptance check

Run:  import step3_imu
"""

import time
from machine import Pin, I2C

import config
from mpu6050 import MPU6050


def make_imu():
    i2c = I2C(config.I2C_ID,
              sda=Pin(config.I2C_SDA),
              scl=Pin(config.I2C_SCL),
              freq=config.I2C_FREQ)
    return MPU6050(i2c, addr=config.MPU6050_ADDR)


def live(imu, seconds=20):
    """Stream accel + gyro. Tilt the board and watch."""
    print()
    print("-- Live stream, {}s. Tilt the board. --".format(seconds))
    print("{:>7} {:>7} {:>7} | {:>8} {:>8} {:>8}".format(
        "ax(g)", "ay(g)", "az(g)", "gx(d/s)", "gy(d/s)", "gz(d/s)"))
    print("-" * 60)

    end = time.ticks_add(time.ticks_ms(), seconds * 1000)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        d = imu.read_all()
        ax, ay, az = d["accel"]
        gx, gy, gz = d["gyro"]
        print("{:7.2f} {:7.2f} {:7.2f} | {:8.1f} {:8.1f} {:8.1f}".format(
            ax, ay, az, gx, gy, gz))
        time.sleep_ms(250)


def six_orientation(imu):
    """
    THE ACCEPTANCE TEST.

    In each orientation, ~1g should show on whichever axis points DOWN,
    and ~0g on the other two. This proves the IMU reads live data rather
    than returning stale bytes, and it validates axis orientation before
    the frame goes together.
    """
    poses = [
        ("Flat, components up",     "az", +1.0),
        ("Flat, components down",   "az", -1.0),
        ("On its LEFT edge",        "ax", +1.0),
        ("On its RIGHT edge",       "ax", -1.0),
        ("Nose DOWN (front edge)",  "ay", +1.0),
        ("Nose UP (back edge)",     "ay", -1.0),
    ]

    print()
    print("=" * 46)
    print("  SIX-ORIENTATION TEST")
    print("=" * 46)
    print("Hold each position steady, then press Enter.")
    print("Sign may be inverted on your board -- that's fine,")
    print("what matters is that ~1g lands on the RIGHT AXIS.")
    print()

    passed = 0
    for name, axis, expected in poses:
        input("  {}  -> Enter: ".format(name))

        # average a few samples to settle noise
        sx = sy = sz = 0.0
        for _ in range(20):
            ax, ay, az = imu.accel()
            sx += ax
            sy += ay
            sz += az
            time.sleep_ms(10)
        ax, ay, az = sx / 20, sy / 20, sz / 20

        vals = {"ax": ax, "ay": ay, "az": az}
        measured = vals[axis]
        ok = abs(abs(measured) - 1.0) < 0.25

        others = [k for k in ("ax", "ay", "az") if k != axis]
        flat = all(abs(vals[k]) < 0.35 for k in others)

        status = "PASS" if (ok and flat) else "CHECK"
        if ok and flat:
            passed += 1

        print("    ax={:6.2f}  ay={:6.2f}  az={:6.2f}   [{}]  {}".format(
            ax, ay, az, axis, status))
        print()

    print("-" * 46)
    print("Result: {}/6 orientations passed".format(passed))
    if passed == 6:
        print("PASS -- IMU is good and axes are understood.")
    elif passed >= 4:
        print("Mostly good. Re-check the failures -- probably held off-angle.")
    else:
        print("Something's off. Check wiring and that the board sat still.")
    return passed


def run():
    print("=" * 46)
    print("  ESP-FLY  --  Step 3: IMU")
    print("=" * 46)

    imu = make_imu()
    print("WHO_AM_I : 0x{:02X}  -- IMU awake".format(imu.who_am_i))
    print("Die temp : {:.1f} C".format(imu.temperature()))

    print()
    print("Calibrating gyro -- KEEP THE BOARD STILL...")
    ox, oy, oz = imu.calibrate_gyro()
    print("Gyro bias: {:.2f}, {:.2f}, {:.2f} deg/s".format(ox, oy, oz))
    print("(Non-zero is normal. This is exactly what ESP-Drone does on boot.)")

    live(imu, seconds=15)
    six_orientation(imu)

    print()
    print("Next: step4_baro")


run()
