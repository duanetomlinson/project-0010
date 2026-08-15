"""
step4_baro.py -- STEP 4: Can we sense altitude?

Two tests:
  1. Noise check -- how stable is the reading when nothing moves?
  2. Lift test -- raise the board ~1m, see a real pressure drop

Run:  import step4_baro
"""

import time
from machine import Pin, I2C

import config
from bmp280 import BMP280, CHIP_BMP280, CHIP_BME280


def make_baro():
    i2c = I2C(config.I2C_ID,
              sda=Pin(config.I2C_SDA),
              scl=Pin(config.I2C_SCL),
              freq=config.I2C_FREQ)
    return BMP280(i2c, addr=config.BMP280_ADDR)


def identify(baro):
    print("Chip ID  : 0x{:02X}  ({})".format(baro.chip_id, baro.chip_name))
    if baro.chip_id == CHIP_BME280:
        print()
        print("  NOTE: this is a BME280, not a BMP280. Plenty of boards")
        print("  are sold mislabelled. Pressure and temperature work fine")
        print("  with this driver -- you just also have an unused humidity")
        print("  sensor. Nothing to fix for our purposes.")
    print()


def noise_check(baro, seconds=10):
    """How much does the reading wander when the board is still?"""
    print("-- Noise check, {}s. DON'T TOUCH IT. --".format(seconds))

    alts = []
    end = time.ticks_add(time.ticks_ms(), seconds * 1000)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        alts.append(baro.altitude(config.SEA_LEVEL_HPA))
        time.sleep_ms(100)

    lo, hi = min(alts), max(alts)
    spread = hi - lo
    mean = sum(alts) / len(alts)

    print("  samples : {}".format(len(alts)))
    print("  mean    : {:.2f} m".format(mean))
    print("  spread  : {:.2f} m  (min {:.2f} / max {:.2f})".format(spread, lo, hi))

    if spread < 0.5:
        print("  PASS -- well within 0.5m of noise.")
    elif spread < 1.5:
        print("  ACCEPTABLE -- a bit noisy. Draughts and AC vents do this.")
    else:
        print("  NOISY -- close doors/windows, keep it away from airflow.")
    print()
    return mean


def lift_test(baro, baseline_alt):
    """
    Raise the board about a metre. Pressure should drop measurably.

    ~1m of altitude is roughly 0.12 hPa. Small, but real -- and it's
    what altitude hold would eventually key off.
    """
    print("-- Lift test --")
    print("Board is on the table. Baseline set.")
    input("Now LIFT it about 1 metre and HOLD. Press Enter: ")

    time.sleep_ms(500)              # let the filter settle

    sa = sp = 0.0
    for _ in range(20):
        t, p = baro.read()
        sa += baro.altitude(config.SEA_LEVEL_HPA)
        sp += p / 100.0
        time.sleep_ms(50)
    alt_up, p_up = sa / 20, sp / 20

    delta = alt_up - baseline_alt

    print()
    print("  baseline : {:.2f} m".format(baseline_alt))
    print("  lifted   : {:.2f} m   ({:.2f} hPa)".format(alt_up, p_up))
    print("  change   : {:+.2f} m".format(delta))
    print()

    if delta > 0.5:
        print("  PASS -- barometer detects real altitude change.")
    elif delta > 0.15:
        print("  WEAK but present. Try lifting higher, or stand on a chair.")
    else:
        print("  NO CHANGE detected. Either it wasn't lifted far enough,")
        print("  or airflow is swamping the signal. Retry more slowly.")
    return delta


def run():
    print("=" * 46)
    print("  ESP-FLY  --  Step 4: Barometer")
    print("=" * 46)

    baro = make_baro()
    identify(baro)

    t, p = baro.read()
    print("Temperature : {:.2f} C".format(t))
    print("Pressure    : {:.2f} hPa".format(p / 100.0))
    print("Altitude    : {:.2f} m  (vs {} hPa sea level)".format(
        baro.altitude(config.SEA_LEVEL_HPA), config.SEA_LEVEL_HPA))
    print()
    print("If altitude looks wrong for New Port Richey, that's expected --")
    print("SEA_LEVEL_HPA is a default guess. Only the CHANGE matters.")
    print()

    baseline = noise_check(baro)
    lift_test(baro, baseline)

    print()
    print("Next: step5_combined")


run()
