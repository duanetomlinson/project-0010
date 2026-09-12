"""
status_led.py -- onboard WS2812 status LED (pin from config.LED_PIN)

show(state) for the named STATES below, set_color(r, g, b) for anything
else, off(). Colours are dim on purpose (full WS2812 is blinding).
Every call is a silent no-op when config.LED_PIN is None.
"""

from machine import Pin
import config

STATES = {
    "boot":       (8, 8, 8),        # dim white: script starting
    "ok":         (0, 20, 0),       # green: stage passed
    "fault":      (40, 0, 0),       # red: nFAULT low / exception
    "motor_test": (30, 12, 0),      # amber: a motor is being driven
    "off":        (0, 0, 0),
}

_pixel = None               # created on first use, then reused


def set_color(r, g, b):
    global _pixel
    if config.LED_PIN is None or not config.LED_IS_NEOPIXEL:
        return
    if _pixel is None:
        import neopixel
        _pixel = neopixel.NeoPixel(Pin(config.LED_PIN), 1)
    _pixel[0] = (r, g, b)
    _pixel.write()


def show(state):
    set_color(*STATES[state])


def off():
    show("off")
