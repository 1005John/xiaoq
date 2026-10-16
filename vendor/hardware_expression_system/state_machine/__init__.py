"""State-machine runtime exports."""

from .expression_machine import (
    LEGACY_EXPRESSION_STATE,
    LEGACY_MOOD_STATE,
    LEGACY_SET_STATE,
    STATE_CONFIG,
    TRANSITIONS,
    ExpressionMachine,
    normalize_event,
    normalize_state,
    resolve_legacy_command,
)

__all__ = [
    "ExpressionMachine",
    "LEGACY_EXPRESSION_STATE",
    "LEGACY_MOOD_STATE",
    "LEGACY_SET_STATE",
    "STATE_CONFIG",
    "TRANSITIONS",
    "normalize_event",
    "normalize_state",
    "resolve_legacy_command",
]
