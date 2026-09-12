# esp-drone vendor patch

`esp-drone/` is a git-ignored checkout of
[espressif/esp-drone](https://github.com/espressif/esp-drone) at commit
`db0f656`. Our source changes to it live in `esp-drone-espfly.patch`;
our Kconfig values live in `../espdrone-overrides.sdkconfig`. Locally the
checkout also carries branch `espfly-0010` (commits `491309e` build fixes,
`2fe79cf` pin map + WS2812) with the same changes committed; the patch is
`git diff db0f656` of that branch, esp-now vendor copy excluded.

What the patch contains:

- `components/drivers/general/led/`: WS2812 status-LED backend
  (`led_esp32.c` over the IDF v5.0 RMT TX driver, plus
  `led_strip_encoder.c/.h` from the IDF `rmt/led_strip` example).
- `main/Kconfig.projbuild`: new `LED_PIN_WS2812` symbol (default 21).
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
