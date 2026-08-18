# XiaoQ ESP32-S3 audio I/O test

This sketch verifies the board's I2S microphone and speaker amplifier paths
without Wi-Fi or XiaoQ authentication.

| Function | Signal | GPIO |
| --- | --- | --- |
| INMP441 microphone | SCK/BCLK | 4 |
| INMP441 microphone | WS/LRCLK | 5 |
| INMP441 microphone | SD | 6 |
| I2S speaker output | DIN | 7 |
| I2S speaker output | BCLK | 15 |
| I2S speaker output | LRCLK | 16 |

Build and upload:

```sh
arduino-cli compile --fqbn esp32:esp32:esp32s3:FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=enabled,CDCOnBoot=cdc xiaoq_audio_io
arduino-cli upload --fqbn esp32:esp32:esp32s3:FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=enabled,CDCOnBoot=cdc --port /dev/cu.usbmodem1101 xiaoq_audio_io
```

At 115200 baud, the firmware reports microphone average/peak levels twice per
second. Speak near the INMP441 and the numbers should rise. It plays a two-note
chime on startup; type `tone` followed by Enter to replay it.

The INMP441 is input-only. Hearing the chime proves the separate I2S amplifier
and speaker path on GPIO 7/15/16, not the microphone itself.
