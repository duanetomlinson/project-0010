"""
step6_motors.py -- DRV8833 motor drive bring-up

PROPS OFF. This test spins motors. Do not run with propellers mounted.
Motors spin on USB power too (5V pin shares the USB VBUS rail) -- every
run is LIVE.

Hardware facts, verified live 2026-08-19:
  - Pin map (per-pin isolation runs): GPIO1=front-right, GPIO2=rear-right,
    GPIO3=front-left, GPIO4=rear-left.
  - EEP (GPIO5) is externally held HIGH -- the drivers are always awake,
    so this test does NOT touch GPIO5. Do not drive it as an output
    until the J1 / 5-6 wire question is resolved in hardware.
  - Reliable isolation requires the clean-pin pattern used here: release
    every motor pin to a plain input, then PWM exactly one pin at a
    time, deinit before moving on. Earlier scaffolding that held
    multiple PWM channels + drove EEP produced all-four-spinning.

Sequence: each motor alone (soft ramp -> hold -> stop -> release), then
all four together briefly. nFAULT (GPIO6, open-drain active-low) is
read after every stage; any LOW aborts. Cleanup always runs.

Run from the REPL:  import step6_motors
Re-run after edit:  Ctrl-D (soft reboot), then import again.
"""

import time
from machine import Pin, PWM
import config

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


def check_fault(stage):
    """nFAULT is open-drain active-low: HIGH = healthy."""
    v = Pin(config.MOTOR_FAULT, Pin.IN, Pin.PULL_UP).value()
    Pin(config.MOTOR_FAULT, Pin.IN)  # drop the pull-up again
    if v == 0:
        release_all()
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
time.sleep(3)

try:
    release_all()
    check_fault("baseline (nothing driven)")

    # Stage 1: one motor at a time, clean-pin pattern
    for label, gpio in MOTORS:
        print("\n>>> GPIO%d: %s" % (gpio, label))
        p = PWM(Pin(gpio), freq=config.MOTOR_PWM_FREQ, duty_u16=0)
        ramp_to(p, SPIN_DUTY)
        time.sleep_ms(SPIN_MS)
        p.duty_u16(0)
        p.deinit()
        Pin(gpio, Pin.IN)
        check_fault(label)
        time.sleep_ms(GAP_MS)

    # Stage 2: all four together
    print("\n>>> ALL FOUR at reduced duty (watch for stutter = rail sag)")
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

    print("\nPASS: all stages completed, no faults.")
    print("Verify by eye: did each printed label match the motor that")
    print("actually spun, in the direction stated? If not, fix the pin")
    print("map in config.py -- not the wiring.")

finally:
    release_all()
    print("Cleanup: all motor pins released (drivers stay awake -- EEP")
    print("is hardware-tied high; released inputs = coast, no drive).")
