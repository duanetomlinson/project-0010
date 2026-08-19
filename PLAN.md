# ESP-FLY Plan Log

Running log of plans, decisions, and execution state. Newest session last.
This file exists so anyone (human or agent) can pick up the project and
know what was decided, what changed, and why — without re-deriving it
from git archaeology.

---

## Architectural map

| File | Type | Depends on | What it does |
|------|------|------------|--------------|
| `config.py` | config | — | All pins and addresses. **Edit here, nowhere else.** |
| `mpu6050.py` | library | — | IMU driver. Nothing runs on import. |
| `bmp280.py` | library | — | Barometer driver + Bosch compensation math. |
| `step1_hello.py` | test | config | Board info + LED blink. |
| `step2_scan.py` | test | config | I2C bus scan. |
| `step3_imu.py` | test | config, mpu6050 | Gyro calibration, live stream, six-orientation test. |
| `step4_baro.py` | test | config, bmp280 | Chip ID, noise check, 1 m lift test. |
| `step5_combined.py` | test | config, both drivers | Both sensors, one loop, rate benchmark. |
| `step6_motors.py` | test | config | DRV8833 wake, per-motor spin, all-four load, fault monitor. |
| `main.py` | boot | — | All commented out on purpose. |

### step6_motors.py logic

```
 import step6_motors
        |
        v
  [banner + 3 s abort window]        Ctrl-C anywhere
        |                                  |
        v                                  v
  EEP high (wake) --5ms--> nFAULT?   [finally: duty=0,
        | high                        EEP low, report]
        v
  for each motor (FR, RR, RL, FL):
      ramp 0 -> 30% over 300 ms      <- soft start, no inrush trip
      hold 1.5 s, stop
      nFAULT low? --> abort           <- overcurrent/overtemp/UVLO
        |
        v
  all four @ 20%, 1.5 s              <- battery sag / ground path check
      nFAULT check
        |
        v
  PASS (human confirms position + direction by eye)
```

---

## Session 1 — 2026-08-16 — Sensor bring-up

**Plan:** validate MPU-6050 + BMP280 over I2C before any motor work.
**Outcome:** done. One deviation from plan: sensors are physically wired
SDA→GPIO10, SCL→GPIO9 (not 8/9 as first planned) — verified by pull-up
sweep + bus scan, recorded in `config.py`.

## Session 2 — 2026-08-18 — Motor drive pivot: MOSFETs → 2× DRV8833

**Decision:** dropped the discrete-MOSFET motor stage (4× SI2302 + flyback
diodes) planned in Session 1 in favor of two DRV8833 dual H-bridge
modules. Rationale: integrated current limit, thermal/UVLO protection,
and a fault output — fewer discrete parts to get wrong on a drone frame.

**Wiring (as built):** one GPIO per motor. Each channel's second input
(IN2/IN4) is jumpered to the module's own GND pad, so PWM on the first
input = drive, low = coast (fast decay). Direction is fixed by wiring
and was verified per-motor before assembly.

| GPIO | Wire | Module | Motor |
|------|------|--------|-------|
| 1 | IN1, DRV8833 #1 (right) | OUT1/2 | M1 front-right, CCW |
| 2 | IN3, DRV8833 #1 (right) | OUT3/4 | M2 rear-right, CW |
| 3 | IN3, DRV8833 #2 (left)  | OUT3/4 | M3 rear-left, CCW |
| 4 | IN1, DRV8833 #2 (left)  | OUT1/2 | M4 front-left, CW |
| 5 | EEP (nSLEEP), Y-spliced to both modules | — | high = awake; J1 cleared on both |
| 6 | ULT (nFAULT), Y-spliced to both modules | — | open-drain, low = fault; ESP32 pull-up |

Motor power: battery + / − at the star point. USB alone will not spin
motors. GPIO 3 is a strapping pin but safe here (sampled only at reset,
JTAG_SEL eFuse not burned, DRV8833 input pulldown defines it at boot).

**Plan of execution:**

1. [x] Add motor section to `config.py` (pins, PWM freq, GPIO 3 note).
2. [x] Write `step6_motors.py` — wake → per-motor spin → all-four →
       fault-checked, cleanup guaranteed via `finally`.
3. [x] Create this plan log; fix README's obsolete MOSFET section.
4. [x] Commit; push `config.py` + `step6_motors.py` to the board via
       mpremote.
5. [x] USB-only dry run 2026-08-18: full sequence ran end-to-end on
       the board (wake, 4x per-motor, all-four, cleanup), no crashes,
       no faults. Drivers were unpowered (no battery), so this proves
       software + PWM/EEP/ULT setup only — motors did not spin, and
       the nFAULT "OK" readings are not meaningful without motor VCC.
6. [ ] Battery run — **props off** — human confirms each motor's
       position and direction matches the printed labels.
7. [ ] Record battery-run outcome here (pass / pin-map corrections).

**Next after motors pass:** flash ESP-Drone (ESP-IDF/C) — replaces
MicroPython entirely; set a unique AP SSID per drone before building.
