"""Product-side switch for the pinned Bluebot expression runtime."""

from __future__ import annotations

from vendor.hardware_expression_system import BluebotExpressionPlayer, MobileWorkStatus


class BluebotIntegration:
    """Own Bluebot playback without changing XiaoQ's existing face renderer."""

    def __init__(self, player: BluebotExpressionPlayer | None = None) -> None:
        self.player = player or BluebotExpressionPlayer()
        self.enabled = False
        self.last_error: str | None = None

    def set_character(self, name: object) -> bool:
        if name == "bluebot":
            self.enabled = True
            self.last_error = None
            return True
        if name == "xiaoq":
            self.enabled = False
            return True
        return False

    def set_status(self, value: object, now_ms: int) -> bool:
        if not isinstance(value, str):
            return False
        try:
            status = MobileWorkStatus(value.strip().upper())
        except ValueError:
            return False
        self.player.set_status(status, now_ms)
        return True

    def draw(self, surface: object, now_ms: int) -> bool:
        """Return False on failure so the caller can draw the old face this frame."""
        if not self.enabled:
            return False
        try:
            self.player.draw(surface, now_ms)
        except Exception as exc:
            self.enabled = False
            self.last_error = f"{type(exc).__name__}: {exc}"
            return False
        return True
