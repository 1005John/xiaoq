"""Bluebot expression style layer.

The state machine produces canonical expression frames.
This module adjusts them for Bluebot's character language.
"""

from __future__ import annotations

import math
from dataclasses import replace

from ..models import ExpressionFrame, ExpressionIntent


def style_bluebot_frame(
    frame: ExpressionFrame,
    intent: ExpressionIntent | None = None,
    now_ms: int = 0,
) -> ExpressionFrame:
    """Apply Bluebot-specific expression details to a canonical frame."""

    variant = intent.visual_variant if intent else frame.expression_id
    pulse = _pulse(now_ms, 0.003, 0)
    slow = _pulse(now_ms, 0.0016, 1.2)
    quick = _pulse(now_ms, 0.008, 0.4)
    sway = _wave(now_ms, 0.0022, 0.0)

    if variant == "idle_wait":
        blink = max(0.0, 1.0 - abs(now_ms % 3200 - 1750) / 110.0)
        breath = _pulse(now_ms, 0.0019, 0.0)
        return replace(
            frame,
            eye_shape="official_eye_vertical",
            eye_open_left=(0.95 + 0.05 * breath) * (1.0 - 0.78 * blink),
            eye_open_right=(0.95 + 0.05 * breath) * (1.0 - 0.78 * blink),
            eye_offset_x=0.0,
            eye_offset_y=-12.0,
            eye_scale=1.0,
            mouth="official_mouth_smile_block",
            mouth_open=0.22,
            mouth_smile=0.46,
            cheek=0.0,
            face_brightness=0.86 + 0.04 * slow,
            screen_pulse=0.16 + 0.04 * slow,
            accent="#64eaff",
        )
    if variant == "planning_scan":
        survey = _keyframe(now_ms, 3200, ((0, 0), (260, -18), (590, -18), (1130, 18), (1460, 18), (1890, 0), (3200, 0)))
        focus = min(1.0, abs(survey) / 18.0)
        return replace(
            frame,
            eye_shape="official_eye_work",
            eye_open_left=1.0 - 0.02 * focus,
            eye_open_right=1.0 - 0.02 * focus,
            eye_offset_x=survey,
            eye_offset_y=0.0,
            eye_scale=0.95,
            mouth="official_mouth_smile_block",
            mouth_open=0.24,
            mouth_smile=0.12,
            mouth_scale=0.94,
            mouth_bow=0.035 - 0.07 * focus,
            mouth_offset_y=3.0 * focus,
            cheek=0.0,
            face_brightness=0.88,
            screen_pulse=0.12,
        )
    if variant == "expert_routing":
        left = _gesture(now_ms, 3000, 180, 300, 300)
        right = _gesture(now_ms - 180, 3000, 180, 300, 300)
        handoff = max(left, right)
        return replace(
            frame,
            eye_shape="official_eye_work",
            eye_open_left=1.0,
            eye_open_right=1.0,
            eye_offset_x=0.0,
            eye_offset_y=0.0,
            eye_shift_left=20.0 * left,
            eye_shift_right=-20.0 * right,
            eye_scale=1.0,
            mouth="official_mouth_smile_block",
            mouth_open=0.24,
            mouth_smile=0.12,
            mouth_scale=0.90 + 0.08 * handoff,
            mouth_bow=0.035 + 0.06 * right,
            mouth_offset_y=-4.0 * right,
            cheek=0.0,
            face_brightness=0.89,
            screen_pulse=0.12,
        )
    if variant == "skill_match":
        compare = _keyframe(now_ms, 2900, ((0, 0), (280, 1), (550, 0), (850, -1), (1130, 0), (2900, 0)))
        return replace(
            frame,
            eye_shape="official_eye_work",
            eye_open_left=0.90 + 0.10 * compare,
            eye_open_right=0.90 - 0.10 * compare,
            eye_offset_x=0.0,
            eye_offset_y=0.0,
            eye_scale=0.99,
            mouth="official_mouth_smile_block",
            mouth_open=0.24,
            mouth_smile=0.18,
            mouth_bow=0.18,
            cheek=0.0,
            face_brightness=0.90,
            screen_pulse=0.12,
        )
    if variant == "knowledge_retrieve":
        dip = _gesture(now_ms, 3100, 300, 650, 450)
        return replace(
            frame,
            eye_shape="official_eye_work",
            eye_open_left=0.98,
            eye_open_right=0.98,
            eye_offset_x=0.0,
            eye_offset_y=22.0 * dip,
            eye_scale=0.99,
            mouth="official_mouth_smile_block",
            mouth_open=0.26,
            mouth_smile=0.10,
            mouth_scale=0.94,
            mouth_bow=0.035,
            mouth_offset_y=3.0 * dip,
            cheek=0.0,
            face_brightness=0.88,
            screen_pulse=0.12,
        )
    if variant == "tool_activity":
        engage = _gesture(now_ms, 1900, 150, 120, 220)
        return replace(
            frame,
            eye_shape="official_eye_work",
            eye_open_left=1.0 - 0.28 * engage,
            eye_open_right=1.0 - 0.28 * engage,
            eye_offset_x=0.0,
            eye_offset_y=0.0,
            eye_scale=0.90,
            mouth="official_mouth_smile_block",
            mouth_open=0.24,
            mouth_smile=0.12,
            mouth_scale=0.98 - 0.20 * engage,
            mouth_bow=0.035 - 0.12 * engage,
            cheek=0.0,
            face_brightness=0.89,
            screen_pulse=0.12,
        )
    if variant == "progress":
        form = _gesture(now_ms, 2900, 550, 120, 550)
        return replace(
            frame,
            eye_shape="official_eye_work",
            eye_open_left=1.0,
            eye_open_right=1.0,
            eye_offset_x=0.0,
            eye_offset_y=0.0,
            eye_scale=1.0 + 0.15 * form,
            mouth="official_mouth_smile_block",
            mouth_open=0.26,
            mouth_smile=0.12,
            mouth_offset_y=-14.0 * form,
            mouth_scale=1.0 + 0.12 * form,
            mouth_bow=0.12,
            cheek=0.0,
            face_brightness=0.89,
            screen_pulse=0.12,
            progress=0.0,
        )
    if variant == "automation_armed":
        arm = _gesture_once(now_ms, 180, 350, 300)
        ready = _gesture(now_ms - 3000, 6200, 170, 200, 260)
        breath = _pulse(now_ms, 0.001, 0.0)
        return replace(
            frame,
            eye_shape="official_eye_work",
            eye_open_left=0.91 + 0.03 * breath - 0.04 * ready,
            eye_open_right=0.91 + 0.03 * breath - 0.04 * ready,
            eye_offset_x=0.0,
            eye_offset_y=7.0 + 19.0 * arm + 6.0 * ready,
            eye_convergence=14.0 + 8.0 * ready,
            eye_scale=0.97,
            mouth="official_mouth_smile_block",
            mouth_open=0.25,
            mouth_smile=0.20,
            mouth_scale=0.86 + 0.05 * arm - 0.08 * ready,
            mouth_bow=0.08,
            cheek=0.0,
            face_brightness=0.88,
            screen_pulse=0.11,
        )
    if variant == "case_replay":
        echo = _keyframe(now_ms, 3300, ((0, 0), (240, -22), (430, -22), (680, 0), (980, -10), (1120, -10), (1370, 0), (3300, 0)))
        recall = min(1.0, abs(echo) / 22.0)
        return replace(
            frame,
            eye_shape="official_eye_work",
            eye_open_left=0.86,
            eye_open_right=0.94,
            eye_offset_x=echo,
            eye_offset_y=-14.0 * recall,
            eye_scale=0.96,
            mouth="official_mouth_smile_block",
            mouth_open=0.28,
            mouth_smile=0.14,
            mouth_bow=0.09 + 0.04 * recall,
            mouth_scale=0.92 + 0.06 * recall,
            mouth_offset_y=-4.0 * recall,
            cheek=0.0,
            face_brightness=0.88,
            screen_pulse=0.12,
        )
    if variant == "security_check":
        first = _gesture(now_ms, 3300, 180, 100, 180)
        second = _gesture(now_ms - 960, 3300, 180, 100, 180)
        inspect = max(first, second)
        return replace(
            frame,
            eye_shape="official_eye_work",
            eye_open_left=0.92 - 0.07 * inspect,
            eye_open_right=0.92 - 0.07 * inspect,
            eye_offset_x=-16.0 * first + 16.0 * second,
            eye_offset_y=0.0,
            eye_scale=0.92,
            mouth="official_mouth_smile_block",
            mouth_open=0.22,
            mouth_smile=0.06,
            mouth_scale=0.82,
            mouth_bow=0.035 - 0.05 * inspect,
            cheek=0.0,
            face_brightness=0.86,
            screen_pulse=0.11,
        )
    if variant == "confirmation":
        ask = _gesture(now_ms, 4000, 180, 1200, 300)
        mouth_ask = _gesture(now_ms - 180, 4000, 180, 1200, 300)
        return replace(
            frame,
            eye_shape="official_eye_work",
            eye_open_left=1.0,
            eye_open_right=1.0,
            eye_offset_x=0.0,
            eye_offset_y=-30.0 * ask,
            eye_scale=1.0,
            mouth="official_mouth_expectant",
            mouth_open=0.30,
            mouth_smile=-0.04,
            mouth_scale=0.96 + 0.26 * mouth_ask,
            mouth_offset_y=-5.0 * mouth_ask,
            mouth_bow=-0.10,
            cheek=0.0,
            face_brightness=0.91,
            screen_pulse=0.13,
        )
    if variant == "completed":
        settle = _smoothstep(now_ms / 360.0)
        bounce = _gesture_once(now_ms, 180, 100, 320)
        return replace(
            frame,
            eye_shape="official_eye_bright_dot",
            eye_open_left=1.0,
            eye_open_right=1.0,
            eye_offset_x=0.0,
            eye_offset_y=-12.0 * settle - 9.0 * bounce,
            eye_scale=1.0 + 0.08 * bounce,
            mouth="official_mouth_big_smile",
            mouth_open=0.63 + 0.13 * bounce,
            mouth_smile=1.0,
            cheek=0.0,
            face_brightness=1.0,
            screen_pulse=0.22 + 0.04 * bounce,
            accent="#7dfffb",
        )
    if variant == "failed":
        settle = _smoothstep(now_ms / 420.0)
        recovery = _gesture_once(now_ms, 220, 80, 380)
        return replace(
            frame,
            eye_shape="official_eye_sorry_vertical",
            eye_open_left=1.0 - 0.06 * settle,
            eye_open_right=1.0 - 0.06 * settle,
            eye_offset_x=0.0,
            eye_offset_y=17.0 * settle + 4.0 * recovery,
            eye_scale=1.0 - 0.02 * settle + 0.015 * recovery,
            mouth="official_mouth_sorry_pout",
            mouth_open=0.30 + 0.10 * recovery,
            mouth_smile=-0.40,
            face_brightness=0.80 + 0.02 * recovery,
            screen_pulse=0.05,
            cheek=0.0,
            accent="#ff96a2",
        )
    if variant == "failed_stress_x":
        recovery = _pulse(now_ms, 0.0038, 0.2)
        tremble = _wave(now_ms, 0.015, 1.3)
        return replace(
            frame,
            eye_shape="failed_stress_x_v24",
            eye_open_left=1.0,
            eye_open_right=1.0,
            eye_offset_x=1.0 * tremble,
            eye_offset_y=-2.0 + 2.5 * recovery,
            eye_scale=0.985 - 0.018 * recovery,
            mouth="failed_stress_capsule_v24",
            mouth_open=0.30 + 0.06 * recovery,
            mouth_smile=-0.24,
            face_brightness=0.78 + 0.04 * recovery,
            screen_pulse=0.18 + 0.07 * recovery,
            cheek=0.0,
            accent="#ff96a2",
        )
    if variant == "blocked":
        hold = _gesture(now_ms, 2600, 190, 430, 300)
        tremble = _wave(now_ms, 0.023, 0.7) * hold
        return replace(
            frame,
            eye_shape="official_eye_squeeze",
            eye_open_left=0.83 - 0.20 * hold,
            eye_open_right=0.83 - 0.20 * hold,
            eye_offset_x=1.2 * tremble,
            eye_offset_y=3.0 + 6.0 * hold,
            eye_scale=1.0 + 0.015 * hold,
            mouth="official_mouth_wobble",
            mouth_open=0.22 - 0.05 * hold,
            mouth_smile=-0.22,
            mouth_scale=1.0 - 0.08 * hold,
            face_brightness=0.80 + 0.05 * hold,
            screen_pulse=0.10 + 0.04 * hold,
            cheek=0.0,
            accent="#ffd36c",
        )
    if variant == "network_warning":
        attempt = _gesture(now_ms, 3900, 180, 420, 350)
        return replace(
            frame,
            eye_shape="official_eye_work",
            eye_open_left=0.90,
            eye_open_right=0.90,
            eye_offset_x=0.0,
            eye_offset_y=0.0,
            eye_convergence=20.0 * attempt,
            eye_scale=0.99,
            mouth="official_mouth_wobble",
            mouth_open=0.24,
            mouth_smile=-0.12,
            mouth_scale=0.95 - 0.15 * attempt,
            mouth_bow=-0.25,
            cheek=0.0,
            face_brightness=0.84,
            screen_pulse=0.10,
        )
    if variant == "human_help":
        held = _pulse(now_ms, 0.0042, 0.7)
        breath = _pulse(now_ms, 0.0017, 2.0)
        breath_anchor = _pulse(1400, 0.0017, 2.0)
        held_anchor = _pulse(1400, 0.0042, 0.7)
        emotion_breath = breath - breath_anchor
        emotion_held = held - held_anchor
        appeal = _gesture_once(now_ms, 180, 620, 300)
        mouth_appeal = _gesture_once(max(0, now_ms - 100), 180, 620, 300)
        return replace(
            frame,
            eye_shape="official_eye_help",
            eye_open_left=1.0,
            eye_open_right=1.0,
            eye_offset_x=0.0,
            eye_offset_y=2.0 + 16.0 * emotion_breath + 13.0 * appeal,
            eye_convergence=14.0 * appeal,
            eye_scale=1.0 + 0.12 * emotion_breath,
            mouth="official_mouth_help_pout",
            mouth_open=0.36 + 0.14 * emotion_held - 0.08 * mouth_appeal,
            mouth_smile=-0.28,
            mouth_scale=1.0 + 0.08 * mouth_appeal,
            face_brightness=0.90 + 0.04 * slow,
            screen_pulse=0.18 + 0.06 * emotion_breath,
            cheek=0.0,
            accent="#ffeaa4",
        )
    return frame


def _pulse(now_ms: int, speed: float, phase: float) -> float:
    return 0.5 + 0.5 * math.sin(now_ms * speed + phase)


def _wave(now_ms: int, speed: float, phase: float) -> float:
    return math.sin(now_ms * speed + phase)


def _gesture(now_ms: int, period_ms: int, attack_ms: int, hold_ms: int, release_ms: int) -> float:
    phase = now_ms % period_ms
    if phase < attack_ms:
        return _smoothstep(phase / attack_ms)
    if phase < attack_ms + hold_ms:
        return 1.0
    if phase < attack_ms + hold_ms + release_ms:
        return 1.0 - _smoothstep((phase - attack_ms - hold_ms) / release_ms)
    return 0.0


def _gesture_once(now_ms: int, attack_ms: int, hold_ms: int, release_ms: int) -> float:
    if now_ms < attack_ms:
        return _smoothstep(now_ms / attack_ms)
    if now_ms < attack_ms + hold_ms:
        return 1.0
    if now_ms < attack_ms + hold_ms + release_ms:
        return 1.0 - _smoothstep((now_ms - attack_ms - hold_ms) / release_ms)
    return 0.0


def _smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def _keyframe(now_ms: int, period_ms: int, points: tuple[tuple[int, float], ...]) -> float:
    phase = now_ms % period_ms
    for (start_ms, start_value), (end_ms, end_value) in zip(points, points[1:]):
        if phase <= end_ms:
            amount = _smoothstep((phase - start_ms) / max(1, end_ms - start_ms))
            return start_value + (end_value - start_value) * amount
    return points[-1][1]
