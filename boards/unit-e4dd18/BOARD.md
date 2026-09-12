# ESP-FLY unit `e4dd18` — firmware snapshot, captured 2026-09-11

Second ESP-FLY drone unit. Captured **read-only** from the live board:
nothing was written to it. Unit 1 (serial `3C:0F:02:E4:D8:4C`,
`/dev/cu.usbmodem101`) was being flashed at the same time and its port was
never opened.

## Identity

| Field | Value | Source |
|---|---|---|
| USB serial | `3C:0F:02:E4:DD:18` (unit id = last 6 hex, `e4dd18`) | `ioreg -p IOUSB -l -w0` → "USB Serial Number" |
| USB VID:PID | `0x303a:0x1001` (12346:4097) "USB JTAG/serial debug unit" | ioreg `idVendor` / `idProduct` |
| Port at capture | `/dev/cu.usbmodem2101` | ioreg IOService plane: `IOCalloutDevice` under the device with this serial |
| STA MAC | `3c:0f:02:e4:dd:18` | boot log `espnow: mac:` |
| SoftAP MAC / SSID | `3c:0f:02:e4:dd:19` / `ESPFLY-0010_3C0F02E4DD19` (pw `12345678`, UDP 2390) | boot log `wifi:mode : softAP`; SSID also seen in a Mac WiFi scan |
| Chip | ESP32-S3 rev v0.2, ROM `esp32s3-20210327` | boot log |

## Firmware (from the boot log)

| Field | Value |
|---|---|
| Project name | `ESPDrone` |
| App version | `db0f656-dirty` (espressif/esp-drone `db0f656` + local changes) |
| Compile time | `Aug 19 2026 01:25:04` |
| ESP-IDF | `d9f9b7d` (release/v5.0) |
| ELF SHA256 (prefix) | `09b3cb2db5d30d1b...` |
| Bootloader | ESP-IDF `d9f9b7d` 2nd stage, compile time `00:51:03` |
| Flash mode | QIO, 80 MHz; image header says 2 MB (chip is 4 MB) |
| Partition table | `nvs` 0x9000/0x6000, `phy_init` 0xF000/0x1000, `factory` 0x10000/0x100000 |
| Self test | `selftestPassed = 1`; MPU6050 [OK]; VL53L1X / PMW3901 [FAIL] (not fitted, expected) |

Full log: `boot-log.txt` (captured over USB-Serial/JTAG at 115200; opening
the port triggers the bridge's `USB_UART_CHIP_RESET`, so the log starts at
a normal `SPI_FAST_FLASH_BOOT`).

## Source reconstruction

- Vendor source: espressif/esp-drone at `db0f656`, plus the 2026-08-19
  "build fixes" set: `adc_esp32.c` battery ADC channel → `ADC_CHANNEL_7`
  (GPIO 8), esp-now `2.1.1` vendored (2.5.x needs FreeRTOS symbols IDF
  v5.0 lacks), console on USB-Serial/JTAG. See `patches/README.md` on
  branch `pins/esp-drone-map`.
- Kconfig overrides: `espdrone-overrides.as-flashed.sdkconfig` in this
  directory is the repo file at commit **`5a74531`**, verbatim. Why that
  commit: the compile time (01:25:04) falls between `9483f6a` (00:55) and
  `5a74531` (01:37), and the only difference between the two is
  `LED_PIN_RED 8→13` + `ADC1_PIN=8` — the boot log claims `GPIO[13]` as an
  LED output, which only `5a74531` sets.
- **Not in this unit:** the WS2812 status-LED change and MPU INT on 13
  (commit `8237b4e`, branch `pins/esp-drone-map`). This unit still has the
  three discrete-LED pins and INT on GPIO 7.

## Pin map: this unit (as flashed) vs unit 1 (current repo map)

Unit 1 column = `espdrone-overrides.sdkconfig` at `8237b4e` / `config.py`
on `pins/as-built-map`. This table is the reference example of how pins
vary between hand-wired units.

| CONFIG_* | Unit 2 `e4dd18` (as flashed) | Unit 1 (current) | Same? |
|---|---|---|---|
| `MOTOR01_PIN` (M1 front-right) | 1 | 1 | same |
| `MOTOR02_PIN` (M2 rear-right) | 2 | 2 | same |
| `MOTOR03_PIN` (M3 rear-left) | 4 | 4 | same |
| `MOTOR04_PIN` (M4 front-left) | 3 | 3 | same |
| `I2C0_PIN_SDA` | 10 | 10 | same |
| `I2C0_PIN_SCL` | 9 | 9 | same |
| `MPU_PIN_INT` | **7** | **13** | differs |
| `LED_PIN_BLUE` | **11** (discrete, nothing wired) | **21** (WS2812) | differs |
| `LED_PIN_GREEN` | **12** (discrete, nothing wired) | **21** (WS2812) | differs |
| `LED_PIN_RED` | **13** (discrete, nothing wired) | **21** (WS2812) | differs |
| `LED_PIN_WS2812` | — (not in this build) | 21 | missing on unit 2 |
| `ADC1_PIN` (battery, unwired) | 8 | 8 | same |
| `WIFI_BASE_SSID` | `ESPFLY-0010` | `ESPFLY-0010` | same |

Boot-log evidence for the unit 2 column: `gpio: GPIO[11]/[13]/[12] OutputEn: 1`
(LEDs) and `gpio: GPIO[7] InputEn: 1 Pullup: 1 Intr:1` (MPU INT).

## Flash dump

| Field | Value |
|---|---|
| `flash-4MB.bin` sha256 | PENDING — dump not yet taken (see below) |
| `flash-4MB.bin.gz` sha256 | PENDING |
| `image_info` of the factory app | PENDING |

The dump was blocked by the agent permission classifier in the capture
session. To take it by hand (this resets the board into download mode;
replug unit 2 afterwards):

```sh
. ~/esp/esp-idf-v5.0/export.sh
esptool.py -p /dev/cu.usbmodem2101 -b 460800 read_flash 0 0x400000 boards/unit-e4dd18/flash-4MB.bin
gzip -9 -k boards/unit-e4dd18/flash-4MB.bin      # commit only the .gz
shasum -a 256 boards/unit-e4dd18/flash-4MB.bin boards/unit-e4dd18/flash-4MB.bin.gz
dd if=boards/unit-e4dd18/flash-4MB.bin of=/tmp/pt.bin bs=1 skip=$((0x8000)) count=$((0xC00))
python ~/esp/esp-idf-v5.0/components/partition_table/gen_esp32part.py /tmp/pt.bin
dd if=boards/unit-e4dd18/flash-4MB.bin of=/tmp/app.bin bs=65536 skip=1 count=16   # factory @0x10000, 1 MB
esptool.py image_info --version 2 /tmp/app.bin
```

**Restore this exact firmware:** `esptool.py -p PORT write_flash 0 flash-4MB.bin`

## Files

| File | What |
|---|---|
| `BOARD.md` | this file |
| `boot-log.txt` | full boot log, ANSI stripped |
| `espdrone-overrides.as-flashed.sdkconfig` | Kconfig overrides at `5a74531`, verbatim |
| `flash-4MB.bin.gz` | (pending) gzip of the raw 4 MB dump |
