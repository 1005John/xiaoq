# XiaoQ Face Authorization Demo - Design

> Version: 2.0.0-demo | Updated: 2026-08-29

## Purpose

This project is the deployable XiaoQ demonstration build. It combines the
desktop robot runtime, Hailo-powered face registration and tracking, mobile
control, MiMo speech/vision services, ESP32 peripherals, and office-oriented
skills in one isolated deployment.

The demo uses its own runtime directory (`/home/johnf/xiaoq-face-auth-demo`)
and its own systemd units. It must not run alongside the production XiaoQ
runtime because both use the same camera, display, audio devices, and gimbal.

## Runtime Architecture

```text
Mobile App / ESP32 voice remote
             |
             v
mobile_control.py :8788
             |
             v
robot_face_v11_fc245e4.py
  |-- Pygame renderer and expression state machines
  |-- MiMo ASR -> semantic skill router / MiMo chat -> streaming MiMo TTS
  |-- Hermes skill execution for multi-step office tasks
  |-- Hailo SCRFD + ArcFace registration, recognition, and tracking
  |-- GimbalController -> serial Pan/Tilt servos
  |-- shared camera frame -> visual Q&A, gesture photo, monitoring
  |-- reminder and off-work background services
             |
             +-- WebSocket :8766 (loopback only)
```

The mobile gateway is the only LAN-facing service. It forwards requests to the
renderer through a loopback WebSocket, so the renderer itself is not exposed
on the LAN.

## Face Authorization Demo

The authorization rule is intentionally stricter than the ordinary XiaoQ
build:

1. A person is registered from the mobile app using the XiaoQ camera.
2. The user selects that registered person as the tracking target.
3. Hailo ArcFace must identify the selected person with a cosine score of at
   least `0.68` within the previous two seconds.
4. Each local voice request, mobile text request, mobile vision request, and
   ESP32 voice request checks this state before ASR, Hermes, skills, or an LLM
   is invoked.
5. A failed check returns `人脸授权失败` and queues one fresh photo for the
   mobile app.

Selecting "任意人脸跟踪" disables the authorization gate and retains ordinary
face-following behavior. Enrollment metadata and face embeddings remain in
`data/face_registry.json`; the short-lived authorization state contains only
the selected identity, score, and timestamp.

## Main Capabilities

| Area | Demo capability |
| --- | --- |
| Interaction | Local push-to-talk, mobile text/hold-to-talk, ESP32 Wi-Fi voice remote, streaming MiMo TTS |
| Personas | F2 switches the face style, response style, and MiMo voice together |
| Vision | Single-frame MiMo visual Q&A, Hailo face tracking, gesture photo, visual monitoring and ESP32 LED alarms |
| Mobile | LAN chat, speaker toggle, camera feed, gimbal control, face registration/selection, photo retrieval, meeting upload |
| Skills | Todo/reminders, off-work briefing, weather/news, email/knowledge, meeting-area PIR, ESP32 LED, remote laptop, AT dispatch |
| Hardware | Pan/Tilt gimbal, IMX219 camera, Hailo-8L, ReSpeaker audio, ESP32 RGB/voice/PIR peripherals |

The default gimbal neutral point is Pan `90` and Tilt `145`. The sleep pose is
Pan `90` and Tilt `162`.

## Request Routing

```text
Speech / text input
  -> face authorization gate (demo mode)
  -> local semantic intent classification
  -> direct MiMo chat for ordinary conversation
  -> Hermes only for multi-step skills and skill context
  -> structured local action execution
  -> card response and optional MiMo streaming TTS
```

Fast local reads such as todo listing use the local skill data path. Operations
that need planning, confirmation, or external systems remain Hermes-backed.
Visual monitoring persists a normalized target and condition, periodically
uses a fresh camera frame, and can invoke an action such as changing an ESP32
LED when the condition is met.

## Services and Ports

| Service | Unit | Interface | Purpose |
| --- | --- | --- | --- |
| Demo runtime | `xiaoq-face-auth-demo.service` | display, camera, audio, gimbal | Main robot process |
| Mobile gateway | `xiaoq-face-auth-demo-mobile.service` | `0.0.0.0:8788` | App API and MJPEG proxy |
| Runtime command channel | Main runtime | `127.0.0.1:8766` | Internal mobile-gateway commands |

The deployment unit templates are under `deploy/systemd/`. The mobile gateway
sets `XIAOQ_RUNTIME_SERVICE=xiaoq-face-auth-demo.service`, so App start/stop
controls target the demo service rather than a production service.

## Deployment

Copy the repository to `/home/johnf/xiaoq-face-auth-demo`, configure runtime
secrets outside Git, then install the unit templates:

```bash
sudo cp deploy/systemd/xiaoq-face-auth-demo*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now xiaoq-face-auth-demo.service
sudo systemctl enable --now xiaoq-face-auth-demo-mobile.service
```

The runtime requires the existing Pi camera/Hailo stack, audio devices,
Python dependencies, Hermes configuration, and MiMo API key. Do not put
credentials in the repository. The project ignores `.env`, ESP32 `secrets.h`,
mobile tokens, face registry data, todos, logs, and generated packages.

## Source Package

Run the following from the repository root after committing the desired state:

```bash
./scripts/package_demo.sh
```

It writes a versioned ZIP to `dist/` using `git archive`. The archive contains
only tracked source and documentation, which keeps secrets and runtime state
out of the package.
