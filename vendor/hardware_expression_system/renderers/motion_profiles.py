"""Motion profiles for expression renderer QA.

Motion profiles change timing and intensity.
They do not change character identity.
They do not change the default renderer unless a caller uses them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from ..models import ExpressionFrame


@dataclass(frozen=True)
class ExpressionMotionProfile:
    id: str
    label: str
    state_time_scale: float = 1.0
    render_time_scale: float = 1.0
    pulse_gain: float = 1.0
    brightness_gain: float = 1.0
    eye_scale_gain: float = 1.0
    mouth_open_gain: float = 1.0
    phase_ms: int = 0


MOTION_PROFILES = {
    "m-official": ExpressionMotionProfile(
        id="m-official",
        label="m-official",
    ),
    "oled-soft": ExpressionMotionProfile(
        id="oled-soft",
        label="oled-soft baseline",
    ),
    "neon-rhythm-probe": ExpressionMotionProfile(
        id="neon-rhythm-probe",
        label="oled palette + neon rhythm probe",
        state_time_scale=1.12,
        render_time_scale=1.48,
        pulse_gain=1.18,
        brightness_gain=1.06,
        eye_scale_gain=1.04,
        mouth_open_gain=1.12,
        phase_ms=180,
    ),
}


def resolve_motion_profiles(profile_id: str) -> list[ExpressionMotionProfile]:
    """Resolve a profile ID to one or more motion profiles."""

    if profile_id == "compare-neon-rhythm":
        return [MOTION_PROFILES["oled-soft"], MOTION_PROFILES["neon-rhythm-probe"]]
    return [MOTION_PROFILES[profile_id]]


def apply_motion_profile(
    frame: ExpressionFrame,
    profile: ExpressionMotionProfile,
    now_ms: int,
) -> ExpressionFrame:
    """Apply timing-intensity changes to an expression frame."""

    if profile.id in {"oled-soft", "m-official"}:
        return frame
    pulse = 0.5 + 0.5 * math.sin(now_ms * 0.005 + 0.4)
    return replace(
        frame,
        face_brightness=_clamp(frame.face_brightness * profile.brightness_gain + 0.04 * pulse, 0.08, 1.0),
        screen_pulse=_clamp(frame.screen_pulse * profile.pulse_gain + 0.1 * pulse, 0.0, 1.0),
        eye_scale=_clamp(frame.eye_scale * profile.eye_scale_gain, 0.72, 1.22),
        mouth_open=_clamp(frame.mouth_open * profile.mouth_open_gain, 0.0, 1.0),
    )


def profile_state_time(now_ms: int, profile: ExpressionMotionProfile) -> int:
    return round((now_ms + profile.phase_ms) * profile.state_time_scale)


def profile_render_time(now_ms: int, profile: ExpressionMotionProfile) -> int:
    return round((now_ms + profile.phase_ms) * profile.render_time_scale)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
