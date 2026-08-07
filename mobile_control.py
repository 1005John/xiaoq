#!/usr/bin/env python3
"""Authenticated LAN API used by the XiaoQ HarmonyOS companion app."""

from __future__ import annotations

import base64
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
REMOTE_DEVICES_STATE_PATH = DATA_ROOT / "remote_devices.json"
TODOS_PATH = DATA_ROOT / "todos.json"
PORT = int(os.environ.get("XIAOQ_MOBILE_PORT", "8788"))
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


def meeting_tasks(filename: str) -> list[str]:
    """Extract user-editable action items from the standard meeting markdown."""
    path = MEETING_OUTPUT / filename
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return []
    section = content.split("## 待办事项", 1)
    if len(section) < 2:
        return []
    body = section[1].split("\n## ", 1)[0]
    tasks: list[str] = []
    for line in body.splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        cleaned = cleaned.lstrip("-* ").strip()
        cleaned = cleaned.removeprefix("[ ]").removeprefix("[x]").strip()
        cleaned = cleaned.split("：", 1)[-1].strip() if cleaned[:2].isdigit() and "：" in cleaned else cleaned
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


def process_voice_job(job_path: Path, source: Path) -> None:
    wav_path = source.with_suffix(".wav")
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
        if not send_command({"type": "voice_inject", "text": text}):
            raise RuntimeError("XiaoQ is not running")
        update_job(job_path, status="dispatched", transcript=text)
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
        send_command({"type": "camera_release"})

    def snapshot(self, timeout: float = VISION_CAPTURE_TIMEOUT) -> bytes:
        """Wait for the latest encoded frame without opening a second camera."""
        self.ensure_started()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self.lock:
                frame = self.frame
                error = self.error
            if error:
                raise RuntimeError(error)
            if frame:
                return frame
            time.sleep(0.05)
        raise RuntimeError("camera frame timeout")

    def _capture(self) -> None:
        camera = None
        try:
            import cv2
            from picamera2 import Picamera2

            # HailoFace exports a throttled JPEG in shared memory. Serving it
            # avoids opening a second Picamera2 while face/gesture inference is
            # active.
            shared_deadline = time.monotonic() + 2.0
            while not self.stop_event.is_set() and time.monotonic() < shared_deadline:
                try:
                    if SHARED_CAMERA_FRAME_PATH.exists() and (
                        time.time() - SHARED_CAMERA_FRAME_PATH.stat().st_mtime < 2.0
                    ):
                        while not self.stop_event.is_set():
                            try:
                                if time.time() - SHARED_CAMERA_FRAME_PATH.stat().st_mtime >= 2.0:
                                    break
                                frame = SHARED_CAMERA_FRAME_PATH.read_bytes()
                                if frame:
                                    with self.lock:
                                        self.frame = frame
                                time.sleep(1 / 15)
                            except OSError:
                                time.sleep(0.05)
                        return
                except OSError:
                    pass
                time.sleep(0.05)

            # No shared Hailo frame: explicitly reserve the camera and use the
            # existing phone-only capture path.
            send_command({"type": "camera_reserve"})
            time.sleep(0.6)

            camera = Picamera2()
            camera.configure(camera.create_preview_configuration(
                main={"size": (640, 360), "format": "RGB888"}, buffer_count=2,
            ))
            camera.start()
            while not self.stop_event.is_set():
                frame = cv2.flip(camera.capture_array(), 1)
                ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 72])
                if ok:
                    with self.lock:
                        self.frame = encoded.tobytes()
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
    return jsonify({"ok": True, "xiaoq_online": ws_online, "camera_error": camera_stream.error, **state})


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


@app.post("/api/vision")
def vision_chat():
    """Capture one frame, ask MiMo-V2.5, and optionally play it on XiaoQ."""
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text", "")).strip()
    speak = bool(payload.get("speak", False))
    if len(text) < 2 or len(text) > MAX_VISION_TEXT:
        return jsonify({"ok": False, "error": "text must contain 2-2000 characters"}), 400
    try:
        try:
            frame = camera_stream.snapshot()
        finally:
            # The model call only needs the captured JPEG, not the live camera.
            camera_stream.stop()
        reply = record_visual_remote_devices(record_visual_led_state(vision_reply(text, frame)))
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
    source = VOICE_ROOT / f"{job_id}{suffix}"
    uploaded.save(source)
    threading.Thread(target=process_voice_job, args=(job_path, source), daemon=True).start()
    return jsonify({"ok": True, "job_id": job_id, "status": "queued"}), 202


@app.get("/api/voice/<job_id>")
def voice_status(job_id: str):
    path = VOICE_ROOT / f"{secure_filename(job_id)}.json"
    job = read_json(path)
    if not job:
        return jsonify({"ok": False, "error": "job not found"}), 404
    return jsonify({"ok": True, "job": job})


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


@app.get("/api/camera/stream")
def camera_video():
    camera_stream.ensure_started()
    if camera_stream.error:
        return jsonify({"ok": False, "error": camera_stream.error}), 503
    return Response(camera_stream.generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


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
        return jsonify({"ok": True, "available": False, "filename": "", "captured_at": ""})
    metadata = read_json(latest)
    filename = secure_filename(str(metadata.get("filename", "")))
    photo = PHOTO_ROOT / filename if filename else None
    if not photo or not photo.exists():
        return jsonify({"ok": True, "available": False, "filename": "", "captured_at": ""})
    return jsonify({
        "ok": True,
        "available": True,
        "filename": filename,
        "captured_at": str(metadata.get("captured_at", "")),
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
