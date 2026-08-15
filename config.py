"""
config.py -- ESP-FLY sensor bring-up
Single source of truth for pins and addresses.
Change things HERE, not in the individual test files.

Board: Waveshare ESP32-S3-Zero (ESP32-S3FH4R2, 4MB flash / 2MB PSRAM)
"""

# ---- I2C bus ----
# On the S3 these are software-assigned, not fixed.
# Chosen to match the eventual drone pin map (motors will take 4-7).
I2C_SDA = 8
I2C_SCL = 9
I2C_FREQ = 400_000          # drop to 100_000 if the bus is flaky
I2C_ID   = 0                # hardware I2C peripheral 0

# ---- Device addresses ----
MPU6050_ADDR = 0x68         # 0x69 if AD0 is tied high
BMP280_ADDR  = 0x76         # 0x77 if SDO is tied high

# ---- Onboard LED ----
# S3-Zero has a WS2812 RGB LED on GPIO 21 (confirmed in Waveshare docs).
# Set LED_PIN to None to skip the blink test entirely.
LED_PIN = 21
LED_IS_NEOPIXEL = True      # WS2812 -- must be True on this board

# ---- Sea-level pressure, for altitude math ----
# 1013.25 hPa is the standard default. For accurate absolute altitude,
# look up your local QNH. For *relative* altitude (what we care about
# tonight) the value doesn't matter -- only the change does.
SEA_LEVEL_HPA = 1013.25

# ---- Pins to avoid on the Waveshare ESP32-S3-Zero ----
# GPIO 0       BOOT button (also a strapping pin)
# GPIO 3,45,46 strapping pins
# GPIO 19,20   native USB D-/D+ -- this board has NO USB-UART chip
# GPIO 21      WS2812 RGB LED
# GPIO 26-32   internal SPI flash
# GPIO 33-37   NOT broken out on this board (reserved for octal PSRAM)
# GPIO 43,44   UART0 TX/RX (the TX/RX silkscreen pads)
#
# 24 GPIOs are broken out. 4-9 are all free and safe, so the drone
# pin map (motors 4-7, I2C 8-9) fits this board with nothing to change.
