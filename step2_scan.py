"""
step2_scan.py -- STEP 2: Can we see the sensors?

Wire BOTH sensors to the SAME two pins:

    MPU6050 / GY-521          BMP280
    ----------------          ------
    VCC -> 3V3                VCC -> 3V3
    GND -> GND                GND -> GND
    SDA -> GPIO 10            SDA/SDI -> GPIO 10   (config.I2C_SDA)
    SCL -> GPIO 9             SCL/SCK -> GPIO 9    (config.I2C_SCL)
    AD0 -> GND (or leave)     SDO -> GND (or leave)

I2C is a BUS. Both devices share the same wires and are told apart
by address. This is not a mistake.

Run:  import step2_scan
"""

from machine import Pin, I2C

import config

KNOWN = {
    0x68: "MPU-6050 (IMU)            [AD0 low]",
    0x69: "MPU-6050 (IMU)            [AD0 high]",
    0x76: "BMP280/BME280 (baro)      [SDO low]",
    0x77: "BMP280/BME280 (baro)      [SDO high]",
    0x0C: "AK8963 magnetometer (MPU-9250 aux)",
    0x3C: "SSD1306 OLED",
}


def make_i2c():
    return I2C(
        config.I2C_ID,
        sda=Pin(config.I2C_SDA),
        scl=Pin(config.I2C_SCL),
        freq=config.I2C_FREQ,
    )


def scan():
    print("=" * 46)
    print("  ESP-FLY  --  Step 2: I2C bus scan")
    print("=" * 46)
    print("SDA = GPIO {}   SCL = GPIO {}   {} Hz".format(
        config.I2C_SDA, config.I2C_SCL, config.I2C_FREQ))
    print()

    i2c = make_i2c()
    found = i2c.scan()

    if not found:
        print("NOTHING FOUND.")
        print()
        print("Check, in this order:")
        print("  1. 3V3 and GND actually connected to both boards")
        print("  2. SDA and SCL not swapped")
        print("  3. GPIO numbers vs the silkscreen label (S3 Minis lie)")
        print("  4. Try I2C_FREQ = 100_000 in config.py")
        print("  5. Only then suspect a dead sensor")
        return []

    print("Found {} device(s):".format(len(found)))
    for addr in sorted(found):
        label = KNOWN.get(addr, "unknown device")
        print("  0x{:02X}  {}".format(addr, label))
    print()

    imu_ok  = config.MPU6050_ADDR in found
    baro_ok = config.BMP280_ADDR in found

    print("MPU-6050 at 0x{:02X} : {}".format(
        config.MPU6050_ADDR, "OK" if imu_ok else "MISSING"))
    print("BMP280   at 0x{:02X} : {}".format(
        config.BMP280_ADDR, "OK" if baro_ok else "MISSING"))
    print()

    if imu_ok and baro_ok:
        print("PASS -- both sensors on the bus.")
        print("Next: step3_imu")
    else:
        print("Fix the missing device before moving on.")
        if not baro_ok:
            other = 0x77 if config.BMP280_ADDR == 0x76 else 0x76
            if other in found:
                print("  -> baro answered at 0x{:02X}. "
                      "Set BMP280_ADDR = 0x{:02X} in config.py".format(other, other))

    return found


scan()
