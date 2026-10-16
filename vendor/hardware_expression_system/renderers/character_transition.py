"""Frame compositor for switching between hardware characters."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pygame


class CharacterSwitchTransition:
    """Fade through the target face field without overlapping two faces."""

    def __init__(self, duration_ms: int = 560) -> None:
        if duration_ms <= 0:
            raise ValueError("duration_ms must be positive")
        self.duration_ms = duration_ms
        self._source: pygame.Surface | None = None
        self._field: pygame.Surface | None = None
        self._field_color = (16, 36, 67)
        self._started_ms = 0

    @property
    def active(self) -> bool:
        return self._source is not None

    def start(self, visible_frame: pygame.Surface, now_ms: int) -> None:
        import pygame

        self._source = visible_frame.copy()
        self._field = pygame.Surface(visible_frame.get_size(), pygame.SRCALPHA)
        self._started_ms = now_ms

    def cancel(self) -> None:
        self._source = None
        self._field = None

    def apply(self, target: pygame.Surface, now_ms: int) -> bool:
        """Compose over an already drawn target. Return whether motion remains."""
        source = self._source
        if source is None:
            return False
        if source.get_size() != target.get_size():
            self.cancel()
            return False

        elapsed = min(self.duration_ms, max(0, now_ms - self._started_ms))
        if elapsed >= self.duration_ms:
            self.cancel()
            return False

        hold_end = self.duration_ms * 60 / 560
        fade_end = self.duration_ms * 230 / 560
        blank_end = self.duration_ms * 290 / 560
        if elapsed < fade_end:
            fade = 0.0 if elapsed < hold_end else self._ease((elapsed - hold_end) / (fade_end - hold_end))
            target.fill(self._field_color)
            source.set_alpha(round(255 * (1.0 - fade)))
            target.blit(source, (0, 0))
        else:
            fade = 0.0 if elapsed < blank_end else self._ease((elapsed - blank_end) / (self.duration_ms - blank_end))
            assert self._field is not None
            self._field.fill((*self._field_color, round(255 * (1.0 - fade))))
            target.blit(self._field, (0, 0))
        return True

    @staticmethod
    def _ease(value: float) -> float:
        return value * value * (3.0 - 2.0 * value)
