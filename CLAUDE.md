# ESP-FLY (project-0010)

MicroPython bring-up for the ESP-FLY drone: Waveshare ESP32-S3-Zero,
MPU-6050 + BMP280 sensors, 2x DRV8833 motor drivers. `config.py` is the
single source of truth for pins; `PLAN.md` is the plan log and wiring
decision record; tests are `stepN_*.py`, run via `import stepN_...`.

## Learnings

### 2026-08-18 · Motors DO spin on USB — the star's VCC is fed from the board 5V rail, not battery-only · Claude Fable 5, session 01EBGTBFkoL9KmkfpZZXKsc1

**What I did:** Ran step6_motors as a "safe dry run" claiming motors could not spin on USB because motor VCC comes from the battery star.
**What went wrong:** All four motors actually spun — the star point is also fed by the board's 5V rail, so USB power drives the DRV8833s.
**Root cause:** Inferred power topology from the wiring note "VCC = battery + at the star" instead of verifying whether the star connects to the board's 5V pin.
**Rule to follow:** Treat every motor-test invocation as live — props off, area clear — regardless of power source; verify power topology at the star before claiming anything is unpowered.
**Where it applies:** `step6_motors.py`, any future motor/ESC test, and all power-rail reasoning in this repo.
