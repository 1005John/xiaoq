# XiaoQ ESP32 Wi-Fi Voice Remote Design

## Purpose

This component is a wireless push-to-talk satellite for XiaoQ. Holding the
ESP32-S3 BOOT key captures microphone audio; releasing it sends the recording
to XiaoQ. The answer is played through the ESP32's I2S speaker, not through
XiaoQ's local speaker.

## Hardware

| Function | Device | Pins |
| --- | --- | --- |
| Push to talk | BOOT key | GPIO0, active low |
| Status LED | On-board RGB | GPIO48 |
| Audio input | INMP441 | BCLK=4, WS=5, DATA=6 |
| Audio output | I2S amplifier | DIN=7, BCLK=15, LRCLK=16 |

The ESP32-S3 must have a stable 5 V, 1 A or greater supply. The I2S amplifier
and ESP32 share ground. USB power that is sufficient for idle Wi-Fi can still
brown out during audio transfer or speaker output.

## Request Flow

```text
BOOT held
  -> RGB blue, INMP441 records 16 kHz / 32-bit mono PCM
BOOT released
  -> WAV upload to POST /api/voice
  -> X-XiaoQ-Reply-Channel: esp32
  -> MiMo ASR, XiaoQ text response with speak=false
  -> MiMo TTS emits 24 kHz PCM
  -> gateway resamples to 16 kHz / 16-bit mono PCM
  -> ESP32 waits for completed + audio_ready=true
  -> GET /api/voice/{job_id}/audio
  -> ESP32 expands mono to stereo I2S and plays it
```

The `audio_ready` gate is required. XiaoQ writes the text reply before the
gateway's TTS worker finishes, so treating `completed` alone as downloadable
would race the audio file and produce a 404 response.

## LED States

| Condition | RGB state |
| --- | --- |
| Wi-Fi disconnected | Off |
| Connected to configured Wi-Fi | Green |
| BOOT held | Blue |

The button state has priority over the network state. On release, the LED
returns to green if Wi-Fi remains connected, otherwise off.

## Resilience

- Button changes are debounced for 35 ms.
- Recording, upload, reply polling, and playback run in a FreeRTOS task so
  button and LED handling remain responsive.
- Reply PCM is downloaded completely into PSRAM before I2S playback. Wi-Fi is
  paused during playback to reduce peak current on compact USB-powered boards.
- The firmware reports authenticated playback stages to the gateway's
  `/api/esp32/debug` endpoint for LAN diagnostics.
- Wi-Fi automatically reconnects after playback or a dropped connection.

## Security

The ESP32 stores the mobile-control token in NVS and sends it as
`X-XiaoQ-Token`. Wi-Fi credentials and the token belong in `secrets.h`, which
is intentionally ignored by Git. `secrets.example.h` documents the required
configuration without real values.
