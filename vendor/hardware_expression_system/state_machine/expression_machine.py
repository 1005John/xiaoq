"""Canonical expression state machine.

The product owns business logic.
This machine owns expression state only.
"""

from __future__ import annotations

import math
import time
from dataclasses import replace

from ..models import ExpressionFrame, StateConfig


MASCOT_STATES = (
    "BOOTING",
    "IDLE",
    "AWARE",
    "WAKE",
    "LISTENING",
    "LISTEN_PROMPT",
    "THINKING",
    "SPEAKING",
    "SPEAK_EXCITED",
    "FULFILLED",
    "HAPPY_SMALL",
    "HAPPY_BIG",
    "CONFUSED_SOFT",
    "CLARIFY",
    "SAD_SOFT",
    "CONCERNED",
    "SLEEPY",
    "SLEEP",
    "PAIRING",
    "OTA",
    "LOW_BATTERY",
    "ERROR",
    "SHUTDOWN",
)

EVENT_ALIASES = {
    "TAP": "TOUCH",
    "HAPPY": "TASK_SUCCESS",
    "CONFUSED": "NEED_CLARIFICATION",
    "SAD": "TASK_FAIL",
    "NLP_DONE": "RESPONSE_READY",
    "AUDIO_END": "TTS_END",
    "PAIRING": "PAIRING_START",
    "OTA": "OTA_START",
    "CHARGE": "CHARGING",
}

STATE_ALIASES = {
    "BOOT": "BOOTING",
    "OTA_UPDATING": "OTA",
    "HAPPY": "HAPPY_BIG",
    "CONFUSED": "CONFUSED_SOFT",
    "ERROR_ALERT": "ERROR",
    "LOW": "LOW_BATTERY",
}

STATE_CONFIG = {
    "BOOTING": StateConfig("开机", "system", "booting", 100, 1800, "IDLE"),
    "IDLE": StateConfig("待机", "interaction", "idle_soft", 10, 0, None),
    "AWARE": StateConfig("注意到人", "interaction", "idle_watch", 20, 5200, "IDLE"),
    "WAKE": StateConfig("唤醒", "interaction", "wake_surprise", 45, 850, "LISTENING"),
    "LISTENING": StateConfig("聆听", "interaction", "listen_focus", 40, 9000, "LISTEN_PROMPT"),
    "LISTEN_PROMPT": StateConfig("等待补充", "interaction", "listen_prompt", 35, 5200, "IDLE"),
    "THINKING": StateConfig("思考", "interaction", "think_scan", 50, 8500, "CLARIFY"),
    "SPEAKING": StateConfig("播报", "interaction", "speak_warm", 55, 15000, "IDLE"),
    "SPEAK_EXCITED": StateConfig("开心播报", "interaction", "speak_excited", 56, 10000, "IDLE"),
    "FULFILLED": StateConfig("完成", "performance", "happy_big", 60, 1700, "IDLE"),
    "HAPPY_SMALL": StateConfig("轻开心", "emotion", "happy_small", 30, 1800, "IDLE"),
    "HAPPY_BIG": StateConfig("开心", "emotion", "happy_big", 38, 2200, "IDLE"),
    "CONFUSED_SOFT": StateConfig("疑惑", "emotion", "confused_soft", 36, 2600, "LISTEN_PROMPT"),
    "CLARIFY": StateConfig("追问", "interaction", "clarify", 42, 3200, "LISTEN_PROMPT"),
    "SAD_SOFT": StateConfig("失落", "emotion", "sad_soft", 32, 2600, "IDLE"),
    "CONCERNED": StateConfig("关切", "emotion", "concerned", 34, 3800, "IDLE"),
    "SLEEPY": StateConfig("困倦", "system", "sleepy", 70, 2600, "SLEEP"),
    "SLEEP": StateConfig("休眠", "system", "sleep", 75, 0, None),
    "PAIRING": StateConfig("配网", "system", "pairing_scan", 80, 0, None),
    "OTA": StateConfig("升级", "system", "ota_progress", 90, 0, None),
    "LOW_BATTERY": StateConfig("低电量", "system", "low_battery", 92, 0, None),
    "ERROR": StateConfig("异常", "system", "error_alert", 100, 0, None),
    "SHUTDOWN": StateConfig("关机", "system", "sleep", 110, 0, None),
}

TRANSITIONS = {
    "BOOTING": {"BOOT_DONE": "IDLE", "ERROR": "ERROR"},
    "IDLE": {
        "PRESENCE_DETECTED": "AWARE",
        "TOUCH": "HAPPY_SMALL",
        "DOUBLE_TAP": "HAPPY_BIG",
        "WAKE_WORD": "WAKE",
        "VOICE_START": "LISTENING",
        "NLU_THINKING": "THINKING",
        "RESPONSE_READY": "SPEAKING",
        "TTS_START": "SPEAKING",
        "TASK_SUCCESS": "FULFILLED",
        "TASK_FAIL": "SAD_SOFT",
        "NEED_CLARIFICATION": "CLARIFY",
    },
    "AWARE": {
        "PRESENCE_LOST": "IDLE",
        "TOUCH": "HAPPY_SMALL",
        "WAKE_WORD": "WAKE",
        "VOICE_START": "LISTENING",
        "NO_SPEECH_TIMEOUT": "IDLE",
    },
    "WAKE": {
        "VOICE_START": "LISTENING",
        "NO_SPEECH_TIMEOUT": "LISTEN_PROMPT",
        "TTS_START": "SPEAKING",
    },
    "LISTENING": {
        "VOICE_END": "THINKING",
        "ASR_DONE": "THINKING",
        "NLU_THINKING": "THINKING",
        "RESPONSE_READY": "SPEAKING",
        "TTS_START": "SPEAKING",
        "TASK_SUCCESS": "FULFILLED",
        "NEED_CLARIFICATION": "CLARIFY",
        "NO_SPEECH_TIMEOUT": "LISTEN_PROMPT",
    },
    "LISTEN_PROMPT": {
        "VOICE_START": "LISTENING",
        "WAKE_WORD": "LISTENING",
        "TOUCH": "AWARE",
        "NEED_CLARIFICATION": "CLARIFY",
        "NO_SPEECH_TIMEOUT": "IDLE",
    },
    "THINKING": {
        "RESPONSE_READY": "SPEAKING",
        "TTS_START": "SPEAKING",
        "TASK_SUCCESS": "FULFILLED",
        "TASK_FAIL": "SAD_SOFT",
        "NEED_CLARIFICATION": "CLARIFY",
    },
    "SPEAKING": {
        "TTS_END": "IDLE",
        "WAKE_WORD": "LISTENING",
        "VOICE_START": "LISTENING",
        "TASK_SUCCESS": "FULFILLED",
        "TASK_FAIL": "CONCERNED",
    },
    "SPEAK_EXCITED": {"TTS_END": "FULFILLED", "WAKE_WORD": "LISTENING", "VOICE_START": "LISTENING"},
    "FULFILLED": {"WAKE_WORD": "WAKE", "VOICE_START": "LISTENING", "TOUCH": "HAPPY_SMALL", "DOUBLE_TAP": "HAPPY_BIG", "TTS_START": "SPEAKING"},
    "HAPPY_SMALL": {"WAKE_WORD": "WAKE", "VOICE_START": "LISTENING", "TOUCH": "HAPPY_SMALL", "DOUBLE_TAP": "HAPPY_BIG", "TTS_START": "SPEAKING"},
    "HAPPY_BIG": {"WAKE_WORD": "WAKE", "VOICE_START": "LISTENING", "TOUCH": "HAPPY_SMALL", "DOUBLE_TAP": "HAPPY_BIG", "TTS_START": "SPEAKING"},
    "CONFUSED_SOFT": {"VOICE_START": "LISTENING", "WAKE_WORD": "LISTENING", "TOUCH": "AWARE", "RESPONSE_READY": "SPEAKING", "TTS_START": "SPEAKING", "TASK_FAIL": "SAD_SOFT"},
    "CLARIFY": {"VOICE_START": "LISTENING", "WAKE_WORD": "LISTENING", "TOUCH": "AWARE", "RESPONSE_READY": "SPEAKING", "TTS_START": "SPEAKING", "TASK_FAIL": "SAD_SOFT"},
    "SAD_SOFT": {"TOUCH": "AWARE", "WAKE_WORD": "WAKE", "VOICE_START": "LISTENING"},
    "CONCERNED": {"TOUCH": "AWARE", "WAKE_WORD": "WAKE", "VOICE_START": "LISTENING", "TASK_SUCCESS": "FULFILLED"},
    "SLEEPY": {"SLEEP": "SLEEP", "WAKE_WORD": "WAKE", "WAKE_FROM_SLEEP": "WAKE", "TOUCH": "WAKE"},
    "SLEEP": {"WAKE_WORD": "WAKE", "WAKE_FROM_SLEEP": "WAKE", "TOUCH": "WAKE"},
    "PAIRING": {"PAIRING_DONE": "IDLE", "RESET": "IDLE"},
    "OTA": {"OTA_DONE": "IDLE", "RESET": "IDLE", "ERROR": "ERROR"},
    "LOW_BATTERY": {"CHARGING": "IDLE", "SLEEP": "SLEEP", "RESET": "IDLE"},
    "ERROR": {"RECOVER": "IDLE", "RESET": "IDLE", "SLEEP": "SLEEP"},
    "SHUTDOWN": {"RESET": "BOOTING"},
}

LEGACY_EXPRESSION_STATE = {
    "idle": "IDLE",
    "smile": "HAPPY_SMALL",
    "relaxed": "IDLE",
    "happy": "HAPPY_BIG",
    "laugh": "HAPPY_BIG",
    "excited": "SPEAK_EXCITED",
    "surprised": "WAKE",
    "curious": "AWARE",
    "thinking": "THINKING",
    "speaking": "SPEAKING",
    "talking": "SPEAKING",
    "confused": "CONFUSED_SOFT",
    "sad": "SAD_SOFT",
    "bored": "SLEEPY",
    "sleepy": "SLEEPY",
    "sleep": "SLEEP",
    "angry": "ERROR",
    "scared": "CONCERNED",
    "wink": "HAPPY_SMALL",
    "blink": "IDLE",
    "look_left": "AWARE",
    "look_right": "AWARE",
    "look_up": "AWARE",
    "heart_eyes": "HAPPY_BIG",
    "star_eyes": "FULFILLED",
}

LEGACY_SET_STATE = {
    "boot": "BOOTING",
    "booting": "BOOTING",
    "idle": "IDLE",
    "observe": "AWARE",
    "aware": "AWARE",
    "engaged": "LISTENING",
    "listening": "LISTENING",
    "thinking": "THINKING",
    "speaking": "SPEAKING",
    "talking": "SPEAKING",
    "warn": "CONCERNED",
    "sleep": "SLEEP",
    "sleepy": "SLEEPY",
    "pairing": "PAIRING",
    "ota": "OTA",
    "ota_updating": "OTA",
    "low_battery": "LOW_BATTERY",
    "error": "ERROR",
}

LEGACY_MOOD_STATE = {
    "neutral": "IDLE",
    "idle": "IDLE",
    "happy": "HAPPY_SMALL",
    "curious": "AWARE",
    "focused": "THINKING",
    "confused": "CONFUSED_SOFT",
    "concerned": "CONCERNED",
    "sad": "SAD_SOFT",
    "sleepy": "SLEEPY",
    "alert": "ERROR",
}


def normalize_event(event: object) -> str:
    if event is None:
        return ""
    key = str(event).strip().upper()
    return EVENT_ALIASES.get(key, key)


def normalize_state(state: object) -> str:
    if state is None:
        return "IDLE"
    key = str(state).strip().upper()
    return STATE_ALIASES.get(key, key)


def resolve_legacy_command(command: object) -> dict[str, str | None] | None:
    if command is None:
        return None
    if isinstance(command, str):
        key = command.strip().lower()
        return {"state": LEGACY_EXPRESSION_STATE.get(key) or normalize_state(key)}
    if not isinstance(command, dict):
        return None

    command_type = str(command.get("type", "")).strip().lower()
    if command_type == "expression":
        key = str(command.get("name") or command.get("expression") or "").strip().lower()
        return {"state": LEGACY_EXPRESSION_STATE.get(key)}
    if command_type == "set_state":
        key = str(command.get("state") or command.get("name") or "").strip().lower()
        return {"state": LEGACY_SET_STATE.get(key)}
    if command_type == "set_mood":
        key = str(command.get("mood") or command.get("name") or "").strip().lower()
        return {"state": LEGACY_MOOD_STATE.get(key)}
    if command_type == "event":
        return {"event": normalize_event(command.get("name") or command.get("event"))}
    return None


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _wave(ms: float, speed: float, phase: float) -> float:
    return math.sin(ms * speed + phase)


def _pulse01(ms: float, speed: float, phase: float) -> float:
    return 0.5 + 0.5 * _wave(ms, speed, phase)


def _pseudo(index: int) -> float:
    x = math.sin(index * 12.9898 + 78.233) * 43758.5453
    return x - math.floor(x)


def _blink_value(ms: float, state_seed: int, disabled: bool) -> float:
    if disabled:
        return 1.0
    segment = math.floor(ms / 6500)
    period = 2800 + _pseudo(segment + state_seed) * 4700
    blink_ms = 120 + _pseudo(segment + state_seed + 5) * 90
    local = (ms + 1400 + _pseudo(state_seed) * 1100) % period
    if local > blink_ms:
        return 1.0
    t = local / blink_ms
    return _clamp(1.0 - math.sin(t * math.pi), 0.05, 1.0)


def _life_for_state(state: str, elapsed_ms: float) -> dict[str, float]:
    config = STATE_CONFIG.get(state, STATE_CONFIG["IDLE"])
    seed = config.priority + len(config.expression_id)
    sleepy = state in {"SLEEP", "SHUTDOWN"}
    system_locked = state in {"ERROR", "OTA", "PAIRING", "LOW_BATTERY"}
    return {
        "blink": _blink_value(elapsed_ms, seed, system_locked or sleepy),
        "gaze_x": 0.0 if system_locked else _wave(elapsed_ms, 0.0011, seed) * 16 + _wave(elapsed_ms, 0.00043, seed * 0.7) * 8,
        "gaze_y": 0.0 if system_locked else _wave(elapsed_ms, 0.001, seed + 1.8) * 5,
        "breath": 0.88 + _pulse01(elapsed_ms, 0.0018, seed) * 0.12,
        "micro_pause": 0.72 if _pseudo(math.floor(elapsed_ms / 26000) + seed) > 0.92 else 1.0,
    }


def _base_expression(state: str, elapsed_ms: float) -> ExpressionFrame:
    normalized = normalize_state(state)
    config = STATE_CONFIG.get(normalized, STATE_CONFIG["IDLE"])
    life = _life_for_state(normalized, elapsed_ms)
    blink = life["blink"] * life["micro_pause"]
    return ExpressionFrame(
        state=normalized,
        expression_id=config.expression_id,
        label=config.label,
        group=config.group,
        priority=config.priority,
        eye_shape="oval",
        eye_open_left=blink,
        eye_open_right=blink,
        eye_offset_x=life["gaze_x"],
        eye_offset_y=life["gaze_y"],
        eye_scale=1.0,
        brow_tilt=0.0,
        mouth="smile",
        mouth_open=0.28,
        mouth_smile=0.48,
        face_brightness=0.78 * life["breath"],
        screen_pulse=0.0,
        cheek=0.0,
        progress=0.0,
        accent="#7dfffb",
    )


def expression_for_state(state: str, elapsed_ms: float = 0.0) -> ExpressionFrame:
    normalized = normalize_state(state)
    elapsed = max(0.0, float(elapsed_ms or 0.0))
    base = _base_expression(normalized, elapsed)

    if normalized == "BOOTING":
        return replace(
            base,
            eye_open_left=_clamp(elapsed / 800, 0.08, 1.0),
            eye_open_right=_clamp((elapsed - 120) / 800, 0.08, 1.0),
            eye_offset_x=0.0,
            eye_offset_y=0.0,
            mouth="small",
            mouth_open=0.16 + _clamp(elapsed / 1000, 0.0, 1.0) * 0.22,
            face_brightness=0.28 + _clamp(elapsed / 1300, 0.0, 1.0) * 0.68,
            screen_pulse=_pulse01(elapsed, 0.014, 0),
        )
    if normalized == "AWARE":
        return replace(base, eye_open_left=1.0, eye_open_right=1.0, eye_offset_x=_wave(elapsed, 0.0022, 0) * 22, eye_offset_y=_wave(elapsed, 0.0017, 1.4) * 4, mouth="small", mouth_open=0.2, mouth_smile=0.38, face_brightness=0.86, screen_pulse=_pulse01(elapsed, 0.004, 0) * 0.28)
    if normalized == "WAKE":
        return replace(base, eye_open_left=1.0, eye_open_right=1.0, eye_offset_x=0.0, eye_offset_y=-2.0, eye_scale=1.12, mouth="o", mouth_open=0.66, mouth_smile=0.35, face_brightness=0.96, screen_pulse=0.75 + 0.25 * _pulse01(elapsed, 0.018, 0), cheek=0.28)
    if normalized == "LISTENING":
        return replace(base, eye_open_left=1.0, eye_open_right=1.0, eye_offset_x=_wave(elapsed, 0.003, 0.3) * 14, eye_offset_y=_wave(elapsed, 0.0022, 1) * 3, mouth="small", mouth_open=0.17, mouth_smile=0.25, face_brightness=0.92, screen_pulse=0.2 + 0.35 * _pulse01(elapsed, 0.006, 0))
    if normalized == "LISTEN_PROMPT":
        return replace(base, eye_open_left=1.0, eye_open_right=0.82, eye_offset_x=-8 + _wave(elapsed, 0.0025, 0) * 7, mouth="o", mouth_open=0.32 + 0.08 * _pulse01(elapsed, 0.004, 0), mouth_smile=0.16, brow_tilt=-0.3, face_brightness=0.84, screen_pulse=0.22)
    if normalized == "THINKING":
        return replace(base, eye_open_left=0.82, eye_open_right=0.82, eye_offset_x=_wave(elapsed, 0.0036, 0) * 28, eye_offset_y=_wave(elapsed, 0.004, 1.2) * 6, mouth="dot", mouth_open=0.22, mouth_smile=0.08, face_brightness=0.84, screen_pulse=0.25 + 0.55 * _pulse01(elapsed, 0.016, 0))
    if normalized == "SPEAKING":
        return replace(base, eye_open_left=1.0, eye_open_right=1.0, eye_offset_x=_wave(elapsed, 0.0012, 0) * 6, mouth="talk", mouth_open=0.3 + 0.58 * _pulse01(elapsed, 0.033, 0), mouth_smile=0.68, face_brightness=0.96, screen_pulse=0.25 + 0.35 * _pulse01(elapsed, 0.026, 2), cheek=0.12)
    if normalized == "SPEAK_EXCITED":
        return replace(base, eye_shape="arc", eye_open_left=1.0, eye_open_right=1.0, mouth="talk", mouth_open=0.44 + 0.52 * _pulse01(elapsed, 0.038, 0), mouth_smile=0.92, face_brightness=1.0, screen_pulse=0.45 + 0.45 * _pulse01(elapsed, 0.024, 1), cheek=0.42)
    if normalized in {"FULFILLED", "HAPPY_BIG"}:
        return replace(base, eye_shape="arc", eye_open_left=1.0, eye_open_right=1.0, mouth="smile", mouth_open=0.72, mouth_smile=1.0, face_brightness=1.0, screen_pulse=0.65 + 0.25 * _pulse01(elapsed, 0.014, 0), cheek=0.62)
    if normalized == "HAPPY_SMALL":
        return replace(base, eye_shape="arc", eye_open_left=1.0, eye_open_right=1.0, mouth="smile", mouth_open=0.42, mouth_smile=0.82, face_brightness=0.94, screen_pulse=0.36, cheek=0.36)
    if normalized == "CONFUSED_SOFT":
        return replace(base, eye_open_left=1.0, eye_open_right=0.56, eye_offset_x=-12.0, eye_offset_y=2.0, brow_tilt=-0.45, mouth="tilt", mouth_open=0.22, mouth_smile=0.12, face_brightness=0.78, screen_pulse=0.16 + 0.24 * _pulse01(elapsed, 0.005, 0))
    if normalized == "CLARIFY":
        return replace(base, eye_open_left=0.9, eye_open_right=1.0, eye_offset_x=_wave(elapsed, 0.0026, 0) * 10, brow_tilt=0.35, mouth="wave", mouth_open=0.22, mouth_smile=0.1, face_brightness=0.86, screen_pulse=0.2 + 0.25 * _pulse01(elapsed, 0.006, 1))
    if normalized == "SAD_SOFT":
        return replace(base, eye_open_left=0.55, eye_open_right=0.55, eye_offset_y=12.0, mouth="frown", mouth_open=0.26, mouth_smile=-0.55, face_brightness=0.62, screen_pulse=0.08, accent="#9fd8ff")
    if normalized == "CONCERNED":
        return replace(base, eye_open_left=0.72, eye_open_right=0.72, eye_offset_y=7.0, brow_tilt=-0.2, mouth="flat", mouth_open=0.16, mouth_smile=-0.12, face_brightness=0.72, screen_pulse=0.22 + 0.28 * _pulse01(elapsed, 0.006, 1.4), accent="#ffd36c")
    if normalized == "SLEEPY":
        return replace(base, eye_shape="closed", eye_open_left=0.18 + 0.08 * _pulse01(elapsed, 0.004, 0), eye_open_right=0.18 + 0.08 * _pulse01(elapsed, 0.004, 0.7), eye_offset_y=12.0, mouth="small", mouth_open=0.12, mouth_smile=0.14, face_brightness=0.42, screen_pulse=0.1)
    if normalized in {"SLEEP", "SHUTDOWN"}:
        return replace(base, eye_shape="closed", eye_open_left=0.06, eye_open_right=0.06, eye_offset_x=0.0, eye_offset_y=14.0, mouth="small", mouth_open=0.08, mouth_smile=0.08, face_brightness=0.12 if normalized == "SHUTDOWN" else 0.28, screen_pulse=0.0 if normalized == "SHUTDOWN" else 0.05)
    if normalized == "PAIRING":
        return replace(base, eye_shape="scan", eye_open_left=1.0, eye_open_right=1.0, eye_offset_x=_wave(elapsed, 0.012, 0) * 30, mouth="small", mouth_open=0.14, face_brightness=0.88, screen_pulse=_pulse01(elapsed, 0.014, 0), progress=_pulse01(elapsed, 0.004, 0))
    if normalized == "OTA":
        return replace(base, eye_shape="progress", eye_open_left=1.0, eye_open_right=1.0, eye_offset_x=0.0, eye_offset_y=0.0, mouth="flat", mouth_open=0.14, face_brightness=0.82, screen_pulse=(elapsed % 2600) / 2600, progress=(elapsed % 5200) / 5200, accent="#ffe071")
    if normalized == "LOW_BATTERY":
        return replace(base, eye_open_left=0.38, eye_open_right=0.38, eye_offset_y=12.0, mouth="flat", mouth_open=0.1, mouth_smile=-0.2, face_brightness=0.38, screen_pulse=0.12 + 0.22 * _pulse01(elapsed, 0.004, 1), progress=0.18, accent="#ffd36c")
    if normalized == "ERROR":
        return replace(base, eye_shape="x", eye_open_left=1.0, eye_open_right=1.0, eye_offset_x=0.0, eye_offset_y=0.0, mouth="flat", mouth_open=0.16, mouth_smile=-0.2, face_brightness=0.72 + 0.22 * _pulse01(elapsed, 0.028, 0), screen_pulse=0.25 + 0.75 * _pulse01(elapsed, 0.03, 1), accent="#ffe071")
    return base


def can_apply_external_gaze(state: str) -> bool:
    return normalize_state(state) not in {
        "BOOTING",
        "PAIRING",
        "OTA",
        "LOW_BATTERY",
        "ERROR",
        "SLEEPY",
        "SLEEP",
        "SHUTDOWN",
    }


class ExpressionMachine:
    def __init__(self, initial_state: str = "BOOTING", now_ms: int | None = None, event_cooldown_ms: int = 140, gaze_hold_ms: int = 2200) -> None:
        now = _now_ms() if now_ms is None else int(now_ms)
        normalized = normalize_state(initial_state)
        self.state = normalized if normalized in STATE_CONFIG else "BOOTING"
        self.state_started_at = now
        self.last_update_at = now
        self.last_transition_at = now
        self.last_event = ""
        self.last_event_at = -10**12
        self.event_cooldown_ms = event_cooldown_ms
        self.gaze_hold_ms = gaze_hold_ms
        self.external_gaze: dict[str, float] | None = None

    def dispatch(self, event: object, now_ms: int | None = None) -> bool:
        now = _now_ms() if now_ms is None else int(now_ms)
        normalized_event = normalize_event(event)
        if not normalized_event:
            return False
        if normalized_event == self.last_event and now - self.last_event_at < self.event_cooldown_ms and normalized_event not in {"ERROR", "RESET"}:
            return False
        next_state = self.next_state_for_event(normalized_event)
        self.last_event = normalized_event
        self.last_event_at = now
        if not next_state or next_state == self.state:
            return False
        self.set_state(next_state, now)
        return True

    def apply_legacy_command(self, command: object, now_ms: int | None = None) -> bool:
        resolved = resolve_legacy_command(command)
        if not resolved:
            return False
        event = resolved.get("event")
        if event:
            return self.dispatch(event, now_ms)
        state = resolved.get("state")
        if state:
            self.set_state(state, now_ms)
            return True
        return False

    def look_at(self, x: float, y: float, now_ms: int | None = None, hold_ms: int | None = None) -> None:
        now = _now_ms() if now_ms is None else int(now_ms)
        self.external_gaze = {
            "x": _clamp(float(x or 0), -1.0, 1.0),
            "y": _clamp(float(y or 0), -1.0, 1.0),
            "until_ms": now + (self.gaze_hold_ms if hold_ms is None else int(hold_ms)),
        }

    def clear_look_at(self) -> None:
        self.external_gaze = None

    def next_state_for_event(self, event: object) -> str | None:
        normalized_event = normalize_event(event)
        if normalized_event in {"RESET", "RECOVER"}:
            return "BOOTING" if self.state == "SHUTDOWN" else "IDLE"
        if normalized_event == "ERROR":
            return "ERROR"
        if normalized_event == "SHUTDOWN":
            return "SHUTDOWN"
        if self.state == "OTA":
            return TRANSITIONS["OTA"].get(normalized_event)
        if normalized_event == "OTA_START":
            return "OTA"
        if normalized_event == "LOW_BATTERY":
            return "LOW_BATTERY"
        if normalized_event == "PAIRING_START":
            return "PAIRING"
        if normalized_event == "SLEEP":
            return None if self.state == "SLEEP" else "SLEEPY"
        if normalized_event == "CHARGING" and self.state == "LOW_BATTERY":
            return "IDLE"
        return TRANSITIONS.get(self.state, {}).get(normalized_event)

    def set_state(self, state: object, now_ms: int | None = None) -> None:
        normalized = normalize_state(state)
        if normalized not in STATE_CONFIG:
            raise ValueError(f"Unknown mascot state: {state}")
        now = _now_ms() if now_ms is None else int(now_ms)
        self.state = normalized
        self.state_started_at = now
        self.last_update_at = now
        self.last_transition_at = now

    def update(self, now_ms: int | None = None) -> ExpressionFrame:
        now = _now_ms() if now_ms is None else int(now_ms)
        self.last_update_at = now
        config = STATE_CONFIG[self.state]
        elapsed = now - self.state_started_at
        if config.timeout_ms > 0 and elapsed >= config.timeout_ms and config.next_state:
            self.set_state(config.next_state, now)
        return self.get_expression(now)

    def get_expression(self, now_ms: int | None = None) -> ExpressionFrame:
        now = _now_ms() if now_ms is None else int(now_ms)
        frame = expression_for_state(self.state, now - self.state_started_at)
        return self._apply_external_gaze(frame, now)

    def _apply_external_gaze(self, frame: ExpressionFrame, now_ms: int) -> ExpressionFrame:
        if not self.external_gaze or now_ms >= self.external_gaze["until_ms"] or not can_apply_external_gaze(frame.state):
            return frame
        remaining = self.external_gaze["until_ms"] - now_ms
        fade = _clamp(remaining / 300, 0.0, 1.0) if remaining < 300 else 1.0
        target_x = self.external_gaze["x"] * 30
        target_y = self.external_gaze["y"] * 10
        return replace(
            frame,
            eye_offset_x=frame.eye_offset_x * (1 - fade) + target_x * fade,
            eye_offset_y=frame.eye_offset_y * (1 - fade) + target_y * fade,
            eye_open_left=max(frame.eye_open_left, 0.9),
            eye_open_right=max(frame.eye_open_right, 0.9),
        )
