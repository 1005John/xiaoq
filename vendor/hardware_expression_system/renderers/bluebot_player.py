"""State-timed Bluebot playback for MobileWork status changes."""

from __future__ import annotations

from dataclasses import dataclass

from ..agent.mobilework_status import MobileWorkStatus, MobileWorkStatusMapper
from ..models import ExpressionFrame, ExpressionIntent
from ..state_machine.expression_machine import expression_for_state
from .bluebot_layout import BluebotFaceLayout
from .pygame_bluebot import BluebotPygameRenderer


@dataclass(frozen=True)
class _TransitionSource:
    frame: ExpressionFrame
    intent: ExpressionIntent
    elapsed_ms: int
    layout: BluebotFaceLayout | None


class BluebotExpressionPlayer:
    """Keep the motion clock local to the current status."""

    def __init__(
        self,
        renderer: BluebotPygameRenderer | None = None,
        mapper: MobileWorkStatusMapper | None = None,
        initial_status: MobileWorkStatus = MobileWorkStatus.WAITING_INPUT,
    ) -> None:
        self.renderer = renderer or BluebotPygameRenderer()
        self.mapper = mapper or MobileWorkStatusMapper()
        self.status = initial_status
        self._started_ms: int | None = None
        self._transition: _TransitionSource | None = None
        self._last_layout: BluebotFaceLayout | None = None

    def set_status(self, status: MobileWorkStatus, now_ms: int) -> None:
        if status == self.status:
            return
        if self._started_ms is not None:
            elapsed = max(0, now_ms - self._started_ms)
            intent = self.mapper.resolve_intent(self.status)
            frame = expression_for_state(intent.expression_state, elapsed)
            self._transition = _TransitionSource(frame, intent, elapsed, self._last_layout)
        self.status = status
        self._started_ms = now_ms

    def reset(self, now_ms: int | None = None) -> None:
        """Start a fresh visual session when a character becomes active."""
        self._started_ms = now_ms
        self._transition = None
        self._last_layout = None

    def draw(self, surface: object, now_ms: int, include_background: bool = True) -> BluebotFaceLayout:
        if self._started_ms is None:
            self._started_ms = now_ms
        elapsed = max(0, now_ms - self._started_ms)
        intent = self.mapper.resolve_intent(self.status)
        frame = expression_for_state(intent.expression_state, elapsed)

        if self._transition is None:
            layout = self.renderer.draw(surface, frame, intent, elapsed, include_background)
        else:
            hold_ms = 100
            duration_ms = 400 if self.status in {MobileWorkStatus.BLOCKED, MobileWorkStatus.FAILED} else 300
            progress = max(0.0, min(1.0, (elapsed - hold_ms) / duration_ms))
            source = self._transition
            layout = self.renderer.draw_transition(
                surface,
                source.frame,
                source.intent,
                frame,
                intent,
                source.elapsed_ms,
                elapsed,
                progress,
                include_background,
                source.layout,
            )
            if progress >= 1.0:
                self._transition = None
        self._last_layout = layout
        return layout
