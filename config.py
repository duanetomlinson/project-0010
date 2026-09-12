"""
config.py -- ESP-FLY sensor bring-up
Single source of truth for pins and addresses.
Change things HERE, not in the individual test files.

Board: Waveshare ESP32-S3-Zero (ESP32-S3FH4R2, 4MB flash / 2MB PSRAM)

As-built pin map (user-confirmed 2026-09-11):
    GPIO1  M1 front-right PWM      GPIO5  ULT / nFAULT (both DRV8833)
    GPIO2  M2 rear-right  PWM      GPIO6  EEP / nSLEEP (both DRV8833)
    GPIO3  M4 front-left  PWM      GPIO9  I2C SCL
    GPIO4  M3 rear-left   PWM      GPIO10 I2C SDA
    GPIO13 MPU-6050 INT            GPIO21 WS2812 status LED (onboard)
"""

# ---- I2C bus ----
# On the S3 these are software-assigned, not fixed.
# Verified by pull-up sweep + scan 2026-08-16: sensors are physically
# wired SDA->GPIO10, SCL->GPIO9 (not 8/9 as originally planned).
I2C_SDA = 10
I2C_SCL = 9
I2C_FREQ = 400_000          # drop to 100_000 if the bus is flaky
I2C_ID   = 0                # hardware I2C peripheral 0

# ---- Device addresses ----
MPU6050_ADDR = 0x68         # 0x69 if AD0 is tied high
BMP280_ADDR  = 0x76         # 0x77 if SDO is tied high

# ---- Onboard status LED ----
# S3-Zero has a WS2812 RGB LED on GPIO 21 -- the only LED on the board.
# status_led.py drives it (boot / ok / fault / motor_test).
# Set LED_PIN to None to disable every LED call.
LED_PIN = 21
LED_IS_NEOPIXEL = True      # WS2812 -- must be True on this board

# ---- Motor drive: 2x DRV8833 modules, one IN pin per motor ----
# Each motor's second input (IN2/IN4) is jumpered to GND on the module,
# so one GPIO per motor: PWM high = drive, low = coast (fast decay).
# Direction is fixed by wiring -- verified per-motor before assembly.
# VERIFIED by per-pin isolation runs 2026-08-19 (drive one GPIO alone,
# watch which corner spins). The left side is SWAPPED vs the original
# wiring notes: GPIO3 is FRONT-left, GPIO4 is REAR-left.
#   DRV8833 #1 (right): GPIO1 -> front-right (CCW), GPIO2 -> rear-right (CW)
#   DRV8833 #2 (left):  GPIO3 -> front-left  (CW),  GPIO4 -> rear-left  (CCW)
# GPIO 3 is a strapping pin (JTAG source select) -- harmless here: only
# sampled at reset, only meaningful if the JTAG_SEL eFuse is burned
# (it isn't), and the DRV8833 input pulldown keeps it defined at boot.
MOTOR_FR = 1                # spins CCW
MOTOR_RR = 2                # spins CW
MOTOR_FL = 3                # spins CW
MOTOR_RL = 4                # spins CCW

# ULT (nFAULT) -- one wire Y-spliced to both modules. Open-drain,
# active LOW (overcurrent / overtemp / undervoltage). Read as an input
# with the ESP32's internal pull-up; HIGH = healthy.
# As-built map (2026-09-11) puts this on GPIO 5, not 6 as first recorded.
# HYPOTHESIS, to confirm on the bench: this explains the 2026-08-19
# measurement of "GPIO5 externally held HIGH" -- a healthy nFAULT line
# with the module's own pull-up to VCC reads HIGH at rest, and GPIO5
# was then labelled EEP. Confirm by tracing both wires at the modules.
MOTOR_FAULT = 5

# EEP (nSLEEP) -- one wire Y-spliced to both modules. HIGH = awake.
# As-built map (2026-09-11) puts this on GPIO 6, not 5 as first recorded.
# Until the swap above is confirmed on the bench, do NOT drive this pin
# as an output by default: if the line turns out to be tied to VCC,
# forcing it low stresses the ESP32 pin and can dip the rail into UVLO
# (seen 2026-08-19 as a phantom nFAULT).
MOTOR_SLEEP = 6
MOTOR_SLEEP_DRIVE = False   # opt-in: True = step6 drives EEP HIGH to wake,
                            # releases it to input on exit. Leave False until
                            # the bench confirms GPIO6 really is nSLEEP.

# PWM: LEDC hardware, one channel per motor. 20 kHz is above audible
# whine and well within the DRV8833's switching range.
MOTOR_PWM_FREQ = 20_000

# ---- MPU6050 data-ready interrupt ----
# GY-521 INT pin wired to GPIO 13 (as-built map 2026-09-11; earlier
# bring-up used GPIO 7). Required by ESP-Drone: its sensor task blocks
# until the INT rising-edge ISR fires. Unused by the MicroPython test
# steps (they poll over I2C).
MPU_INT = 13

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
# 24 GPIOs are broken out. Current pin map: motors 1-4, ULT 5, EEP 6,
# I2C on 9/10, MPU INT 13. GPIO 3 caveat is at the motor section above.
