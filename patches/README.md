# esp-drone vendor patch

`esp-drone/` is a git-ignored checkout of
[espressif/esp-drone](https://github.com/espressif/esp-drone) at commit
`db0f656`. Our source changes to it live in `esp-drone-espfly.patch`;
our Kconfig values live in `../espdrone-overrides.sdkconfig`. Locally the
checkout also carries branch `espfly-0010` with the same changes
committed; the patch is `git diff db0f656..3540dbd` of that branch
(11 files, esp-now vendor copy excluded). Commits on `espfly-0010`:

| Commit | Date | What |
|---|---|---|
| `491309e` | 2026-08-19 | build fixes: ADC channel, esp-now 2.1.1 vendored |
| `2fe79cf` | 2026-09-11 | pin map + first WS2812 backend |
| `032d336` | 2026-09-11 | LED task fix (`ws2812Task` owns RMT) |
| `986bcf9` | 2026-09-12 | Kconfig `choice IMU_MOUNT` + `ATTITUDE_BENCH_PRINT`, body-frame negations |
| `42955c4` | 2026-09-12 | unit 1 default `IMU_MOUNT_INVERTED_X` (superseded: pitch/roll reversed on the bench) |
| `a4a6801` | 2026-09-12 | unit 1 default `IMU_MOUNT_INVERTED_Y`, bench-verified (PLAN.md Session 6) |
| `3540dbd` | 2026-09-12 | flight build: `ATTITUDE_BENCH_PRINT=n` (built, not yet flashed) |

What the patch contains:

- `components/drivers/general/led/`: WS2812 status-LED backend
  (`led_esp32.c` over the IDF v5.0 RMT TX driver — setters write
  `state[]` and notify a `ws2812Task` that owns every RMT call — plus
  `led_strip_encoder.c/.h` from the IDF `rmt/led_strip` example).
- `main/Kconfig.projbuild`: new `LED_PIN_WS2812` symbol (default 21);
  `choice IMU_MOUNT` (`IMU_MOUNT_UPRIGHT` / `_INVERTED_X` / `_INVERTED_Y`)
  and `ATTITUDE_BENCH_PRINT` (default n).
- `components/core/crazyflie/hal/src/sensors_mpu6050_hm5883L_ms5611.c`:
  body-frame negations after the register swap for an upside-down IMU
  (INVERTED_X negates y,z; INVERTED_Y negates x,z) so acc.z reads +1 g
  at rest and the `sitaw.c` tumble detector stays quiet.
- `components/core/crazyflie/modules/src/stabilizer.c`: under
  `CONFIG_ATTITUDE_BENCH_PRINT`, a 1 Hz `BENCH acc.z=.. roll=.. pitch=..
  yaw=..` console line for checking the mount on the bench.
- `components/drivers/general/adc/adc_esp32.c`: battery ADC channel
  `ADC_CHANNEL_1` (GPIO 2, a motor pin) -> `ADC_CHANNEL_7` (GPIO 8).
- `components/drivers/general/wifi/idf_component.yml` and
  `components/core/crazyflie/idf_component.yml`: esp-now pinned to the
  vendored 2.1.1 copy via `override_path` (2.5.x needs FreeRTOS symbols
  IDF v5.0 lacks).
- `sdkconfig.defaults.esp32s3`: the appended ESP-FLY block (identical to
  `../espdrone-overrides.sdkconfig`).

## Re-apply from a fresh clone

```sh
git clone https://github.com/espressif/esp-drone.git esp-drone
git -C esp-drone checkout db0f656
git -C esp-drone apply ../patches/esp-drone-espfly.patch

# esp-now 2.1.1 is vendored, not patched: put a copy of
# espressif/esp-now tag v2.1.1 at esp-drone/components/espressif__esp-now
# (from the IDF component registry or a local copy), then add the
# fallback CONFIG_ESP_CONSOLE_UART_BAUDRATE define in its espnow_console.c
# (see the note in ../espdrone-overrides.sdkconfig).

# If the patch did not carry the sdkconfig block for some reason:
#   cat espdrone-overrides.sdkconfig >> esp-drone/sdkconfig.defaults.esp32s3

. ~/esp/esp-idf-v5.0/export.sh
cd esp-drone && rm -f sdkconfig && idf.py set-target esp32s3 && idf.py build
```

Regenerate the patch after editing the vendor tree:

```sh
git -C esp-drone diff db0f656 -- . ':!components/espressif__esp-now' > patches/esp-drone-espfly.patch
```
