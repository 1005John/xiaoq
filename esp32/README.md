# XiaoQ ESP32 Components

## Production firmware

Use [`xiaoq_audio_ptt`](xiaoq_audio_ptt/) for the tested push-to-talk voice
remote. Hold the ESP32-S3 BOOT button to record from the INMP441, release it
to upload the WAV to XiaoQ, and play the MiMo TTS reply through the connected
I2S speaker amplifier.

The production firmware is already part of the repository history in commit
`86da750` (`feat: add ESP32 Wi-Fi voice remote`).

## Hardware mapping

| Function | GPIO |
| --- | ---: |
| INMP441 BCLK/SCK | 4 |
| INMP441 WS/LRCLK | 5 |
| INMP441 SD | 6 |
| I2S amplifier DIN | 7 |
| I2S amplifier BCLK | 15 |
| I2S amplifier LRCLK | 16 |
| BOOT button | 0 |
| On-board RGB data | 48 |

INMP441 is a microphone only. It cannot play audio. Playback requires an I2S
amplifier and speaker connected to GPIO 7/15/16.

## Verification firmware

[`xiaoq_audio_io`](xiaoq_audio_io/) is a standalone hardware check. It reads
INMP441 levels and plays a short I2S speaker chime, without Wi-Fi or XiaoQ
authentication. Run it before flashing the production firmware when debugging
wiring, power, or the speaker amplifier.

The other sketches under this directory are narrow LED/BOOT diagnostics and
are not required for normal operation.

## Power and recovery

- Use a stable 5 V supply rated for at least 1 A.
- Keep the ESP32, INMP441, amplifier, and speaker grounds common.
- Do not hold BOOT while pressing reset after flashing; GPIO0 is also the
  download-mode strap.
- Store Wi-Fi credentials and the XiaoQ token in a local `secrets.h`; never
  commit that file.
