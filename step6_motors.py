"""
step6_motors.py -- DRV8833 motor drive bring-up

PROPS OFF. This test spins motors. Do not run with propellers mounted.

Hardware under test: 2x DRV8833 modules, one GPIO per motor (the second
input of each channel is jumpered to GND on the module, so PWM on IN1
drives forward, low coasts). EEP (nSLEEP) and ULT (nFAULT) are each one
wire Y-spliced to both modules. Motor power comes from the battery at
the star point -- USB alone will NOT spin motors.

What this proves, in order:
  1. WAKE    -- EEP high wakes both drivers, nFAULT reads healthy.
  2. SPIN    -- each motor alone: soft ramp to test duty, hold, stop.
                You confirm by eye that the RIGHT motor spun the
                RIGHT direction (labels printed at each step).
  3. ALL     -- all four together at reduced duty: catches battery sag
                and shared-ground problems that single motors hide.
  4. FAULT   -- nFAULT checked after every stage; any LOW aborts.

Cleanup always runs: all PWM to zero, drivers back to sleep.

Run from the REPL:  import step6_motors
Re-run after edit:  Ctrl-D (soft reboot), then import again.
"""

import time
from machine import Pin, PWM
import config

# Bench-test power levels. Full scale is 65535.
SPIN_DUTY = 20_000          # ~30% -- enough to spin bare coreless motors
ALL_DUTY = 13_000           # ~20% -- gentler when all four run at once
SPIN_MS = 1500              # per-motor run time
RAMP_STEPS = 10             # soft-start steps (avoids inrush current spike)

# Order matters: printed labels are how you verify position + direction.
MOTORS = (
    ("M1 front-right, should spin CCW", config.MOTOR_FR),
    ("M2 rear-right,  should spin CW",  config.MOTOR_RR),
    ("M3 rear-left,   should spin CCW", config.MOTOR_RL),
    ("M4 front-left,  should spin CW",  config.MOTOR_FL),
)

sleep_pin = Pin(config.MOTOR_SLEEP, Pin.OUT, value=0)   # start asleep
fault_pin = Pin(config.MOTOR_FAULT, Pin.IN, Pin.PULL_UP)

pwms = []
for label, gpio in MOTORS:
    p = PWM(Pin(gpio), freq=config.MOTOR_PWM_FREQ, duty_u16=0)
    pwms.append((label, p))


def stop_all():
    for _, p in pwms:
        p.duty_u16(0)


def check_fault(stage):
    """nFAULT is open-drain active-low: HIGH = healthy."""
    if fault_pin.value() == 0:
        stop_all()
        sleep_pin.value(0)
        raise RuntimeError("nFAULT LOW after '%s' -- overcurrent/overtemp/"
                           "undervoltage. Motors stopped, drivers asleep." % stage)
    print("  fault line OK after: %s" % stage)


def ramp_to(p, duty):
    for i in range(1, RAMP_STEPS + 1):
        p.duty_u16(duty * i // RAMP_STEPS)
        time.sleep_ms(30)


print("=" * 52)
print("DRV8833 MOTOR BRING-UP  --  PROPS MUST BE OFF")
print("Battery must be connected (motors don't run on USB).")
print("=" * 52)
print("Starting in 3 seconds... Ctrl-C to abort.")
time.sleep(3)

try:
    # Stage 1: wake the drivers
    sleep_pin.value(1)
    time.sleep_ms(5)                      # DRV8833 wake-up time is ~1 ms
    check_fault("wake (EEP high, no drive)")

    # Stage 2: one motor at a time
    for label, p in pwms:
        print("\n>>> %s" % label)
        ramp_to(p, SPIN_DUTY)
        time.sleep_ms(SPIN_MS)
        p.duty_u16(0)
        check_fault(label)
        time.sleep_ms(800)                # gap so you can tell motors apart

    # Stage 3: all four together
    print("\n>>> ALL FOUR at reduced duty (watch for stutter = battery sag)")
    for _, p in pwms:
        ramp_to(p, ALL_DUTY)
    time.sleep_ms(SPIN_MS)
    stop_all()
    check_fault("all four together")

    print("\nPASS: all stages completed, no faults.")
    print("Verify by eye: did each printed label match the motor that")
    print("actually spun, in the direction stated? If not, fix the pin")
    print("map in config.py -- not the wiring.")

finally:
    stop_all()
    sleep_pin.value(0)                    # drivers back to sleep
    print("Cleanup: motors stopped, drivers asleep.")
