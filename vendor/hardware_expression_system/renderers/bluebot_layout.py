"""Bluebot expression layout.

The layout layer has no pygame dependency.
It lets tests validate safety before pixels are drawn.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..characters.xiaoq_reference import XIAOQ_CUTE_REFERENCE_GEOMETRY
from ..models import ExpressionFrame, ExpressionIntent, SafeRect, ScreenProfile
from ..screen import DEFAULT_SCREEN_PROFILE, get_safe_areas


@dataclass(frozen=True)
class LayoutRect:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2


@dataclass(frozen=True)
class BluebotVariantProfile:
    id: str
    motion_family: str
    activity_level: float
    accent: str = "#7dfffb"
    progress_enabled: bool = False


@dataclass(frozen=True)
class BluebotFaceLayout:
    screen: ScreenProfile
    visible: SafeRect
    expression_core: SafeRect
    face_rect: LayoutRect
    left_eye: LayoutRect
    right_eye: LayoutRect
    mouth: LayoutRect
    left_cheek: LayoutRect
    right_cheek: LayoutRect
    progress_rect: LayoutRect
    variant_profile: BluebotVariantProfile
    critical_rects: tuple[LayoutRect, ...]


VARIANT_PROFILES = {
    "idle_wait": BluebotVariantProfile("idle_wait", "breath", 0.2),
    "planning_scan": BluebotVariantProfile("planning_scan", "scan", 0.7),
    "expert_routing": BluebotVariantProfile("expert_routing", "orbit", 0.85),
    "skill_match": BluebotVariantProfile("skill_match", "match", 0.65),
    "knowledge_retrieve": BluebotVariantProfile("knowledge_retrieve", "retrieve", 0.65),
    "tool_activity": BluebotVariantProfile("tool_activity", "activity", 0.8),
    "progress": BluebotVariantProfile("progress", "progress", 0.7, progress_enabled=True),
    "automation_armed": BluebotVariantProfile("automation_armed", "timer", 0.35),
    "case_replay": BluebotVariantProfile("case_replay", "replay", 0.55),
    "security_check": BluebotVariantProfile("security_check", "verify", 0.7, "#ffd36c"),
    "confirmation": BluebotVariantProfile("confirmation", "confirm", 0.55),
    "completed": BluebotVariantProfile("completed", "complete", 0.65),
    "failed": BluebotVariantProfile("failed", "soft_fail", 0.35, "#ff96a2"),
    "failed_stress_x": BluebotVariantProfile("failed_stress_x", "stress_pressure", 0.62, "#ff96a2"),
    "blocked": BluebotVariantProfile("blocked", "stress_pressure", 0.72, "#ffd36c"),
    "network_warning": BluebotVariantProfile("network_warning", "network", 0.55, "#ffd36c"),
    "human_help": BluebotVariantProfile("human_help", "breath", 0.32, "#ffeaa4"),
    "stress_squeeze_candidate": BluebotVariantProfile("stress_squeeze_candidate", "stress_pressure", 0.72, "#bffcff"),
}

XIAOQ_CUTE_REFERENCE = {
    "eye_width": XIAOQ_CUTE_REFERENCE_GEOMETRY.eye_width,
    "eye_height": XIAOQ_CUTE_REFERENCE_GEOMETRY.eye_height,
    "eye_gap": XIAOQ_CUTE_REFERENCE_GEOMETRY.eye_center_gap,
    "mouth_width": XIAOQ_CUTE_REFERENCE_GEOMETRY.mouth_width_px,
}

BLUEBOT_OLED_SIZE_RATIO = 0.9


class BluebotLayoutEngine:
    """Convert an expression frame into Bluebot drawing geometry."""

    def __init__(self, screen: ScreenProfile | None = None) -> None:
        self.screen = screen or DEFAULT_SCREEN_PROFILE
        areas = get_safe_areas(self.screen)
        self.visible = areas["visible"]
        self.expression_core = areas["expression_core"]

    def layout(
        self,
        frame: ExpressionFrame,
        intent: ExpressionIntent | None = None,
        now_ms: int = 0,
    ) -> BluebotFaceLayout:
        profile = self.variant_profile(frame, intent)
        core = self.expression_core
        visible = self.visible
        phase = (now_ms % 100000) / 1000.0
        pulse = 0.5 + 0.5 * math.sin(phase * 2.2)
        eye_scale = self._clamp(frame.eye_scale, 0.72, 1.22)
        open_left = self._clamp(frame.eye_open_left, 0.06, 1.0)
        open_right = self._clamp(frame.eye_open_right, 0.06, 1.0)

        face_rect = LayoutRect(
            0,
            0,
            self.screen.width,
            self.screen.height,
        )

        is_failed_v21 = frame.eye_shape == "fail_v21"
        is_failed_v47 = frame.eye_shape == "fail_v47"
        is_failed_soft = frame.eye_shape.startswith("fail_soft")
        is_failed_sad_oval = frame.eye_shape.startswith("fail_sad_oval")
        is_failed_stress_x = frame.eye_shape == "failed_stress_x_v24"
        is_official = frame.eye_shape.startswith("official_eye")
        is_stress_squeeze = frame.eye_shape.startswith("stress_squeeze")
        is_puppy_squeeze = frame.eye_shape.startswith("puppy_squeeze")
        is_wide_pressure = frame.eye_shape.startswith("wide_pressure")

        if is_official:
            eye_scale *= 1.415
            eye_gap = self.screen.width * 0.350 - 2.0 * self._clamp(frame.eye_convergence, 0.0, 24.0)
            eye_y = self.screen.height * 0.442 + frame.eye_offset_y
            left_x = self.screen.width / 2 - eye_gap / 2 + frame.eye_offset_x + frame.eye_shift_left
            right_x = self.screen.width / 2 + eye_gap / 2 + frame.eye_offset_x + frame.eye_shift_right
            if frame.eye_shape == "official_eye_vertical":
                eye_width = self.screen.width * 0.064 * eye_scale
                eye_height_base = self.screen.height * 0.160 * eye_scale
            elif frame.eye_shape == "official_eye_bright_dot":
                eye_width = self.screen.width * 0.071 * eye_scale
                eye_height_base = self.screen.height * 0.190 * eye_scale
            elif frame.eye_shape == "official_eye_happy_arc":
                eye_width = self.screen.width * 0.098 * eye_scale
                eye_height_base = self.screen.height * 0.090 * eye_scale
            elif frame.eye_shape == "official_eye_help":
                eye_width = self.screen.width * 0.071 * eye_scale
                eye_height_base = self.screen.height * 0.190 * eye_scale
            elif frame.eye_shape == "official_eye_work":
                eye_width = self.screen.width * 0.071 * eye_scale
                eye_height_base = self.screen.height * 0.190 * eye_scale
            elif frame.eye_shape == "official_eye_sorry_vertical":
                eye_width = self.screen.width * 0.071 * eye_scale
                eye_height_base = self.screen.height * 0.185 * eye_scale
            elif frame.eye_shape == "official_eye_squeeze":
                eye_width = self.screen.width * 0.073 * eye_scale
                eye_height_base = self.screen.height * 0.190 * eye_scale
            elif frame.eye_shape == "official_eye_sad":
                eye_width = self.screen.width * 0.085 * eye_scale
                eye_height_base = self.screen.height * 0.120 * eye_scale
            else:
                eye_width = self.screen.width * 0.068 * eye_scale
                eye_height_base = self.screen.height * 0.135 * eye_scale
        elif is_failed_stress_x:
            eye_width = self.screen.width * 0.194 * eye_scale
            eye_height_base = self.screen.height * 0.124 * eye_scale
            eye_gap = self.screen.width * 0.302
            eye_y = self.screen.height * 0.445 + frame.eye_offset_y
            left_x = self.screen.width / 2 - eye_gap / 2 + frame.eye_offset_x
            right_x = self.screen.width * 0.651 + frame.eye_offset_x
        elif is_wide_pressure:
            eye_width = self.screen.width * 0.190 * eye_scale
            eye_height_base = self.screen.height * 0.305 * eye_scale
            eye_gap = self.screen.width * 0.170
            eye_y = self.screen.height * 0.455 + frame.eye_offset_y
            left_x = self.screen.width / 2 - eye_gap / 2 + frame.eye_offset_x
            right_x = self.screen.width / 2 + eye_gap / 2 + frame.eye_offset_x
        elif is_puppy_squeeze:
            eye_width = self.screen.width * 0.188 * eye_scale
            eye_height_base = self.screen.height * 0.205 * eye_scale
            eye_gap = self.screen.width * 0.245
            eye_y = self.screen.height * 0.475 + frame.eye_offset_y
            left_x = self.screen.width / 2 - eye_gap / 2 + frame.eye_offset_x
            right_x = self.screen.width / 2 + eye_gap / 2 + frame.eye_offset_x
        elif is_stress_squeeze:
            eye_width = self.screen.width * 0.200 * eye_scale
            eye_height_base = self.screen.height * 0.176 * eye_scale
            eye_gap = self.screen.width * 0.292
            eye_y = self.screen.height * 0.448 + frame.eye_offset_y
            left_x = self.screen.width / 2 - eye_gap / 2 + frame.eye_offset_x
            right_x = self.screen.width / 2 + eye_gap / 2 + frame.eye_offset_x
        elif is_failed_sad_oval:
            eye_width = self.screen.width * 0.160 * eye_scale
            eye_height_base = self.screen.height * 0.284 * eye_scale
            eye_gap = self.screen.width * 0.282
            eye_y = self.screen.height * 0.462 + frame.eye_offset_y
            left_x = self.screen.width / 2 - eye_gap / 2 + frame.eye_offset_x
            right_x = self.screen.width / 2 + eye_gap / 2 + frame.eye_offset_x
        elif is_failed_soft:
            eye_width = self.screen.width * 0.176 * eye_scale
            eye_height_base = self.screen.height * 0.255 * eye_scale
            eye_gap = self.screen.width * 0.245
            eye_y = self.screen.height * 0.468 + frame.eye_offset_y
            left_x = self.screen.width / 2 - eye_gap / 2 + frame.eye_offset_x
            right_x = self.screen.width / 2 + eye_gap / 2 + frame.eye_offset_x
        elif is_failed_v47:
            eye_width = self.screen.width * 0.180 * eye_scale
            eye_height_base = self.screen.height * 0.240 * eye_scale
            eye_gap = self.screen.width * 0.245
            eye_y = self.screen.height * 0.455 + frame.eye_offset_y
            left_x = self.screen.width / 2 - eye_gap / 2 + frame.eye_offset_x
            right_x = self.screen.width / 2 + eye_gap / 2 + frame.eye_offset_x
        elif is_failed_v21:
            eye_width = self.screen.width * 0.162 * 0.98 * eye_scale
            eye_height_base = self.screen.height * 0.190 * 0.98 * eye_scale
            eye_gap = self.screen.width * 0.305
            eye_y = self.screen.height * 0.445 + frame.eye_offset_y
            left_x = self.screen.width / 2 - eye_gap / 2 + frame.eye_offset_x
            right_x = self.screen.width / 2 + eye_gap / 2 + frame.eye_offset_x
        elif frame.eye_shape == "puppy_teary" or frame.eye_shape.startswith("puppy_ring"):
            eye_width = self.screen.width * 0.168 * eye_scale
            eye_height_base = self.screen.height * 0.305 * eye_scale
            eye_gap = self.screen.width * 0.245
            eye_y = self.screen.height * 0.5 + frame.eye_offset_y
            left_x = self.screen.width / 2 - eye_gap / 2 + frame.eye_offset_x
            right_x = self.screen.width / 2 + eye_gap / 2 + frame.eye_offset_x
        else:
            eye_width = core.width * (0.292 + 0.015 * profile.activity_level) * eye_scale
            eye_height_base = core.height * (0.655 + 0.035 * profile.activity_level) * eye_scale
            eye_gap = min(
                core.width * 0.58,
                XIAOQ_CUTE_REFERENCE["eye_gap"] * BLUEBOT_OLED_SIZE_RATIO,
            )
            eye_y = core.y + core.height * 0.39 + frame.eye_offset_y * 0.6
            eye_y += math.sin(phase * 1.7) * 1.5 * profile.activity_level
            left_x = core.x + core.width / 2 - eye_gap / 2 + frame.eye_offset_x * 0.7
            right_x = core.x + core.width / 2 + eye_gap / 2 + frame.eye_offset_x * 0.7

        left_eye = self._rect_from_center(
            left_x,
            eye_y,
            eye_width,
            max(18.0, eye_height_base * open_left),
            core,
        )
        right_eye = self._rect_from_center(
            right_x,
            eye_y,
            eye_width,
            max(18.0, eye_height_base * open_right),
            core,
        )
        if is_failed_v21:
            right_eye = self._rect_from_center(
                right_x,
                eye_y + self.screen.height * 0.008,
                self.screen.width * 0.162 * 0.90 * eye_scale,
                max(18.0, self.screen.height * 0.190 * 0.90 * eye_scale * open_right),
                core,
            )
        if is_failed_v47:
            right_eye = self._rect_from_center(
                right_x,
                eye_y + self.screen.height * 0.006,
                self.screen.width * 0.180 * 0.82 * eye_scale,
                max(18.0, self.screen.height * 0.240 * 0.82 * eye_scale * open_right),
                core,
            )

        mouth_width = core.width * (0.24 + 0.26 * self._clamp(abs(frame.mouth_smile), 0.0, 1.0))
        if frame.mouth in {"talk", "o"}:
            mouth_width = core.width * (0.15 + 0.2 * self._clamp(frame.mouth_smile, 0.0, 1.0))
        if frame.mouth in {"flat", "dot", "small"}:
            mouth_width = core.width * (0.14 + 0.12 * max(frame.mouth_open, 0.2))
        if frame.mouth in {"plead", "question", "wobble"}:
            mouth_width = core.width * (0.24 + 0.18 * max(frame.mouth_open, 0.2))
        if frame.mouth in {"pout_bridge", "pout_bridge_soft", "pout_bridge_round", "pout_bridge_deep"}:
            mouth_width = self.screen.width * 0.144 * (1.0 + 0.02 * math.sin(phase * 6.3))
        if frame.mouth.startswith("moe_pout"):
            mouth_width = self.screen.width * 0.118 * (1.0 + 0.015 * math.sin(phase * 6.0))
        if frame.mouth.startswith("moe_pout_clench"):
            mouth_width = self.screen.width * 0.145 * (1.0 - 0.018 * pulse)
        if frame.mouth.startswith("blocked_tiny_pout"):
            mouth_width = self.screen.width * 0.092 * (1.0 - 0.012 * pulse)
        if frame.mouth.startswith("fail_capsule"):
            mouth_width = self.screen.width * 0.154 * (1.0 - 0.025 * pulse)
        if frame.mouth.startswith("fail_capsule_v47"):
            mouth_width = self.screen.width * 0.174 * (1.0 - 0.025 * pulse)
        if frame.mouth.startswith("fail_soft_pout"):
            mouth_width = self.screen.width * 0.142 * (1.0 - 0.018 * pulse)
        if frame.mouth.startswith("fail_quiver_pout"):
            mouth_width = self.screen.width * 0.146 * (1.0 - 0.020 * pulse)
        if frame.mouth.startswith("fail_apology_pout"):
            mouth_width = self.screen.width * 0.130 * (1.0 - 0.018 * pulse)
        if frame.mouth.startswith("fail_apology_pout_v54"):
            mouth_width = self.screen.width * 0.116 * (1.0 - 0.018 * pulse)
        if frame.mouth.startswith("fail_apology_pout_v55"):
            mouth_width = self.screen.width * 0.124 * (1.0 - 0.018 * pulse)
        if frame.mouth.startswith("official_mouth"):
            mouth_width = self.screen.width * 0.290
        if frame.mouth == "official_mouth_smile_block":
            mouth_width = self.screen.width * 0.160
        if frame.mouth == "official_mouth_big_smile":
            mouth_width = self.screen.width * 0.183
        if frame.mouth == "official_mouth_help_pout":
            mouth_width = self.screen.width * 0.235
        if frame.mouth == "official_mouth_wobble":
            mouth_width = self.screen.width * 0.172
        if frame.mouth == "official_mouth_sorry_pout":
            mouth_width = self.screen.width * 0.172
        if frame.mouth == "official_mouth_expectant":
            mouth_width = self.screen.width * 0.185
        if frame.mouth.startswith("failed_stress_capsule"):
            mouth_width = self.screen.width * 0.160 * (1.0 - 0.02 * pulse)
        if frame.mouth.startswith("stress_clench"):
            mouth_width = self.screen.width * 0.135 * (1.0 - 0.018 * pulse)
        if frame.mouth.startswith("stress_grimace"):
            mouth_width = self.screen.width * 0.150 * (1.0 - 0.016 * pulse)
        if frame.mouth.startswith("pressure_grimace"):
            mouth_width = self.screen.width * 0.176 * (1.0 - 0.016 * pulse)
        if frame.mouth in {"beam", "soft_smile"}:
            mouth_width = core.width * (0.32 + 0.24 * self._clamp(frame.mouth_smile, 0.0, 1.0))
        if frame.mouth == "grimace":
            mouth_width = core.width * 0.24
        if frame.mouth.startswith("official_mouth"):
            mouth_width *= 0.86
            mouth_width *= self._clamp(frame.mouth_scale, 0.75, 1.20)
        mouth_width = min(
            mouth_width,
            self.screen.width * 0.36 if frame.mouth.startswith("official_mouth") else XIAOQ_CUTE_REFERENCE["mouth_width"] * BLUEBOT_OLED_SIZE_RATIO,
        )
        mouth_height = core.height * (0.06 + 0.19 * self._clamp(frame.mouth_open, 0.0, 1.0))
        if frame.mouth in {"pout_bridge", "pout_bridge_soft", "pout_bridge_round", "pout_bridge_deep"}:
            mouth_height = self.screen.height * 0.104
        if frame.mouth.startswith("moe_pout"):
            mouth_height = self.screen.height * 0.110
        if frame.mouth.startswith("moe_pout_clench"):
            mouth_height = self.screen.height * 0.082 * (1.0 - 0.018 * pulse)
        if frame.mouth.startswith("fail_capsule"):
            mouth_height = self.screen.height * 0.088 * (1.0 - 0.035 * pulse)
        if frame.mouth.startswith("fail_soft_pout"):
            mouth_height = self.screen.height * 0.104 * (1.0 - 0.020 * pulse)
        if frame.mouth.startswith("fail_quiver_pout"):
            mouth_height = self.screen.height * 0.112 * (1.0 - 0.024 * pulse)
        if frame.mouth.startswith("fail_apology_pout"):
            mouth_height = self.screen.height * 0.094 * (1.0 - 0.022 * pulse)
        if frame.mouth.startswith("fail_apology_pout_v54"):
            mouth_height = self.screen.height * 0.088 * (1.0 - 0.022 * pulse)
        if frame.mouth.startswith("fail_apology_pout_v55"):
            mouth_height = self.screen.height * 0.096 * (1.0 - 0.024 * pulse)
        if frame.mouth.startswith("official_mouth"):
            mouth_height = self.screen.height * 0.156
        if frame.mouth == "official_mouth_smile_block":
            mouth_height = self.screen.height * 0.140
        if frame.mouth == "official_mouth_big_smile":
            mouth_height = self.screen.height * 0.153
        if frame.mouth == "official_mouth_help_pout":
            mouth_height = self.screen.height * 0.138
        if frame.mouth == "official_mouth_wobble":
            mouth_height = self.screen.height * 0.124
        if frame.mouth == "official_mouth_sorry_pout":
            mouth_height = self.screen.height * 0.138
        if frame.mouth == "official_mouth_expectant":
            mouth_height = self.screen.height * 0.130
        if frame.mouth.startswith("failed_stress_capsule"):
            mouth_height = self.screen.height * 0.086 * (1.0 - 0.024 * pulse)
        if frame.mouth.startswith("stress_clench"):
            mouth_height = self.screen.height * 0.058 * (1.0 - 0.02 * pulse)
        if frame.mouth.startswith("stress_grimace"):
            mouth_height = self.screen.height * 0.070 * (1.0 - 0.018 * pulse)
        if frame.mouth.startswith("pressure_grimace"):
            mouth_height = self.screen.height * 0.076 * (1.0 - 0.018 * pulse)
        if frame.mouth in {"plead", "question"}:
            mouth_height *= 0.98
        if frame.mouth in {"beam", "soft_smile"}:
            mouth_height *= 1.18
        if (
            frame.mouth.startswith("fail_capsule")
            or frame.mouth.startswith("fail_soft_pout")
            or frame.mouth.startswith("fail_quiver_pout")
            or frame.mouth.startswith("fail_apology_pout")
            or frame.mouth.startswith("failed_stress_capsule")
        ):
            mouth_height += core.height * 0.004 * pulse * profile.activity_level
        elif (
            frame.mouth.startswith("stress_clench")
            or frame.mouth.startswith("stress_grimace")
            or frame.mouth.startswith("pressure_grimace")
        ):
            mouth_height += core.height * 0.003 * pulse * profile.activity_level
        elif frame.mouth.startswith("moe_pout_clench"):
            mouth_height += core.height * 0.003 * pulse * profile.activity_level
        elif frame.mouth.startswith("moe_pout"):
            mouth_height += core.height * 0.004 * pulse * profile.activity_level
        else:
            mouth_height += core.height * 0.018 * pulse * profile.activity_level
        if frame.mouth.startswith("official_mouth"):
            mouth_height *= 0.92
            mouth_height *= self._clamp(frame.mouth_scale, 0.75, 1.20)
        mouth_y = core.y + core.height * 0.73
        if frame.mouth in {"pout_bridge", "pout_bridge_soft", "pout_bridge_round", "pout_bridge_deep"}:
            mouth_y = self.screen.height * 0.735
        if frame.mouth.startswith("moe_pout"):
            mouth_y = self.screen.height * 0.744
        if frame.mouth.startswith("moe_pout_clench"):
            mouth_y = self.screen.height * 0.724
        if frame.mouth.startswith("fail_capsule"):
            mouth_y = self.screen.height * 0.705
        if frame.mouth.startswith("fail_soft_pout"):
            mouth_y = self.screen.height * 0.718
        if frame.mouth.startswith("fail_quiver_pout"):
            mouth_y = self.screen.height * 0.722
        if frame.mouth.startswith("fail_apology_pout"):
            mouth_y = self.screen.height * 0.716
        if frame.mouth.startswith("fail_apology_pout_v54"):
            mouth_y = self.screen.height * 0.712
        if frame.mouth.startswith("fail_apology_pout_v55"):
            mouth_y = self.screen.height * 0.716
        if frame.mouth.startswith("official_mouth"):
            mouth_y = self.screen.height * 0.635 + frame.mouth_offset_y
        if frame.mouth in {"official_mouth_sorry_pout", "official_mouth_big_smile"}:
            mouth_y += frame.eye_offset_y
        if frame.mouth.startswith("failed_stress_capsule"):
            mouth_y = self.screen.height * 0.705
        if frame.mouth.startswith("stress_clench"):
            mouth_y = self.screen.height * 0.715
        if frame.mouth.startswith("stress_grimace"):
            mouth_y = self.screen.height * 0.704
        if frame.mouth.startswith("pressure_grimace"):
            mouth_y = self.screen.height * 0.700
        if frame.mouth.startswith("official_mouth"):
            mouth_y = max(mouth_y, max(left_eye.bottom, right_eye.bottom) + 8.0 + max(14.0, mouth_height) / 2)
        mouth = self._rect_from_center(
            core.x + core.width / 2 + frame.eye_offset_x * 0.2,
            mouth_y,
            mouth_width,
            max(14.0, mouth_height),
            core,
        )

        if is_official:
            center_x = self.screen.width / 2
            center_y = self.screen.height / 2

            def enlarge(rect: LayoutRect) -> LayoutRect:
                return self._rect_from_center(
                    center_x + (rect.center_x - center_x) * 1.10,
                    center_y + (rect.center_y - center_y) * 1.10,
                    rect.width * 1.10,
                    rect.height * 1.10,
                    core,
                )

            left_eye = enlarge(left_eye)
            right_eye = enlarge(right_eye)
            mouth = enlarge(mouth)

        cheek_size = core.width * (0.062 + 0.03 * self._clamp(frame.cheek, 0.0, 1.0))
        cheek_y = core.y + core.height * 0.63
        cheek_gap = core.width * 0.42
        left_cheek = self._rect_from_center(core.x + core.width / 2 - cheek_gap, cheek_y, cheek_size, cheek_size * 0.58, core)
        right_cheek = self._rect_from_center(core.x + core.width / 2 + cheek_gap, cheek_y, cheek_size, cheek_size * 0.58, core)

        progress_width = core.width * 0.54
        progress_height = core.height * 0.04
        progress_rect = self._rect_from_center(
            core.x + core.width / 2,
            core.y + core.height * 0.88,
            progress_width,
            progress_height,
            core,
        )

        critical = (left_eye, right_eye, mouth)
        if profile.progress_enabled or frame.progress > 0.0:
            critical = critical + (progress_rect,)

        return BluebotFaceLayout(
            screen=self.screen,
            visible=visible,
            expression_core=core,
            face_rect=face_rect,
            left_eye=left_eye,
            right_eye=right_eye,
            mouth=mouth,
            left_cheek=left_cheek,
            right_cheek=right_cheek,
            progress_rect=progress_rect,
            variant_profile=profile,
            critical_rects=critical,
        )

    def variant_profile(
        self,
        frame: ExpressionFrame,
        intent: ExpressionIntent | None = None,
    ) -> BluebotVariantProfile:
        variant = intent.visual_variant if intent else frame.expression_id
        base = VARIANT_PROFILES.get(variant)
        if base:
            accent = intent.accent if intent and intent.accent else base.accent
            return BluebotVariantProfile(
                id=base.id,
                motion_family=base.motion_family,
                activity_level=base.activity_level,
                accent=accent,
                progress_enabled=base.progress_enabled or bool(intent and intent.progress_enabled),
            )
        return BluebotVariantProfile(
            id=variant,
            motion_family=frame.expression_id,
            activity_level=self._activity_for_state(frame.state),
            accent=intent.accent if intent and intent.accent else frame.accent,
            progress_enabled=bool(intent and intent.progress_enabled),
        )

    def _rect_from_center(self, cx: float, cy: float, width: float, height: float, bounds: SafeRect) -> LayoutRect:
        width = min(width, bounds.width)
        height = min(height, bounds.height)
        x = self._clamp(cx - width / 2, bounds.x, bounds.right - width)
        y = self._clamp(cy - height / 2, bounds.y, bounds.bottom - height)
        return LayoutRect(x=x, y=y, width=width, height=height)

    def _activity_for_state(self, state: str) -> float:
        if state in {"THINKING", "PAIRING", "OTA"}:
            return 0.75
        if state in {"SPEAKING", "SPEAK_EXCITED", "WAKE"}:
            return 0.65
        if state in {"ERROR", "LOW_BATTERY", "CONCERNED"}:
            return 0.55
        if state in {"FULFILLED", "HAPPY_BIG", "HAPPY_SMALL"}:
            return 0.5
        return 0.25

    def _clamp(self, value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))
