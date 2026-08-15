"""
main.py -- ESP-FLY sensor bring-up

EVERYTHING IS COMMENTED OUT ON PURPOSE.

main.py runs automatically on every boot and reset. If it contains a
long test loop, you'll fight the board every time you plug it in --
it'll be busy running instead of listening for you.

So: work through the steps by hand in the REPL first.

    >>> import step1_hello
    >>> import step2_scan
    >>> import step3_imu
    >>> import step4_baro
    >>> import step5_combined

(To re-run one after editing it, easiest is Ctrl-D to soft reboot,
then import again. MicroPython caches imports.)

Only once all five pass should you uncomment something below.
"""

# ---------------------------------------------------------------
# STAGE 1 -- board only. Nothing wired yet.
# ---------------------------------------------------------------
# import step1_hello


# ---------------------------------------------------------------
# STAGE 2 -- sensors wired. Do they appear on the bus?
# ---------------------------------------------------------------
# import step2_scan


# ---------------------------------------------------------------
# STAGE 3 -- IMU. Six-orientation acceptance test.
# ---------------------------------------------------------------
# import step3_imu


# ---------------------------------------------------------------
# STAGE 4 -- barometer. Noise check + 1m lift test.
# ---------------------------------------------------------------
# import step4_baro


# ---------------------------------------------------------------
# STAGE 5 -- both together on the shared bus.
# ---------------------------------------------------------------
# import step5_combined


# ---------------------------------------------------------------
# OPTIONAL -- quick boot check.
#
# Safe to leave enabled: it scans the bus, prints what it found,
# and gets out of the way. Useful for confirming a connection
# survived being knocked about, without blocking the REPL.
# ---------------------------------------------------------------
def boot_check():
    from machine import Pin, I2C
    import config

    try:
        i2c = I2C(config.I2C_ID,
                  sda=Pin(config.I2C_SDA),
                  scl=Pin(config.I2C_SCL),
                  freq=config.I2C_FREQ)
        found = i2c.scan()

        imu_ok = config.MPU6050_ADDR in found
        baro_ok = config.BMP280_ADDR in found

        print("[boot] I2C: {} device(s)  IMU:{}  BARO:{}".format(
            len(found),
            "ok" if imu_ok else "MISSING",
            "ok" if baro_ok else "MISSING"))
    except Exception as e:
        print("[boot] I2C init failed:", e)


# boot_check()

print("main.py loaded -- steps are commented out. Import them manually.")
