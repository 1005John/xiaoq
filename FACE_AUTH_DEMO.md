# XiaoQ Face Authorization Demo

This is an isolated demonstration copy of XiaoQ. It requires the person selected in the mobile app's face-following screen to be recognized by the Hailo ArcFace pipeline before any dialogue is allowed.

## Rule

1. Register a person from the mobile app and select that person as the tracking target.
2. The Hailo pipeline must recognize that selected identity in the camera view.
3. The successful match remains valid for two seconds and requires an ArcFace cosine score of at least `0.68`. Every new speech, phone text request, ESP32 voice request, and phone vision request checks it again.
4. If a registered person is selected but absent, another person is visible, or the match is older than two seconds, the reply is exactly `人脸授权失败`.
5. Selecting "任意人脸跟踪" is an opt-out: XiaoQ follows any face and dialogue does not require face authorization.

The gate runs before ASR, Hermes, skills, or MiMo dialogue calls. ESP32 requests receive the same text as their response and its existing TTS return channel can speak it.

## Demo Data Isolation

The demo's `start_xiaoq.sh` exports `XIAOQ_ROOT` to this project's directory. Its enrollment data and temporary authorization state are therefore kept below:

```text
<demo-root>/data/face_registry.json
<demo-root>/data/face_auth_state.json
```

The authorization state contains only the selected person's identifier, display name, match score, and timestamp. It does not contain images or face embeddings.

## Running On The Pi

This demo uses the same camera, display, WebSocket port, and audio devices as the normal XiaoQ service, so do not run both at once. Stop the normal service, copy this directory to the Pi, then start the demo from its own directory:

```bash
sudo systemctl stop xiaoq.service
cd /home/johnf/xiaoq-face-auth-demo
./start_xiaoq.sh
```

Run the mobile gateway with the same isolated root in another terminal. Use a different port only if the normal mobile gateway remains online:

```bash
cd /home/johnf/xiaoq-face-auth-demo
XIAOQ_ROOT="$PWD" XIAOQ_MOBILE_PORT=8790 python3 mobile_control.py
```

Point the mobile app to the Pi address and selected gateway port. `GET /api/status` now includes `face_auth.authorized` and the matched identity name for inspection.
