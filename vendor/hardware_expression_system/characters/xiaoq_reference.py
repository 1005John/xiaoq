"""Reusable XiaoQ expression reference data.

This module is pure data.
It does not import pygame.
It does not start product services.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class XiaoQFaceGeometry:
    source: str
    screen_width: int
    screen_height: int
    legacy_fps_target: int
    latest_fps_target: int
    face_center_x: int
    face_center_y: int
    eye_radius_x: int
    eye_radius_y: int
    eye_center_gap: int
    mouth_width_ratio: float

    @property
    def eye_width(self) -> int:
        return self.eye_radius_x * 2

    @property
    def eye_height(self) -> int:
        return self.eye_radius_y * 2

    @property
    def mouth_width_px(self) -> int:
        return round(self.eye_center_gap * self.mouth_width_ratio)


XIAOQ_NEON_REFERENCE_GEOMETRY = XiaoQFaceGeometry(
    source="32_cubicle_npc/pi_reference/robot_face_v10.py",
    screen_width=1280,
    screen_height=720,
    legacy_fps_target=60,
    latest_fps_target=30,
    face_center_x=640,
    face_center_y=310,
    eye_radius_x=160,
    eye_radius_y=170,
    eye_center_gap=580,
    mouth_width_ratio=0.65,
)

XIAOQ_CUTE_STYLE_GEOMETRY = XiaoQFaceGeometry(
    source="1005John/xiaoq:cute_face.py@d29add0",
    screen_width=1280,
    screen_height=720,
    legacy_fps_target=30,
    latest_fps_target=30,
    face_center_x=640,
    face_center_y=380,
    eye_radius_x=144,
    eye_radius_y=179,
    eye_center_gap=500,
    mouth_width_ratio=0.65,
)

XIAOQ_CUTE_REFERENCE_GEOMETRY = XIAOQ_CUTE_STYLE_GEOMETRY

XIAOQ_LEGACY_PARAM_NAMES = (
    "l_open",
    "r_open",
    "l_w",
    "r_w",
    "l_y",
    "r_y",
    "l_cut",
    "r_cut",
    "pupil_scale",
    "highlight",
    "brow_l",
    "brow_r",
    "blush",
)

XIAOQ_NEON_EXPRESSION_PARAMS = {
    "happy": (1.0, 1.0, 1.1, 1.1, -5, -5, 0.55, 0.55, 1.2, 0.9, -3, -3, 0.5),
    "laugh": (1.0, 1.0, 1.2, 1.2, -8, -8, 0.65, 0.65, 1.3, 1.0, -5, -5, 0.7),
    "excited": (1.3, 1.3, 1.0, 1.0, -5, -5, 0, 0, 1.4, 1.0, -4, -4, 0.3),
    "angry": (0.7, 0.7, 1.2, 1.2, 8, 8, 0, 0, 0.6, 0.3, 8, 8, 0),
    "surprised": (1.5, 1.5, 1.1, 1.1, -10, -10, 0, 0, 0.5, 0.95, -8, -8, 0),
    "scared": (1.3, 1.0, 0.9, 1.3, -8, -5, 0, 0, 0.7, 0.4, -5, 5, 0),
    "smile": (0.85, 0.85, 1.0, 1.0, 0, 0, 0.25, 0.25, 1.1, 0.8, -1, -1, 0.3),
    "relaxed": (0.8, 0.8, 1.0, 1.0, 0, 0, 0, 0, 0.9, 0.5, 0, 0, 0),
    "sad": (0.5, 0.5, 1.0, 1.0, 5, 5, 0, 0, 0.7, 0.3, 5, 5, 0),
    "sleepy": (0.15, 0.15, 1.0, 1.0, 0, 0, 0, 0, 0.5, 0.15, 2, 2, 0),
    "bored": (0.4, 0.6, 1.0, 0.8, 3, 0, 0, 0, 0.8, 0.3, 3, -1, 0),
    "idle": (1.0, 1.0, 1.0, 1.0, 0, 0, 0, 0, 1.0, 0.7, 0, 0, 0),
    "curious": (1.2, 0.8, 1.1, 0.9, -5, 2, 0, 0, 1.3, 0.8, -3, 2, 0),
    "thinking": (0.8, 0.5, 0.9, 0.7, -2, 3, 0, 0, 0.8, 0.4, 2, 6, 0),
    "confused": (1.0, 0.6, 1.0, 0.8, 0, 3, 0, 0, 0.9, 0.5, -2, 5, 0),
    "speaking": (0.95, 0.95, 1.0, 1.0, 0, 0, 0, 0, 1.0, 0.6, 0, 0, 0),
    "look_left": (1.0, 1.0, 1.15, 0.85, -2, -2, 0, 0, 1.0, 0.7, 0, 0, 0),
    "look_right": (1.0, 1.0, 0.85, 1.15, -2, -2, 0, 0, 1.0, 0.7, 0, 0, 0),
    "look_up": (1.1, 1.1, 0.9, 0.9, -10, -10, 0, 0, 1.0, 0.7, -2, -2, 0),
    "wink": (1.0, 0.0, 1.1, 1.0, -2, 0, 0, 0, 1.1, 0.8, -2, 0, 0.2),
    "blink": (0.0, 0.0, 1.0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0),
    "heart_eyes": (1.2, 1.2, 1.1, 1.1, -5, -5, 0.4, 0.4, 1.0, 0.9, -3, -3, 0.8),
    "star_eyes": (1.3, 1.3, 1.0, 1.0, -5, -5, 0, 0, 1.0, 1.0, -4, -4, 0.3),
}

XIAOQ_CUTE_EXPRESSION_PARAMS = {
    "idle": (0.90, 0.90, 1.00, 1.00, 0, 0, 0.00, 0.00, 1.00, 0.80, -2, -2, 0.55),
    "happy": (1.05, 1.05, 1.12, 1.12, -3, -3, 0.20, 0.20, 1.20, 1.00, -8, -8, 0.75),
    "laugh": (0.40, 0.40, 1.15, 1.15, 0, 0, 0.75, 0.75, 1.10, 0.90, -9, -9, 0.55),
    "excited": (1.20, 1.20, 1.20, 1.20, -5, -5, 0.00, 0.00, 1.40, 1.00, -10, -10, 0.55),
    "smile": (0.70, 0.70, 1.08, 1.08, 0, 0, 0.50, 0.50, 1.15, 0.85, -5, -5, 0.55),
    "relaxed": (0.65, 0.65, 1.00, 1.00, 0, 0, 0.00, 0.00, 0.90, 0.50, 0, 0, 0.55),
    "angry": (0.60, 0.60, 0.90, 0.90, 4, 4, 0.00, 0.00, 0.60, 0.30, 6, 6, 0.55),
    "sad": (0.45, 0.45, 0.95, 0.95, 5, 5, 0.00, 0.00, 0.70, 0.30, 10, 10, 0.00),
    "scared": (1.30, 0.90, 0.95, 1.20, -7, -3, 0.00, 0.00, 0.60, 0.40, -5, 7, 0.55),
    "sleepy": (0.08, 0.08, 0.85, 0.85, 0, 0, 0.00, 0.00, 1.00, 0.05, 2, 2, 0.00),
    "deep_sleep": (0.00, 0.00, 0.85, 0.85, 0, 0, 0.00, 0.00, 1.00, 0.00, 2, 2, 0.00),
    "bored": (0.40, 0.60, 0.95, 0.85, 3, 0, 0.00, 0.00, 0.80, 0.30, 3, -1, 0.55),
    "surprised": (1.40, 1.40, 1.05, 1.05, -6, -6, 0.00, 0.00, 0.50, 0.90, -12, -12, 0.55),
    "curious": (1.15, 0.85, 1.10, 1.00, -3, 2, 0.00, 0.00, 1.25, 0.80, -6, 3, 0.55),
    "thinking": (0.75, 0.40, 0.90, 0.80, -2, 3, 0.00, 0.30, 0.80, 0.35, 3, 7, 0.55),
    "confused": (1.00, 0.60, 1.00, 0.85, 0, 3, 0.00, 0.00, 0.85, 0.40, -3, 6, 0.55),
    "speaking": (0.90, 0.90, 1.00, 1.00, 0, 0, 0.00, 0.00, 1.00, 0.60, -2, -2, 0.55),
    "blink": (0.00, 0.00, 1.00, 1.00, 0, 0, 0.00, 0.00, 1.00, 0.00, -1, -1, 0.55),
    "wink": (0.90, 0.00, 1.05, 1.00, -1, 0, 0.00, 0.00, 1.10, 0.80, -4, 2, 0.55),
    "look_left": (0.90, 0.90, 0.85, 1.08, -1, -1, 0.00, 0.00, 0.95, 0.70, 0, 0, 0.55),
    "look_right": (0.90, 0.90, 1.08, 0.85, -1, -1, 0.00, 0.00, 0.95, 0.70, 0, 0, 0.55),
    "look_up": (1.05, 1.05, 0.90, 0.90, -8, -8, 0.00, 0.00, 0.95, 0.70, -2, -2, 0.55),
    "heart_eyes": (1.10, 1.10, 1.10, 1.10, -3, -3, 0.30, 0.30, 1.00, 0.90, -7, -7, 0.55),
    "star_eyes": (1.20, 1.20, 1.05, 1.05, -4, -4, 0.00, 0.00, 1.00, 1.00, -9, -9, 0.55),
}

XIAOQ_LEGACY_EXPRESSION_PARAMS = XIAOQ_NEON_EXPRESSION_PARAMS

XIAOQ_LEGACY_NPC_STATE_DEFAULT_EXPR = {
    "idle": "idle",
    "observe": "curious",
    "engaged": "happy",
    "warn": "bored",
    "sleep": "sleepy",
}

XIAOQ_LEGACY_VOICE_STATE_EXPR = {
    "idle": "idle",
    "listening": "curious",
    "thinking": "thinking",
    "speaking": "speaking",
}

XIAOQ_LEGACY_TRANSITION_RULES = {
    ("idle", "happy"): {"duration": 0.30, "easing": "ease_out_back"},
    ("idle", "excited"): {"duration": 0.25, "easing": "ease_out_back"},
    ("any", "surprised"): {"duration": 0.10, "easing": "linear"},
    ("surprised", "any"): {"duration": 0.60, "easing": "ease_in_out_sine"},
    ("any", "angry"): {"duration": 0.15, "easing": "ease_in_quad"},
    ("happy", "sad"): {"duration": 0.80, "easing": "ease_in_out_sine"},
    ("excited", "sad"): {"duration": 0.80, "easing": "ease_in_out_sine"},
    ("any", "sleepy"): {"duration": 1.00, "easing": "ease_in_out_sine"},
    ("sleepy", "surprised"): {"duration": 0.08, "easing": "linear"},
}

XIAOQ_LEGACY_COMMAND_TYPES = {
    "expression",
    "set_state",
    "set_mood",
    "set_theme",
    "voice_start",
    "voice_stop",
    "voice_tts",
    "voice_inject",
    "mobile_reply",
    "tts_end",
    "persona_set",
    "persona_toggle",
    "set_personality",
    "character_set",
    "style_set",
    "look_at",
}

XIAOQ_LEGACY_RENDER_EFFECT_COMMAND_TYPES = {
    "trigger_vfx",
    "set_ambient",
    "trigger_squash",
    "set_pupil_mode",
}

XIAOQ_PRODUCT_OWNED_COMMAND_TYPES = {
    "card_show",
    "card_hide",
    "screenshot",
    "auto",
    "mobile_ping",
    "gimbal_manual",
    "gimbal_move",
    "gimbal_auto",
    "face_register",
    "face_target_select",
    "face_delete",
    "face_auth_snapshot",
    "camera_reserve",
    "camera_release",
    "volume_set",
}
