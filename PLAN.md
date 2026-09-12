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
| `espdrone-overrides.sdkconfig` | config | — | Tracked copy of the Kconfig values appended to `esp-drone/sdkconfig.defaults.esp32s3` (pins, SSID, LED, IMU mount, bench print). Every pin the firmware uses is a `CONFIG_*` symbol here. |
| `patches/esp-drone-espfly.patch` | patch | esp-drone @ db0f656 | Source changes to the git-ignored `esp-drone/` vendor tree: WS2812 LED backend (`led_esp32.c`: setters write `state[]` + notify, a `ws2812Task` owns every RMT call; plus the led_strip encoder), `LED_PIN_WS2812` Kconfig symbol, IMU mount remap (`choice IMU_MOUNT` + body-frame negations in the MPU-6050 driver), 1 Hz `ATTITUDE_BENCH_PRINT` line in `stabilizer.c`, ADC channel fix, esp-now pin. `patches/README.md` has the re-apply recipe and the `espfly-0010` commit list. |

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
7. [x] Re-sync `espdrone-overrides.sdkconfig` (MPU_PIN_INT 7 → 13) —
       done in Session 5. Bench re-verify of the INT edge count on
       GPIO 13 is tracked there.
8. [ ] Push `config.py`, `status_led.py`, `step6_motors.py`,
       `step1_hello.py` to the board via mpremote; run step1 (LED
       blink) and step6 (props off) and watch the status LED.

## Session 5 — 2026-09-11 — ESP-Drone firmware onto the as-built map + WS2812 status LED

**Trigger:** Session 4 moved the MicroPython side to the as-built map
(MPU INT on GPIO 13, WS2812 on GPIO 21 as the only LED). The ESP-Drone
build still carried INT=7 and three "parked" discrete-LED pins, one of
which (RED=13) now collided with MPU INT. Every pin the firmware touches
must be a Kconfig symbol, and the vendor-tree changes must be recoverable
(the `esp-drone/` checkout is git-ignored).

**Pin map used (authoritative, unchanged unless noted):**

| Signal | GPIO | Kconfig symbol |
|--------|------|----------------|
| M1 front-right / M2 rear-right / M3 rear-left / M4 front-left | 1 / 2 / 4 / 3 | `MOTOR01..04_PIN` |
| I2C SDA / SCL | 10 / 9 | `I2C0_PIN_SDA` / `I2C0_PIN_SCL` |
| MPU-6050 INT | **13** (was 7) | `MPU_PIN_INT` |
| Battery ADC (nothing wired) | 8 | `ADC1_PIN` + `adc_esp32.c` channel patch |
| WS2812 status LED | 21 | **`LED_PIN_WS2812`** (new) |
| DRV8833 nFAULT / nSLEEP | 5 / 6 | none — firmware never touches them |

**Decisions:**
- `led_esp32.c` is rewritten as a WS2812 backend over the IDF v5.0 RMT
  TX driver (`led_strip_encoder.c/.h` copied from the IDF `rmt/led_strip`
  example). `led.h` is untouched, so `ledseq.c`, `system.c`, `cfassert.c`
  compile as-is. The three logical LEDs are on/off bits mixed into one
  GRB pixel at brightness 32/255: BLUE = system / link down, GREEN =
  link up, RED = charge / low battery / assert.
- `ledSet` never blocks and never touches the RMT driver: it writes
  `state[]` and `xTaskNotifyGive`s a dedicated `ws2812Task` (3072 B
  stack, prio 1) that owns every RMT call and blocks until the previous
  ~80 µs frame has left the wire before sending the next. A burst of
  `ledSet` calls collapses into one frame. (The first backend polled
  `rmt_tx_wait_all_done(chan, 0)` inline from `ledSet`; that overflowed
  the 2 KB LEDSEQCMD task — see "Reboot loop + fix" below.)
  `cfassert.c` calls `ledSet` after `portDISABLE_INTERRUPTS()`: the
  notify is harmless there, but the task cannot run, so the frame may
  never reach the LED; the console "Assert failed" line is the real
  signal. Documented in the `led_esp32.c` file header; `led.h` untouched.
- `CONFIG_LED_PIN_BLUE/GREEN/RED` are kept as symbols (upstream Kconfig)
  but pinned to 21 in the overrides so the generated `sdkconfig` shows no
  phantom claims on 7/9/8; the backend does not read them.
- The vendor tree gets a local branch `espfly-0010` (from upstream
  `db0f656`) with everything committed — `491309e` build fixes,
  `2fe79cf` pin map + first WS2812 backend, `032d336` LED task fix — and
  the tracked delta lives in `patches/esp-drone-espfly.patch`
  (`git diff db0f656..032d336`, esp-now vendor copy excluded — it is
  re-vendored, not patched).

**LED path:**

```
 ledseq.c timer cb        system.c           cfassert.c (IRQs off)
      |                      |                       |
      +---------- ledSet(led, on) / ledClearAll / ledSetAll ----------+
                             |
                             v
                   state[3]  {BLUE, RED, GREEN}      (led_esp32.c: a store, nothing else
                             |                        on the caller's stack)
                             v
                   xTaskNotifyGive(ws2812Task)       (a burst of calls = one notification)
                             |
   - - - - - - - - - - - - - | - - - - - - - - - - - - - - -  task boundary
                             v
                   ws2812Task  (3072 B stack, prio 1, owns every RMT call)
                     ulTaskNotifyTake(portMAX_DELAY)
                             |
                             v
                   rmt_tx_wait_all_done(chan, -1)    (block until the previous
                             |                        ~80 us frame is done)
                             v
                   pixel[3] = {G, R, B}  each 0 or 32
                             |
                             v
                   rmt_transmit(led_strip encoder)
                             |
                             v
                   RMT TX channel, 10 MHz ticks
                             |
                             v
                   GPIO 21 (CONFIG_LED_PIN_WS2812) -> onboard WS2812
```

**Plan of execution:**

1. [x] `esp-drone/sdkconfig.defaults.esp32s3`: fix the missing newline
       after `CPU_FREQ_MHZ=240` and the duplicate `LED_PIN_RED`;
       `MPU_PIN_INT=13`; `LED_PIN_WS2812=21`; LED_PIN_BLUE/GREEN/RED=21.
2. [x] `esp-drone/main/Kconfig.projbuild`: add `LED_PIN_WS2812` (default
       21) under "led config".
3. [x] `esp-drone/components/drivers/general/led/`: WS2812 backend
       (`led_esp32.c`), encoder files, `REQUIRES driver`.
4. [x] `espdrone-overrides.sdkconfig` re-synced (same CONFIG_ lines as the
       appended block; comments rewritten: INT 13, WS2812 backend,
       nFAULT/nSLEEP untouched).
5. [x] Clean build: `rm -f sdkconfig && idf.py set-target esp32s3 &&
       idf.py build` on IDF v5.0 — see the Session 5 PR for the size line.
6. [x] `patches/esp-drone-espfly.patch` + `patches/README.md` tracked here
       (patch = upstream db0f656 -> working tree, verified by re-applying
       to pristine copies; 9 files, esp-now vendor copy excluded).
6b. [x] Nested repo: branch `espfly-0010` from `db0f656`, tree clean —
       `491309e` (Aug build fixes: ADC channel, esp-now 2.1.1 vendored),
       `2fe79cf` (pin map + first WS2812 backend), `032d336` (LED task
       fix, 2026-09-11). Local only, never pushed. Patch regenerated as
       `git diff db0f656..032d336` (9 files, reverse-apply checked).
7. [x] 2026-09-11 — Flashed unit 1 (USB serial 3C:0F:02:E4:D8:4C).
       First build (`2fe79cf`) reboot-looped every 10.5 s with a
       LEDSEQCMD stack overflow; re-flashed with `032d336` at ~23:31.
       After the USB replug at 23:45 a 75 s passive serial capture
       shows 0 `rst:`, 0 overflow, 0 `rmt:` lines; AP
       `ESPFLY-0010_3C0F02E4D84D` visible on channel 6. Details under
       "Reboot loop + fix" below. Not re-checked in this pass: the
       `gpio:` claim lines and the LED colour sequence by eye.
8. [x] 2026-09-11 — INT on GPIO 13 = 100 edges/s at the 100 Hz sample
       rate (live MicroPython check on unit 1 before the flash; MPU-6050
       at 0x68 on SDA 10 / SCL 9). The pin the firmware reads carries
       the data-ready edge; no reset in the 75 s firmware capture.

### Reboot loop + fix — 2026-09-11

The first Session 5 build on unit 1 rebooted every ~10.5 s with
`***ERROR*** A stack overflow in task LEDSEQCMD has been detected`
(capture `boot3.raw`). Root cause, verified in the vendor tree and the
IDF v5.0 source:

1. LEDSEQCMD's stack is `2 * CONFIG_BASE_STACK_SIZE` = 2048 B
   (`components/config/include/config.h:152`); only ~1332 B are free
   at idle.
2. The first WS2812 backend called `rmt_tx_wait_all_done(chan, 0)`
   inline from `ledSet`. In IDF v5.0 (`rmt_tx.c:540`) a zero timeout
   fails whenever the previous ~80 µs frame is still in flight — it
   drops the frame AND runs `ESP_LOGE("flush timeout")` on the caller's
   stack.
3. At `systemStart` ledseq issues back-to-back `ledSet` calls; the
   second one landed on that ESP_LOGE/vprintf path inside LEDSEQCMD and
   overflowed it -> reboot every 10.5 s.
4. Fix (vendor `032d336`, patch v2): setters only write `state[3]` +
   `xTaskNotifyGive`; a `ws2812Task` (3072 B, prio 1) owns every RMT
   call and waits with a blocking timeout. No polling, no rmt log
   lines; bursts collapse into one frame.
5. cfassert path: the notify is harmless (interrupts off = critical
   section), the task cannot run, the frame may not go out — accepted
   and documented in the `led_esp32.c` header. `led.h` untouched.

**Flash / boot record (unit 1, USB serial 3C:0F:02:E4:D8:4C):**

| Time (2026-09-11) | Action | Result |
|---|---|---|
| ~23:15 | erase + flash first Session 5 build | reboot loop, LEDSEQCMD overflow (`boot3.raw`) |
| ~23:31 | re-flash with `032d336` | chip parked in download mode after `idf.py flash` (expected over USB-JTAG) |
| 23:45 | USB replug, 75 s passive capture (port opened with DTR/RTS asserted, no reset) | 0 `rst:`, 0 overflow, 0 `rmt:` |
| after | WiFi scan | AP `ESPFLY-0010_3C0F02E4D84D` on channel 6 |

**Same unit, live MicroPython pin check (before the flash):** I2C on
SDA 10 / SCL 9 confirmed (MPU-6050 answers at 0x68); **BMP280 ABSENT**
at 0x76 and 0x77 — wiring check pending; esp-drone ignores it, the
MicroPython `step4_baro` test cannot pass on this unit until it is
found. MPU INT on GPIO 13 = 100 edges/s. GPIO 6 (nSLEEP) held HIGH by
the module; GPIO 5 (nFAULT) readings consistent with an open-drain
output.

**Two units on the bench:** unit 2 (USB serial 3C:0F:02:E4:DD:18) still
runs the 2026-08-19 build (INT 7, LEDs 11/12/13); its snapshot is PR #4
(`unit2/board-snapshot`). Identify a board by its USB serial (`ioreg`),
never by `/dev/cu.*` port number — the numbers change with plug order.

## Session 6 — 2026-09-12 — Controls dead: inverted IMU → tumble kill

**Trigger:** Unit 1 on the Session 5 build boots clean, the AP is up,
the app connects — but under app control the motors spin for a split
second and stop. Every attempt ends the same way and the console says
nothing.

**Root cause (verified in source and on the bench):** the GY-521 on
unit 1 is mounted upside down (header on the drone's right side, chips
underneath), so the MPU-6050 reports acc.z = -1 g at rest. The tumble
detector in `sitaw.c:118-147` counts samples with acc.z <= -0.5 g once
the motor ratio sum exceeds 1000; 30 consecutive samples at 1 kHz
(30 ms) declares a tumble and calls `stabilizerSetEmergencyStop()`
(`stabilizer.c:59,307-310`). The stop is a latch: motors go to zero,
no log line, cleared only by a reboot or by writing param
`stabilizer.stop` = 0. A 7-minute passive console capture on unit 1
showed zero `rst:` lines — not a brownout, not a reset.

**Kill path:**

```
 GY-521 mounted upside down (unit 1: header on the right, chips underneath)
      |
      v
 MPU-6050 raw: acc.z = -1 g at rest
      |
      v
 sensors_mpu6050_hm5883L_ms5611.c  processAccGyroMeasurements()  (~387-405)
      |                                ^
      |                                +-- FIX lands here: CONFIG_IMU_MOUNT_INVERTED_Y
      |                                    negates acc/gyro x and z after the
      |                                    register swap -> acc.z = +1 g
      v
 sensorData.acc.z = -1.0                              (unfixed build)
      |
      v
 stabilizerTask, 1 kHz  ---->  sitaw.c:118-147 tumble detector
                                     |
                       motor ratio sum > 1000 ?    (throttle applied)
                                     | yes
                                     v
                       acc.z <= -0.5 g for 30 samples (30 ms)
                                     | yes
                                     v
                       stabilizerSetEmergencyStop()   stabilizer.c:59,307-310
                                     |
                                     v
                       emergency-stop LATCH -> motors = 0
                       no log line; cleared only by reboot
                       or param stabilizer.stop = 0
```

**Fix (vendor `986bcf9` + `a4a6801` + `3540dbd`; patch v4 =
`git diff db0f656..3540dbd`, 11 files, reverse-apply checked):**

- `main/Kconfig.projbuild`: `choice IMU_MOUNT` — `IMU_MOUNT_UPRIGHT`
  (default) / `IMU_MOUNT_INVERTED_X` / `IMU_MOUNT_INVERTED_Y` — plus
  `ATTITUDE_BENCH_PRINT` (default n).
- `sensors_mpu6050_hm5883L_ms5611.c` (~lines 387-405): after the
  existing register swap, negate the body-frame axes for the chosen
  mount — INVERTED_X: gyro/acc y and z; INVERTED_Y: gyro/acc x and z
  (a 180° body rotation about the roll or the pitch axis) — before the
  LPF and align-to-gravity steps.
- `stabilizer.c`: under `CONFIG_ATTITUDE_BENCH_PRINT`, a 1 Hz
  `BENCH acc.z=… roll=… pitch=… yaw=…` line on the USB console.
- `espdrone-overrides.sdkconfig` / `sdkconfig.defaults.esp32s3`: unit 1
  = `CONFIG_IMU_MOUNT_INVERTED_Y=y`; `CONFIG_ATTITUDE_BENCH_PRINT=n`
  (flight build, `3540dbd`; the bench runs below were built with `=y`).

**Bench (unit 1, USB, props off, `passive_read4.py` console capture):**

| Build | Level | Nose down | Right side down | Verdict |
|---|---|---|---|---|
| INVERTED_X (`42955c4`) | acc.z +1.00 | pitch **+32.8** | roll **-42 … -21** | acc.z fixed, both horizontal signs reversed → wrong axis |
| INVERTED_Y (`a4a6801`) | acc.z 0.99, roll +5.5, pitch +4.4 | pitch **-26.9** | roll **+34 … +36** | matches the firmware convention |

Reference sign convention, verified in source: nose down ⇒ pitch
NEGATIVE (`sensfusion6.c:273-274`; `kalman_core.c:1051-1059` legacy
negation; `controller_pid.c:109` uses `-gyro.y`;
`power_distribution_stock.c:88-94` adds +pitch on M1/M4 = the front
motors); right side down ⇒ roll POSITIVE. The geometry guess from the
header position was wrong twice — only the bench print settled it.

Throttle hold, 5 s, INVERTED_Y build: all four motors ran and held, no
kill.

**Plan of execution:**

1. [x] Trace the kill from the symptom: `sitaw.c` tumble detector →
       `stabilizerSetEmergencyStop()` latch; 7-min capture with zero
       resets rules out brownout.
2. [x] Vendor `986bcf9`: Kconfig `choice IMU_MOUNT` +
       `ATTITUDE_BENCH_PRINT`; body-frame negations in the MPU-6050
       driver; 1 Hz BENCH line in `stabilizer.c`.
3. [x] Vendor `42955c4`: build + flash INVERTED_X; bench print: acc.z
       ok, pitch and roll reversed → superseded.
4. [x] Vendor `a4a6801`: build + flash INVERTED_Y; bench print signs
       match the reference convention; 5 s throttle hold, all four
       motors.
5. [x] Track it in this repo (PR #3): patch v4 (11 files, reverse-apply
       checked), `espdrone-overrides.sdkconfig` re-synced with the IMU
       block, `patches/README.md` commit list, CLAUDE.md learnings.
6. [x] Flight build: `CONFIG_ATTITUDE_BENCH_PRINT=n` in both
       `esp-drone/sdkconfig.defaults.esp32s3` and
       `espdrone-overrides.sdkconfig`, clean rebuild done (vendor
       `3540dbd`). **Built, NOT yet flashed** — unit 1 still runs the
       `a4a6801` bench build. To flash:
       `cd esp-drone && idf.py -p /dev/cu.usbmodem<unit-1 port> flash`,
       then replug USB (the chip parks in download mode after the
       flash) and confirm no `BENCH` lines in a passive capture.
7. [ ] BMP280 still absent on unit 1 (Session 5) — wiring check.
8. [ ] Boot log claims GPIO 34 for the flow-deck CS0 default — harmless
       (nothing wired there); pin it off in Kconfig if it ever matters.
9. [ ] Unit 3 discovery is staged only in the job tmp dir (firmware sha
       `8c6039d4…`, `portmap.py`, `u3_*.py`) — copy somewhere durable
       before the tmp dir is cleaned.
