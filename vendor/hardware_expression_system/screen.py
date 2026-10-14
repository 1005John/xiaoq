"""Screen profile and safe-area helpers."""

from __future__ import annotations

from .models import SafeInsets, SafeRect, ScreenProfile


DEFAULT_SCREEN_PROFILE = ScreenProfile(
    width=1280,
    height=720,
    fps_target=30,
    visible_safe_inset=SafeInsets(left=0.08, right=0.08, top=0.08, bottom=0.08),
    expression_safe_inset=SafeInsets(left=0.15, right=0.15, top=0.14, bottom=0.14),
)


def safe_rect(screen: ScreenProfile, inset: SafeInsets) -> SafeRect:
    left = round(screen.width * inset.left)
    top = round(screen.height * inset.top)
    right = round(screen.width * (1.0 - inset.right))
    bottom = round(screen.height * (1.0 - inset.bottom))
    return SafeRect(x=left, y=top, width=right - left, height=bottom - top)


def get_safe_areas(screen: ScreenProfile | None = None) -> dict[str, SafeRect | ScreenProfile]:
    resolved = screen or DEFAULT_SCREEN_PROFILE
    return {
        "screen": resolved,
        "visible": safe_rect(resolved, resolved.visible_safe_inset),
        "expression_core": safe_rect(resolved, resolved.expression_safe_inset),
    }
