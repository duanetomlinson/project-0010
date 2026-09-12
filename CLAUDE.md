# ESP-FLY (project-0010)

MicroPython bring-up for the ESP-FLY drone: Waveshare ESP32-S3-Zero,
MPU-6050 + BMP280 sensors, 2x DRV8833 motor drivers. `config.py` is the
single source of truth for pins; `PLAN.md` is the plan log and wiring
decision record; tests are `stepN_*.py`, run via `import stepN_...`.

## Learnings

### 2026-09-11 · LED backend stack overflow: an IDF driver that can ESP_LOGE must not run on a 2 KB ESP-Drone task · Claude Fable 5.1, session 01Qtp5KGh6v7qYUdaPuvsaBS

**What I did:** Wrote the first WS2812 backend so `ledSet` called `rmt_tx_wait_all_done(chan, 0)` + `rmt_transmit` inline, reasoning "zero timeout = non-blocking = safe from any caller".
**What went wrong:** Unit 1 rebooted every 10.5 s with `stack overflow in task LEDSEQCMD`. ledseq's back-to-back `ledSet` calls at `systemStart` hit the zero-timeout failure path in IDF v5.0 (`rmt_tx.c:540`), which drops the frame and runs `ESP_LOGE("flush timeout")` — vprintf on a 2048 B stack (`config.h:152`, ~1332 B free at idle).
**Root cause:** "Non-blocking" says nothing about stack. ESP-Drone's ledseq/system tasks are sized for GPIO writes; any IDF driver call that can log is an order of magnitude heavier.
**Rule to follow:** Peripheral work goes on its own task: setters write state + `xTaskNotifyGive`; a dedicated task (3 KB+) owns every driver call and blocks properly. Never call an IDF driver that can `ESP_LOGE` from a 2 KB ESP-Drone task or a timer callback.
**Where it applies:** `patches/esp-drone-espfly.patch` (`led_esp32.c`), any future esp-drone driver backend (buzzer, extra sensors), anything reachable from `ledseq.c` / `cfassert.c`.

### 2026-09-11 · Passive serial on the S3-Zero: open the USB-JTAG port with DTR/RTS asserted, plan the replug, identify boards by USB serial · Claude Fable 5.1, session 01Qtp5KGh6v7qYUdaPuvsaBS

**What I did:** Tried to watch the app boot by opening the USB-JTAG port with DTR low and, separately, with `idf.py monitor`; picked the board by `/dev/cu.usbmodem*` number with two units plugged in.
**What went wrong:** The DTR-low open and `idf.py monitor` both reset the chip, so the capture showed the reset I caused, not the app; after `idf.py flash` the chip was already parked in download mode; and the port number did not say which unit I was on.
**Root cause:** USB-Serial/JTAG turns DTR/RTS into reset/boot strapping, so a monitor attach is a reset. Port numbers are enumeration order, not identity.
**Rule to follow:** For a passive capture open the port with DTR and RTS asserted (no reset pulse). After `idf.py flash` expect download mode and replug USB before reading anything. Map port to board via the USB serial number in `ioreg` (unit 1 = `3C:0F:02:E4:D8:4C`, unit 2 = `3C:0F:02:E4:DD:18`), never by port number.
**Where it applies:** every flash / monitor / capture on either S3-Zero, `esp-drone/` boot verification, PLAN.md flash records.

### 2026-09-11 · The `esp-fly-custom-tw` fork is Seeed's XIAO firmware, not our port; and unit 1 has no BMP280 on the bus · Claude Fable 5.1, session 01Qtp5KGh6v7qYUdaPuvsaBS

**What I did:** Treated the GitHub fork `esp-fly-custom-tw` as the ESP-FLY firmware source and started reading its pin map as ours; assumed the BMP280 from the parts list.
**What went wrong:** The fork is byte-identical to Seeed's XIAO ESP32-S3 esp-drone firmware (0 commits ahead). Its I2C pins 5/6 are our DRV8833 nFAULT/nSLEEP lines, so building it would drive the motor-driver control pins as an I2C bus. Separately, the live scan on unit 1 found only the MPU-6050 (0x68) — no BMP280 at 0x76 or 0x77.
**Root cause:** A fork carrying the project's name was taken as our code without checking commits-ahead against its upstream; a part's presence was inferred from the BOM instead of the bus.
**Rule to follow:** The real port is the nested `esp-drone/` checkout on branch `espfly-0010`, reproducible from `patches/` + `espdrone-overrides.sdkconfig`; ignore `esp-fly-custom-tw`. Before trusting a repo, check `git log upstream..HEAD`. Treat the BMP280 as absent on unit 1 until a wiring check finds it.
**Where it applies:** any "which firmware" question, `patches/README.md`, `step2_scan.py` / `step4_baro.py` expectations on unit 1.

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
