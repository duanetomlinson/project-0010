"""
step1_hello.py -- STEP 1: Is the board alive?

Nothing is wired yet. This just proves MicroPython flashed correctly
and we can talk to the chip.

Run:  import step1_hello
"""

import sys
import time
import machine

import config


def board_info():
    print("=" * 46)
    print("  ESP-FLY  --  Step 1: Board check")
    print("=" * 46)
    print("MicroPython :", sys.version)
    print("Platform    :", sys.platform)
    print("CPU freq    :", machine.freq() // 1_000_000, "MHz")

    try:
        import esp32
        print("Temperature :", round(esp32.mcu_temperature(), 1), "C")
    except Exception:
        pass                      # not on every port, not important

    import gc
    gc.collect()
    print("Free RAM    :", gc.mem_free(), "bytes")

    uid = machine.unique_id()
    print("Unique ID   :", "".join("{:02x}".format(b) for b in uid))
    print()


def blink(count=5):
    """Blink the onboard LED. Purely so you can SEE it working."""
    if config.LED_PIN is None:
        print("LED_PIN is None -- skipping blink.")
        return

    if config.LED_IS_NEOPIXEL:
        try:
            import neopixel
            np = neopixel.NeoPixel(machine.Pin(config.LED_PIN), 1)
            print("Blinking NeoPixel on GPIO", config.LED_PIN)
            for i in range(count):
                np[0] = (0, 20, 0)     # dim green -- full brightness is blinding
                np.write()
                time.sleep_ms(200)
                np[0] = (0, 0, 0)
                np.write()
                time.sleep_ms(200)
            return
        except ImportError:
            print("neopixel module missing -- trying plain LED instead")

    led = machine.Pin(config.LED_PIN, machine.Pin.OUT)
    print("Blinking LED on GPIO", config.LED_PIN)
    for i in range(count):
        led.value(1)
        time.sleep_ms(200)
        led.value(0)
        time.sleep_ms(200)


def run():
    board_info()
    blink()
    print("PASS -- board is alive.")
    print("Next: wire the sensors, then run step2_scan.")


run()
