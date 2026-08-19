# ESP-FLY (project-0010)

MicroPython bring-up for the ESP-FLY drone: Waveshare ESP32-S3-Zero,
MPU-6050 + BMP280 sensors, 2x DRV8833 motor drivers. `config.py` is the
single source of truth for pins; `PLAN.md` is the plan log and wiring
decision record; tests are `stepN_*.py`, run via `import stepN_...`.

## Learnings

### 2026-08-19 · ESP-Drone flash gotchas: dependency drift, LED pin collisions, I2C lockup, fake software resets · Claude Fable 5, session 01EBGTBFkoL9KmkfpZZXKsc1

**What I did:** Flashed esp-drone on IDF v5.0 assuming stock defaults + our pin overrides were the whole configuration surface.
**What went wrong:** Five separate traps: (1) `espressif/esp-now: "*"` resolved to 2.5.3, which needs FreeRTOS symbols IDF v5.0 lacks; (2) the target's default status-LED pins (7/9/8) silently collide with our MPU INT and I2C SCL; (3) every esptool/monitor software reset over USB-Serial/JTAG parked the S3 in DOWNLOAD mode, so "no AP" really meant "app never ran"; (4) a button reset mid-I2C left the MPU6050 holding the bus — only a USB power cycle clears it; (5) the battery ADC defaults to GPIO2 (and adc_esp32.c hardcodes the channel) — analog mode silently disconnects that motor's PWM, with nothing in the boot log.
**Root cause:** Unpinned registry dependencies and per-target pin defaults are invisible until a build/boot log is read line by line; USB-JTAG DTR/RTS reset emulation is not a normal reset.
**Rule to follow:** After flashing this board, verify boot via serial log (USB console), not via absence/presence of WiFi; on sensor FAIL, power-cycle USB before debugging; when a boot log shows `gpio:` claims, check every claimed pin against config.py's map.
**Where it applies:** esp-drone/ builds, espdrone-overrides.sdkconfig, any future ESP-IDF firmware on the S3-Zero.

### 2026-08-19 · Verify each motor corner by single-pin isolation — wiring notes lie, and dirty pin state ruins the test · Claude Fable 5, session 01EBGTBFkoL9KmkfpZZXKsc1

**What I did:** Trusted the user's detailed wiring notes for the GPIO→corner map, and ran motor tests with scaffolding that held multiple PWM channels and drove EEP/read nFAULT every run.
**What went wrong:** The left-side corners were swapped in the notes (GPIO3 is front-left, not rear-left), and the scaffolding produced "all four motors spin from one pin" — masking the real behavior; EEP (GPIO5) also turned out to be hardware-held high, so driving it low stressed the pin and caused a phantom nFAULT via rail dip.
**Root cause:** Isolation tests weren't isolated — extra driven pins and stale assumptions about EEP changed the system under test.
**Rule to follow:** To identify a motor channel, release every related pin to a plain input and PWM exactly one pin at a time; and never drive a line as an output before measuring what the hardware does with it at rest (input + pull, both directions).
**Where it applies:** `step6_motors.py`, `config.py` motor map, all future motor/ESC bring-up in this repo.

### 2026-08-18 · Motors DO spin on USB — the star's VCC is fed from the board 5V rail, not battery-only · Claude Fable 5, session 01EBGTBFkoL9KmkfpZZXKsc1

**What I did:** Ran step6_motors as a "safe dry run" claiming motors could not spin on USB because motor VCC comes from the battery star.
**What went wrong:** All four motors actually spun — the star point is also fed by the board's 5V rail, so USB power drives the DRV8833s.
**Root cause:** Inferred power topology from the wiring note "VCC = battery + at the star" instead of verifying whether the star connects to the board's 5V pin.
**Rule to follow:** Treat every motor-test invocation as live — props off, area clear — regardless of power source; verify power topology at the star before claiming anything is unpowered.
**Where it applies:** `step6_motors.py`, any future motor/ESC test, and all power-rail reasoning in this repo.
