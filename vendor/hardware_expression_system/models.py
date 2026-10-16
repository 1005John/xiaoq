"""Shared data models for expression runtime code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class SafeInsets:
    left: float
    right: float
    top: float
    bottom: float


@dataclass(frozen=True)
class SafeRect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


@dataclass(frozen=True)
class ScreenProfile:
    width: int
    height: int
    fps_target: int
    visible_safe_inset: SafeInsets
    expression_safe_inset: SafeInsets


@dataclass(frozen=True)
class StateConfig:
    label: str
    group: str
    expression_id: str
    priority: int
    timeout_ms: int
    next_state: str | None


@dataclass(frozen=True)
class ExpressionIntent:
    source: str
    expression_state: str
    visual_variant: str
    progress_enabled: bool = False
    accent: str = "#7dfffb"
    metadata: Mapping[str, object] | None = None


@dataclass(frozen=True)
class ExpressionFrame:
    state: str
    expression_id: str
    label: str
    group: str
    priority: int
    eye_shape: str
    eye_open_left: float
    eye_open_right: float
    eye_offset_x: float
    eye_offset_y: float
    eye_scale: float
    brow_tilt: float
    mouth: str
    mouth_open: float
    mouth_smile: float
    face_brightness: float
    screen_pulse: float
    cheek: float
    progress: float
    accent: str
    eye_convergence: float = 0.0
    eye_shift_left: float = 0.0
    eye_shift_right: float = 0.0
    mouth_offset_y: float = 0.0
    mouth_scale: float = 1.0
    mouth_bow: float | None = None
