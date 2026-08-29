#!/usr/bin/env python3
"""Authenticated LAN API used by the XiaoQ HarmonyOS companion app."""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request, send_file, send_from_directory
from werkzeug.utils import secure_filename


APP_ROOT = Path(os.environ.get("XIAOQ_ROOT", "/home/johnf/xiaoq"))
DATA_ROOT = APP_ROOT / "data"
MOBILE_ROOT = DATA_ROOT / "mobile"
VOICE_ROOT = MOBILE_ROOT / "voice"
TOKEN_PATH = DATA_ROOT / "mobile_control_token"
MEETING_ROOT = DATA_ROOT / "meetings"
MEETING_INBOX = MEETING_ROOT / "inbox"
MEETING_ARCHIVE = MEETING_ROOT / "archive"
MEETING_OUTPUT = MEETING_ROOT / "output"
MEETING_JOBS = MEETING_ROOT / "jobs"
CHAT_ROOT = MOBILE_ROOT / "chat"
PHOTO_ROOT = MOBILE_ROOT / "photos"
ESP32_LED_STATE_PATH = DATA_ROOT / "esp32_led_state.json"
ESP32_DEBUG_STATE_PATH = DATA_ROOT / "esp32_debug_state.json"
REMOTE_DEVICES_STATE_PATH = DATA_ROOT / "remote_devices.json"
VISION_CONTEXT_PATH = DATA_ROOT / "vision_context.json"
TODOS_PATH = DATA_ROOT / "todos.json"
FACE_REGISTRY_PATH = DATA_ROOT / "face_registry.json"
PORT = int(os.environ.get("XIAOQ_MOBILE_PORT", "8788"))
# The production and demonstration deployments use different systemd units.
# Keep the mobile API bound to the unit that launched this gateway.
RUNTIME_SERVICE = os.environ.get("XIAOQ_RUNTIME_SERVICE", "xiaoq.service").strip()
MAX_UPLOAD_BYTES = 256 * 1024 * 1024
VOICE_EXTENSIONS = {".m4a", ".mp3", ".wav", ".aac", ".ogg", ".webm"}
MEETING_EXTENSIONS = VOICE_EXTENSIONS | {".wma"}
MIMO_URL = "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
VISION_MODEL = "mimo-v2.5"
VISION_CAPTURE_TIMEOUT = 10.0
MAX_VISION_TEXT = 2000
MAX_VISION_IMAGE_BYTES = 8 * 1024 * 1024
SHARED_CAMERA_FRAME_PATH = Path("/dev/shm/xiaoq_camera_latest.jpg")

for directory in (VOICE_ROOT, CHAT_ROOT, MEETING_INBOX, MEETING_ARCHIVE, MEETING_OUTPUT, MEETING_JOBS, PHOTO_ROOT):
    directory.mkdir(parents=True, exist_ok=True)


def load_token() -> str:
    if not TOKEN_PATH.exists():
        TOKEN_PATH.write_text(secrets.token_urlsafe(32), encoding="utf-8")
        TOKEN_PATH.chmod(0o600)
    return TOKEN_PATH.read_text(encoding="utf-8").strip()


TOKEN = load_token()
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
gimbal_lock = threading.Lock()
gimbal_state = {"mode": "auto", "pan": 90, "tilt": 150}
todo_lock = threading.Lock()
ptt_lock = threading.Lock()
ptt_active = False


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def authorized() -> bool:
    supplied = (
        request.headers.get("X-XiaoQ-Token", "")
        or request.form.get("token", "")
        or request.args.get("token", "")
    )
    return bool(supplied) and hmac.compare_digest(supplied, TOKEN)


@app.before_request
def require_token():
    if request.path in {"/", "/health"}:
        return None
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    return None


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def record_visual_led_state(reply: str) -> str:
    """Persist only MiMo's explicit, machine-readable ESP32 observations."""
    match = re.search(r"\[\[ESP32_STATE:(\{.*?\})\]\]", reply, flags=re.DOTALL)
    if not match:
        return reply.strip()
    visible_reply = (reply[:match.start()] + reply[match.end():]).strip()
    try:
        observations = json.loads(match.group(1))
    except json.JSONDecodeError:
        return visible_reply
    if not isinstance(observations, dict):
        return visible_reply

    valid_colors = {"red", "green", "blue", "white", "yellow", "purple", "off"}
    state = read_json(ESP32_LED_STATE_PATH)
    devices = state.setdefault("devices", {}) if isinstance(state, dict) else {}
    if not isinstance(devices, dict):
        devices = state["devices"] = {}
    changed = False
    for device_id, color in observations.items():
        if not str(device_id).isdigit() or color not in valid_colors:
            continue
        previous = devices.get(str(device_id), {})
        devices[str(device_id)] = {
            "name": str(previous.get("name") or f"{device_id}号ESP32"),
            "color": color,
            "source": "vision",
            "updated_at": iso_now(),
        }
        changed = True
    if changed:
        write_json(ESP32_LED_STATE_PATH, state)
    return visible_reply


def record_visual_remote_devices(reply: str) -> str:
    """Persist only explicit, machine-readable remote-device observations."""
    match = re.search(r"\[\[REMOTE_DEVICE_STATE:(\{.*?\})\]\]", reply, flags=re.DOTALL)
    if not match:
        return reply.strip()
    visible_reply = (reply[:match.start()] + reply[match.end():]).strip()
    try:
        observations = json.loads(match.group(1))
    except json.JSONDecodeError:
        return visible_reply
    if not isinstance(observations, dict):
        return visible_reply

    state = read_json(REMOTE_DEVICES_STATE_PATH)
    devices = state.setdefault("devices", {})
    if not isinstance(devices, dict):
        devices = state["devices"] = {}
    changed = False
    if observations.get("laptop") is True:
        device = devices.get("laptop", {})
        if not isinstance(device, dict):
            device = {}
        device.update({"name": "笔记本电脑", "last_seen_source": "vision", "last_seen_at": iso_now()})
        devices["laptop"] = device
        changed = True
    if changed:
        write_json(REMOTE_DEVICES_STATE_PATH, state)
    return visible_reply


def face_authorization_status() -> dict[str, Any]:
    """Read the short-lived ArcFace authorization written by the renderer."""
    try:
        from face_identity import FaceRegistry
        return FaceRegistry().authorization_status()
    except Exception as error:
        app.logger.warning("face authorization status unavailable: %s", error)
        return {"authorized": False, "reason": "unavailable"}


def face_authorization_reply(text: str, speak: bool = False):
    """Return the demo's consistent denial reply without calling a model."""
    reply = "人脸授权失败"
    photo_capture_requested = send_command({"type": "face_auth_snapshot"})
    speaker_dispatched = False
    if speak:
        speaker_dispatched = send_command({"type": "mobile_reply", "reply": reply, "speak": True})
    return jsonify({
        "ok": True,
        "status": "completed",
        "text": text,
        "reply": reply,
        "face_authorized": False,
        "photo_capture_requested": photo_capture_requested,
        "speaker_dispatched": speaker_dispatched,
    })


def meeting_tasks(filename: str) -> list[str]:
    """Extract user-editable action items from the standard meeting markdown."""
    path = MEETING_OUTPUT / filename
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return []
    # MiMo sometimes emits the section as plain "待办事项" instead of a
    # Markdown level-2 heading. Accept both forms, then stop at the next
    # heading (or the common "备注" section).
    section_match = re.search(r"(?im)^\s*(?:#+\s*)?待办事项\s*$", content)
    if section_match is None:
        return []
    body = content[section_match.end():]
    next_section = re.search(r"(?im)^\s*(?:#+\s*)?(?:备注|附注|说明)\s*$", body)
    if next_section is not None:
        body = body[:next_section.start()]
    else:
        next_heading = re.search(r"(?m)^\s*#{1,6}\s+", body)
        if next_heading is not None:
            body = body[:next_heading.start()]
    tasks: list[str] = []
    for line in body.splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        # Ignore Markdown table headers/separators from older summaries.
        if cleaned.startswith("|"):
            if re.fullmatch(r"\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)+\|?", cleaned):
                continue
            if any(label in cleaned for label in ("负责人", "事项", "截止时间")):
                continue
            cleaned = cleaned.strip("|").replace("|", " ").strip()
        # Only accept list-like lines so prose below the section cannot become
        # a false todo. Support "1.", "1、", "-" and "*" forms.
        cleaned = re.sub(r"^(?:[-*]\s+|\d+[.、）)]\s*)", "", cleaned).strip()
        if not cleaned:
            continue
        cleaned = cleaned.removeprefix("[ ]").removeprefix("[x]").strip()
        if cleaned and cleaned not in tasks:
            tasks.append(cleaned[:300])
    return tasks[:30]


def next_reminder(time_text: str, date_text: str = "") -> tuple[str, str]:
    try:
        hour, minute = (int(value) for value in time_text.split(":", 1))
        if hour not in range(24) or minute not in range(60):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        raise ValueError("reminder_time must use HH:MM")
    cn_tz = timezone(timedelta(hours=8))
    now = datetime.now(cn_tz)
    if date_text:
        try:
            reminder_date = datetime.strptime(date_text, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("reminder_date must use YYYY-MM-DD")
        reminder = datetime(
            reminder_date.year, reminder_date.month, reminder_date.day,
            hour, minute, tzinfo=cn_tz,
        )
        if reminder <= now:
            raise ValueError("reminder date and time must be in the future")
    else:
        reminder = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if reminder <= now:
            reminder += timedelta(days=1)
    return reminder.isoformat(), reminder.strftime("%Y-%m-%d %H:%M")


def new_job(kind: str, filename: str, stored_file: str = "") -> tuple[str, Path, dict[str, Any]]:
    job_id = f"{time.strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}"
    job = {
        "job_id": job_id,
        "kind": kind,
        "filename": filename,
        "stored_file": stored_file,
        "status": "queued",
        "created_at": iso_now(),
        "updated_at": iso_now(),
    }
    path = (VOICE_ROOT if kind == "voice" else MEETING_JOBS) / f"{job_id}.json"
    write_json(path, job)
    return job_id, path, job


def update_job(path: Path, **updates: Any) -> dict[str, Any]:
    job = read_json(path)
    job.update(updates)
    job["updated_at"] = iso_now()
    write_json(path, job)
    return job


def send_command(command: dict[str, Any]) -> bool:
    """The XiaoQ renderer accepts commands only on its loopback WebSocket."""
    try:
        from websockets.sync.client import connect

        with connect("ws://127.0.0.1:8766", open_timeout=3, close_timeout=3) as ws:
            ws.send(json.dumps(command, ensure_ascii=False))
        return True
    except Exception as exc:
        app.logger.warning("XiaoQ WebSocket unavailable: %s", exc)
        return False


def mimo_key() -> str:
    for name in ("XIAOMI_MIMO_API_KEY", "XIAOMI_API_KEY"):
        key = os.environ.get(name, "").strip()
        if key:
            return key
    env_path = Path.home() / ".hermes/.env"
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() in {"XIAOMI_MIMO_API_KEY", "XIAOMI_API_KEY"}:
                key = value.strip().strip("\"'")
                if key:
                    return key
    except OSError:
        pass
    config = Path.home() / ".hermes/hermes-desktop-assistant/config.json"
    try:
        values = json.loads(config.read_text(encoding="utf-8"))
        return str(values.get("xiaomi_mimo_api_key", values.get("aliyun_api_key", ""))).strip()
    except (OSError, json.JSONDecodeError):
        return ""


def chat_content(data: dict[str, Any]) -> str:
    """Read text from the OpenAI-compatible response variants used by MiMo."""
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return ""
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "".join(
            part.get("text", "") for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ).strip()
    return ""


def vision_reply(question: str, frame: bytes) -> str:
    """Ask MiMo-V2.5 about one camera frame and return the visible answer."""
    if len(frame) == 0:
        raise RuntimeError("camera returned an empty frame")
    if len(frame) > MAX_VISION_IMAGE_BYTES:
        raise RuntimeError("camera frame is too large")
    key = mimo_key()
    if not key:
        raise RuntimeError("MiMo API key is not configured")

    image = base64.b64encode(frame).decode("ascii")
    payload = json.dumps({
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "system",
                "content": '你是小Q的视觉助手。根据摄像头当前画面回答用户问题；看不清或画面没有依据时要明确说明，不要猜测。回答简洁、自然。若且仅若能清晰看见带有ESP32-N或N号ESP32标签的设备及其LED颜色，在回答末尾附加一行[[ESP32_STATE:{"N":"red"}]]，用实际编号和英文颜色red、green、blue、white、yellow、purple、off替换示例。若且仅若能清晰看见笔记本电脑或电脑，在回答末尾另附一行[[REMOTE_DEVICE_STATE:{"laptop":true}]]。设备不清晰时绝不附加对应标记。',
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}},
                ],
            },
        ],
        # Leave enough budget for MiMo's internal reasoning before its visible
        # answer. The phone should receive only `content`, never hidden traces.
        "max_tokens": 1500,
        "stream": False,
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(MIMO_URL, data=payload, headers={
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {key}",
        "api-key": key,
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:240]
        raise RuntimeError(f"MiMo 视觉请求失败 ({exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"MiMo 视觉请求超时或网络不可用: {exc}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("MiMo 视觉接口返回了无效响应") from exc

    reply = chat_content(data)
    if not reply:
        raise RuntimeError("MiMo 视觉接口没有返回文字回答")
    return reply


def remember_visual_context(question: str, reply: str, source: str = "mobile") -> None:
    """Expose recent visual results to a later natural-language monitor task."""
    try:
        from skills.vision_monitor import remember_visual_context as remember
        remember(question, reply, source)
    except Exception as error:
        app.logger.warning("unable to save vision context: %s", error)


def transcribe_wav(wav_path: Path) -> str:
    audio = base64.b64encode(wav_path.read_bytes()).decode("ascii")
    payload = json.dumps({
        "model": "mimo-v2.5-asr",
        "messages": [{"role": "user", "content": [{
            "type": "input_audio",
            "input_audio": {"data": f"data:audio/wav;base64,{audio}"},
        }]}],
        "stream": True,
    }, ensure_ascii=False).encode("utf-8")
    key = mimo_key()
    if not key:
        raise RuntimeError("MiMo API key is not configured")
    req = urllib.request.Request(MIMO_URL, data=payload, headers={
        "Content-Type": "application/json; charset=utf-8",
        "api-key": key,
    })
    pieces: list[str] = []
    with urllib.request.urlopen(req, timeout=90) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                content = json.loads(data)["choices"][0]["delta"].get("content")
                if content:
                    pieces.append(content)
            except (KeyError, IndexError, TypeError, json.JSONDecodeError):
                continue
    return "".join(pieces).strip()


def synthesize_esp32_tts(text: str, output_path: Path) -> None:
    """Generate 16 kHz mono PCM matching the verified ESP32 I2S path."""
    key = mimo_key()
    if not key:
        raise RuntimeError("MiMo API key is not configured")
    payload = json.dumps({
        "model": "mimo-v2.5-tts",
        "messages": [
            {"role": "user", "content": "用自然清晰的中文声音回答，语速适中。"},
            {"role": "assistant", "content": text},
        ],
        "audio": {"format": "pcm16", "voice": os.environ.get("XIAOQ_ESP32_TTS_VOICE", "冰糖")},
        "stream": True,
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(MIMO_URL, data=payload, headers={
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {key}",
        "api-key": key,
    })
    temporary = output_path.with_suffix(output_path.suffix + ".24k.tmp")
    audio_bytes = 0
    try:
        with urllib.request.urlopen(req, timeout=90) as response, temporary.open("wb") as target:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    item = json.loads(data)
                    audio = item.get("choices", [{}])[0].get("delta", {}).get("audio", {})
                    encoded = audio.get("data") if isinstance(audio, dict) else ""
                    if encoded:
                        chunk = base64.b64decode(encoded)
                        target.write(chunk)
                        audio_bytes += len(chunk)
                except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
                    continue
        if audio_bytes == 0:
            raise RuntimeError("MiMo TTS returned no audio")
        conversion = subprocess.run(
            [
                "ffmpeg", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1",
                "-i", str(temporary), "-f", "s16le", "-ar", "16000", "-ac", "1",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if conversion.returncode != 0 or not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("failed to resample ESP32 TTS audio")
    finally:
        temporary.unlink(missing_ok=True)


def finish_esp32_voice_job(job_path: Path, text: str) -> None:
    """Wait for the renderer's text reply, then prepare its ESP32 audio."""
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        job = read_json(job_path)
        if job.get("status") in {"completed", "failed"}:
            if job.get("status") == "failed":
                return
            reply = str(job.get("reply", "")).strip()
            if not reply:
                update_job(job_path, status="failed", error="XiaoQ returned an empty reply")
                return
            try:
                update_job(job_path, status="synthesizing", reply=reply)
                audio_path = VOICE_ROOT / f"{job_path.stem}.reply.pcm"
                synthesize_esp32_tts(reply, audio_path)
                update_job(
                    job_path,
                    status="completed",
                    reply=reply,
                    audio_ready=True,
                    audio_format="pcm_s16le",
                    sample_rate=16000,
                    channels=1,
                )
            except Exception as exc:
                app.logger.exception("ESP32 TTS failed")
                update_job(job_path, status="failed", error=str(exc)[:200])
            return
        time.sleep(0.5)
    update_job(job_path, status="failed", error="XiaoQ reply timed out")


def process_voice_job(job_path: Path, source: Path, esp32_reply: bool = False) -> None:
    # Keep the uploaded source separate from ffmpeg's output. When ESP32 sends
    # a WAV directly, using the same path for input and output makes ffmpeg
    # fail with an in-place conversion error before ASR is reached.
    wav_path = source.with_name(f"{source.stem}.converted.wav")
    try:
        update_job(job_path, status="transcribing")
        conversion = subprocess.run(
            ["ffmpeg", "-y", "-i", str(source), "-ac", "1", "-ar", "16000", str(wav_path)],
            capture_output=True, text=True, timeout=90,
        )
        if conversion.returncode != 0:
            raise RuntimeError("audio conversion failed")
        text = transcribe_wav(wav_path)
        if len(text) < 2:
            raise RuntimeError("no speech recognized")
        update_job(job_path, status="dispatching", transcript=text, reply_channel="esp32" if esp32_reply else "xiaoq")
        if not send_command({
            "type": "voice_inject",
            "text": text,
            "speak": not esp32_reply,
            "reply_path": str(job_path) if esp32_reply else "",
        }):
            raise RuntimeError("XiaoQ is not running")
        if esp32_reply:
            finish_esp32_voice_job(job_path, text)
        else:
            update_job(job_path, status="dispatched", transcript=text, reply_channel="xiaoq")
    except Exception as exc:
        app.logger.exception("voice job failed")
        update_job(job_path, status="failed", error=str(exc)[:160])
    finally:
        wav_path.unlink(missing_ok=True)


def refresh_meeting_job(job: dict[str, Any]) -> dict[str, Any]:
    """Derive progress from the inbox/archive lifecycle maintained by XiaoQ."""
    stored = job.get("stored_file", "")
    if not stored or job.get("status") in {"completed", "failed"}:
        return job
    inbox = MEETING_INBOX / stored
    archive = MEETING_ARCHIVE / stored
    if inbox.exists():
        return job
    if archive.exists():
        created = archive.stat().st_mtime
        outputs = sorted(
            (file for file in MEETING_OUTPUT.glob("*.md") if file.stat().st_mtime >= created - 10),
            key=lambda file: file.stat().st_mtime,
            reverse=True,
        )
        if outputs:
            job["status"] = "completed"
            job["result_file"] = outputs[0].name
            job["tasks"] = meeting_tasks(outputs[0].name)
            job["updated_at"] = iso_now()
    return job


class CameraStream:
    """A lazy single-camera MJPEG producer for the remote-control page."""

    def __init__(self):
        self.lock = threading.Lock()
        self.frame: bytes | None = None
        self.frame_captured_at = 0.0
        self.frame_source = ""
        self.error = ""
        self.started = False
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        # More than one WebView request can briefly subscribe to the MJPEG
        # endpoint while HarmonyOS reloads a page. Keep the producer alive
        # until the last subscriber disconnects.
        self.clients = 0

    def ensure_started(self) -> None:
        with self.lock:
            if self.started:
                return
            self.error = ""
            self.frame = None
            self.frame_captured_at = 0.0
            self.frame_source = ""
            self.stop_event.clear()
            self.started = True
        # Prefer the frame exported by XiaoQ's existing Hailo pipeline. The
        # fallback in _capture reserves Picamera2 only when that pipeline is
        # unavailable, so live phone video and gesture detection can coexist.
        thread = threading.Thread(target=self._capture, daemon=True, name="mobile-camera")
        with self.lock:
            self.thread = thread
        thread.start()

    def stop(self) -> None:
        """Release Picamera2 and allow automatic Hailo tracking to resume."""
        with self.lock:
            thread = self.thread
            if not self.started and thread is None:
                return
            self.stop_event.set()
            self.clients = 0
        if thread and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        with self.lock:
            self.started = False
            self.thread = None
            self.frame = None
            self.frame_captured_at = 0.0
            self.frame_source = ""
        send_command({"type": "camera_release"})

    def _publish_frame(self, frame: bytes, captured_at: float, source: str) -> None:
        """Publish one JPEG together with when its source produced it."""
        with self.lock:
            self.frame = frame
            self.frame_captured_at = captured_at
            self.frame_source = source

    def snapshot(self, timeout: float = VISION_CAPTURE_TIMEOUT, *, min_captured_at: float = 0.0) -> bytes:
        """Wait for a JPEG, optionally requiring one newer than a request."""
        self.ensure_started()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self.lock:
                frame = self.frame
                error = self.error
                captured_at = self.frame_captured_at
                source = self.frame_source
            if error:
                raise RuntimeError(error)
            if frame and captured_at >= min_captured_at:
                app.logger.info(
                    "vision frame selected source=%s age=%.3fs bytes=%d sha256=%s",
                    source,
                    max(0.0, time.time() - captured_at),
                    len(frame),
                    hashlib.sha256(frame).hexdigest()[:16],
                )
                return frame
            time.sleep(0.05)
        if min_captured_at:
            raise RuntimeError("camera did not produce a fresh frame in time")
        raise RuntimeError("camera frame timeout")

    def _capture(self) -> None:
        camera = None
        try:
            # HailoFace exports a throttled JPEG in shared memory. Serving it
            # avoids opening a second Picamera2 while face/gesture inference is
            # active. Fall back to a direct capture when XiaoQ is stopped or
            # its shared frame is stale, otherwise the phone stream emits no
            # bytes at all after a XiaoQ restart.
            shared_deadline = time.monotonic() + 2.0
            while not self.stop_event.is_set() and time.monotonic() < shared_deadline:
                try:
                    if SHARED_CAMERA_FRAME_PATH.exists() and (
                        time.time() - SHARED_CAMERA_FRAME_PATH.stat().st_mtime < 2.0
                    ):
                        while not self.stop_event.is_set():
                            try:
                                source_mtime = SHARED_CAMERA_FRAME_PATH.stat().st_mtime
                                if time.time() - source_mtime >= 2.0:
                                    break
                                frame = SHARED_CAMERA_FRAME_PATH.read_bytes()
                                if frame:
                                    self._publish_frame(frame, source_mtime, "hailo_shared")
                                time.sleep(1 / 15)
                            except OSError:
                                time.sleep(0.05)
                        if self.stop_event.is_set():
                            return
                        break
                except OSError:
                    pass
                time.sleep(0.05)

            if self.stop_event.is_set():
                return

            send_command({"type": "camera_reserve"})
            time.sleep(0.6)
            import cv2
            from picamera2 import Picamera2

            camera = Picamera2()
            camera.configure(camera.create_preview_configuration(
                main={"size": (640, 360), "format": "RGB888"}, buffer_count=2,
            ))
            camera.start()
            while not self.stop_event.is_set():
                frame = cv2.flip(camera.capture_array(), 1)
                ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 72])
                if ok:
                    self._publish_frame(encoded.tobytes(), time.time(), "picamera2")
                time.sleep(1 / 15)
        except Exception as exc:
            app.logger.warning("camera unavailable: %s", exc)
            with self.lock:
                self.error = "camera unavailable"
                self.started = False
        finally:
            if camera is not None:
                try:
                    camera.stop()
                    camera.close()
                except Exception:
                    pass

    def generate(self):
        self.ensure_started()
        with self.lock:
            self.clients += 1
        try:
            while True:
                with self.lock:
                    frame = self.frame
                    error = self.error
                if error:
                    return
                if frame:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                time.sleep(1 / 15)
        finally:
            with self.lock:
                self.clients = max(0, self.clients - 1)
                last_client = self.clients == 0
            if last_client:
                self.stop()


camera_stream = CameraStream()


@app.get("/")
def index():
    return Response("""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>小Q手机控制</title><style>body{font-family:system-ui,sans-serif;max-width:640px;margin:10vh auto;padding:24px;color:#17202d;line-height:1.7}code{background:#f0f3f6;padding:2px 5px;border-radius:3px}</style>
<h1>小Q手机控制服务</h1><p>服务正在运行。请在鸿蒙 App 的“设置”页填写树莓派 IP 地址和设备令牌后连接。</p>
<p>接口和视频流均需设备令牌访问。服务状态：<a href="/health">/health</a></p>""", mimetype="text/html")


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "xiaoq-mobile-control"})


@app.get("/api/status")
def status():
    ws_online = send_command({"type": "mobile_ping"})
    with gimbal_lock:
        state = dict(gimbal_state)
    return jsonify({
        "ok": True,
        "xiaoq_online": ws_online,
        "camera_error": camera_stream.error,
        "face_auth": face_authorization_status(),
        **state,
    })


def xiaoq_service_state() -> str:
    result = subprocess.run(
        ["systemctl", "is-active", RUNTIME_SERVICE],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip() or "unknown"


def manage_xiaoq_service(action: str) -> tuple[bool, str]:
    result = subprocess.run(
        ["sudo", "-n", "systemctl", action, RUNTIME_SERVICE],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip() or f"systemctl {action} failed"
    if action == "stop":
        # start_xiaoq.sh exits with SIGTERM during an intentional stop.
        subprocess.run(["sudo", "-n", "systemctl", "reset-failed", RUNTIME_SERVICE],
                       capture_output=True, text=True, timeout=10)
    return True, xiaoq_service_state()


@app.get("/api/runtime")
def runtime_status():
    return jsonify({"ok": True, "xiaoq_service": xiaoq_service_state()})


@app.post("/api/runtime/start")
def runtime_start():
    ok, detail = manage_xiaoq_service("start")
    if not ok:
        return jsonify({"ok": False, "error": detail}), 502
    return jsonify({"ok": True, "xiaoq_service": detail})


@app.post("/api/runtime/stop")
def runtime_stop():
    ok, detail = manage_xiaoq_service("stop")
    if not ok:
        return jsonify({"ok": False, "error": detail}), 502
    return jsonify({"ok": True, "xiaoq_service": detail})


@app.post("/api/runtime/poweroff")
def runtime_poweroff():
    def poweroff_after_response() -> None:
        time.sleep(2)
        subprocess.run(["sudo", "-n", "systemctl", "poweroff"], capture_output=True, text=True, timeout=30)

    threading.Thread(target=poweroff_after_response, daemon=True).start()
    return jsonify({"ok": True, "accepted": True, "message": "poweroff scheduled"})


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text", "")).strip()
    speak = bool(payload.get("speak", False))
    if len(text) < 2 or len(text) > 2000:
        return jsonify({"ok": False, "error": "text must contain 2-2000 characters"}), 400
    job_id = f"{time.strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}"
    job_path = CHAT_ROOT / f"{job_id}.json"
    write_json(job_path, {"status": "queued", "text": text, "created_at": iso_now()})
    if not send_command({
        "type": "voice_inject",
        "text": text,
        "speak": speak,
        "reply_path": str(job_path),
    }):
        job_path.unlink(missing_ok=True)
        return jsonify({"ok": False, "error": "xiaoq offline"}), 503
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        job = read_json(job_path)
        if job.get("status") in {"completed", "failed"}:
            job_path.unlink(missing_ok=True)
            if job.get("status") == "failed":
                return jsonify({"ok": False, "error": job.get("error", "chat failed")}), 502
            return jsonify({
                "ok": True,
                "status": "completed",
                "text": text,
                "reply": job.get("reply", ""),
            })
        time.sleep(0.2)
    job_path.unlink(missing_ok=True)
    return jsonify({"ok": False, "error": "小Q回复超时"}), 504


@app.post("/api/ptt/start")
def ptt_start():
    """Start XiaoQ's local microphone, matching a Space key-down event."""
    global ptt_active
    payload = request.get_json(silent=True) or {}
    speak = bool(payload.get("speak", True))
    use_vision = bool(payload.get("use_vision", False))
    with ptt_lock:
        if ptt_active:
            return jsonify({"ok": True, "active": True, "already_active": True})
        if not send_command({
            "type": "voice_start",
            "speak": speak,
            "use_vision": use_vision,
        }):
            return jsonify({"ok": False, "error": "xiaoq offline"}), 503
        ptt_active = True
    return jsonify({"ok": True, "active": True})


@app.post("/api/ptt/stop")
def ptt_stop():
    """Stop XiaoQ's local microphone, matching a Space key-up event."""
    global ptt_active
    with ptt_lock:
        if not ptt_active:
            return jsonify({"ok": True, "active": False, "already_stopped": True})
        ptt_active = False
        if not send_command({"type": "voice_stop"}):
            return jsonify({"ok": False, "error": "xiaoq offline"}), 503
    return jsonify({"ok": True, "active": False})


@app.post("/api/persona/toggle")
def persona_toggle():
    """Switch the complete persona, matching the desktop F2 shortcut."""
    if not send_command({"type": "persona_toggle"}):
        return jsonify({"ok": False, "error": "xiaoq offline"}), 503
    return jsonify({"ok": True, "accepted": True})


@app.post("/api/tts/volume")
def tts_volume():
    """Set XiaoQ speaker volume immediately while TTS may be playing."""
    payload = request.get_json(silent=True) or {}
    try:
        percent = max(0, min(100, int(payload["percent"])))
    except (KeyError, TypeError, ValueError):
        return jsonify({"ok": False, "error": "percent must be an integer from 0 to 100"}), 400
    if not send_command({"type": "volume_set", "percent": percent}):
        return jsonify({"ok": False, "error": "xiaoq offline"}), 503
    return jsonify({"ok": True, "percent": percent})


@app.post("/api/vision")
def vision_chat():
    """Capture one frame, ask MiMo-V2.5, and optionally play it on XiaoQ."""
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text", "")).strip()
    speak = bool(payload.get("speak", False))
    if len(text) < 2 or len(text) > MAX_VISION_TEXT:
        return jsonify({"ok": False, "error": "text must contain 2-2000 characters"}), 400
    if not face_authorization_status().get("authorized"):
        return face_authorization_reply(text, speak)
    request_started_at = time.time()
    try:
        try:
            # Do not reuse a JPEG left by the phone's live preview. The image
            # sent to MiMo must have been produced after this request arrived.
            frame = camera_stream.snapshot(min_captured_at=request_started_at)
        finally:
            # The model call only needs the captured JPEG, not the live camera.
            camera_stream.stop()
        reply = record_visual_remote_devices(record_visual_led_state(vision_reply(text, frame)))
        remember_visual_context(text, reply)
    except RuntimeError as exc:
        app.logger.warning("vision chat failed: %s", exc)
        status_code = 503 if "camera" in str(exc).lower() else 502
        return jsonify({"ok": False, "error": str(exc)}), status_code

    speaker_dispatched = False
    if speak:
        speaker_dispatched = send_command({
            "type": "mobile_reply",
            "reply": reply,
            "speak": True,
        })
    return jsonify({
        "ok": True,
        "status": "completed",
        "text": text,
        "reply": reply,
        "model": VISION_MODEL,
        "speaker_dispatched": speaker_dispatched,
    })


@app.post("/api/voice")
def voice_upload():
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"ok": False, "error": "audio file is required"}), 400
    filename = secure_filename(uploaded.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in VOICE_EXTENSIONS:
        return jsonify({"ok": False, "error": "unsupported audio format"}), 400
    job_id, job_path, _ = new_job("voice", filename)
    esp32_reply = request.headers.get("X-XiaoQ-Reply-Channel", "").strip().lower() == "esp32"
    if esp32_reply:
        update_job(job_path, reply_channel="esp32")
    source = VOICE_ROOT / f"{job_id}{suffix}"
    uploaded.save(source)
    threading.Thread(
        target=process_voice_job,
        args=(job_path, source, esp32_reply),
        daemon=True,
    ).start()
    return jsonify({"ok": True, "job_id": job_id, "status": "queued"}), 202


@app.get("/api/voice/<job_id>")
def voice_status(job_id: str):
    path = VOICE_ROOT / f"{secure_filename(job_id)}.json"
    job = read_json(path)
    if not job:
        return jsonify({"ok": False, "error": "job not found"}), 404
    return jsonify({"ok": True, "job": job})


@app.get("/api/voice/<job_id>/audio")
def voice_audio(job_id: str):
    """Serve the generated ESP32 PCM reply after the voice job completes."""
    safe_id = secure_filename(job_id)
    audio_path = VOICE_ROOT / f"{safe_id}.reply.pcm"
    if not audio_path.is_file():
        return jsonify({"ok": False, "error": "reply audio is not ready"}), 404
    return send_file(
        audio_path,
        mimetype="application/octet-stream",
        as_attachment=False,
        download_name=f"{safe_id}.pcm",
        max_age=0,
    )


@app.post("/api/esp32/debug")
def esp32_debug():
    """Persist the latest authenticated ESP32 playback stage for diagnostics."""
    payload = request.get_json(silent=True) or {}
    event = str(payload.get("event", "")).strip()[:120]
    if not event:
        return jsonify({"ok": False, "error": "event is required"}), 400
    write_json(ESP32_DEBUG_STATE_PATH, {
        "updated_at": iso_now(),
        "event": event,
        "job_id": str(payload.get("job_id", "")).strip()[:80],
    })
    return jsonify({"ok": True})


@app.post("/api/meetings")
def meeting_upload():
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"ok": False, "error": "audio file is required"}), 400
    filename = secure_filename(uploaded.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in MEETING_EXTENSIONS:
        return jsonify({"ok": False, "error": "unsupported audio format"}), 400
    job_id, job_path, job = new_job("meeting", filename)
    stored = f"{job_id}_{filename}"
    target = MEETING_INBOX / stored
    uploaded.save(target)
    update_job(job_path, stored_file=stored, status="queued")
    if not send_command({"type": "voice_inject", "text": "生成会议纪要"}):
        return jsonify({"ok": False, "error": "xiaoq offline", "job_id": job_id}), 503
    return jsonify({"ok": True, "job_id": job_id, "status": "queued", "filename": job["filename"]}), 202


@app.get("/api/meetings")
def meetings():
    files = sorted((file for file in MEETING_OUTPUT.glob("*.md")), key=lambda file: file.stat().st_mtime, reverse=True)
    return jsonify({"ok": True, "items": [{
        "filename": file.name,
        "html_filename": file.with_suffix(".html").name if file.with_suffix(".html").exists() else "",
        "updated_at": datetime.fromtimestamp(file.stat().st_mtime, tz=timezone.utc).isoformat(),
        "tasks": meeting_tasks(file.name),
    } for file in files]})


@app.get("/api/meetings/jobs/<job_id>")
def meeting_status(job_id: str):
    path = MEETING_JOBS / f"{secure_filename(job_id)}.json"
    job = read_json(path)
    if not job:
        return jsonify({"ok": False, "error": "job not found"}), 404
    previous_status = job.get("status")
    refreshed = refresh_meeting_job(job)
    if refreshed.get("status") != previous_status:
        write_json(path, refreshed)
    return jsonify({"ok": True, "job": refreshed})


@app.get("/api/meetings/files/<path:filename>")
def meeting_file(filename: str):
    candidate = Path(filename)
    resolved = (MEETING_OUTPUT / candidate).resolve()
    if candidate.name != filename or MEETING_OUTPUT.resolve() not in resolved.parents or candidate.suffix.lower() not in {".md", ".html", ".pdf"}:
        return jsonify({"ok": False, "error": "invalid filename"}), 400
    return send_from_directory(MEETING_OUTPUT, filename, as_attachment=candidate.suffix.lower() == ".pdf")


@app.get("/api/meetings/results/<path:filename>")
def meeting_result(filename: str):
    candidate = Path(filename)
    resolved = (MEETING_OUTPUT / candidate).resolve()
    if candidate.name != filename or MEETING_OUTPUT.resolve() not in resolved.parents or candidate.suffix.lower() != ".md":
        return jsonify({"ok": False, "error": "invalid filename"}), 400
    try:
        markdown = resolved.read_text(encoding="utf-8")
    except OSError:
        return jsonify({"ok": False, "error": "meeting result not found"}), 404
    return jsonify({"ok": True, "filename": filename, "markdown": markdown, "tasks": meeting_tasks(filename)})


@app.post("/api/todos")
def create_todo():
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text", "")).strip()
    reminder_time = str(payload.get("reminder_time", "09:00")).strip()
    reminder_date = str(payload.get("reminder_date", "")).strip()
    if not 2 <= len(text) <= 300:
        return jsonify({"ok": False, "error": "text must contain 2-300 characters"}), 400
    try:
        remind_at, remind_text = next_reminder(reminder_time, reminder_date)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    try:
        # Use XiaoQ's own skill so the mobile-created item has exactly the same
        # storage format and is picked up by the existing ReminderWatcher.
        with todo_lock:
            todos = read_json(TODOS_PATH)
            if isinstance(todos, list):
                # Meeting results are reloadable. When the same active action
                # item is submitted again, treat it as an edit so its revised
                # reminder time does not create a duplicate 09:00 todo.
                existing = next(
                    (item for item in todos
                     if not item.get("done") and not item.get("deleted")
                     and (item.get("text") or item.get("title")) == text),
                    None,
                )
                if existing is not None:
                    existing.update({
                        "title": text,
                        "text": text,
                        "remind_at": remind_at,
                        "remind_text": remind_text,
                        "notified": False,
                        "reminded": False,
                    })
                    write_json(TODOS_PATH, todos)
                    return jsonify({"ok": True, "todo": existing, "created": False})

            from skills.todo import TodoSkill
            entry = TodoSkill().add(text, remind_at=remind_at, remind_text=remind_text)
    except Exception as exc:
        app.logger.exception("could not create todo")
        return jsonify({"ok": False, "error": f"could not save todo: {exc}"}), 500
    return jsonify({"ok": True, "todo": entry, "created": True}), 201


@app.put("/api/todos/<int:todo_id>")
def update_todo(todo_id: int):
    """Update a mobile-created todo without creating a duplicate entry."""
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text", "")).strip()
    reminder_time = str(payload.get("reminder_time", "09:00")).strip()
    reminder_date = str(payload.get("reminder_date", "")).strip()
    if not 2 <= len(text) <= 300:
        return jsonify({"ok": False, "error": "text must contain 2-300 characters"}), 400
    try:
        remind_at, remind_text = next_reminder(reminder_time, reminder_date)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    with todo_lock:
        todos = read_json(TODOS_PATH)
        if not isinstance(todos, list):
            return jsonify({"ok": False, "error": "todo store is invalid"}), 500
        todo = next((item for item in todos if item.get("id") == todo_id), None)
        if todo is None:
            return jsonify({"ok": False, "error": "todo not found"}), 404
        if todo.get("done") or todo.get("deleted"):
            return jsonify({"ok": False, "error": "completed todo cannot be updated"}), 409

        # Keep both spellings because voice and mobile entry points both read
        # this shared JSON file. A changed time needs a new one-shot reminder.
        todo.update({
            "title": text,
            "text": text,
            "remind_at": remind_at,
            "remind_text": remind_text,
            "notified": False,
            "reminded": False,
        })
        write_json(TODOS_PATH, todos)
    return jsonify({"ok": True, "todo": todo})


@app.post("/api/gimbal")
def gimbal_move():
    payload = request.get_json(silent=True) or {}
    try:
        pan = max(75, min(105, int(payload["pan"])))
        tilt = max(138, min(162, int(payload["tilt"])))
    except (KeyError, TypeError, ValueError):
        return jsonify({"ok": False, "error": "pan and tilt are required"}), 400
    with gimbal_lock:
        if gimbal_state["mode"] != "manual":
            return jsonify({"ok": False, "error": "gimbal is in automatic mode"}), 409
    if not send_command({"type": "gimbal_move", "pan": pan, "tilt": tilt, "hold_seconds": 30}):
        return jsonify({"ok": False, "error": "xiaoq offline"}), 503
    with gimbal_lock:
        gimbal_state["pan"] = pan
        gimbal_state["tilt"] = tilt
        state = dict(gimbal_state)
    return jsonify({"ok": True, **state})


@app.get("/api/gimbal/state")
def gimbal_status():
    with gimbal_lock:
        state = dict(gimbal_state)
    return jsonify({"ok": True, **state})


@app.post("/api/gimbal/mode")
def gimbal_mode():
    payload = request.get_json(silent=True) or {}
    mode = str(payload.get("mode", "")).lower()
    if mode not in {"manual", "auto"}:
        return jsonify({"ok": False, "error": "mode must be manual or auto"}), 400
    command = {"type": "gimbal_manual"} if mode == "manual" else {"type": "gimbal_auto"}
    if not send_command(command):
        return jsonify({"ok": False, "error": "xiaoq offline"}), 503
    with gimbal_lock:
        gimbal_state["mode"] = mode
        state = dict(gimbal_state)
    return jsonify({"ok": True, **state})


@app.post("/api/gimbal/release")
def gimbal_release():
    if not send_command({"type": "gimbal_auto"}):
        return jsonify({"ok": False, "error": "xiaoq offline"}), 503
    with gimbal_lock:
        gimbal_state["mode"] = "auto"
        state = dict(gimbal_state)
    return jsonify({"ok": True, **state})


def face_registry_view() -> dict[str, Any]:
    """Expose enrollment metadata without ever returning face embeddings."""
    raw = read_json(FACE_REGISTRY_PATH)
    people = raw.get("people", []) if isinstance(raw, dict) else []
    result = []
    for person in people:
        if not isinstance(person, dict):
            continue
        person_id = str(person.get("id", "")).strip()
        name = str(person.get("name", "")).strip()
        if not person_id or not name:
            continue
        result.append({
            "id": person_id,
            "name": name,
            "sample_count": int(person.get("sample_count", 0) or 0),
            "created_at": str(person.get("created_at", "")),
        })
    active = raw.get("active_person_id") if isinstance(raw, dict) else None
    return {"people": result, "active_person_id": active if isinstance(active, str) else None}


@app.get("/api/faces")
def face_list():
    return jsonify({"ok": True, **face_registry_view()})


@app.post("/api/faces/register")
def face_register():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    if not name or len(name) > 32 or "\n" in name or "\r" in name:
        return jsonify({"ok": False, "error": "name must be 1 to 32 characters"}), 400
    if any(person["name"] == name for person in face_registry_view()["people"]):
        return jsonify({"ok": False, "error": "face name already exists"}), 409
    if not send_command({"type": "face_register", "name": name}):
        return jsonify({"ok": False, "error": "xiaoq offline"}), 503
    return jsonify({"ok": True, "status": "started", "name": name})


@app.post("/api/faces/active")
def face_select_active():
    payload = request.get_json(silent=True) or {}
    person_id = str(payload.get("person_id", "")).strip()
    if person_id and not any(person["id"] == person_id for person in face_registry_view()["people"]):
        return jsonify({"ok": False, "error": "face not found"}), 404
    if not send_command({"type": "face_target_select", "person_id": person_id}):
        return jsonify({"ok": False, "error": "xiaoq offline"}), 503
    return jsonify({"ok": True, "active_person_id": person_id or None})


@app.delete("/api/faces/<person_id>")
def face_delete(person_id: str):
    if not person_id or not any(person["id"] == person_id for person in face_registry_view()["people"]):
        return jsonify({"ok": False, "error": "face not found"}), 404
    if not send_command({"type": "face_delete", "person_id": person_id}):
        return jsonify({"ok": False, "error": "xiaoq offline"}), 503
    return jsonify({"ok": True})


@app.get("/api/camera/stream")
def camera_video():
    camera_stream.ensure_started()
    if camera_stream.error:
        return jsonify({"ok": False, "error": camera_stream.error}), 503
    return Response(camera_stream.generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/camera/snapshot")
def camera_snapshot():
    """Return a JPEG produced after this request, then release the camera."""
    requested_at = time.time()
    try:
        frame = camera_stream.snapshot(timeout=12.0, min_captured_at=requested_at)
        return Response(
            frame,
            mimetype="image/jpeg",
            headers={"Cache-Control": "no-store, no-cache, max-age=0"},
        )
    except RuntimeError as exc:
        app.logger.warning("camera snapshot failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 503
    finally:
        # The caller receives the bytes above, so retaining the camera only
        # delays Hailo face tracking from resuming.
        camera_stream.stop()


@app.get("/api/camera")
def camera_page():
    token = html.escape(request.args.get("token", ""), quote=True)
    return Response(f"""<!doctype html><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<style>html,body{{margin:0;background:#101722;height:100%;overflow:hidden}}img{{display:block;width:100%;height:100%;object-fit:contain}}</style>
<img src=\"/api/camera/stream?token={token}\" alt=\"小Q摄像头\">""", mimetype="text/html")


@app.get("/api/camera/status")
def camera_status():
    return jsonify({"ok": not bool(camera_stream.error), "error": camera_stream.error})


@app.get("/api/photos/status")
def photo_status():
    """Return the latest gesture-triggered photo without opening the camera."""
    latest = PHOTO_ROOT / "latest.json"
    if not latest.exists():
        return jsonify({"ok": True, "available": False, "filename": "", "captured_at": "", "source": ""})
    metadata = read_json(latest)
    filename = secure_filename(str(metadata.get("filename", "")))
    photo = PHOTO_ROOT / filename if filename else None
    if not photo or not photo.exists():
        return jsonify({"ok": True, "available": False, "filename": "", "captured_at": "", "source": ""})
    return jsonify({
        "ok": True,
        "available": True,
        "filename": filename,
        "captured_at": str(metadata.get("captured_at", "")),
        "source": str(metadata.get("source", "")),
    })


@app.get("/api/photos/latest")
def latest_photo_page():
    """Serve an authenticated page so Harmony Web can display the JPEG."""
    latest = PHOTO_ROOT / "latest.json"
    metadata = read_json(latest) if latest.exists() else {}
    filename = secure_filename(str(metadata.get("filename", "")))
    photo = PHOTO_ROOT / filename if filename else None
    if not photo or not photo.exists():
        return jsonify({"ok": False, "error": "no gesture photo"}), 404
    token = html.escape(request.args.get("token", ""), quote=True)
    image_url = f"/api/photos/file/{html.escape(filename, quote=True)}?token={token}"
    captured_at = html.escape(str(metadata.get("captured_at", "")))
    return Response(
        f"""<!doctype html><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<style>html,body{{margin:0;background:#101722;height:100%;overflow:hidden}}img{{display:block;width:100%;height:100%;object-fit:contain}}</style>
<img src=\"{image_url}\" alt=\"小Q手势拍照\" title=\"{captured_at}\">""",
        mimetype="text/html",
    )


@app.get("/api/photos/file/<filename>")
def latest_photo_file(filename: str):
    safe_name = secure_filename(filename)
    photo = PHOTO_ROOT / safe_name
    if not safe_name or not photo.exists() or photo.parent != PHOTO_ROOT:
        return jsonify({"ok": False, "error": "photo not found"}), 404
    return send_file(photo, mimetype="image/jpeg", max_age=0, conditional=True)


@app.errorhandler(413)
def file_too_large(_error):
    return jsonify({"ok": False, "error": "file is too large"}), 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
