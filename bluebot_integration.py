"""Product-side switch for the pinned Bluebot expression runtime."""

from __future__ import annotations

from vendor.hardware_expression_system import (
    BluebotExpressionPlayer,
    CharacterSwitchTransition,
    MobileWorkStatus,
)


class BluebotIntegration:
    """Own Bluebot playback without changing XiaoQ's existing face renderer."""

    def __init__(self, player: BluebotExpressionPlayer | None = None) -> None:
        self.player = player or BluebotExpressionPlayer()
        self.enabled = False
        self.last_error: str | None = None
        self.transition = CharacterSwitchTransition()
        self._last_drawn_character = "xiaoq"
        self._switch_pending = False

    def set_character(self, name: object, now_ms: int | None = None, surface: object | None = None) -> bool:
        if name == "bluebot":
            if not self.enabled:
                reset = getattr(self.player, "reset", None)
                if reset is not None:
                    reset(now_ms)
                self._switch_to("bluebot", surface, now_ms)
            self.enabled = True
            self.last_error = None
            return True
        if name == "xiaoq":
            if self.enabled:
                self._switch_to("xiaoq", surface, now_ms)
            self.enabled = False
            return True
        return False

    def _switch_to(self, name: str, surface: object | None, now_ms: int | None) -> None:
        if self._switch_pending and name == self._last_drawn_character:
            self.transition.cancel()
            self._switch_pending = False
            return
        self._start_transition(surface, now_ms)
        self._switch_pending = True

    def _start_transition(self, surface: object | None, now_ms: int | None) -> None:
        if surface is None or now_ms is None:
            self.transition.cancel()
        else:
            self.transition.start(surface, now_ms)

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
            self.transition.apply(surface, now_ms)
            self._last_drawn_character = "bluebot"
            self._switch_pending = False
        except Exception as exc:
            self.enabled = False
            self.transition.cancel()
            self._last_drawn_character = "xiaoq"
            self._switch_pending = False
            self.last_error = f"{type(exc).__name__}: {exc}"
            return False
        return True

    def draw_xiaoq_transition(self, surface: object, now_ms: int) -> None:
        """Compose the previous Bluebot frame over a live XiaoQ frame."""
        if not self.enabled:
            self.transition.apply(surface, now_ms)
            self._last_drawn_character = "xiaoq"
            self._switch_pending = False
