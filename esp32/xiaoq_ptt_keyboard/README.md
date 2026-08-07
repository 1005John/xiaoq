# XiaoQ ESP32-S3 PTT keyboard

This firmware makes the ESP32-S3 advertise as a BLE HID keyboard named
`XiaoQ-PTT`.

- Hold the board BOOT button (GPIO0): sends a held space key.
- Release BOOT: releases the space key.
- The board RGB LED is blue while BOOT is held and off after release.
- Do not hold BOOT while powering on or resetting; GPIO0 is the ESP32-S3
  download-mode strap pin.

Build with Arduino CLI:

```sh
arduino-cli compile --fqbn esp32:esp32:esp32s3 xiaoq_ptt_keyboard
arduino-cli upload -p /dev/cu.usbmodem13301 --fqbn esp32:esp32:esp32s3 xiaoq_ptt_keyboard
```
