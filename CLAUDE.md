# ESP-FLY (project-0010)

MicroPython bring-up for the ESP-FLY drone: Waveshare ESP32-S3-Zero,
MPU-6050 + BMP280 sensors, 2x DRV8833 motor drivers. `config.py` is the
single source of truth for pins; `PLAN.md` is the plan log and wiring
decision record; tests are `stepN_*.py`, run via `import stepN_...`.

## Learnings

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
