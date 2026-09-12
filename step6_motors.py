"""
step6_motors.py -- DRV8833 motor drive bring-up

PROPS OFF. This test spins motors. Do not run with propellers mounted.
Motors spin on USB power too (5V pin shares the USB VBUS rail) -- every
run is LIVE.

Hardware facts (pins from config.py -- as-built map 2026-09-11):
  - Motor pins verified by per-pin isolation runs 2026-08-19:
    MOTOR_FR=front-right, MOTOR_RR=rear-right, MOTOR_FL=front-left,
    MOTOR_RL=rear-left.
  - nFAULT (config.MOTOR_FAULT, GPIO5) is open-drain active-low; read
    with the internal pull-up, HIGH = healthy.
  - EEP / nSLEEP (config.MOTOR_SLEEP, GPIO6) is NOT driven unless
    config.MOTOR_SLEEP_DRIVE is True. The 2026-08-19 "GPIO5 held HIGH"
    measurement is thought to be nFAULT's own pull-up (the 5/6 labels
    were swapped) -- confirm on the bench before flipping that flag.
  - Reliable isolation requires the clean-pin pattern used here: release
    every motor pin to a plain input, then PWM exactly one pin at a
    time, deinit before moving on. Earlier scaffolding that held
    multiple PWM channels + drove EEP produced all-four-spinning.

Sequence: each motor alone (soft ramp -> hold -> stop -> release), then
all four together briefly. nFAULT is read after every stage; any LOW
aborts. Cleanup always runs. Status LED: white = starting, amber = a
motor is being driven, green = pass, red = fault or exception.

Run from the REPL:  import step6_motors
Re-run after edit:  Ctrl-D (soft reboot), then import again.
"""

import time
from machine import Pin, PWM
import config
import status_led

SPIN_DUTY = 20_000          # ~30% of 65535 -- bench spin, props off
ALL_DUTY = 13_000           # ~20% -- gentler when all four run at once
SPIN_MS = 1500              # per-motor run time
GAP_MS = 800                # pause between motors so you can tell them apart
RAMP_STEPS = 10             # soft-start steps (avoids inrush current spike)

MOTORS = (
    ("front-right, should spin CCW", config.MOTOR_FR),
    ("rear-right,  should spin CW",  config.MOTOR_RR),
    ("front-left,  should spin CW",  config.MOTOR_FL),
    ("rear-left,   should spin CCW", config.MOTOR_RL),
)

ALL_PINS = tuple(g for _, g in MOTORS)


def release_all():
    for g in ALL_PINS:
        Pin(g, Pin.IN)              # plain input: no drive, no pull


def wake_drivers():
    """Drive EEP high only when config.MOTOR_SLEEP_DRIVE opts in."""
    if config.MOTOR_SLEEP_DRIVE:
        Pin(config.MOTOR_SLEEP, Pin.OUT, value=1)
        time.sleep_ms(5)            # DRV8833 wake-up time
        print("  EEP (GPIO%d) driven HIGH -- MOTOR_SLEEP_DRIVE=True"
              % config.MOTOR_SLEEP)
    else:
        print("  EEP (GPIO%d) left untouched -- MOTOR_SLEEP_DRIVE=False"
              % config.MOTOR_SLEEP)


def release_drivers():
    """Never force EEP low: release it to a plain input instead."""
    if config.MOTOR_SLEEP_DRIVE:
        Pin(config.MOTOR_SLEEP, Pin.IN)


def check_fault(stage):
    """nFAULT is open-drain active-low: HIGH = healthy."""
    v = Pin(config.MOTOR_FAULT, Pin.IN, Pin.PULL_UP).value()
    Pin(config.MOTOR_FAULT, Pin.IN)  # drop the pull-up again
    if v == 0:
        release_all()
        status_led.show("fault")
        raise RuntimeError("nFAULT LOW after '%s' -- overcurrent/overtemp/"
                           "undervoltage. All pins released." % stage)
    print("  fault line OK after: %s" % stage)


def ramp_to(p, duty):
    for i in range(1, RAMP_STEPS + 1):
        p.duty_u16(duty * i // RAMP_STEPS)
        time.sleep_ms(30)


print("=" * 52)
print("DRV8833 MOTOR BRING-UP  --  PROPS MUST BE OFF")
print("Motors spin on USB power too -- every run is LIVE.")
print("=" * 52)
print("Starting in 3 seconds... Ctrl-C to abort.")
status_led.show("boot")
time.sleep(3)

try:
    release_all()
    wake_drivers()
    check_fault("baseline (nothing driven)")

    # Stage 1: one motor at a time, clean-pin pattern
    for label, gpio in MOTORS:
        print("\n>>> GPIO%d: %s" % (gpio, label))
        status_led.show("motor_test")
        p = PWM(Pin(gpio), freq=config.MOTOR_PWM_FREQ, duty_u16=0)
        ramp_to(p, SPIN_DUTY)
        time.sleep_ms(SPIN_MS)
        p.duty_u16(0)
        p.deinit()
        Pin(gpio, Pin.IN)
        check_fault(label)
        status_led.show("ok")
        time.sleep_ms(GAP_MS)

    # Stage 2: all four together
    print("\n>>> ALL FOUR at reduced duty (watch for stutter = rail sag)")
    status_led.show("motor_test")
    pwms = [PWM(Pin(g), freq=config.MOTOR_PWM_FREQ, duty_u16=0)
            for g in ALL_PINS]
    for p in pwms:
        ramp_to(p, ALL_DUTY)
    time.sleep_ms(SPIN_MS)
    for p in pwms:
        p.duty_u16(0)
        p.deinit()
    release_all()
    check_fault("all four together")
    status_led.show("ok")

    print("\nPASS: all stages completed, no faults.")
    print("Verify by eye: did each printed label match the motor that")
    print("actually spun, in the direction stated? If not, fix the pin")
    print("map in config.py -- not the wiring.")

except Exception:
    status_led.show("fault")
    raise

finally:
    release_all()
    release_drivers()
    print("Cleanup: all motor pins released (inputs = coast, no drive).")
