# ESP-FLY — Session 1: Sensor Bring-Up

MicroPython sensor validation for the ESP-FLY drone build.
ESP32-S3 Mini + MPU-6050 (GY-521) + BMP280.

**No motors tonight.** This session proves the flight controller can sense
the world. Motor drive stage comes next session.

---

## Wiring

Both sensors share the **same two pins**. I2C is a bus — devices are
distinguished by address, not by wiring.

| ESP32-S3 | MPU-6050 (GY-521) | BMP280   |
|----------|-------------------|----------|
| 3V3      | VCC               | VCC/VIN  |
| GND      | GND               | GND      |
| GPIO 10  | SDA               | SDA/SDI  |
| GPIO 9   | SCL               | SCL/SCK  |
| —        | AD0 → GND         | SDO → GND |

(Originally planned as SDA on GPIO 8; verified by pull-up sweep + scan
2026-08-16 that the sensors are physically on GPIO 10. `config.py` is
the source of truth.)

Expected addresses: **MPU-6050 at 0x68**, **BMP280 at 0x76**.
(Tie AD0/SDO high instead and they become 0x69 / 0x77.)

Both breakouts have onboard pull-up resistors. Two sets in parallel is
fine at these wire lengths — it just makes the pull-up stiffer.

**Avoid on the Waveshare ESP32-S3-Zero:** GPIO 0 (BOOT button + strapping);
3, 45, 46 (strapping); 19, 20 (native USB); 21 (WS2812 LED); 26–32 (flash).
GPIO 33–37 aren't broken out at all on this board.

As-built pin map (from `config.py`): motors on GPIO 1–4, EEP 5, ULT 6,
MPU INT 7, I2C on 9/10. Interactive diagram of every wire, both DRV8833
modules and the power star: open **`docs/esp-fly-wiring.html`** in a
browser (single file, no network needed).

---

## Flashing MicroPython

```bash
pip install esptool mpremote

# Find the port
ls /dev/cu.usb*            # macOS
```

Download the **ESP32-S3 generic** firmware from
[micropython.org/download/ESP32_GENERIC_S3](https://micropython.org/download/ESP32_GENERIC_S3/)

**S3-Zero has no USB-to-UART chip.** You must **hold BOOT (GPIO 0) *before*
connecting the Type-C cable**, every single time you flash. Plugging in first
and then pressing BOOT does not work. (Alternatively: hold BOOT, tap RESET,
release BOOT.)

```bash
esptool.py --chip esp32s3 --port /dev/cu.usbmodem1101 erase_flash

esptool.py --chip esp32s3 --port /dev/cu.usbmodem1101 \
    write_flash -z 0 ESP32_GENERIC_S3-20250809-v1.25.0.bin
```

Unplug, replug (no BOOT this time), then connect:

```bash
mpremote connect /dev/cu.usbmodem1101
```

Or use Thonny → Interpreter → MicroPython (ESP32) → select port.

---

## Copying the files

```bash
mpremote connect /dev/cu.usbmodem1101 fs cp config.py :
mpremote connect /dev/cu.usbmodem1101 fs cp mpu6050.py :
mpremote connect /dev/cu.usbmodem1101 fs cp bmp280.py :
mpremote connect /dev/cu.usbmodem1101 fs cp step1_hello.py :
mpremote connect /dev/cu.usbmodem1101 fs cp step2_scan.py :
mpremote connect /dev/cu.usbmodem1101 fs cp step3_imu.py :
mpremote connect /dev/cu.usbmodem1101 fs cp step4_baro.py :
mpremote connect /dev/cu.usbmodem1101 fs cp step5_combined.py :
mpremote connect /dev/cu.usbmodem1101 fs cp main.py :
```

In Thonny: open each file → File → Save as → MicroPython device.

---

## Running the steps

In the REPL, one at a time:

```python
>>> import step1_hello      # board alive?
>>> import step2_scan       # sensors on the bus?
>>> import step3_imu        # IMU reading correctly?
>>> import step4_baro       # barometer sensing altitude?
>>> import step5_combined   # both together
```

MicroPython caches imports — to re-run a step after editing it, press
**Ctrl-D** to soft reboot, then import again.

`main.py` has everything commented out deliberately. It runs on every
boot, so leaving a test loop in it means fighting the board for the REPL.

---

## File map

| File | Type | What it does |
|------|------|--------------|
| `config.py` | config | Pins and addresses. **Edit here, nowhere else.** |
| `mpu6050.py` | library | IMU driver. Nothing runs on import. |
| `bmp280.py` | library | Barometer driver + Bosch compensation math. |
| `step1_hello.py` | test | Board info + LED blink. |
| `step2_scan.py` | test | I2C bus scan. |
| `step3_imu.py` | test | Gyro calibration, live stream, six-orientation test. |
| `step4_baro.py` | test | Chip ID, noise check, 1m lift test. |
| `step5_combined.py` | test | Both sensors, one loop, rate benchmark. |
| `step6_motors.py` | test | **PROPS OFF.** DRV8833 wake, per-motor spin, all-four load, fault monitor. |
| `main.py` | boot | All commented out on purpose. |

---

## Tonight's acceptance criteria

**1. Six-orientation test** (step 3)
Rotate through all six faces. ~1 g should appear on whichever axis points
down, ~0 g on the other two. Proves the IMU reads live data and validates
axis orientation before the frame goes together.

**2. Altitude test** (step 4)
Reading stable within ~0.5 m when still. Lift ~1 m → measurable pressure
drop (~0.12 hPa).

Both pass → the flight controller can sense the world.

---

## Troubleshooting

**Serial port vanishes after flashing** — expected on the S3-Zero. It uses the
ESP32's own native USB, so the port disappears and re-enumerates when the chip
resets. Unplug, replug (no BOOT), and look for the new port.

**Bus scan finds nothing** — almost always wiring, power, or pin
assignment, not a dead sensor. Check in order: 3V3 and GND connected;
SDA/SCL not swapped; GPIO number vs silkscreen label (S3 Minis often
disagree); drop `I2C_FREQ` to `100_000`.

**IMU reads all zeros** — it boots asleep. The driver clears the sleep bit
in `PWR_MGMT_1` (0x6B), so if you see zeros, the write didn't land.

**Chip ID is 0x60, not 0x58** — you have a BME280, not a BMP280. Common
mislabelling. Pressure and temperature work identically; you just have an
unused humidity sensor. Nothing to fix.

**Altitude is wildly wrong** — expected. `SEA_LEVEL_HPA` is a default
guess. Only the *change* matters for a drone.

**Gyro bias isn't zero** — normal. Every MPU-6050 has a resting offset.
This is exactly why ESP-Drone calibrates on boot, and why the drone must
sit still and level while it does.

---

## Session 2 — Motor drive (2× DRV8833)

The discrete-MOSFET stage originally planned here was dropped in favor
of two DRV8833 dual H-bridge modules (integrated current limit, thermal
and undervoltage protection, fault output). Full wiring map and
decision record live in `PLAN.md`; pins live in `config.py`; the
interactive wiring page is `docs/esp-fly-wiring.html`.

- One GPIO per motor (IN2/IN4 jumpered to GND on each module):
  GPIO 1 = front-right, 2 = rear-right, 3 = front-left, 4 = rear-left
  (left side verified by single-pin isolation 2026-08-19 — the original
  wiring notes had it swapped)
- EEP (nSLEEP) on GPIO 5, ULT (nFAULT) on GPIO 6 — each one wire
  Y-spliced to both modules. J1 cleared on both or EEP does nothing.
- Motor VCC/GND at the star point, fed by both the battery and the
  board's 5V rail — **motors spin on USB power alone** (verified live
  2026-08-18), so every test run is live
- Test with `import step6_motors` — **props off**. Verifies each
  motor's position and direction at low PWM, then all four together.
- Flash ESP-Drone (ESP-IDF/C) — this **replaces** MicroPython entirely
- Set a unique AP SSID per drone in the WiFi config before building
