# XiaoQ ESP32 Wi-Fi voice remote

This ESP32-S3 firmware records while BOOT (GPIO0) is held, sends the WAV
recording to XiaoQ over Wi-Fi, and plays the reply through an I2S speaker.

| Device | Signal | GPIO |
| --- | --- | --- |
| INMP441 | SCK/BCLK | 4 |
| INMP441 | WS/LRCLK | 5 |
| INMP441 | SD | 6 |
| I2S speaker amplifier | DIN | 7 |
| I2S speaker amplifier | BCLK | 15 |
| I2S speaker amplifier | LRCLK | 16 |
| On-board RGB | data | 48 |

The reply path is explicitly marked `esp32`: XiaoQ does not use its own
speaker. The mobile gateway resamples MiMo output to 16 kHz PCM, and the ESP32 downloads
and plays it as stereo I2S (the mono sample is copied to both channels). It waits for
`audio_ready=true`, rather than only `status=completed`, so it never races the TTS worker.

LED state is part of the interaction contract: it is off while Wi-Fi is unavailable,
solid green once the configured network is connected, and solid blue while BOOT is held.
Releasing BOOT returns it to green when connected.

Build with the board settings used by the 16 MB ESP32-S3-N16R8:

```sh
arduino-cli compile --fqbn esp32:esp32:esp32s3:FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=opi,USBMode=hwcdc,CDCOnBoot=cdc xiaoq_audio_ptt
arduino-cli upload --fqbn esp32:esp32:esp32s3:FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=opi,USBMode=hwcdc,CDCOnBoot=cdc --port /dev/cu.usbmodemXXXX xiaoq_audio_ptt
```

Copy `secrets.example.h` to `secrets.h`, set the Wi-Fi and XiaoQ host, then
store the mobile token once over the serial console:

```text
token <value-from-data/mobile_control_token>
status
```

After flashing, do not hold BOOT while resetting; GPIO0 is also the download
mode strap pin.

See [DESIGN.md](DESIGN.md) for the protocol, power requirement, and recovery behavior.
