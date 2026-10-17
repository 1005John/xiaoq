"""Frame compositor for switching between hardware characters."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pygame


class CharacterSwitchTransition:
    """Reveal the live target from the center while the old frame stays visible."""

    def __init__(self, duration_ms: int = 560) -> None:
        if duration_ms <= 0:
            raise ValueError("duration_ms must be positive")
        self.duration_ms = duration_ms
        self._source: pygame.Surface | None = None
        self._accent = (110, 229, 255)
        self._started_ms = 0

    @property
    def active(self) -> bool:
        return self._source is not None

    def start(self, visible_frame: pygame.Surface, now_ms: int, accent: tuple[int, int, int] = (110, 229, 255)) -> None:
        self._source = visible_frame.copy()
        self._accent = accent
        self._started_ms = now_ms

    def cancel(self) -> None:
        self._source = None

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

        import pygame

        width, height = target.get_size()
        progress = self._ease(elapsed / self.duration_ms)
        half_open = round(width * 0.5 * progress)
        left = width // 2 - half_open
        right = width // 2 + half_open
        if left > 0:
            target.blit(source, (0, 0), (0, 0, left, height))
        if right < width:
            target.blit(source, (right, 0), (right, 0, width - right, height))

        if 0 < half_open < width // 2:
            alpha = round(120 * (1.0 - progress))
            edge = pygame.Surface((5, height), pygame.SRCALPHA)
            edge.fill((*self._accent, alpha))
            target.blit(edge, (left - 2, 0))
            target.blit(edge, (right - 2, 0))
        return True

    @staticmethod
    def _ease(value: float) -> float:
        return value * value * (3.0 - 2.0 * value)
