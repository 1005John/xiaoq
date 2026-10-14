"""Pygame renderer for Bluebot expressions."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from ..models import ExpressionFrame, ExpressionIntent, ScreenProfile
from ..screen import DEFAULT_SCREEN_PROFILE
from .bluebot_layout import BluebotFaceLayout, BluebotLayoutEngine, LayoutRect
from .bluebot_style import style_bluebot_frame


@dataclass(frozen=True)
class BluebotPygameTheme:
    background_top: tuple[int, int, int] = (6, 52, 154)
    background_bottom: tuple[int, int, int] = (1, 16, 58)
    face_blue: tuple[int, int, int] = (8, 88, 214)
    face_blue_dark: tuple[int, int, int] = (2, 40, 118)
    cyan: tuple[int, int, int] = (125, 255, 251)
    white_cyan: tuple[int, int, int] = (219, 255, 255)
    amber: tuple[int, int, int] = (255, 211, 108)
    soft_blue: tuple[int, int, int] = (159, 216, 255)


@dataclass(frozen=True)
class _OfficialMouthPose:
    body_width: float
    body_height: float
    body_y: float
    bow: float
    inner_alpha: float


@dataclass(frozen=True)
class _OfficialCheekPose:
    color: tuple[int, int, int]
    alpha: float


class BluebotPygameRenderer:
    """Draw Bluebot expression frames on a pygame surface."""

    def __init__(
        self,
        screen: ScreenProfile | None = None,
        theme: BluebotPygameTheme | None = None,
        debug_safe_area: bool = False,
    ) -> None:
        self.screen = screen or DEFAULT_SCREEN_PROFILE
        self.theme = theme or BluebotPygameTheme()
        self.layout_engine = BluebotLayoutEngine(self.screen)
        self.debug_safe_area = debug_safe_area
        self._background_layer: object | None = None
        self._background_layers: dict[tuple[int, int, tuple[int, int, int], tuple[int, int, int]], object] = {}
        self._layer_cache: dict[tuple[int, int], object] = {}
        self._official_background_layer: object | None = None
        self._radial_glow_cache: dict[tuple[int, int, tuple[int, int, int], int], object] = {}

    def draw(
        self,
        surface: object,
        frame: ExpressionFrame,
        intent: ExpressionIntent | None = None,
        now_ms: int = 0,
        include_background: bool = True,
    ) -> BluebotFaceLayout:
        frame = style_bluebot_frame(frame, intent, now_ms)
        layout = self.layout_engine.layout(frame, intent, now_ms)
        return self._draw_styled(surface, frame, layout, now_ms, include_background)

    def draw_transition(
        self,
        surface: object,
        previous_frame: ExpressionFrame,
        previous_intent: ExpressionIntent,
        next_frame: ExpressionFrame,
        next_intent: ExpressionIntent,
        previous_elapsed_ms: int,
        next_elapsed_ms: int,
        progress: float,
        include_background: bool = True,
        previous_layout: BluebotFaceLayout | None = None,
    ) -> BluebotFaceLayout:
        if progress <= 0.0:
            previous = style_bluebot_frame(previous_frame, previous_intent, previous_elapsed_ms)
            layout = previous_layout or self.layout_engine.layout(previous, previous_intent, previous_elapsed_ms)
            return self._draw_styled(surface, previous, layout, previous_elapsed_ms, include_background)
        if progress >= 1.0:
            return self.draw(surface, next_frame, next_intent, next_elapsed_ms, include_background)

        previous = style_bluebot_frame(previous_frame, previous_intent, previous_elapsed_ms)
        current = style_bluebot_frame(next_frame, next_intent, next_elapsed_ms)
        previous_layout = previous_layout or self.layout_engine.layout(previous, previous_intent, previous_elapsed_ms)
        current_layout = self.layout_engine.layout(current, next_intent, next_elapsed_ms)
        amount = progress * progress * (3.0 - 2.0 * progress)
        left_eye = self._lerp_rect(previous_layout.left_eye, current_layout.left_eye, amount)
        right_eye = self._lerp_rect(previous_layout.right_eye, current_layout.right_eye, amount)
        mouth = self._lerp_rect(previous_layout.mouth, current_layout.mouth, amount)
        critical_rects = (left_eye, right_eye, mouth)
        if current_layout.variant_profile.progress_enabled or current.progress > 0:
            critical_rects += (current_layout.progress_rect,)
        layout = replace(
            current_layout,
            left_eye=left_eye,
            right_eye=right_eye,
            mouth=mouth,
            critical_rects=critical_rects,
        )
        frame = replace(
            current,
            face_brightness=self._lerp(previous.face_brightness, current.face_brightness, amount),
            screen_pulse=self._lerp(previous.screen_pulse, current.screen_pulse, amount),
        )
        return self._draw_styled(
            surface,
            frame,
            layout,
            next_elapsed_ms,
            include_background,
            transition_source=(previous, previous_layout),
            transition_amount=amount,
        )

    def _draw_styled(
        self,
        surface: object,
        frame: ExpressionFrame,
        layout: BluebotFaceLayout,
        now_ms: int,
        include_background: bool,
        transition_source: tuple[ExpressionFrame, BluebotFaceLayout] | None = None,
        transition_amount: float = 1.0,
    ) -> BluebotFaceLayout:
        pygame = self._pygame()
        accent = self._parse_color(layout.variant_profile.accent, self.theme.cyan)
        brightness = self._clamp(frame.face_brightness, 0.08, 1.0)
        mouth_pose = self._official_mouth_pose(frame.mouth, now_ms, frame.mouth_bow) if frame.mouth.startswith("official_mouth") else None
        cheek_pose = None
        if transition_source and frame.mouth.startswith("official_mouth"):
            previous, _ = transition_source
            if previous.mouth.startswith("official_mouth"):
                mouth_pose = self._lerp_mouth_pose(
                    self._official_mouth_pose(previous.mouth, now_ms, previous.mouth_bow),
                    self._official_mouth_pose(frame.mouth, now_ms, frame.mouth_bow),
                    transition_amount,
                )
                cheek_pose = self._lerp_cheek_pose(
                    self._official_cheek_pose(previous.mouth),
                    self._official_cheek_pose(frame.mouth),
                    transition_amount,
                )
        if include_background:
            self._draw_background(pygame, surface, layout, frame, accent, brightness, now_ms)
        previous_clip = surface.get_clip()
        surface.set_clip(self._pygame_rect(pygame, self._from_safe(layout.visible)))
        try:
            self._draw_variant_activity(pygame, surface, layout, frame, accent, now_ms, transition_amount)
            if transition_source and transition_source[0].eye_shape.startswith("official_eye"):
                previous, _ = transition_source
                if previous.eye_shape == "official_eye_squeeze" and frame.eye_shape != "official_eye_squeeze":
                    self._draw_official_pressure_marks(pygame, surface, layout, accent, now_ms, 1.0 - transition_amount)
            self._draw_eye(pygame, surface, layout.left_eye, frame.eye_shape, frame.eye_open_left, accent, brightness, now_ms, side=-1)
            self._draw_eye(pygame, surface, layout.right_eye, frame.eye_shape, frame.eye_open_right, accent, brightness, now_ms, side=1)
            self._draw_mouth(pygame, surface, layout.mouth, frame, accent, brightness, now_ms, mouth_pose)
            self._draw_cheeks(pygame, surface, layout, frame, accent, cheek_pose)
            if (layout.variant_profile.progress_enabled or frame.progress > 0) and not frame.eye_shape.startswith("official_eye"):
                self._draw_progress(pygame, surface, layout, frame, accent, now_ms)
            if self.debug_safe_area:
                self._draw_debug(pygame, surface, layout)
        finally:
            surface.set_clip(previous_clip)
        return layout

    @staticmethod
    def _lerp(start: float, end: float, amount: float) -> float:
        return start + (end - start) * amount

    @classmethod
    def _lerp_rect(cls, start: LayoutRect, end: LayoutRect, amount: float) -> LayoutRect:
        return LayoutRect(
            cls._lerp(start.x, end.x, amount),
            cls._lerp(start.y, end.y, amount),
            cls._lerp(start.width, end.width, amount),
            cls._lerp(start.height, end.height, amount),
        )

    @classmethod
    def _lerp_mouth_pose(cls, start: _OfficialMouthPose, end: _OfficialMouthPose, amount: float) -> _OfficialMouthPose:
        return _OfficialMouthPose(
            cls._lerp(start.body_width, end.body_width, amount),
            cls._lerp(start.body_height, end.body_height, amount),
            cls._lerp(start.body_y, end.body_y, amount),
            cls._lerp(start.bow, end.bow, amount),
            cls._lerp(start.inner_alpha, end.inner_alpha, amount),
        )

    @classmethod
    def _lerp_cheek_pose(cls, start: _OfficialCheekPose, end: _OfficialCheekPose, amount: float) -> _OfficialCheekPose:
        color = tuple(round(cls._lerp(a, b, amount)) for a, b in zip(start.color, end.color))
        return _OfficialCheekPose(color, cls._lerp(start.alpha, end.alpha, amount))

    def create_surface(self) -> object:
        pygame = self._pygame()
        return pygame.Surface((self.screen.width, self.screen.height), pygame.SRCALPHA)

    def _draw_background(
        self,
        pygame: object,
        surface: object,
        layout: BluebotFaceLayout,
        frame: ExpressionFrame,
        accent: tuple[int, int, int],
        brightness: float,
        now_ms: int,
    ) -> None:
        width = self.screen.width
        height = self.screen.height
        if frame.eye_shape.startswith("official_eye"):
            surface.blit(self._official_background(pygame), (0, 0))
            return
        top, bottom = self._background_colors(layout)
        layer_key = (width, height, top, bottom)
        background_layer = self._background_layers.get(layer_key)
        if background_layer is None:
            background_layer = pygame.Surface((width, height))
            for y in range(height):
                t = y / max(1, height - 1)
                color = tuple(round(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
                pygame.draw.line(background_layer, color, (0, y), (width, y))
            self._background_layers[layer_key] = background_layer
        surface.blit(background_layer, (0, 0))

        pulse = 0.35 + 0.65 * self._pulse(now_ms, 0.0024, 0)
        if layout.variant_profile.id == "human_help":
            face_color = (5, 60, 166)
            face_alpha = round(72 + 30 * brightness + 8 * frame.screen_pulse * pulse)
        elif layout.variant_profile.id in {"failed", "failed_stress_x"}:
            face_color = (5, 55, 156)
            face_alpha = round(78 + 18 * brightness + 6 * frame.screen_pulse * pulse)
        else:
            face_color = self._mix(self.theme.face_blue_dark, self.theme.face_blue, 0.5 + brightness * 0.38)
            face_alpha = round(64 + 70 * brightness + 20 * frame.screen_pulse * pulse)
        self._draw_soft_rounded_rect(pygame, surface, layout.face_rect, face_color, face_alpha, 0, glow=0)

        if layout.variant_profile.id == "human_help":
            mood_cyan = (78, 205, 229)
            upper = LayoutRect(width * 0.15, height * 0.09, width * 0.70, height * 0.28)
            lower = LayoutRect(width * 0.14, height * 0.69, width * 0.72, height * 0.16)
            self._draw_soft_ellipse(pygame, surface, upper, mood_cyan, round(7 + 6 * frame.screen_pulse), 0)
            self._draw_soft_ellipse(pygame, surface, lower, mood_cyan, round(4 + 5 * frame.screen_pulse), 0)
            return

        if layout.variant_profile.id == "failed":
            upper = LayoutRect(width * 0.31, height * 0.13, width * 0.38, height * 0.16)
            lower = LayoutRect(width * 0.36, height * 0.735, width * 0.28, height * 0.07)
            error_blue = (107, 186, 206)
            soft_red = (255, 150, 162)
            self._draw_soft_ellipse(pygame, surface, upper, error_blue, round(1 + 1 * frame.screen_pulse), 4)
            self._draw_soft_ellipse(pygame, surface, lower, soft_red, round(1 + 1 * frame.screen_pulse), 4)
            return

        if layout.variant_profile.id == "failed_stress_x":
            upper = LayoutRect(width * 0.18, height * 0.08, width * 0.64, height * 0.30)
            lower = LayoutRect(width * 0.19, height * 0.70, width * 0.62, height * 0.15)
            error_blue = (107, 186, 206)
            soft_red = (255, 150, 162)
            self._draw_soft_ellipse(pygame, surface, upper, error_blue, round(8 + 6 * frame.screen_pulse), 10)
            self._draw_soft_ellipse(pygame, surface, lower, soft_red, round(7 + 5 * frame.screen_pulse), 10)
            return

        if layout.variant_profile.id == "blocked":
            return

        glow_rect = LayoutRect(
            width * 0.13,
            height * 0.11,
            width * 0.74,
            height * 0.4,
        )
        self._draw_soft_ellipse(pygame, surface, glow_rect, accent, round(4 + 9 * frame.screen_pulse), 18)

    def _background_colors(self, layout: BluebotFaceLayout) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        if layout.variant_profile.id in {"idle_wait", "human_help", "failed", "blocked", "completed"}:
            return (10, 102, 217), (1, 17, 77)
        if layout.variant_profile.id == "human_help":
            return (2, 34, 108), (0, 7, 33)
        if layout.variant_profile.id in {"failed", "failed_stress_x"}:
            return (4, 31, 100), (0, 7, 32)
        return self.theme.background_top, self.theme.background_bottom

    def _official_background(self, pygame: object) -> object:
        if self._official_background_layer is None:
            small = pygame.Surface((320, 180))
            for y in range(180):
                v = y / 179
                base = self._mix((5, 111, 222), (1, 23, 85), v ** 1.2)
                for x in range(320):
                    u = x / 319
                    dome = math.exp(-((u - 0.46) / 0.57) ** 2 - ((v - 0.18) / 0.49) ** 2)
                    crown = math.exp(-((u - 0.38) / 0.38) ** 2 - ((v - 0.04) / 0.11) ** 2)
                    gloss_y = 0.115 + 0.11 * ((u - 0.46) / 0.46) ** 2
                    gloss = math.exp(-((u - 0.46) / 0.42) ** 4 - ((v - gloss_y) / 0.052) ** 2)
                    lower_reflection = math.exp(-((u - 0.53) / 0.55) ** 2 - ((v - 0.80) / 0.19) ** 2)
                    side = (abs(u - 0.5) / 0.5) ** 2
                    light = 0.30 * dome + 0.12 * crown + 0.07 * lower_reflection
                    shade = 0.19 * side + 0.04 * max(0.0, v - 0.55)
                    rim_top = math.exp(-v / 0.035) * 0.23
                    rim_side = math.exp(-min(u, 1.0 - u) / 0.025) * max(0.0, 0.14 - 0.12 * v)
                    rim = rim_top + rim_side + 0.20 * gloss
                    color = tuple(
                        round(
                            base[i] * (1 - shade - light - rim)
                            + (45, 151, 245)[i] * light
                            + (94, 204, 251)[i] * rim
                        )
                        for i in range(3)
                    )
                    small.set_at((x, y), color)
            self._official_background_layer = pygame.transform.smoothscale(small, (self.screen.width, self.screen.height))
        return self._official_background_layer

    def _draw_eye(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        shape: str,
        eye_open: float,
        accent: tuple[int, int, int],
        brightness: float,
        now_ms: int,
        side: int,
    ) -> None:
        shape = (shape or "oval").lower()
        color = self._mix(accent, self.theme.white_cyan, 0.42 + 0.32 * brightness)
        if shape == "left_x" and side < 0:
            self._draw_eye_x(pygame, surface, rect, color)
            return
        if shape == "right_x" and side > 0:
            self._draw_eye_x(pygame, surface, rect, color)
            return
        if shape in {"left_x", "right_x"}:
            self._draw_eye_shaped(pygame, surface, rect, "squint", color, brightness, now_ms, side)
            return
        if shape == "x":
            self._draw_eye_x(pygame, surface, rect, color)
            return
        if shape in {"fail_v21", "fail_v47"}:
            if side < 0:
                self._draw_eye_fail_ring(pygame, surface, rect, brightness, now_ms)
            else:
                self._draw_eye_fail_x(pygame, surface, rect, now_ms)
            return
        if shape.startswith("fail_soft"):
            self._draw_eye_fail_soft(pygame, surface, rect, brightness, now_ms, side, shape)
            return
        if shape.startswith("fail_sad_oval"):
            self._draw_eye_fail_sad_oval(pygame, surface, rect, brightness, now_ms, side, shape)
            return
        if shape.startswith("official_eye"):
            self._draw_eye_official(pygame, surface, rect, shape, brightness, now_ms, side)
            return
        if shape == "failed_stress_x_v24":
            if side < 0:
                self._draw_eye_stress_squeeze(pygame, surface, rect, brightness, now_ms, side, "stress_squeeze_b")
            else:
                self._draw_eye_failed_stress_x(pygame, surface, rect, now_ms)
            return
        if shape.startswith("fail_ring"):
            self._draw_eye_fail_ring(pygame, surface, rect, brightness, now_ms)
            return
        if shape.startswith("fail_x"):
            self._draw_eye_fail_x(pygame, surface, rect, now_ms)
            return
        if shape.startswith("stress_squeeze"):
            self._draw_eye_stress_squeeze(pygame, surface, rect, brightness, now_ms, side, shape)
            return
        if shape.startswith("wide_pressure"):
            self._draw_eye_wide_pressure(pygame, surface, rect, brightness, now_ms, side)
            return
        if shape.startswith("puppy_squeeze"):
            self._draw_eye_puppy_squeeze(pygame, surface, rect, brightness, now_ms, side)
            return
        if shape.startswith("puppy_ring"):
            self._draw_eye_puppy_ring(pygame, surface, rect, brightness, now_ms, side, shape)
            return
        if shape == "puppy_teary":
            self._draw_eye_puppy_teary(pygame, surface, rect, color, brightness, now_ms, side)
            return
        if shape == "puppy":
            self._draw_eye_puppy(pygame, surface, rect, color, brightness, now_ms, side)
            return
        if shape in {"dome", "almond", "bean", "squint"}:
            self._draw_eye_shaped(pygame, surface, rect, shape, color, brightness, now_ms, side)
            return
        if shape in {"arc", "closed"} or eye_open < 0.22:
            self._draw_eye_arc(pygame, surface, rect, color, up=shape == "arc", alpha=230)
            return
        if shape == "scan":
            self._draw_soft_ellipse(pygame, surface, rect, color, 225, 24)
            glint = self._eye_glint_rect(rect, side, now_ms)
            self._draw_soft_ellipse(pygame, surface, glint, self.theme.white_cyan, 90, 4)
            return
        if shape == "progress":
            self._draw_soft_ellipse(pygame, surface, rect, color, 210, 24)
            inset = max(6, round(rect.width * 0.13))
            inner = self._inflate(rect, -inset, -inset)
            self._draw_soft_ellipse(pygame, surface, inner, self.theme.background_top, 115, 8)
            return
        self._draw_soft_ellipse(pygame, surface, rect, color, round(210 + 34 * brightness), 30)
        glint = self._eye_glint_rect(rect, side, now_ms)
        self._draw_soft_ellipse(pygame, surface, glint, self.theme.white_cyan, round(54 + 32 * brightness), 4)

    def _draw_mouth(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        frame: ExpressionFrame,
        accent: tuple[int, int, int],
        brightness: float,
        now_ms: int,
        official_pose: _OfficialMouthPose | None = None,
    ) -> None:
        mouth = (frame.mouth or "smile").lower()
        if mouth == "none":
            return
        color = self._mix(accent, self.theme.white_cyan, 0.34 + 0.34 * brightness)
        thickness = max(9, round(rect.height * 0.4))
        if mouth in {"talk", "o", "soft_o"}:
            self._draw_soft_rounded_rect(pygame, surface, rect, color, 210, max(8, round(rect.height / 2)), glow=16)
            if mouth == "talk":
                inner_scale = 0.5 + 0.16 * self._pulse(now_ms, 0.032, 0)
            elif mouth == "soft_o":
                inner_scale = 0.44 + 0.06 * self._pulse(now_ms, 0.008, 0)
            else:
                inner_scale = 0.62
            inner = LayoutRect(
                rect.x + rect.width * (1 - inner_scale) / 2,
                rect.y + rect.height * 0.28,
                rect.width * inner_scale,
                rect.height * 0.45,
            )
            self._draw_soft_rounded_rect(pygame, surface, inner, self.theme.background_bottom, 120, round(inner.height / 2), glow=0)
            return
        if mouth == "beam":
            points = self._mouth_curve_points(rect, depth=0.36, width_ratio=0.9)
            self._draw_mouth_ribbon(pygame, surface, points, color, max(12, thickness + 2), 48)
            shine = LayoutRect(rect.x + rect.width * 0.26, rect.center_y + rect.height * 0.23, rect.width * 0.48, max(5, rect.height * 0.1))
            self._draw_soft_rounded_rect(pygame, surface, shine, color, 72, round(shine.height / 2), glow=8)
            return
        if mouth == "soft_smile":
            points = self._mouth_curve_points(rect, depth=0.22, width_ratio=0.84)
            self._draw_mouth_ribbon(pygame, surface, points, color, max(10, thickness - 1), 40)
            dot_size = max(5, rect.height * 0.12)
            left_dot = LayoutRect(rect.x + rect.width * 0.08, rect.center_y + rect.height * 0.13, dot_size, dot_size)
            right_dot = LayoutRect(rect.right - rect.width * 0.08 - dot_size, rect.center_y + rect.height * 0.13, dot_size, dot_size)
            self._draw_soft_ellipse(pygame, surface, left_dot, color, 150, 5)
            self._draw_soft_ellipse(pygame, surface, right_dot, color, 150, 5)
            return
        if mouth == "plead":
            points = self._mouth_curve_points(rect, depth=-0.24, width_ratio=0.62)
            self._draw_mouth_ribbon(pygame, surface, points, color, max(9, thickness - 2), 44)
            glint = LayoutRect(rect.center_x - rect.width * 0.08, rect.center_y + rect.height * 0.2, rect.width * 0.16, max(4, rect.height * 0.08))
            self._draw_soft_rounded_rect(pygame, surface, glint, color, 78, round(glint.height / 2), glow=5)
            return
        if mouth in {"pout_bridge", "pout_bridge_soft", "pout_bridge_round", "pout_bridge_deep"}:
            self._draw_pout_bridge_mouth(pygame, surface, rect, mouth, color, now_ms)
            return
        if mouth.startswith("moe_pout_clench"):
            self._draw_moe_pout_mouth(pygame, surface, rect, mouth, now_ms)
            return
        if mouth.startswith("moe_pout"):
            self._draw_moe_pout_mouth(pygame, surface, rect, mouth, now_ms)
            return
        if mouth.startswith("blocked_tiny_pout"):
            self._draw_blocked_tiny_pout_mouth(pygame, surface, rect, now_ms)
            return
        if mouth.startswith("fail_soft_pout"):
            self._draw_fail_soft_pout_mouth(pygame, surface, rect, now_ms)
            return
        if mouth.startswith("fail_quiver_pout"):
            self._draw_fail_quiver_pout_mouth(pygame, surface, rect, now_ms)
            return
        if mouth.startswith("fail_apology_pout"):
            self._draw_fail_apology_pout_mouth(pygame, surface, rect, now_ms)
            return
        if mouth.startswith("official_mouth"):
            self._draw_official_mouth(pygame, surface, rect, mouth, now_ms, official_pose)
            return
        if mouth.startswith("fail_capsule") or mouth.startswith("failed_stress_capsule"):
            self._draw_fail_capsule_mouth(pygame, surface, rect, mouth, now_ms)
            return
        if (
            mouth.startswith("stress_clench")
            or mouth.startswith("stress_grimace")
            or mouth.startswith("pressure_grimace")
        ):
            self._draw_stress_clench_mouth(pygame, surface, rect, mouth, accent, brightness, now_ms)
            return
        if mouth == "question":
            points = [
                (rect.x + rect.width * 0.12, rect.center_y + rect.height * 0.08),
                (rect.x + rect.width * 0.45, rect.center_y - rect.height * 0.1),
                (rect.x + rect.width * 0.72, rect.center_y + rect.height * 0.12),
            ]
            self._draw_mouth_ribbon(pygame, surface, points, color, max(8, thickness - 1), 42)
            dot = LayoutRect(rect.right - rect.width * 0.12, rect.center_y + rect.height * 0.02, max(7, rect.height * 0.2), max(7, rect.height * 0.2))
            self._draw_soft_ellipse(pygame, surface, dot, color, 180, 5)
            return
        if mouth == "wobble":
            points = [
                (rect.x + rect.width * 0.05, rect.center_y - rect.height * 0.03),
                (rect.x + rect.width * 0.32, rect.center_y + rect.height * 0.16),
                (rect.x + rect.width * 0.54, rect.center_y + rect.height * 0.02),
                (rect.x + rect.width * 0.78, rect.center_y + rect.height * 0.2),
                (rect.right - rect.width * 0.05, rect.center_y + rect.height * 0.08),
            ]
            self._draw_mouth_ribbon(pygame, surface, points, color, max(8, thickness - 1), 40)
            return
        if mouth == "grimace":
            h = max(9, rect.height * 0.38)
            small = LayoutRect(rect.x, rect.center_y - h / 2, rect.width, h)
            self._draw_soft_rounded_rect(pygame, surface, small, color, 210, round(h / 2), glow=12)
            notch_w = max(3, small.width * 0.08)
            for offset in (0.36, 0.64):
                notch = LayoutRect(small.x + small.width * offset - notch_w / 2, small.y + h * 0.18, notch_w, h * 0.64)
                self._draw_soft_rounded_rect(pygame, surface, notch, self.theme.background_bottom, 110, round(notch_w / 2), glow=0)
            return
        if mouth in {"dot", "small", "flat"}:
            h = max(8, rect.height * (0.35 if mouth == "flat" else 0.55))
            small = LayoutRect(rect.x, rect.center_y - h / 2, rect.width, h)
            self._draw_soft_rounded_rect(pygame, surface, small, color, 220, round(h / 2), glow=14)
            return
        if mouth == "frown":
            self._draw_arc(pygame, surface, rect, color, math.radians(205), math.radians(335), thickness)
            return
        if mouth in {"tilt", "wave"}:
            points = self._mouth_wave_points(rect, wave=mouth == "wave")
            self._draw_mouth_ribbon(pygame, surface, points, color, thickness, 42)
            return
        self._draw_arc(pygame, surface, rect, color, math.radians(198), math.radians(342), thickness)

    def _draw_cheeks(
        self,
        pygame: object,
        surface: object,
        layout: BluebotFaceLayout,
        frame: ExpressionFrame,
        accent: tuple[int, int, int],
        official_pose: _OfficialCheekPose | None = None,
    ) -> None:
        if frame.eye_shape.startswith("official_eye"):
            pose = official_pose or self._official_cheek_pose(frame.mouth)
            for x in (self.screen.width * 0.250, self.screen.width * 0.750):
                cheek_rect = LayoutRect(
                    x - self.screen.width * 0.040,
                    self.screen.height * 0.506,
                    self.screen.width * 0.080,
                    self.screen.height * 0.084,
                )
                self._draw_radial_glow(pygame, surface, cheek_rect, pose.color, round(pose.alpha))
            return
        cheek = self._clamp(frame.cheek, 0.0, 1.0)
        if cheek <= 0.04:
            return
        alpha = round(35 + 95 * cheek)
        self._draw_soft_ellipse(pygame, surface, layout.left_cheek, accent, alpha, 16)
        self._draw_soft_ellipse(pygame, surface, layout.right_cheek, accent, alpha, 16)

    def _draw_progress(
        self,
        pygame: object,
        surface: object,
        layout: BluebotFaceLayout,
        frame: ExpressionFrame,
        accent: tuple[int, int, int],
        now_ms: int,
    ) -> None:
        track = layout.progress_rect
        self._draw_soft_rounded_rect(pygame, surface, track, self.theme.background_top, 95, round(track.height / 2), glow=0)
        progress = frame.progress if frame.progress > 0 else self._pulse(now_ms, 0.0016, 0)
        fill = LayoutRect(track.x, track.y, max(track.height, track.width * self._clamp(progress, 0.05, 1.0)), track.height)
        self._draw_soft_rounded_rect(pygame, surface, fill, accent, 220, round(track.height / 2), glow=12)

    def _draw_variant_activity(
        self,
        pygame: object,
        surface: object,
        layout: BluebotFaceLayout,
        frame: ExpressionFrame,
        accent: tuple[int, int, int],
        now_ms: int,
        official_cue_amount: float = 1.0,
    ) -> None:
        family = layout.variant_profile.motion_family
        if frame.eye_shape.startswith("official_eye") and layout.variant_profile.id != "blocked":
            return
        if family == "scan":
            self._draw_scan_sweep(pygame, surface, layout, accent, now_ms)
        elif family == "orbit":
            self._draw_orbit_points(pygame, surface, layout, accent, now_ms)
        elif family == "match":
            self._draw_match_nodes(pygame, surface, layout, accent, now_ms)
        elif family == "retrieve":
            self._draw_retrieve_lines(pygame, surface, layout, accent, now_ms)
        elif family == "activity":
            self._draw_activity_meter(pygame, surface, layout, accent, now_ms)
        elif family == "timer":
            self._draw_timer_ring(pygame, surface, layout, accent, now_ms)
        elif family == "replay":
            self._draw_replay_arcs(pygame, surface, layout, accent, now_ms)
        elif family == "verify":
            self._draw_verify_diamond(pygame, surface, layout, accent, now_ms)
        elif family == "network":
            self._draw_network_waves(pygame, surface, layout, accent, now_ms)
        elif family == "help":
            self._draw_help_beacon(pygame, surface, layout, accent, now_ms)
        elif family == "stress_pressure" and not frame.eye_shape.startswith("official_eye"):
            self._draw_stress_pressure_marks(pygame, surface, layout, accent, now_ms)
        if layout.variant_profile.id == "blocked" and frame.eye_shape.startswith("official_eye"):
            self._draw_official_pressure_marks(pygame, surface, layout, accent, now_ms, official_cue_amount)
        if family == "complete" and not frame.eye_shape.startswith("official_eye"):
            self._draw_complete_ring(pygame, surface, layout, accent, now_ms)
        # Warning variants should read from the face itself.
        # Do not add a separate shadow under the mouth.

    def _draw_scan_sweep(
        self,
        pygame: object,
        surface: object,
        layout: BluebotFaceLayout,
        accent: tuple[int, int, int],
        now_ms: int,
    ) -> None:
        core = layout.expression_core
        y = core.y + core.height * (0.23 + 0.08 * self._pulse(now_ms, 0.003, 0))
        x = core.x + core.width * (0.3 + 0.4 * self._pulse(now_ms, 0.0028, 0))
        trail = [
            (x - core.width * 0.08, y + 8),
            (x - core.width * 0.02, y),
            (x + core.width * 0.06, y - 6),
        ]
        self._draw_line_glow(pygame, surface, trail, accent, 4, 38)
        self._draw_soft_ellipse(pygame, surface, LayoutRect(x + 16, y - 12, 12, 12), accent, 95, 8)

    def _draw_orbit_points(
        self,
        pygame: object,
        surface: object,
        layout: BluebotFaceLayout,
        accent: tuple[int, int, int],
        now_ms: int,
    ) -> None:
        center_x = layout.expression_core.x + layout.expression_core.width / 2
        center_y = layout.expression_core.y + layout.expression_core.height * 0.32
        radius_x = layout.expression_core.width * 0.39
        radius_y = layout.expression_core.height * 0.22
        count = 6
        phase = now_ms * 0.0018
        for index in range(count):
            angle = phase + index * math.tau / count
            x = center_x + math.cos(angle) * radius_x
            y = center_y + math.sin(angle) * radius_y
            size = 7 + 8 * self._pulse(now_ms, 0.004, index)
            dot = LayoutRect(x - size / 2, y - size / 2, size, size)
            self._draw_soft_ellipse(pygame, surface, dot, accent, 86, 9)

    def _draw_match_nodes(
        self,
        pygame: object,
        surface: object,
        layout: BluebotFaceLayout,
        accent: tuple[int, int, int],
        now_ms: int,
    ) -> None:
        core = layout.expression_core
        center_x = core.x + core.width * 0.5
        y = core.y + core.height * 0.25
        spread = core.width * (0.18 - 0.05 * self._pulse(now_ms, 0.0028, 0))
        for index, x in enumerate((center_x - spread, center_x, center_x + spread)):
            size = 9 + 5 * self._pulse(now_ms, 0.004, index)
            dot = LayoutRect(x - size / 2, y + abs(index - 1) * 8 - size / 2, size, size)
            self._draw_soft_ellipse(pygame, surface, dot, accent, 98, 8)

    def _draw_retrieve_lines(
        self,
        pygame: object,
        surface: object,
        layout: BluebotFaceLayout,
        accent: tuple[int, int, int],
        now_ms: int,
    ) -> None:
        core = layout.expression_core
        center_x = core.x + core.width * 0.5
        y0 = core.y + core.height * 0.18
        for index in range(6):
            side = -1 if index % 2 == 0 else 1
            phase = self._pulse(now_ms, 0.0025, index)
            x = center_x + side * core.width * (0.12 + 0.13 * phase)
            y = y0 + core.height * (0.035 * index)
            size = 7 + 5 * phase
            self._draw_soft_ellipse(pygame, surface, LayoutRect(x - size / 2, y - size / 2, size, size), accent, 70 + index * 9, 7)

    def _draw_activity_meter(
        self,
        pygame: object,
        surface: object,
        layout: BluebotFaceLayout,
        accent: tuple[int, int, int],
        now_ms: int,
    ) -> None:
        core = layout.expression_core
        center_x = core.x + core.width * 0.5
        y = core.y + core.height * 0.23
        for index in range(5):
            phase = self._pulse(now_ms, 0.006, index)
            x = center_x + (index - 2) * core.width * 0.055
            size = 7 + 13 * phase
            rect = LayoutRect(x - size / 2, y - size / 2 - phase * 12, size, size)
            self._draw_soft_ellipse(pygame, surface, rect, accent, 78 + round(35 * phase), 8)

    def _draw_timer_ring(
        self,
        pygame: object,
        surface: object,
        layout: BluebotFaceLayout,
        accent: tuple[int, int, int],
        now_ms: int,
    ) -> None:
        core = layout.expression_core
        orbit = core.height * 0.09
        center = (core.x + core.width * 0.5, core.y + core.height * 0.23)
        angle = math.tau * self._pulse(now_ms, 0.001, 0)
        x = center[0] + math.cos(angle) * orbit
        y = center[1] + math.sin(angle) * orbit * 0.65
        self._draw_soft_ellipse(pygame, surface, LayoutRect(x - 8, y - 8, 16, 16), accent, 105, 10)
        self._draw_soft_ellipse(pygame, surface, LayoutRect(center[0] - 4, center[1] - 4, 8, 8), accent, 55, 6)

    def _draw_replay_arcs(
        self,
        pygame: object,
        surface: object,
        layout: BluebotFaceLayout,
        accent: tuple[int, int, int],
        now_ms: int,
    ) -> None:
        core = layout.expression_core
        center_x = core.x + core.width * 0.5
        y = core.y + core.height * 0.21
        for index in range(4):
            phase = self._pulse(now_ms, 0.002, index)
            x = center_x + (index - 1.5) * core.width * 0.045
            size = 5 + 4 * phase
            self._draw_soft_ellipse(pygame, surface, LayoutRect(x - size / 2, y - size / 2, size, size), accent, 45 + index * 10, 6)

    def _draw_verify_diamond(
        self,
        pygame: object,
        surface: object,
        layout: BluebotFaceLayout,
        accent: tuple[int, int, int],
        now_ms: int,
    ) -> None:
        core = layout.expression_core
        y = core.y + core.height * 0.2
        for offset in (-0.11, 0.11):
            x = core.x + core.width * (0.5 + offset)
            rect = LayoutRect(x - core.width * 0.05, y, core.width * 0.1, 6)
            self._draw_soft_rounded_rect(pygame, surface, rect, accent, 95, 4, glow=8)
        center = LayoutRect(core.x + core.width * 0.5 - 6, y + 12, 12, 12)
        self._draw_soft_ellipse(pygame, surface, center, accent, 105, 8)

    def _draw_network_waves(
        self,
        pygame: object,
        surface: object,
        layout: BluebotFaceLayout,
        accent: tuple[int, int, int],
        now_ms: int,
    ) -> None:
        core = layout.expression_core
        cx = core.x + core.width * 0.5
        cy = core.y + core.height * 0.24
        for index in range(5):
            angle = -0.75 + index * 0.38
            x = cx + math.sin(angle) * core.width * 0.17
            y = cy + abs(index - 2) * 9
            size = 6 + 4 * self._pulse(now_ms, 0.003, index)
            self._draw_soft_ellipse(pygame, surface, LayoutRect(x - size / 2, y - size / 2, size, size), accent, 70 + index * 9, 7)

    def _draw_help_beacon(
        self,
        pygame: object,
        surface: object,
        layout: BluebotFaceLayout,
        accent: tuple[int, int, int],
        now_ms: int,
    ) -> None:
        core = layout.expression_core
        pulse = self._pulse(now_ms, 0.004, 0)
        size = core.height * (0.05 + pulse * 0.03)
        rect = LayoutRect(core.x + core.width * 0.5 - size / 2, core.y + core.height * 0.22 - size / 2, size, size)
        self._draw_soft_ellipse(pygame, surface, rect, accent, 110, 14)

    def _draw_complete_ring(
        self,
        pygame: object,
        surface: object,
        layout: BluebotFaceLayout,
        accent: tuple[int, int, int],
        now_ms: int,
    ) -> None:
        pulse = self._pulse(now_ms, 0.003, 0)
        core = layout.expression_core
        size = core.height * (0.028 + 0.012 * pulse)
        rect = LayoutRect(
            core.x + core.width * 0.5 - size / 2,
            core.y + core.height * 0.22 - size / 2,
            size,
            size,
        )
        self._draw_soft_ellipse(pygame, surface, rect, accent, 86, 10)

    def _draw_stress_pressure_marks(
        self,
        pygame: object,
        surface: object,
        layout: BluebotFaceLayout,
        accent: tuple[int, int, int],
        now_ms: int,
    ) -> None:
        color = self._mix(accent, self.theme.white_cyan, 0.42)
        pulse = self._pulse(now_ms, 0.0066, 1.1)
        hold = pulse * pulse
        center_y = (layout.left_eye.center_y + layout.right_eye.center_y) / 2
        height = layout.left_eye.height * (0.30 + 0.10 * hold)
        gap = layout.left_eye.width * 0.052
        left_x = layout.left_eye.x - layout.left_eye.width * 0.19
        right_x = layout.right_eye.right + layout.right_eye.width * 0.19
        for side_x, direction in ((left_x, -1), (right_x, 1)):
            for index in range(4):
                length_pattern = (0.66, 0.92, 1.0, 0.78)
                independent = self._pulse(now_ms, 0.0048 + index * 0.0007, index * 0.9 + direction)
                drift = self._wave(now_ms, 0.010 + index * 0.0015, index + direction)
                bar_h = height * length_pattern[index] * (0.86 + 0.20 * independent)
                x = side_x + direction * (index * gap + drift * 2.2)
                y = center_y - bar_h / 2 + self._wave(now_ms, 0.014 + index * 0.001, index) * (1.0 + 2.0 * independent)
                points = [(x, y), (x, y + bar_h)]
                alpha = round(58 + 68 * independent + 18 * (index in {1, 2}))
                self._draw_line_glow(pygame, surface, points, color, 5, alpha)

    def _draw_official_pressure_marks(
        self,
        pygame: object,
        surface: object,
        layout: BluebotFaceLayout,
        accent: tuple[int, int, int],
        now_ms: int,
        opacity: float = 1.0,
    ) -> None:
        color = self._mix(accent, self.theme.white_cyan, 0.38)
        pulse = self._pulse(now_ms, 0.006, 0.4)
        center_y = (layout.left_eye.center_y + layout.right_eye.center_y) / 2
        for base_x, direction in ((layout.left_eye.x - 70, -1), (layout.right_eye.right + 70, 1)):
            lengths = (21, 36, 27)
            for index, length in enumerate(lengths):
                x = base_x + direction * index * 18
                y = center_y - length / 2 + self._wave(now_ms, 0.010 + index * 0.002, index) * 2.0
                alpha = round((24 + 18 * pulse) * opacity)
                self._draw_line_glow(pygame, surface, [(x, y), (x, y + length)], color, 3, alpha)

    def _draw_warning_band(
        self,
        pygame: object,
        surface: object,
        layout: BluebotFaceLayout,
        accent: tuple[int, int, int],
        now_ms: int,
    ) -> None:
        alpha = round(16 + 18 * self._pulse(now_ms, 0.004, 0))
        glow = LayoutRect(
            layout.visible.x + layout.visible.width * 0.24,
            layout.visible.bottom - layout.visible.height * 0.15,
            layout.visible.width * 0.52,
            layout.visible.height * 0.08,
        )
        self._draw_soft_ellipse(pygame, surface, glow, accent, alpha, 14)

    def _draw_eye_x(self, pygame: object, surface: object, rect: LayoutRect, color: tuple[int, int, int]) -> None:
        pad_x = rect.width * 0.16
        pad_y = rect.height * 0.18
        thickness = max(8, round(min(rect.width, rect.height) * 0.13))
        points_a = [(rect.x + pad_x, rect.y + pad_y), (rect.right - pad_x, rect.bottom - pad_y)]
        points_b = [(rect.right - pad_x, rect.y + pad_y), (rect.x + pad_x, rect.bottom - pad_y)]
        self._draw_line_glow(pygame, surface, points_a, color, thickness + 12, 55)
        self._draw_line_glow(pygame, surface, points_b, color, thickness + 12, 55)
        pygame.draw.line(surface, (*color, 230), points_a[0], points_a[1], thickness)
        pygame.draw.line(surface, (*color, 230), points_b[0], points_b[1], thickness)

    def _draw_eye_fail_ring(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        brightness: float,
        now_ms: int,
    ) -> None:
        ring = (148, 242, 248)
        inner = (1, 14, 42)
        inner_blue = (57, 175, 208)
        red_light = (255, 202, 208)
        glint = (248, 255, 255)
        dip = 1.4 * self._pulse(now_ms, 0.0036, 0.8)
        shifted = LayoutRect(rect.x, rect.y + dip, rect.width, rect.height)
        halo = self._inflate(shifted, shifted.width * 0.08, shifted.height * 0.08)
        self._draw_soft_ellipse(pygame, surface, halo, ring, 20, 0)
        self._draw_soft_ellipse(pygame, surface, shifted, ring, round(212 + 16 * brightness), 18)
        pupil = LayoutRect(
            shifted.x + shifted.width * 0.20,
            shifted.y + shifted.height * 0.24,
            shifted.width * 0.60,
            shifted.height * 0.55,
        )
        self._draw_soft_ellipse(pygame, surface, pupil, inner, 236, 5)
        lower_error = LayoutRect(
            shifted.x + shifted.width * 0.18,
            shifted.y + shifted.height * 0.73,
            shifted.width * 0.64,
            shifted.height * 0.12,
        )
        self._draw_soft_ellipse(pygame, surface, lower_error, red_light, 30, 5)
        lower_blue = LayoutRect(
            shifted.x + shifted.width * 0.31,
            shifted.y + shifted.height * 0.61,
            shifted.width * 0.38,
            shifted.height * 0.14,
        )
        self._draw_soft_ellipse(pygame, surface, lower_blue, inner_blue, 36, 5)
        pulse = self._pulse(now_ms, 0.0018, 0.6)
        main = LayoutRect(
            shifted.x + shifted.width * (0.34 + 0.015 * pulse),
            shifted.y + shifted.height * 0.22,
            shifted.width * 0.16,
            shifted.height * 0.10,
        )
        self._draw_soft_ellipse(pygame, surface, main, glint, round(135 + 26 * pulse), 3)

    def _draw_eye_fail_x(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        now_ms: int,
    ) -> None:
        red_dim = (90, 36, 62)
        red_light = (255, 184, 194)
        pulse = self._pulse(now_ms, 0.0036, 0.2)
        alpha = round(154 + 24 * pulse)
        base = LayoutRect(
            rect.x + rect.width * 0.05,
            rect.y + rect.height * 0.08,
            rect.width * 0.90,
            rect.height * 0.84,
        )
        self._draw_soft_ellipse(pygame, surface, base, red_dim, round(26 + 7 * pulse), 12)
        pad_x = rect.width * 0.20
        pad_y = rect.height * 0.20
        thickness = max(8, round(min(rect.width, rect.height) * 0.105))
        points_a = [(rect.x + pad_x, rect.y + pad_y), (rect.right - pad_x, rect.bottom - pad_y)]
        points_b = [(rect.right - pad_x, rect.y + pad_y), (rect.x + pad_x, rect.bottom - pad_y)]
        self._draw_line_glow(pygame, surface, points_a, red_light, thickness + 8, 24)
        self._draw_line_glow(pygame, surface, points_b, red_light, thickness + 8, 24)
        pygame.draw.line(surface, (*red_light, alpha), points_a[0], points_a[1], thickness)
        pygame.draw.line(surface, (*red_light, alpha), points_b[0], points_b[1], thickness)

    def _draw_eye_fail_soft(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        brightness: float,
        now_ms: int,
        side: int,
        shape: str = "fail_soft_v52",
    ) -> None:
        ring = (141, 241, 248)
        inner = (1, 13, 40)
        inner_blue = (59, 169, 205)
        red_light = (255, 174, 185)
        glint = (248, 255, 255)
        pulse = self._pulse(now_ms, 0.0036, 0.4)
        sigh = self._wave(now_ms, 0.0024, 1.1)
        is_v53 = shape.endswith("_v53")
        droop = rect.height * (0.018 + 0.008 * pulse if is_v53 else 0.010 + 0.010 * pulse)
        skew = side * rect.width * 0.010 * sigh
        eye = LayoutRect(
            rect.x + rect.width * 0.010,
            rect.y + droop,
            rect.width * 0.980,
            rect.height * (0.965 - 0.018 * pulse),
        )
        halo = self._inflate(eye, eye.width * 0.08, eye.height * 0.08)
        self._draw_soft_ellipse(pygame, surface, halo, ring, 17, 0)
        self._draw_soft_ellipse(pygame, surface, eye, ring, round(210 + 15 * brightness), 18)

        pupil = LayoutRect(
            eye.x + eye.width * (0.20 + 0.012 * side),
            eye.y + eye.height * (0.33 if is_v53 else 0.29),
            eye.width * 0.60,
            eye.height * 0.50,
        )
        self._draw_soft_ellipse(pygame, surface, pupil, inner, 234, 5)

        lower_blue = LayoutRect(
            eye.x + eye.width * 0.30,
            eye.y + eye.height * 0.62,
            eye.width * 0.40,
            eye.height * 0.13,
        )
        self._draw_soft_ellipse(pygame, surface, lower_blue, inner_blue, 34, 5)

        lower_error = LayoutRect(
            eye.x + eye.width * 0.18,
            eye.y + eye.height * 0.76,
            eye.width * 0.64,
            eye.height * 0.09,
        )
        self._draw_soft_ellipse(pygame, surface, lower_error, red_light, 24 if side > 0 else 14, 4)

        if side > 0:
            cx = eye.center_x + eye.width * (0.12 + 0.006 * pulse)
            cy = eye.center_y - eye.height * 0.08 + skew
            thickness = max(3, round(min(eye.width, eye.height) * (0.030 if is_v53 else 0.032)))
            if is_v53:
                mark_w = eye.width * 0.18
                mark_h = eye.height * 0.13
                points_a = [(cx - mark_w * 0.40, cy - mark_h * 0.40), (cx + mark_w * 0.40, cy + mark_h * 0.40)]
                points_b = [(cx + mark_w * 0.40, cy - mark_h * 0.40), (cx - mark_w * 0.40, cy + mark_h * 0.40)]
                alpha = round(112 + 22 * pulse)
                self._draw_line_glow(pygame, surface, points_a, red_light, thickness + 4, 18)
                self._draw_line_glow(pygame, surface, points_b, red_light, thickness + 4, 18)
                pygame.draw.line(surface, (*red_light, alpha), points_a[0], points_a[1], thickness)
                pygame.draw.line(surface, (*red_light, alpha), points_b[0], points_b[1], thickness)
            else:
                crack = [
                    (cx - eye.width * 0.070, cy - eye.height * 0.040),
                    (cx - eye.width * 0.006, cy + eye.height * 0.018),
                    (cx + eye.width * 0.065, cy - eye.height * 0.006),
                ]
                self._draw_line_glow(pygame, surface, crack, red_light, thickness + 5, 24)
                pygame.draw.lines(surface, (*red_light, round(128 + 24 * pulse)), False, crack, thickness)
                dot = LayoutRect(
                    cx + eye.width * 0.080,
                    cy + eye.height * 0.020,
                    eye.width * 0.032,
                    eye.height * 0.024,
                )
                self._draw_soft_ellipse(pygame, surface, dot, red_light, round(74 + 18 * pulse), 1)

        main = LayoutRect(
            eye.x + eye.width * (0.32 - 0.03 * side + 0.010 * pulse),
            eye.y + eye.height * 0.20,
            eye.width * 0.16,
            eye.height * 0.10,
        )
        self._draw_soft_ellipse(pygame, surface, main, glint, round(126 + 22 * pulse), 3)

    def _draw_eye_fail_sad_oval(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        brightness: float,
        now_ms: int,
        side: int,
        shape: str = "fail_sad_oval_v54",
    ) -> None:
        ring = (116, 232, 242)
        white = (202, 252, 255)
        inner = (1, 13, 40)
        shadow = (34, 126, 164)
        glint = (232, 255, 255)
        pulse = self._pulse(now_ms, 0.0036, 0.3)
        sigh = self._pulse(now_ms, 0.0018, 1.0)
        is_v55 = shape.endswith("_v55")
        eye = LayoutRect(
            rect.x,
            rect.y + rect.height * ((0.020 if is_v55 else 0.010) + 0.012 * sigh) + (3.0 if side > 0 else 0.0),
            rect.width,
            rect.height * ((0.965 if is_v55 else 0.982) - 0.016 * pulse),
        )
        halo = self._inflate(eye, eye.width * 0.08, eye.height * 0.08)
        self._draw_soft_ellipse(pygame, surface, halo, ring, 16, 0)
        self._draw_soft_ellipse(pygame, surface, eye, white, round(212 + 18 * brightness), 18)

        inward = 1 if side < 0 else -1
        pupil = LayoutRect(
            eye.center_x + inward * eye.width * (0.050 if is_v55 else 0.028) - eye.width * (0.300 if is_v55 else 0.305),
            eye.y + eye.height * (0.415 if is_v55 else 0.36),
            eye.width * (0.60 if is_v55 else 0.61),
            eye.height * (0.43 if is_v55 else 0.47),
        )
        self._draw_soft_ellipse(pygame, surface, pupil, inner, 232, 5)

        lower_shadow = LayoutRect(
            pupil.x + pupil.width * 0.05,
            pupil.y + pupil.height * (0.55 if is_v55 else 0.62),
            pupil.width * 0.90,
            pupil.height * (0.30 if is_v55 else 0.24),
        )
        self._draw_soft_ellipse(pygame, surface, lower_shadow, shadow, 44 if is_v55 else 34, 4)

        shine = LayoutRect(
            eye.x + eye.width * (0.35 if side < 0 else 0.32),
            eye.y + eye.height * (0.165 if is_v55 else 0.18),
            eye.width * (0.14 if is_v55 else 0.17),
            eye.height * (0.08 if is_v55 else 0.10),
        )
        self._draw_soft_ellipse(pygame, surface, shine, glint, round((72 if is_v55 else 92) + 16 * pulse), 3)

    def _draw_eye_failed_stress_x(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        now_ms: int,
    ) -> None:
        red_dim = (90, 34, 58)
        red_light = (255, 204, 210)
        pulse = self._pulse(now_ms, 0.0038, 0.4)
        backing = LayoutRect(
            rect.center_x - rect.width * 0.40 / 2,
            rect.center_y - rect.height * 0.48 / 2,
            rect.width * 0.40,
            rect.height * 0.48,
        )
        self._draw_soft_ellipse(pygame, surface, backing, red_dim, round(46 + 10 * pulse), 12)

        pad_x = rect.width * 0.19
        pad_y = rect.height * 0.18
        thickness = max(14, min(16, round(min(rect.width, rect.height) * 0.17)))
        alpha = round(173 + 21 * pulse)
        points_a = [(rect.x + pad_x, rect.y + pad_y), (rect.right - pad_x, rect.bottom - pad_y)]
        points_b = [(rect.right - pad_x, rect.y + pad_y), (rect.x + pad_x, rect.bottom - pad_y)]
        self._draw_line_glow(pygame, surface, points_a, red_light, thickness + 12, 34)
        self._draw_line_glow(pygame, surface, points_b, red_light, thickness + 12, 34)
        for start, end in (points_a, points_b):
            pygame.draw.line(surface, (*red_light, alpha), start, end, thickness)
            radius = max(3, thickness // 2)
            pygame.draw.circle(surface, (*red_light, alpha), (round(start[0]), round(start[1])), radius)
            pygame.draw.circle(surface, (*red_light, alpha), (round(end[0]), round(end[1])), radius)

    def _draw_eye_stress_squeeze(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        brightness: float,
        now_ms: int,
        side: int,
        shape: str,
    ) -> None:
        is_pressure_c = shape.endswith("_c")
        white = self._mix((255, 211, 108), self.theme.white_cyan, 0.16) if is_pressure_c else self._mix((184, 252, 255), self.theme.white_cyan, 0.72)
        rim = (255, 211, 108) if is_pressure_c else (126, 239, 248)
        lower_rim = (255, 233, 142) if is_pressure_c else rim
        ink = (1, 10, 30)
        pulse = self._pulse(now_ms, 0.0068, 0.5)
        squeeze = 0.43 + 0.13 * pulse if is_pressure_c else 0.66 + 0.08 * pulse
        jitter = self._wave(now_ms, 0.016, side) * (2.0 if is_pressure_c else 1.6)
        inward = 1 if side < 0 else -1
        pinch_shift = inward * rect.width * 0.030 * pulse if is_pressure_c else 0.0
        pinch_scale = 1.0 - (0.055 * pulse if is_pressure_c else 0.02 * pulse)
        eye = LayoutRect(
            rect.x + rect.width * (1.0 - pinch_scale) / 2 + pinch_shift,
            rect.y + rect.height * (1.0 - squeeze) / 2 + jitter,
            rect.width * pinch_scale,
            rect.height * squeeze,
        )
        halo = self._inflate(eye, eye.width * 0.07, eye.height * 0.14)
        self._draw_soft_ellipse(pygame, surface, halo, rim, 26, 0)
        if is_pressure_c:
            points = self._lens_points(eye, height_ratio=0.68, top_bias=-0.02, bottom_bias=0.02)
            self._draw_soft_polygon(pygame, surface, points, white, round(222 + 18 * brightness), 14)
        else:
            self._draw_soft_ellipse(pygame, surface, eye, white, round(230 + 18 * brightness), 18)

        if is_pressure_c:
            slit = LayoutRect(
                eye.x + eye.width * 0.22,
                eye.center_y - eye.height * 0.08,
                eye.width * 0.56,
                max(5.0, eye.height * 0.16),
            )
            self._draw_soft_rounded_rect(pygame, surface, slit, ink, 176, round(slit.height / 2), glow=0)
            pinch = LayoutRect(
                eye.center_x + inward * eye.width * 0.20 - eye.height * 0.08,
                eye.center_y - eye.height * 0.14,
                eye.height * 0.16,
                eye.height * 0.16,
            )
            self._draw_soft_ellipse(pygame, surface, pinch, ink, 128, 1)
        else:
            pupil_size = min(eye.width, eye.height) * 0.24
            pupil = LayoutRect(
                eye.center_x + inward * eye.width * 0.23 - pupil_size / 2,
                eye.center_y - pupil_size * 0.52,
                pupil_size,
                pupil_size,
            )
            self._draw_soft_ellipse(pygame, surface, pupil, ink, 238, 2)

        lower = LayoutRect(
            eye.x + eye.width * 0.18,
            eye.y + eye.height * (0.66 if is_pressure_c else 0.70),
            eye.width * 0.64,
            eye.height * (0.13 if is_pressure_c else 0.11),
        )
        self._draw_soft_ellipse(pygame, surface, lower, lower_rim, 34 if is_pressure_c else 30, 4)

        shine = LayoutRect(
            eye.x + eye.width * (0.20 if side < 0 else 0.58),
            eye.y + eye.height * (0.13 if is_pressure_c else 0.14),
            eye.width * (0.14 if is_pressure_c else 0.12),
            eye.height * (0.10 if is_pressure_c else 0.08),
        )
        self._draw_soft_ellipse(pygame, surface, shine, self.theme.white_cyan, 56 if is_pressure_c else 64, 3)

    def _draw_eye_wide_pressure(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        brightness: float,
        now_ms: int,
        side: int,
    ) -> None:
        outer = (139, 239, 248)
        dark = (1, 14, 45)
        eye_fill = (229, 252, 255)
        wet_blue = (75, 198, 228)
        warm = (255, 234, 164)
        glint = (248, 255, 255)
        pulse = self._pulse(now_ms, 0.0066, 1.1 + side * 0.12)
        brace = self._wave(now_ms, 0.018, 1.8 + side * 0.4)
        micro = self._wave(now_ms, 0.041, side * 1.7)
        tremble = (brace * 1.0 + micro * 0.6) * (0.35 + 0.65 * pulse)
        inward = 1 if side < 0 else -1
        base_size = min(rect.width * 1.02, rect.height * 0.98)
        squeeze = self._pulse(now_ms, 0.009, 0.4 + side * 0.2)
        stretch_x = 1.0 + 0.022 * squeeze + 0.004 * brace
        stretch_y = 1.0 - 0.082 * squeeze + 0.006 * brace
        eye_w = base_size * stretch_x
        eye_h = base_size * stretch_y
        eye = LayoutRect(
            rect.center_x - eye_w / 2 + inward * rect.width * (0.006 + 0.006 * pulse) + micro * 0.45,
            rect.center_y - eye_h / 2 + tremble,
            eye_w,
            eye_h,
        )
        self._draw_soft_ellipse(pygame, surface, eye, outer, round(218 + 18 * brightness), 2)

        core = LayoutRect(
            eye.x + eye.width * 0.10,
            eye.y + eye.height * 0.12,
            eye.width * 0.80,
            eye.height * 0.78,
        )
        self._draw_soft_ellipse(pygame, surface, core, eye_fill, 236, 0)

        wet = LayoutRect(
            core.x + core.width * 0.14,
            core.y + core.height * 0.58,
            core.width * 0.72,
            core.height * 0.18,
        )
        self._draw_soft_ellipse(pygame, surface, wet, wet_blue, 24, 4)

        lower = LayoutRect(
            eye.x + eye.width * 0.18,
            eye.y + eye.height * 0.78,
            eye.width * 0.64,
            eye.height * 0.13,
        )
        self._draw_soft_ellipse(pygame, surface, lower, warm, 22, 5)

        pupil_size = eye.width * (0.168 + 0.006 * pulse)
        pupil = LayoutRect(
            eye.center_x + inward * eye.width * (0.245 + 0.012 * pulse) - pupil_size / 2 + micro * 0.30,
            eye.center_y - eye.height * (0.035 + 0.012 * pulse) - pupil_size / 2 + brace * 0.45,
            pupil_size,
            pupil_size,
        )
        self._draw_soft_ellipse(pygame, surface, pupil, dark, 252, 1)

        shine = LayoutRect(
            eye.x + eye.width * (0.26 if side < 0 else 0.52),
            eye.y + eye.height * 0.16,
            eye.width * 0.18,
            eye.height * 0.075,
        )
        self._draw_soft_ellipse(pygame, surface, shine, glint, 112, 3)

    def _draw_eye_puppy(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        color: tuple[int, int, int],
        brightness: float,
        now_ms: int,
        side: int,
    ) -> None:
        self._draw_soft_ellipse(pygame, surface, rect, color, round(220 + 20 * brightness), 32)
        lower = LayoutRect(
            rect.x + rect.width * 0.18,
            rect.y + rect.height * 0.67,
            rect.width * 0.64,
            rect.height * 0.16,
        )
        self._draw_soft_ellipse(pygame, surface, lower, self.theme.white_cyan, 60, 5)
        wobble = self._pulse(now_ms, 0.004, side * 0.8)
        big = LayoutRect(
            rect.x + rect.width * (0.23 + 0.06 * wobble),
            rect.y + rect.height * 0.16,
            rect.width * 0.2,
            rect.height * 0.13,
        )
        small = LayoutRect(
            rect.x + rect.width * 0.58,
            rect.y + rect.height * (0.27 + 0.03 * wobble),
            rect.width * 0.11,
            rect.height * 0.08,
        )
        self._draw_soft_ellipse(pygame, surface, big, self.theme.white_cyan, 105, 4)
        self._draw_soft_ellipse(pygame, surface, small, self.theme.white_cyan, 82, 3)

    def _draw_eye_puppy_teary(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        color: tuple[int, int, int],
        brightness: float,
        now_ms: int,
        side: int,
    ) -> None:
        self._draw_soft_ellipse(pygame, surface, rect, color, round(224 + 18 * brightness), 32)
        lower = LayoutRect(
            rect.x + rect.width * 0.13,
            rect.y + rect.height * 0.62,
            rect.width * 0.74,
            rect.height * 0.22,
        )
        self._draw_soft_ellipse(pygame, surface, lower, self._mix(color, self.theme.white_cyan, 0.22), 48, 5)
        drift = 2.0 * self._wave(now_ms, 0.0026, side * 0.9)
        alpha = round(148 + 36 * self._pulse(now_ms, 0.0019, side))
        big = LayoutRect(
            rect.x + rect.width * 0.31 + drift,
            rect.y + rect.height * 0.26 - drift * 0.25,
            rect.width * 0.18,
            rect.height * 0.12,
        )
        small = LayoutRect(
            rect.x + rect.width * 0.58 + drift * 0.5,
            rect.y + rect.height * 0.34 + drift * 0.2,
            rect.width * 0.1,
            rect.height * 0.08,
        )
        drop = LayoutRect(
            rect.x + rect.width * 0.43 - drift * 0.2,
            rect.y + rect.height * 0.52 + drift * 0.25,
            rect.width * 0.12,
            rect.height * 0.18,
        )
        self._draw_soft_ellipse(pygame, surface, big, self.theme.white_cyan, alpha, 5)
        self._draw_soft_ellipse(pygame, surface, small, self.theme.white_cyan, max(98, alpha - 42), 4)
        self._draw_soft_ellipse(pygame, surface, drop, self.theme.white_cyan, max(104, alpha - 34), 5)

    def _draw_eye_puppy_ring(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        brightness: float,
        now_ms: int,
        side: int,
        shape: str,
    ) -> None:
        outer = (139, 239, 248)
        dark = (1, 14, 45)
        wet_blue = (75, 198, 228)
        warm = (255, 234, 164)
        glint = (248, 255, 255)

        ring_alpha = round(222 + 16 * brightness)
        halo = LayoutRect(
            rect.x - rect.width * 0.05,
            rect.y - rect.height * 0.05,
            rect.width * 1.10,
            rect.height * 1.10,
        )
        self._draw_soft_ellipse(pygame, surface, halo, outer, 18, 0)
        self._draw_soft_ellipse(pygame, surface, rect, outer, ring_alpha, 0)

        pupil = LayoutRect(
            rect.x + rect.width * 0.18,
            rect.y + rect.height * 0.21,
            rect.width * 0.64,
            rect.height * 0.63,
        )
        self._draw_soft_ellipse(pygame, surface, pupil, dark, 238, 0)

        wet = LayoutRect(
            pupil.x + pupil.width * 0.12,
            pupil.y + pupil.height * 0.58,
            pupil.width * 0.76,
            pupil.height * 0.20,
        )
        self._draw_soft_ellipse(pygame, surface, wet, wet_blue, 42, 5)

        lower = LayoutRect(
            rect.x + rect.width * 0.16,
            rect.y + rect.height * 0.78,
            rect.width * 0.68,
            rect.height * 0.16,
        )
        self._draw_soft_ellipse(pygame, surface, lower, warm, 44, 8)

        pulse = self._pulse(now_ms, 0.0018, side * 0.7)
        drift = 1.8 * self._wave(now_ms, 0.0016, side * 0.8)
        inward = 1 if side < 0 else -1
        tear_drop = 1.2 * self._pulse(now_ms, 0.0021, 1.6 + side)

        if side < 0:
            main = (0.48, 0.18, 0.23, 0.16)
            small = (0.37, 0.40, 0.10, 0.09)
            tear = (0.57, 0.60, 0.10, 0.15)
        else:
            main = (0.30, 0.18, 0.23, 0.16)
            small = (0.60, 0.40, 0.10, 0.09)
            tear = (0.35, 0.60, 0.10, 0.15)

        main_alpha = round(208 + 28 * pulse)
        small_alpha = round(168 + 20 * pulse)
        tear_alpha = round(132 + 36 * self._pulse(now_ms, 0.002, side + 2.5))
        self._draw_eye_light(pygame, surface, rect, main, glint, main_alpha, 5, dx=inward * drift, dy=-0.35 * abs(drift))
        self._draw_eye_light(pygame, surface, rect, small, glint, small_alpha, 4, dx=inward * drift * 0.35, dy=0.2 * drift)
        self._draw_eye_light(pygame, surface, rect, tear, glint, tear_alpha, 4, dx=-inward * drift * 0.15, dy=tear_drop)

    def _draw_eye_puppy_squeeze(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        brightness: float,
        now_ms: int,
        side: int,
    ) -> None:
        outer = (139, 239, 248)
        dark = (1, 14, 45)
        wet_blue = (75, 198, 228)
        warm = (255, 234, 164)
        glint = (248, 255, 255)
        pulse = self._pulse(now_ms, 0.0066, 1.1 + side * 0.16)
        hold = pulse * pulse
        inward = 1 if side < 0 else -1
        effort = self._wave(now_ms, 0.022, side) * (0.7 + 1.2 * hold)
        eye = LayoutRect(
            rect.x + rect.width * (0.05 + 0.018 * hold) + inward * rect.width * (0.012 + 0.026 * hold),
            rect.y + rect.height * (0.24 + 0.02 * hold) + effort,
            rect.width * (0.90 - 0.035 * hold),
            rect.height * (0.52 - 0.05 * hold),
        )

        cx = eye.x + eye.width * 0.5
        cy = eye.y + eye.height * (0.54 + 0.03 * hold)
        left = eye.x + eye.width * (0.03 + 0.015 * hold)
        right = eye.right - eye.width * (0.03 + 0.015 * hold)
        top_center = eye.y + eye.height * (0.18 + 0.12 * hold)
        lower_center = eye.y + eye.height * (0.74 - 0.08 * hold)
        inner_pull = inward * eye.width * (0.025 + 0.025 * hold)
        left_tip = (left, cy + eye.height * (0.015 + 0.015 * hold))
        right_tip = (right, cy + eye.height * (0.02 + 0.012 * hold))
        upper: list[tuple[float, float]] = [left_tip]
        lower: list[tuple[float, float]] = [right_tip]
        for index in range(1, 8):
            t = index / 8
            x = left + (right - left) * t
            arch = math.sin(math.pi * t)
            end_lift = abs(t - 0.5) * 2
            x += inner_pull * arch
            y = (
                top_center
                + eye.height * (0.22 * end_lift)
                - eye.height * (0.12 - 0.04 * hold) * arch
                + eye.height * 0.03 * math.sin(math.pi * t * 2 + side)
            )
            upper.append((x, y))
        upper.append(right_tip)
        for index in range(7, 0, -1):
            t = index / 8
            x = left + (right - left) * t
            arch = math.sin(math.pi * t)
            end_lift = abs(t - 0.5) * 2
            x -= inner_pull * arch * 0.35
            y = (
                lower_center
                - eye.height * (0.12 * end_lift)
                + eye.height * (0.09 - 0.03 * hold) * arch
                + eye.height * 0.012 * math.sin(math.pi * t * 2 + side + 1.4)
            )
            lower.append((x, y))
        lower.append(left_tip)
        points = upper + lower
        halo = self._inflate(eye, eye.width * 0.08, eye.height * 0.14)
        self._draw_soft_ellipse(pygame, surface, halo, outer, 10, 0)
        self._draw_soft_polygon(pygame, surface, points, outer, round(216 + 18 * brightness), 8)

        pupil = [
            (eye.x + eye.width * 0.20, cy + eye.height * 0.01),
            (eye.x + eye.width * 0.36, cy - eye.height * (0.08 - 0.02 * hold)),
            (eye.x + eye.width * 0.64, cy - eye.height * (0.08 - 0.02 * hold)),
            (eye.x + eye.width * 0.80, cy + eye.height * 0.02),
            (eye.x + eye.width * 0.65, cy + eye.height * (0.12 + 0.02 * hold)),
            (eye.x + eye.width * 0.35, cy + eye.height * (0.12 + 0.02 * hold)),
        ]
        self._draw_soft_polygon(pygame, surface, pupil, dark, 224, 2)

        crease = [
            (left + eye.width * 0.08, top_center + eye.height * (0.10 + 0.01 * hold)),
            (eye.x + eye.width * 0.32 + inner_pull, top_center + eye.height * (0.00 + 0.01 * hold)),
            (cx + inward * eye.width * 0.04, top_center - eye.height * (0.04 + 0.01 * hold)),
            (eye.x + eye.width * 0.68 + inner_pull, top_center + eye.height * (0.02 + 0.01 * hold)),
            (right - eye.width * 0.08, top_center + eye.height * (0.10 + 0.01 * hold)),
        ]
        self._draw_line_glow(pygame, surface, crease, outer, 4, round(108 + 42 * hold))

        inner_corner = [
            (eye.x + (eye.width * 0.80 if side < 0 else eye.width * 0.10), cy - eye.height * 0.03),
            (eye.x + (eye.width * 0.91 if side < 0 else eye.width * 0.21), cy + eye.height * 0.02),
            (eye.x + (eye.width * 0.78 if side < 0 else eye.width * 0.08), cy + eye.height * 0.09),
        ]
        self._draw_soft_polygon(pygame, surface, inner_corner, warm, round(34 + 30 * hold), 2)

        wet = LayoutRect(
            eye.x + eye.width * 0.30,
            cy + eye.height * 0.06,
            eye.width * 0.40,
            max(4.0, eye.height * 0.08),
        )
        self._draw_soft_ellipse(pygame, surface, wet, wet_blue, 24, 2)

        drift = 1.2 * self._wave(now_ms, 0.0032, side * 0.8)
        if side < 0:
            main = (0.48, 0.04, 0.23, 0.15)
            small = (0.36, 0.50, 0.10, 0.10)
            tear = (0.58, 0.60, 0.09, 0.17)
        else:
            main = (0.29, 0.04, 0.23, 0.15)
            small = (0.61, 0.50, 0.10, 0.10)
            tear = (0.34, 0.60, 0.09, 0.17)
        self._draw_eye_light(pygame, surface, eye, main, glint, round(176 + 34 * pulse), 4, dx=inward * drift)
        self._draw_eye_light(pygame, surface, eye, small, glint, round(128 + 26 * pulse), 3, dx=inward * drift * 0.3)
        self._draw_eye_light(pygame, surface, eye, tear, glint, round(92 + 28 * pulse), 3, dx=-inward * drift * 0.2)

    def _draw_eye_light(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        item: tuple[float, float, float, float],
        color: tuple[int, int, int],
        alpha: int,
        glow: int,
        dx: float = 0.0,
        dy: float = 0.0,
    ) -> None:
        x, y, w, h = item
        self._draw_soft_ellipse(
            pygame,
            surface,
            LayoutRect(
                rect.x + rect.width * x + dx,
                rect.y + rect.height * y + dy,
                rect.width * w,
                rect.height * h,
            ),
            color,
            alpha,
            glow,
        )

    def _draw_eye_official(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        shape: str,
        brightness: float,
        now_ms: int,
        side: int,
    ) -> None:
        if shape == "official_eye_happy_arc":
            arc_rect = LayoutRect(rect.x, rect.y + rect.height * 0.12, rect.width, rect.height * 0.78)
            self._draw_arc(pygame, surface, arc_rect, (180, 248, 255), math.radians(205), math.radians(335), max(8, round(rect.height * 0.18)), alpha=230)
            return
        if shape == "official_eye_sad":
            pulse = self._pulse(now_ms, 0.003, side)
            eye = LayoutRect(rect.x, rect.y + rect.height * (0.10 + 0.04 * pulse), rect.width, rect.height * 0.78)
            self._draw_soft_ellipse(pygame, surface, eye, (104, 234, 255), round(210 + 18 * brightness), 10)
            pupil = LayoutRect(eye.x + eye.width * 0.18, eye.y + eye.height * 0.48, eye.width * 0.64, eye.height * 0.32)
            self._draw_soft_ellipse(pygame, surface, pupil, (1, 19, 78), 118, 2)
            return

        pulse = self._pulse(now_ms, 0.003, side)
        is_help = shape == "official_eye_help"
        eye = LayoutRect(
            rect.x + rect.width * 0.04,
            rect.y + rect.height * (0.04 + 0.02 * pulse),
            rect.width * 0.92,
            rect.height * 0.92,
        )
        self._draw_soft_ellipse(pygame, surface, eye, (112, 231, 255), round(210 + 12 * brightness), 11)
        glint = LayoutRect(eye.x + eye.width * 0.30, eye.y + eye.height * 0.12, eye.width * 0.36, eye.height * 0.24)
        self._draw_soft_ellipse(pygame, surface, glint, (238, 255, 255), 113, 3)
        lower = LayoutRect(eye.center_x - eye.width * 0.16, eye.y + eye.height * 0.56, eye.width * 0.32, eye.height * 0.24)
        self._draw_soft_ellipse(pygame, surface, lower, (255, 224, 112), 38 if is_help else 22, 2)

    def _draw_eye_shaped(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        shape: str,
        color: tuple[int, int, int],
        brightness: float,
        now_ms: int,
        side: int,
    ) -> None:
        points = self._eye_shape_points(rect, shape, now_ms, side)
        self._draw_soft_polygon(pygame, surface, points, color, round(212 + 24 * brightness), 18)
        if shape != "squint":
            glint = self._eye_glint_rect(rect, side, now_ms)
            self._draw_soft_ellipse(pygame, surface, glint, self.theme.white_cyan, round(46 + 28 * brightness), 4)

    def _eye_shape_points(
        self,
        rect: LayoutRect,
        shape: str,
        now_ms: int,
        side: int,
    ) -> list[tuple[float, float]]:
        if shape == "dome":
            base_y = rect.y + rect.height * 0.62
            top_cy = base_y
            rx = rect.width * 0.45
            ry = rect.height * 0.52
            top = [
                (
                    rect.center_x + math.cos(math.pi + math.pi * index / 18) * rx,
                    top_cy + math.sin(math.pi + math.pi * index / 18) * ry,
                )
                for index in range(19)
            ]
            bottom = [
                (
                    rect.center_x + rx - 2 * rx * index / 18,
                    base_y + rect.height * 0.1 * math.sin(math.pi * index / 18),
                )
                for index in range(19)
            ]
            return top + bottom

        if shape == "squint":
            return self._lens_points(rect, height_ratio=0.26, top_bias=-0.02, bottom_bias=0.02)

        if shape == "almond":
            return self._lens_points(rect, height_ratio=0.72, top_bias=-0.08, bottom_bias=0.02)

        if shape == "bean":
            wave = math.sin(now_ms * 0.002 + side)
            points: list[tuple[float, float]] = []
            count = 18
            for index in range(count + 1):
                t = index / count
                x = rect.x + rect.width * (0.08 + 0.84 * t)
                y = rect.center_y - rect.height * (0.34 + 0.05 * wave) * math.sin(math.pi * t)
                y += rect.height * 0.06 * math.sin(math.pi * t * 2 + side)
                points.append((x, y))
            for index in range(count, -1, -1):
                t = index / count
                x = rect.x + rect.width * (0.08 + 0.84 * t)
                y = rect.center_y + rect.height * (0.28 - 0.03 * wave) * math.sin(math.pi * t)
                y += rect.height * 0.05 * math.sin(math.pi * t * 2 + side + 1.8)
                points.append((x, y))
            return points

        return self._lens_points(rect, height_ratio=0.82, top_bias=0.0, bottom_bias=0.0)

    def _lens_points(
        self,
        rect: LayoutRect,
        height_ratio: float,
        top_bias: float,
        bottom_bias: float,
    ) -> list[tuple[float, float]]:
        count = 18
        half_height = rect.height * height_ratio * 0.5
        points: list[tuple[float, float]] = []
        for index in range(count + 1):
            t = index / count
            x = rect.x + rect.width * (0.08 + 0.84 * t)
            y = rect.center_y + rect.height * top_bias - half_height * math.sin(math.pi * t)
            points.append((x, y))
        for index in range(count, -1, -1):
            t = index / count
            x = rect.x + rect.width * (0.08 + 0.84 * t)
            y = rect.center_y + rect.height * bottom_bias + half_height * 0.72 * math.sin(math.pi * t)
            points.append((x, y))
        return points

    def _draw_eye_arc(self, pygame: object, surface: object, rect: LayoutRect, color: tuple[int, int, int], up: bool, alpha: int) -> None:
        thickness = max(7, round(min(rect.width, rect.height) * 0.13))
        start = math.radians(25 if up else 205)
        end = math.radians(155 if up else 335)
        self._draw_arc(pygame, surface, rect, color, start, end, thickness, alpha=alpha)

    def _draw_arc(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        color: tuple[int, int, int],
        start: float,
        end: float,
        thickness: int,
        alpha: int = 225,
    ) -> None:
        pygame_rect = self._pygame_rect(pygame, rect)
        margin = max(12, 8 + thickness // 2)
        layer_size = (pygame_rect.width + margin * 2, pygame_rect.height + margin * 2)
        glow = self._layer_for_size(pygame, layer_size)
        local_rect = pygame.Rect(margin, margin, pygame_rect.width, pygame_rect.height)
        for add, glow_alpha in ((16, 26), (9, 42)):
            big_rect = local_rect.inflate(add, add)
            pygame.draw.arc(glow, (*color, glow_alpha), big_rect, start, end, thickness + add // 2)
        surface.blit(glow, (pygame_rect.x - margin, pygame_rect.y - margin))
        pygame.draw.arc(surface, (*color, alpha), pygame_rect, start, end, thickness)

    def _draw_soft_ellipse(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        color: tuple[int, int, int],
        alpha: int,
        glow: int,
    ) -> None:
        pygame_rect = self._pygame_rect(pygame, rect)
        margin = max(1, math.ceil(max(rect.width, rect.height) * 0.21)) if glow > 0 else 1
        layer_size = (pygame_rect.width + margin * 2, pygame_rect.height + margin * 2)
        layer = self._layer_for_size(pygame, layer_size)
        local_rect = pygame.Rect(margin, margin, pygame_rect.width, pygame_rect.height)
        if glow > 0:
            for scale, glow_alpha in ((1.42, 18), (1.22, 36)):
                inflated = local_rect.inflate(
                    round(rect.width * (scale - 1)),
                    round(rect.height * (scale - 1)),
                )
                pygame.draw.ellipse(layer, (*color, glow_alpha), inflated)
        pygame.draw.ellipse(layer, (*color, alpha), local_rect)
        surface.blit(layer, (pygame_rect.x - margin, pygame_rect.y - margin))

    def _draw_radial_glow(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        color: tuple[int, int, int],
        alpha: int,
    ) -> None:
        target = self._pygame_rect(pygame, rect)
        key = (target.width, target.height, color, alpha)
        glow = self._radial_glow_cache.get(key)
        if glow is None:
            seed = pygame.Surface((96, 48), pygame.SRCALPHA)
            for y in range(48):
                ny = (y - 23.5) / 23.5
                for x in range(96):
                    nx = (x - 47.5) / 47.5
                    falloff = math.exp(-4.5 * (nx * nx + ny * ny))
                    seed.set_at((x, y), (*color, round(alpha * falloff)))
            glow = pygame.transform.smoothscale(seed, target.size)
            self._radial_glow_cache[key] = glow
        surface.blit(glow, target.topleft)

    def _draw_soft_rounded_rect(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        color: tuple[int, int, int],
        alpha: int,
        radius: int,
        glow: int,
    ) -> None:
        pygame_rect = self._pygame_rect(pygame, rect)
        margin = max(1, glow)
        layer_size = (pygame_rect.width + margin * 2, pygame_rect.height + margin * 2)
        layer = self._layer_for_size(pygame, layer_size)
        local_rect = pygame.Rect(margin, margin, pygame_rect.width, pygame_rect.height)
        if glow > 0:
            for add, glow_alpha in ((glow * 2, 14), (glow, 28)):
                big = local_rect.inflate(add, add)
                pygame.draw.rect(layer, (*color, glow_alpha), big, border_radius=radius + add // 2)
        pygame.draw.rect(layer, (*color, alpha), local_rect, border_radius=radius)
        surface.blit(layer, (pygame_rect.x - margin, pygame_rect.y - margin))

    def _draw_line_glow(
        self,
        pygame: object,
        surface: object,
        points: list[tuple[float, float]] | tuple[tuple[float, float], ...],
        color: tuple[int, int, int],
        thickness: int,
        alpha: int,
    ) -> None:
        min_x = min(point[0] for point in points)
        max_x = max(point[0] for point in points)
        min_y = min(point[1] for point in points)
        max_y = max(point[1] for point in points)
        margin = max(1, thickness // 2 + 1)
        origin_x = math.floor(min_x) - margin
        origin_y = math.floor(min_y) - margin
        width = max(1, math.ceil(max_x) - origin_x + margin)
        height = max(1, math.ceil(max_y) - origin_y + margin)
        layer = self._layer_for_size(pygame, (width, height))
        local_points = [(round(x - origin_x), round(y - origin_y)) for x, y in points]
        pygame.draw.lines(layer, (*color, alpha), False, local_points, thickness)
        surface.blit(layer, (origin_x, origin_y))

    def _draw_soft_polygon(
        self,
        pygame: object,
        surface: object,
        points: list[tuple[float, float]],
        color: tuple[int, int, int],
        alpha: int,
        glow: int,
    ) -> None:
        center_x = sum(point[0] for point in points) / len(points)
        center_y = sum(point[1] for point in points) / len(points)
        scaled_sets: list[tuple[list[tuple[float, float]], int]] = []
        if glow > 0:
            for scale, glow_alpha in ((1.22, 18), (1.11, 34)):
                scaled_sets.append((
                    [
                        (
                            center_x + (x - center_x) * scale,
                            center_y + (y - center_y) * scale,
                        )
                        for x, y in points
                    ],
                    glow_alpha,
                ))
        scaled_sets.append((points, alpha))
        all_points = [point for point_set, _ in scaled_sets for point in point_set]
        min_x = min(point[0] for point in all_points)
        max_x = max(point[0] for point in all_points)
        min_y = min(point[1] for point in all_points)
        max_y = max(point[1] for point in all_points)
        margin = max(1, glow)
        origin_x = math.floor(min_x) - margin
        origin_y = math.floor(min_y) - margin
        width = max(1, math.ceil(max_x) - origin_x + margin)
        height = max(1, math.ceil(max_y) - origin_y + margin)
        layer = self._layer_for_size(pygame, (width, height))
        for point_set, draw_alpha in scaled_sets:
            local = [(round(x - origin_x), round(y - origin_y)) for x, y in point_set]
            pygame.draw.polygon(layer, (*color, draw_alpha), local)
        surface.blit(layer, (origin_x, origin_y))

    def _draw_debug(self, pygame: object, surface: object, layout: BluebotFaceLayout) -> None:
        pygame.draw.rect(surface, (120, 255, 255, 80), self._pygame_rect(pygame, self._from_safe(layout.visible)), 1)
        pygame.draw.rect(surface, (255, 211, 108, 100), self._pygame_rect(pygame, self._from_safe(layout.expression_core)), 1)

    def _draw_pout_bridge_mouth(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        shape: str,
        color: tuple[int, int, int],
        now_ms: int,
    ) -> None:
        quiver = 0.55 * self._wave(now_ms, 0.009, 0.2) + 0.45 * self._wave(now_ms, 0.013, 1.7)
        y_shift = quiver * min(3.0, rect.height * 0.04)
        if shape == "pout_bridge_soft":
            points = self._pout_bridge_points(rect, y_shift, center_drop=0.62, lower_drop=0.74)
        elif shape == "pout_bridge_round":
            points = self._pout_bridge_points(rect, y_shift, center_drop=0.68, lower_drop=0.82, side_y=0.45)
        elif shape == "pout_bridge_deep":
            points = self._pout_bridge_points(rect, y_shift, center_drop=0.72, lower_drop=0.84, side_y=0.44)
        else:
            points = self._pout_bridge_points(rect, y_shift, center_drop=0.70, lower_drop=0.82)
        self._draw_soft_polygon(pygame, surface, points, color, 226, 14)
        shadow = LayoutRect(
            rect.x + rect.width * 0.43,
            rect.y + rect.height * 0.62 + y_shift,
            rect.width * 0.14,
            rect.height * 0.09,
        )
        self._draw_soft_ellipse(pygame, surface, shadow, self.theme.background_bottom, 34, 1)

    def _draw_moe_pout_mouth(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        shape: str,
        now_ms: int,
    ) -> None:
        warm = (255, 226, 138)
        warm_shadow = (221, 177, 82)
        dark = (1, 14, 45)
        quiver = 0.55 * self._wave(now_ms, 0.008, 0.4) + 0.45 * self._wave(now_ms, 0.013, 2.1)
        y_shift = quiver * min(1.6, rect.height * 0.022)

        if shape == "moe_pout_clench_v25":
            hold = self._pulse(now_ms, 0.0066, 1.1) ** 2
            body_y = 0.38 + 0.04 * hold
            body_h = 0.40 - 0.08 * hold
            arc_drop = 0.58
            body_x = 0.13 + 0.02 * hold
            body_w = 0.74 - 0.04 * hold
            inner_w = 0.62 - 0.10 * hold
            inner_alpha = round(92 + 34 * hold)
        elif shape == "moe_pout_c":
            body_y = 0.49
            body_h = 0.42
            arc_drop = 0.66
            body_x = 0.26
            body_w = 0.48
            inner_w = 0.0
            inner_alpha = 0
        elif shape == "moe_pout_d":
            body_y = 0.48
            body_h = 0.34
            arc_drop = 0.60
            body_x = 0.26
            body_w = 0.48
            inner_w = 0.0
            inner_alpha = 0
        else:
            body_y = 0.47
            body_h = 0.38
            arc_drop = 0.63
            body_x = 0.26
            body_w = 0.48
            inner_w = 0.0
            inner_alpha = 0

        body = LayoutRect(
            rect.x + rect.width * body_x,
            rect.y + rect.height * body_y + y_shift,
            rect.width * body_w,
            rect.height * body_h,
        )
        self._draw_soft_ellipse(pygame, surface, body, warm, 226, 5)

        lower = LayoutRect(
            body.x + body.width * 0.12,
            body.y + body.height * 0.58,
            body.width * 0.76,
            body.height * 0.30,
        )
        self._draw_soft_ellipse(pygame, surface, lower, warm_shadow, 52, 4)

        shine = LayoutRect(
            body.x + body.width * 0.22,
            body.y + body.height * 0.18,
            body.width * 0.54,
            body.height * 0.16,
        )
        self._draw_soft_ellipse(pygame, surface, shine, self.theme.white_cyan, 50, 3)

        if inner_w > 0:
            inner = LayoutRect(
                body.x + body.width * (0.5 - inner_w / 2),
                body.y + body.height * 0.50,
                body.width * inner_w,
                max(4.0, body.height * 0.15),
            )
            self._draw_soft_rounded_rect(pygame, surface, inner, dark, inner_alpha, round(inner.height / 2), glow=0)

            bite_y = body.y + body.height * (0.49 + 0.05 * self._pulse(now_ms, 0.0066, 1.1))
            bite = [
                (body.x + body.width * 0.29, bite_y),
                (body.x + body.width * 0.43, bite_y + body.height * 0.07),
                (body.x + body.width * 0.57, bite_y - body.height * 0.01),
                (body.x + body.width * 0.71, bite_y + body.height * 0.04),
            ]
            self._draw_line_glow(pygame, surface, bite, dark, max(3, round(rect.height * 0.036)), 48)

        points = self._mouth_down_arc_points(
            rect,
            left=0.38,
            right=0.62,
            edge_y=0.51,
            center_y=arc_drop,
            y_shift=y_shift,
        )
        thickness = max(3, round(rect.height * 0.045))
        self._draw_line_glow(pygame, surface, points, dark, thickness, 54)

    def _draw_official_mouth(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        shape: str,
        now_ms: int,
        pose: _OfficialMouthPose | None = None,
    ) -> None:
        fill = (127, 239, 253)
        pose = pose or self._official_mouth_pose(shape, now_ms)
        body = LayoutRect(
            rect.x + rect.width * (0.5 - pose.body_width / 2),
            rect.y + rect.height * pose.body_y,
            rect.width * pose.body_width,
            rect.height * pose.body_height,
        )
        outline = []
        for index in range(48):
            angle = 2.0 * math.pi * index / 48
            cos_angle = math.cos(angle)
            sin_angle = math.sin(angle)
            nx = math.copysign(abs(cos_angle) ** 0.60, cos_angle)
            ny = math.copysign(abs(sin_angle) ** 0.60, sin_angle)
            outline.append((
                body.center_x + body.width * 0.5 * nx,
                body.center_y + body.height * (0.5 * ny + pose.bow * (1.0 - nx * nx)),
            ))
        self._draw_soft_polygon(pygame, surface, outline, fill, 226, 10)
        shine = LayoutRect(body.x + body.width * 0.17, body.y + body.height * 0.14, body.width * 0.54, body.height * 0.20)
        self._draw_soft_ellipse(pygame, surface, shine, self.theme.white_cyan, 67, 4)
        if pose.inner_alpha > 0:
            inner = LayoutRect(
                body.x + body.width * 0.30,
                body.y + body.height * 0.57,
                body.width * 0.40,
                max(3.0, body.height * 0.13),
            )
            self._draw_soft_rounded_rect(
                pygame, surface, inner, (1, 45, 103), round(pose.inner_alpha), round(inner.height / 2), glow=0
            )

    def _official_mouth_pose(self, shape: str, now_ms: int, bow_override: float | None = None) -> _OfficialMouthPose:
        pulse = self._pulse(now_ms, 0.0032, 0.5)
        body_w = 0.72 if shape == "official_mouth_big_smile" else 0.64
        if shape == "official_mouth_help_pout":
            body_w = 0.48
        if shape == "official_mouth_expectant":
            body_w = 0.58
        body_h = 0.85 if shape == "official_mouth_help_pout" else 0.72
        if shape == "official_mouth_wobble":
            body_h = 0.66
        if shape == "official_mouth_expectant":
            body_h = 0.82
        body_y = (1.0 - body_h) / 2
        if shape == "official_mouth_big_smile":
            body_w *= 0.96 + 0.07 * pulse
        else:
            body_w *= 1.0 - 0.018 * pulse
        body_h *= 1.0 + (0.07 * (pulse - 0.5) if shape in {"official_mouth_help_pout", "official_mouth_wobble"} else -0.014 * pulse)
        bow = {
            "official_mouth_sorry_pout": -0.25,
            "official_mouth_help_pout": -0.05,
            "official_mouth_wobble": -0.10,
            "official_mouth_big_smile": 0.19,
            "official_mouth_expectant": -0.08,
        }.get(shape, 0.035)
        if bow_override is not None:
            bow = bow_override
        inner_alpha = 0 if shape in {"official_mouth_smile_block", "official_mouth_big_smile"} else 38 if shape == "official_mouth_sorry_pout" else 28
        return _OfficialMouthPose(body_w, body_h, body_y, bow, inner_alpha)

    @staticmethod
    def _official_cheek_pose(mouth: str) -> _OfficialCheekPose:
        if mouth == "official_mouth_help_pout":
            return _OfficialCheekPose((247, 163, 177), 125)
        if mouth == "official_mouth_big_smile":
            return _OfficialCheekPose((125, 216, 224), 105)
        if mouth == "official_mouth_sorry_pout":
            return _OfficialCheekPose((249, 119, 169), 92)
        return _OfficialCheekPose((177, 114, 206), 64 if mouth == "official_mouth_wobble" else 92)

    def _draw_blocked_tiny_pout_mouth(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        now_ms: int,
    ) -> None:
        fill = (255, 226, 138)
        shade = (180, 130, 52)
        ink = (1, 14, 45)
        squeeze = self._pulse(now_ms, 0.009, 0.4)
        quiver = self._wave(now_ms, 0.019, 1.5) * min(1.4, rect.height * 0.022)
        body = LayoutRect(
            rect.x + rect.width * (0.24 + 0.02 * squeeze),
            rect.y + rect.height * (0.38 + 0.02 * squeeze) + quiver,
            rect.width * (0.52 - 0.04 * squeeze),
            rect.height * (0.24 - 0.03 * squeeze),
        )
        self._draw_soft_ellipse(pygame, surface, body, fill, 242, 3)

        crease = LayoutRect(
            body.x + body.width * 0.22,
            body.y + body.height * 0.48,
            body.width * 0.56,
            max(3.0, body.height * 0.13),
        )
        self._draw_soft_rounded_rect(pygame, surface, crease, ink, 94, round(crease.height / 2), glow=0)

        arc = [
            (body.x + body.width * 0.28, body.y + body.height * 0.52),
            (body.x + body.width * 0.50, body.y + body.height * 0.62 + squeeze * body.height * 0.04),
            (body.x + body.width * 0.72, body.y + body.height * 0.52),
        ]
        self._draw_line_glow(pygame, surface, arc, ink, max(2, round(rect.height * 0.022)), 58)

        lower = LayoutRect(
            body.x + body.width * 0.24,
            body.y + body.height * 0.68,
            body.width * 0.52,
            max(3.0, body.height * 0.12),
        )
        self._draw_soft_ellipse(pygame, surface, lower, shade, 40, 2)

    def _draw_fail_soft_pout_mouth(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        now_ms: int,
    ) -> None:
        fill = (255, 171, 182)
        edge = (255, 224, 228)
        shade = (151, 55, 80)
        ink = (1, 12, 36)
        pulse = self._pulse(now_ms, 0.0036, 0.5)
        quiver = self._wave(now_ms, 0.010, 0.8) * min(1.5, rect.height * 0.020)
        body_w = 0.70 - 0.020 * pulse
        body_h = 0.46 - 0.018 * pulse
        body = LayoutRect(
            rect.x + rect.width * (0.5 - body_w / 2),
            rect.y + rect.height * 0.30 + quiver,
            rect.width * body_w,
            rect.height * body_h,
        )
        self._draw_soft_rounded_rect(pygame, surface, body, fill, 224, round(body.height * 0.48), glow=7)

        upper_highlight = LayoutRect(
            body.x + body.width * 0.19,
            body.y + body.height * 0.18,
            body.width * 0.62,
            body.height * 0.16,
        )
        self._draw_soft_ellipse(pygame, surface, upper_highlight, edge, 50, 3)

        hollow = LayoutRect(
            body.x + body.width * 0.25,
            body.y + body.height * 0.47,
            body.width * 0.50,
            body.height * (0.18 + 0.018 * pulse),
        )
        self._draw_soft_ellipse(pygame, surface, hollow, ink, 72, 1)

        crease = [
            (body.x + body.width * 0.22, body.y + body.height * 0.55),
            (body.x + body.width * 0.50, body.y + body.height * (0.66 + 0.035 * pulse)),
            (body.x + body.width * 0.78, body.y + body.height * 0.55),
        ]
        self._draw_line_glow(pygame, surface, crease, shade, max(3, round(rect.height * 0.025)), 62)

        lower_shadow = LayoutRect(
            body.x + body.width * 0.24,
            body.y + body.height * 0.72,
            body.width * 0.52,
            body.height * 0.10,
        )
        self._draw_soft_ellipse(pygame, surface, lower_shadow, shade, 34, 2)

    def _draw_fail_quiver_pout_mouth(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        now_ms: int,
    ) -> None:
        fill = (255, 178, 188)
        edge = (255, 230, 233)
        shade = (146, 54, 79)
        ink = (1, 12, 36)
        pulse = self._pulse(now_ms, 0.0042, 0.6)
        quiver = (
            self._wave(now_ms, 0.010, 0.8) * 0.55
            + self._wave(now_ms, 0.017, 1.9) * 0.45
        ) * min(1.8, rect.height * 0.024)
        body_w = 0.58 - 0.020 * pulse
        body_h = 0.54 - 0.030 * pulse
        body = LayoutRect(
            rect.x + rect.width * (0.5 - body_w / 2),
            rect.y + rect.height * (0.27 + 0.018 * pulse) + quiver,
            rect.width * body_w,
            rect.height * body_h,
        )
        self._draw_soft_ellipse(pygame, surface, body, fill, 226, 5)

        lower_lip = LayoutRect(
            body.x + body.width * 0.16,
            body.y + body.height * 0.60,
            body.width * 0.68,
            body.height * 0.25,
        )
        self._draw_soft_ellipse(pygame, surface, lower_lip, shade, 42, 4)

        shine = LayoutRect(
            body.x + body.width * 0.23,
            body.y + body.height * 0.17,
            body.width * 0.54,
            body.height * 0.14,
        )
        self._draw_soft_ellipse(pygame, surface, shine, edge, 52, 3)

        hollow = LayoutRect(
            body.x + body.width * 0.24,
            body.y + body.height * 0.48,
            body.width * 0.52,
            body.height * (0.16 + 0.018 * pulse),
        )
        self._draw_soft_ellipse(pygame, surface, hollow, ink, 68, 1)

        arc = [
            (body.x + body.width * 0.24, body.y + body.height * 0.54),
            (body.x + body.width * 0.50, body.y + body.height * (0.70 + 0.025 * pulse)),
            (body.x + body.width * 0.76, body.y + body.height * 0.54),
        ]
        self._draw_line_glow(pygame, surface, arc, ink, max(3, round(rect.height * 0.023)), 50)

    def _draw_fail_apology_pout_mouth(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        now_ms: int,
    ) -> None:
        fill = (255, 179, 189)
        edge = (255, 231, 234)
        shade = (148, 55, 79)
        ink = (1, 12, 36)
        pulse = self._pulse(now_ms, 0.0038, 0.6)
        is_v55 = rect.width > 155
        body_w = (0.64 if is_v55 else 0.68) - 0.024 * pulse
        body_h = (0.58 if is_v55 else 0.52) - 0.020 * pulse
        y_shift = rect.height * (0.010 * pulse)
        body = LayoutRect(
            rect.x + rect.width * (0.5 - body_w / 2),
            rect.y + rect.height * (0.25 if is_v55 else 0.29) + y_shift,
            rect.width * body_w,
            rect.height * body_h,
        )
        self._draw_soft_rounded_rect(pygame, surface, body, fill, 224, round(body.height * 0.50), glow=7)

        shine = LayoutRect(
            body.x + body.width * 0.20,
            body.y + body.height * 0.18,
            body.width * 0.60,
            body.height * 0.14,
        )
        self._draw_soft_ellipse(pygame, surface, shine, edge, 48, 3)

        inner = LayoutRect(
            body.x + body.width * 0.30,
            body.y + body.height * (0.48 if is_v55 else 0.50),
            body.width * 0.40,
            max(4.0, body.height * ((0.16 if is_v55 else 0.13) + 0.012 * pulse)),
        )
        self._draw_soft_rounded_rect(pygame, surface, inner, ink, 78 if is_v55 else 66, round(inner.height / 2), glow=0)

        down_arc = [
            (body.x + body.width * 0.22, body.y + body.height * 0.52),
            (body.x + body.width * 0.50, body.y + body.height * ((0.76 if is_v55 else 0.70) + 0.030 * pulse)),
            (body.x + body.width * 0.78, body.y + body.height * 0.52),
        ]
        self._draw_line_glow(pygame, surface, down_arc, shade, max(3, round(rect.height * (0.030 if is_v55 else 0.024))), 64 if is_v55 else 56)

        lower = LayoutRect(
            body.x + body.width * 0.22,
            body.y + body.height * 0.70,
            body.width * 0.56,
            body.height * 0.10,
        )
        self._draw_soft_ellipse(pygame, surface, lower, shade, 30, 2)

    def _draw_fail_capsule_mouth(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        shape: str,
        now_ms: int,
    ) -> None:
        fill = (255, 166, 176)
        edge = (255, 218, 222)
        shade = (162, 60, 84)
        ink = (1, 12, 36)
        pulse = self._pulse(now_ms, 0.0036, 0.5)
        quiver = self._wave(now_ms, 0.0022, 1.1) * min(1.2, rect.height * 0.018)

        if shape == "fail_capsule_a":
            body_w, body_h, body_y = 0.76, 0.44, 0.32
            inner_w, inner_h, inner_y = 0.48, 0.16, 0.47
            tilt = -0.02
        elif shape == "fail_capsule_v47":
            body_w, body_h, body_y = 0.82, 0.52, 0.30
            inner_w, inner_h, inner_y = 0.52, 0.18, 0.51
            tilt = 0.0
        elif shape == "failed_stress_capsule_v24":
            body_w, body_h, body_y = 0.78, 0.50, 0.28
            inner_w, inner_h, inner_y = 0.48, 0.16, 0.53
            tilt = 0.0
        elif shape == "fail_capsule_c":
            body_w, body_h, body_y = 0.84, 0.50, 0.29
            inner_w, inner_h, inner_y = 0.55, 0.18, 0.48
            tilt = 0.03
        elif shape == "fail_capsule_d":
            body_w, body_h, body_y = 0.66, 0.40, 0.35
            inner_w, inner_h, inner_y = 0.36, 0.14, 0.49
            tilt = 0.0
        else:
            body_w, body_h, body_y = 0.78, 0.48, 0.31
            inner_w, inner_h, inner_y = 0.46, 0.17, 0.49
            tilt = 0.0

        body_w *= 1.0 - 0.025 * pulse
        body_h *= 1.0 - 0.018 * pulse
        body = LayoutRect(
            rect.x + rect.width * (0.5 - body_w / 2 + tilt),
            rect.y + rect.height * body_y + quiver,
            rect.width * body_w,
            rect.height * body_h,
        )
        self._draw_soft_rounded_rect(pygame, surface, body, fill, 224, round(body.height * 0.48), glow=9)

        inner = LayoutRect(
            rect.x + rect.width * (0.5 - inner_w / 2),
            rect.y + rect.height * inner_y + quiver,
            rect.width * inner_w,
            rect.height * inner_h,
        )
        self._draw_soft_ellipse(pygame, surface, inner, ink, 72, 1)

        highlight = LayoutRect(
            rect.x + rect.width * 0.31,
            rect.y + rect.height * 0.37 + quiver,
            rect.width * 0.38,
            rect.height * 0.13,
        )
        self._draw_soft_ellipse(pygame, surface, highlight, edge, 58, 4)

        lower = LayoutRect(
            rect.x + rect.width * 0.34,
            rect.y + rect.height * 0.59 + quiver,
            rect.width * 0.32,
            rect.height * 0.13,
        )
        self._draw_soft_ellipse(pygame, surface, lower, shade, 42, 4)

    def _draw_stress_clench_mouth(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        shape: str,
        accent: tuple[int, int, int],
        brightness: float,
        now_ms: int,
    ) -> None:
        if shape.startswith("stress_grimace") or shape.startswith("pressure_grimace"):
            self._draw_stress_grimace_mouth(pygame, surface, rect, accent, brightness, now_ms)
            return

        color = self._mix(accent, self.theme.white_cyan, 0.46 + 0.22 * brightness)
        dark = (1, 12, 36)
        pulse = self._pulse(now_ms, 0.0068, 0.2)
        quiver = self._wave(now_ms, 0.014, 1.2) * min(1.4, rect.height * 0.04)
        body = LayoutRect(
            rect.x + rect.width * 0.16,
            rect.y + rect.height * (0.42 + 0.02 * pulse) + quiver,
            rect.width * 0.68,
            rect.height * 0.32,
        )
        self._draw_soft_rounded_rect(pygame, surface, body, color, 214, round(body.height / 2), glow=8)
        inner = LayoutRect(
            body.x + body.width * 0.24,
            body.y + body.height * 0.46,
            body.width * 0.52,
            max(3.0, body.height * 0.16),
        )
        self._draw_soft_rounded_rect(pygame, surface, inner, dark, 58, round(inner.height / 2), glow=0)

    def _draw_stress_grimace_mouth(
        self,
        pygame: object,
        surface: object,
        rect: LayoutRect,
        accent: tuple[int, int, int],
        brightness: float,
        now_ms: int,
    ) -> None:
        fill = self._mix(accent, self.theme.white_cyan, 0.12 + 0.08 * brightness)
        edge = self._mix(accent, self.theme.white_cyan, 0.42)
        shade = (151, 113, 42)
        ink = (1, 12, 36)
        pulse = self._pulse(now_ms, 0.0068, 0.2)
        quiver = self._wave(now_ms, 0.014, 1.2) * min(2.1, rect.height * 0.045)
        body = LayoutRect(
            rect.x + rect.width * (0.07 + 0.01 * pulse),
            rect.y + rect.height * (0.30 + 0.035 * pulse) + quiver,
            rect.width * (0.86 - 0.02 * pulse),
            rect.height * (0.46 - 0.05 * pulse),
        )
        self._draw_soft_rounded_rect(pygame, surface, body, fill, 222, round(body.height * 0.48), glow=8)

        inner = LayoutRect(
            body.x + body.width * 0.21,
            body.y + body.height * 0.54,
            body.width * 0.58,
            max(5.0, body.height * 0.13),
        )
        self._draw_soft_rounded_rect(pygame, surface, inner, ink, 76, round(inner.height / 2), glow=0)

        lower = LayoutRect(
            body.x + body.width * 0.18,
            body.y + body.height * 0.58,
            body.width * 0.64,
            body.height * 0.18,
        )
        self._draw_soft_ellipse(pygame, surface, lower, shade, 34, 3)

        shine = LayoutRect(
            body.x + body.width * 0.22,
            body.y + body.height * 0.18,
            body.width * 0.52,
            body.height * 0.13,
        )
        self._draw_soft_ellipse(pygame, surface, shine, edge, 48, 3)

    def _mouth_down_arc_points(
        self,
        rect: LayoutRect,
        left: float,
        right: float,
        edge_y: float,
        center_y: float,
        y_shift: float,
    ) -> list[tuple[float, float]]:
        points: list[tuple[float, float]] = []
        count = 8
        for index in range(count + 1):
            t = index / count
            x = rect.x + rect.width * (left + (right - left) * t)
            curve = math.sin(math.pi * t)
            y_ratio = edge_y + (center_y - edge_y) * curve
            y = rect.y + rect.height * y_ratio + y_shift * (0.8 + 0.4 * curve)
            points.append((x, y))
        return points

    def _pout_bridge_points(
        self,
        rect: LayoutRect,
        y_shift: float,
        center_drop: float,
        lower_drop: float,
        side_y: float = 0.46,
    ) -> list[tuple[float, float]]:
        x = rect.x
        y = rect.y
        w = rect.width
        h = rect.height
        return [
            (x + w * 0.10, y + h * side_y),
            (x + w * 0.28, y + h * 0.40),
            (x + w * 0.43, y + h * 0.58 + y_shift),
            (x + w * 0.50, y + h * center_drop + y_shift),
            (x + w * 0.57, y + h * 0.58 + y_shift),
            (x + w * 0.72, y + h * 0.40),
            (x + w * 0.90, y + h * side_y),
            (x + w * 0.82, y + h * 0.64 + y_shift * 0.4),
            (x + w * 0.62, y + h * 0.62 + y_shift * 0.4),
            (x + w * 0.50, y + h * lower_drop + y_shift),
            (x + w * 0.38, y + h * 0.62 + y_shift * 0.4),
            (x + w * 0.18, y + h * 0.64 + y_shift * 0.4),
        ]

    def _mouth_wave_points(self, rect: LayoutRect, wave: bool) -> list[tuple[float, float]]:
        if not wave:
            return [
                (rect.x, rect.center_y + rect.height * 0.22),
                (rect.center_x, rect.center_y - rect.height * 0.14),
                (rect.right, rect.center_y + rect.height * 0.08),
            ]
        return [
            (rect.x, rect.center_y),
            (rect.x + rect.width * 0.33, rect.center_y - rect.height * 0.22),
            (rect.x + rect.width * 0.66, rect.center_y + rect.height * 0.18),
            (rect.right, rect.center_y - rect.height * 0.03),
        ]

    def _mouth_curve_points(self, rect: LayoutRect, depth: float, width_ratio: float) -> list[tuple[float, float]]:
        inset = rect.width * (1 - width_ratio) / 2
        left = rect.x + inset
        right = rect.right - inset
        center = rect.center_x
        base_y = rect.center_y - rect.height * 0.05
        mid_y = base_y + rect.height * depth
        return [
            (left, base_y),
            (left + (center - left) * 0.45, base_y + (mid_y - base_y) * 0.76),
            (center, mid_y),
            (center + (right - center) * 0.55, base_y + (mid_y - base_y) * 0.76),
            (right, base_y),
        ]

    def _draw_mouth_ribbon(
        self,
        pygame: object,
        surface: object,
        points: list[tuple[float, float]],
        color: tuple[int, int, int],
        thickness: int,
        glow_alpha: int,
    ) -> None:
        half = max(3.0, thickness / 2)
        upper = [(x, y - half) for x, y in points]
        lower = [(x, y + half) for x, y in reversed(points)]
        ribbon = upper + lower
        self._draw_soft_polygon(pygame, surface, ribbon, color, 218, max(8, thickness + 3))
        center = points[len(points) // 2]
        highlight = LayoutRect(
            center[0] - thickness * 0.38,
            center[1] - half * 0.42,
            thickness * 0.76,
            max(3.0, thickness * 0.24),
        )
        self._draw_soft_rounded_rect(
            pygame,
            surface,
            highlight,
            self.theme.white_cyan,
            min(90, glow_alpha + 28),
            round(highlight.height / 2),
            glow=3,
        )

    def _eye_glint_rect(self, rect: LayoutRect, side: int, now_ms: int) -> LayoutRect:
        pulse = self._pulse(now_ms, 0.003, side)
        size = max(7, min(rect.width, rect.height) * 0.16)
        return LayoutRect(
            rect.x + rect.width * (0.26 + 0.08 * pulse),
            rect.y + rect.height * 0.18,
            size,
            size * 0.72,
        )

    def _pygame(self) -> object:
        try:
            import pygame  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError("pygame is required for BluebotPygameRenderer") from exc
        return pygame

    def _layer_for_size(self, pygame: object, size: tuple[int, int]) -> object:
        resolved_size = (max(1, size[0]), max(1, size[1]))
        layer = self._layer_cache.get(resolved_size)
        if layer is None:
            layer = pygame.Surface(resolved_size, pygame.SRCALPHA)
            self._layer_cache[resolved_size] = layer
        layer.fill((0, 0, 0, 0))
        return layer

    def _pygame_rect(self, pygame: object, rect: LayoutRect) -> object:
        return pygame.Rect(round(rect.x), round(rect.y), round(rect.width), round(rect.height))

    def _from_safe(self, rect: object) -> LayoutRect:
        return LayoutRect(rect.x, rect.y, rect.width, rect.height)

    def _inflate(self, rect: LayoutRect, dx: float, dy: float) -> LayoutRect:
        return LayoutRect(rect.x - dx / 2, rect.y - dy / 2, rect.width + dx, rect.height + dy)

    def _pulse(self, now_ms: int, speed: float, phase: float) -> float:
        return 0.5 + 0.5 * math.sin(now_ms * speed + phase)

    def _wave(self, now_ms: int, speed: float, phase: float) -> float:
        return math.sin(now_ms * speed + phase)

    def _parse_color(self, value: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
        if not value or not isinstance(value, str):
            return fallback
        text = value.strip().lstrip("#")
        if len(text) != 6:
            return fallback
        try:
            return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
        except ValueError:
            return fallback

    def _mix(self, a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
        clamped = self._clamp(t, 0.0, 1.0)
        return tuple(round(a[i] * (1 - clamped) + b[i] * clamped) for i in range(3))

    def _clamp(self, value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))
