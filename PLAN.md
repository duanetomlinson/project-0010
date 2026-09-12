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
| `status_led.py` | library | config | Onboard WS2812 (GPIO 21) helper: `set_color(r,g,b)`, `show(state)` for `boot`/`ok`/`fault`/`motor_test`, `off()`. No-op when `LED_PIN` is None. |
| `mpu6050.py` | library | — | IMU driver. Nothing runs on import. |
| `bmp280.py` | library | — | Barometer driver + Bosch compensation math. |
| `step1_hello.py` | test | config, status_led | Board info + LED blink. |
| `step2_scan.py` | test | config | I2C bus scan. |
| `step3_imu.py` | test | config, mpu6050 | Gyro calibration, live stream, six-orientation test. |
| `step4_baro.py` | test | config, bmp280 | Chip ID, noise check, 1 m lift test. |
| `step5_combined.py` | test | config, both drivers | Both sensors, one loop, rate benchmark. |
| `step6_motors.py` | test | config, status_led | Per-motor spin, all-four load, nFAULT monitor, status LED. EEP wake only when `MOTOR_SLEEP_DRIVE=True`. |
| `main.py` | boot | — | All commented out on purpose. |
| `docs/esp-fly-wiring.html` | doc | config (by hand) | Interactive wiring page: SVG board + both DRV8833s + sensors + power star, copyable spec. Re-sync whenever `config.py` pins change. |

### step6_motors.py logic

```
 import step6_motors
        |
        v
  [banner + 3 s abort window]  LED white     Ctrl-C / any exception
        |                                          |
        v                                          v
  release all motor pins to inputs         [except: LED red, re-raise]
  EEP: MOTOR_SLEEP_DRIVE? --yes--> drive    [finally: release motor pins,
        | no (default: untouched)           release EEP to input, report]
        v
  nFAULT (pull-up read) low? --> abort, LED red
        |
        v
  for each motor (FR, RR, FL, RL):    LED amber while driven
      PWM exactly one pin: ramp 0 -> 30%, hold 1.5 s, stop, release
      nFAULT low? --> abort            <- overcurrent/overtemp/UVLO
      LED green
        |
        v
  all four @ 20%, 1.5 s              <- battery sag / ground path check
      nFAULT check, LED green
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

| GPIO | Wire | Motor (VERIFIED by isolation runs 2026-08-19) |
|------|------|-----------------------------------------------|
| 1 | DRV8833 #1 (right) | front-right, CCW |
| 2 | DRV8833 #1 (right) | rear-right, CW |
| 3 | DRV8833 #2 (left)  | **front-left**, CW (wiring notes said rear-left — notes were wrong) |
| 4 | DRV8833 #2 (left)  | **rear-left**, CCW (wiring notes said front-left) |
| 5 | EEP (nSLEEP), Y-spliced | measured externally held HIGH → drivers always awake. Suspect J1 not cleared or 5/6 wires swapped. **Do not drive as output** until resolved. |
| 6 | ULT (nFAULT), Y-spliced | open-drain, low = fault; read with ESP32 pull-up |

Motor power: the star point ties to the board's **5V pin**, which is
the same rail as USB VBUS. The battery will also connect to the 5V pin,
so either source (USB or battery) powers the motors — every run of
step6 is live. **CAUTION, unverified:** if the S3-Zero has no diode
between USB VBUS and the 5V pin, plugging in USB with the battery
attached parallels the two sources — USB would push uncontrolled
charge current into the battery. Check the Waveshare S3-Zero schematic
(or measure) before ever having battery + USB connected at the same
time. GPIO 3 is a strapping pin but safe here (sampled only at reset,
JTAG_SEL eFuse not burned, DRV8833 input pulldown defines it at boot).

**Plan of execution:**

1. [x] Add motor section to `config.py` (pins, PWM freq, GPIO 3 note).
2. [x] Write `step6_motors.py` — wake → per-motor spin → all-four →
       fault-checked, cleanup guaranteed via `finally`.
3. [x] Create this plan log; fix README's obsolete MOSFET section.
4. [x] Commit; push `config.py` + `step6_motors.py` to the board via
       mpremote.
5. [x] Live run on USB, 2026-08-18: full sequence completed — wake,
       all four motors spun one at a time IN THE LABELED ORDER, all
       four together, no faults, clean shutdown. (First logged as an
       "unpowered dry run" — wrong: the star's VCC is also fed from
       the board's 5V rail, so motors run on USB. See CLAUDE.md
       Learnings. There is no unpowered "safe" state; every run of
       step6 is live.)
6. [x] Per-pin isolation runs 2026-08-19 (drive ONE GPIO, all other
       pins released to plain inputs, human calls the corner):
       GPIO1→front-right ✓, GPIO2→rear-right ✓, GPIO3→**front-left**
       (map said rear-left), GPIO4→**rear-left** (map said front-left).
       `config.py` corrected; `step6_motors.py` rewritten to use the
       clean-pin pattern and to stop driving EEP.
7. [ ] Hardware checks before next session:
       - Why is EEP (GPIO5) held high? J1 confirmed NOT soldered on
         either module (checked 2026-08-19), so the leading suspect is
         the 5/6 wires being swapped: these modules typically have a
         10k pull-up to VCC on ULT (nFAULT), which would present as a
         stuck-high line — and would also mean GPIO5 sees ~5V through
         10k. Trace both wires at the modules.
       - Sleep control matters for flight (coast-safe boot); until
         fixed, drivers are always awake and only the IN pins gate
         the motors.
8. [ ] Confirm spin DIRECTIONS by eye during the next full step6 run
       (FR/RL = CCW, RR/FL = CW).

**Next after motors pass:** flash ESP-Drone (ESP-IDF/C) — replaces
MicroPython entirely; set a unique AP SSID per drone before building.

## ESP-Drone compatibility assessment — 2026-08-19

Verified against espressif/esp-drone master. Verdict: **compatible, but
NOT flashable as-is** — stock defaults would PWM the EEP/ULT lines as
motors. All fixes are menuconfig-only.

What matches out of the box:
- ESP32-S3 is a supported target (`sdkconfig.defaults.esp32s3`; the
  hardware-version choice auto-selects TARGET_ESP32_S2_DRONE_V1_2).
- Corner/direction convention is IDENTICAL to our build
  (docs/_static/motors_direction.png): M1=front-right CCW,
  M2=rear-right CW, M3=rear-left CCW, M4=front-left CW.
- Brushed drive = one active-high LEDC PWM per motor — our
  single-input DRV8833 wiring is drop-in compatible. No sleep-pin
  concept in the firmware, so the stuck-high EEP is actually fine.
- BMP280 is simply unsupported (only MS5611, disabled by default) —
  it gets ignored; stock esp-drone flies on MPU6050 alone.

Required menuconfig changes (ESPDrone Config):
| Setting | Default (S2/S3 target) | Ours |
|---------|------------------------|------|
| MOTOR01_PIN (M1 front-right) | 5 (= our EEP!) | **1** |
| MOTOR02_PIN (M2 rear-right)  | 6 (= our ULT!) | **2** |
| MOTOR03_PIN (M3 rear-left)   | 3 | **4** |
| MOTOR04_PIN (M4 front-left)  | 4 | **3** |
| I2C0_PIN_SDA | 11 | **10** |
| I2C0_PIN_SCL | 10 | **9** |
| MPU_PIN_INT  | 12 | **7** (GY-521 INT soldered to GPIO 7, 2026-08-19) |

Hard blocker found: **the MPU6050 INT pin is mandatory** — the sensor
task blocks on a semaphore given only by the rising-edge ISR on
CONFIG_MPU_PIN_INT (sensors_mpu6050_hm5883L_ms5611.c:629-668).
Resolution: GY-521 INT soldered to **GPIO 7** (2026-08-19), and
CONFIG_MPU_PIN_INT=7 set in the overrides. **VERIFIED live**: GPIO 7
reads 0 at rest; with DATA_RDY enabled at 100 Hz, 101 rising edges
counted in 1 s. I2C scan still shows 0x68 + 0x76 post-solder.

Build environment: esp-drone requires **ESP-IDF release/v5.0** (per
its README). Not yet installed on this machine (`idf.py` not on PATH).

Setup done 2026-08-19: espressif/esp-drone cloned into `esp-drone/`
(git-ignored vendor checkout). All overrides above are appended to
`esp-drone/sdkconfig.defaults.esp32s3` and kept as a tracked copy in
`espdrone-overrides.sdkconfig` (with re-apply instructions) at the
repo root. Build: `cd esp-drone && idf.py set-target esp32s3 &&
idf.py build` (delete any stale `sdkconfig` first so defaults apply).

### FLASHED AND BOOTING — 2026-08-19

ESP-Drone built (IDF v5.0 + Python 3.11) and flashed to the board.
Verified boot log over USB-Serial/JTAG console: MPU6050 [OK], MPU INT
active on GPIO 7, LEDs relocated to 8/11/12 (defaults 7/9 collided
with INT/SCL), AP up as `ESPFLY-0010_3C0F02E4DD19` (pw 12345678, UDP
2390), `selftestPassed = 1`. Optional deck sensors (VL53L1X, PMW3901)
absent → expected FAILs. Build fixes recorded in
`espdrone-overrides.sdkconfig`; hard-won gotchas in CLAUDE.md
Learnings (software resets park the S3 in download mode — use the
RESET button or USB replug; sensor FAIL after button reset → USB
power cycle).

### App control verified — 2026-08-19 (second session)

Found and fixed a fourth pin collision: the battery-voltage ADC
defaults to GPIO2 (ADC1_CH1) = our rear-right motor — analog mode
disconnects the PWM, so the right side looked dead under app control.
Moved to GPIO 8 (CONFIG_ADC1_PIN=8 + hardcoded-channel patch in
adc_esp32.c, see espdrone-overrides.sdkconfig); red LED moved 8→13.
After the fix all four motors respond from the app. Uneven motor
distribution on the bench (CW pair at initial thrust, CCW pair only
with yaw input) is restrained-quad physics — yaw-integrator wind-up
plus a non-level jig — not a fault.

Gyro calibration timing: ~90 s warm, 4-5 min from cold (MPU6050
warm-up drift). Drone must sit untouched until "Ready to fly".

Next (flight bring-up) — **POWER IS THE CURRENT FOCUS**:
1. [ ] Power testing: add a boost converter (charge module → steady
       5 V into the 5 V pin) and verify boot + AP + motor load on
       battery. The onboard LDO browns out on 1S under WiFi + motor
       load (AP never appears on battery). NEVER boost and USB at
       the same time. Likely needs a cleaner physical build — the
       charge module + boost + DRV8833s are small modules that need
       a tidier mounting to fit the frame (consider a mounting
       plate/enclosure; freecad if we design one).
2. [ ] Tape the jig flat and re-verify even four-motor spin-up at
       level attitude — PROPS OFF.
3. [ ] Resolve EEP/ULT 5-6 wire question (GPIO 5 sees ~5 V through
       the suspected nFAULT pull-up) — disconnect both wires from
       GPIO 5/6, or re-trace; esp-drone uses neither pin.
4. [ ] Level calibration on a flat surface, then props on (FR/RL
       CCW props, RR/FL CW props) and first tethered hover.

Minor / cosmetic: battery-voltage ADC not wired (battery warnings
bogus), buzzer/LED pin defaults don't match this board (disable or
ignore), set a unique WIFI_BASE_SSID.

## Session 3 — 2026-09-11 — Interactive wiring page (docs/esp-fly-wiring.html)

**Plan:** replace the stale Aug 17 wiring page (lived in ~/Downloads, five
pins wrong: SDA on 8, EEP on 7, no MPU INT, left corners swapped) with a
single-file interactive page inside the repo, sourced from `config.py`.

**Sources:** `config.py` for every GPIO (I2C verified 2026-08-16, corners
2026-08-19, MPU INT 2026-08-19); Waveshare ESP32-S3-Zero pin-definition
image (2026-09-11) for the physical rail order — left rail 5V, GND, 3V3,
GP1–GP6; right rail TX, RX, GP13–GP7. Every wire in this build lands on
those two rails. DRV8833 pad order on the drawing is schematic; solder by
silkscreen label.

**Plan of execution:**

1. [x] Build `docs/esp-fly-wiring.html` with the `wiring-playground`
       pattern: wire list as data → SVG, connection table, warnings,
       copyable spec. Both modules show IN1–IN4, EEP, ULT, VCC, GND;
       IN2/IN4 jumpered to each module's own GND pad; EEP/ULT Y-spliced
       to GPIO 5/6; MPU INT on GPIO 7; AD0/SDO to GND (0x68 / 0x76).
       Safety callouts: props off / every run live on USB, USB+battery
       unverified, EEP held high externally.
2. [x] Fix README motor line (3 = front-left, 4 = rear-left) and point
       README at the page.
3. [x] Render check headless over localhost (Playwright): zero console
       errors, wires reach pins.
4. [x] Commit on `docs/esp-fly-wiring`, push, draft PR → `mvp-dual-drv8833`.
5. [x] Superseded by Session 4: the as-built map resolves the 5/6
       labels (ULT=5, EEP=6); bench confirmation still open there.

## Session 4 — 2026-09-11 — As-built pin map into config.py + status LED

**Trigger:** the user supplied an authoritative as-built pin map. Three
signals differ from what `config.py` recorded during bring-up:

| Signal | Was | As-built | Note |
|--------|-----|----------|------|
| ULT / nFAULT (both DRV8833, Y-spliced) | 6 | **5** | open-drain, active LOW, read with pull-up |
| EEP / nSLEEP (both DRV8833, Y-spliced) | 5 | **6** | HIGH = awake |
| MPU-6050 INT | 7 | **13** | ESP-Drone needs it; MicroPython polls |

Motors (1–4), I2C (SCL 9 / SDA 10) and the WS2812 on GPIO 21 are
unchanged. The onboard WS2812 is the only LED on the board and is now
the status LED.

**Hypothesis (not yet verified):** the swap explains the 2026-08-19
"GPIO5 externally held HIGH" measurement — a healthy nFAULT line with
the module's pull-up to VCC reads HIGH at rest, and GPIO5 was then
labelled EEP. Confirm by tracing both wires at the modules before
driving GPIO6 as an output.

**Decisions:**
- Every GPIO in every `.py` file comes from a `config.py` name; no
  numeric pin literal outside `config.py`.
- `MOTOR_SLEEP_DRIVE = False` (new, `config.py`) gates the only code
  that would drive EEP. Default keeps the "do not drive" behaviour;
  when True, `step6_motors` drives EEP HIGH to wake and releases it to
  an input on exit (never forces it low).
- `status_led.py` (new): `set_color`, `show(state)`, `off`. States:
  boot = white, ok = green, fault = red, motor_test = amber. Used by
  `step6_motors` (fault → red) and `step1_hello` (blink).
- `espdrone-overrides.sdkconfig` / `esp-drone/` are NOT touched here —
  a separate pass re-syncs CONFIG_MPU_PIN_INT to 13.

**Plan of execution:**

1. [x] `config.py`: MOTOR_FAULT=5, MOTOR_SLEEP=6, MOTOR_SLEEP_DRIVE=False,
       MPU_INT=13; comments rewritten with the hypothesis wording.
2. [x] `status_led.py` added; `step6_motors.py` and `step1_hello.py`
       use it. `step6_motors.py` honours MOTOR_SLEEP_DRIVE.
3. [x] `step2_scan.py` docstring: SDA on GPIO 10 (was stale at 8).
4. [x] `docs/esp-fly-wiring.html`: wire data (ULT→GP5, EEP→GP6,
       INT→GP13), legend, warnings, copyable spec.
5. [x] README + this log updated; architectural map has `status_led.py`.
6. [ ] Bench: trace ULT/EEP at both modules; confirm GPIO5 reads HIGH
       via nFAULT pull-up and GPIO6 is nSLEEP. Then decide whether to
       set MOTOR_SLEEP_DRIVE=True.
7. [ ] Re-sync `espdrone-overrides.sdkconfig` (MPU_PIN_INT 7 → 13) and
       re-verify the INT edge count on GPIO 13 — separate pass.
8. [ ] Push `config.py`, `status_led.py`, `step6_motors.py`,
       `step1_hello.py` to the board via mpremote; run step1 (LED
       blink) and step6 (props off) and watch the status LED.
