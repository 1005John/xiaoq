"""Compatibility mappings for legacy XiaoQ expression inputs.

These mappings are compatibility inputs.
They are not a new business-state model.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import ExpressionIntent
from ..state_machine.expression_machine import (
    LEGACY_EXPRESSION_STATE,
    LEGACY_MOOD_STATE,
    LEGACY_SET_STATE,
)


@dataclass(frozen=True)
class XiaoQCompatibilityMapping:
    source_layer: str
    source_value: str
    expression_state: str
    visual_variant: str
    note: str = ""

    def to_intent(self) -> ExpressionIntent:
        return ExpressionIntent(
            source=f"xiaoq_compat:{self.source_layer}:{self.source_value}",
            expression_state=self.expression_state,
            visual_variant=self.visual_variant,
            metadata={
                "source_layer": self.source_layer,
                "source_value": self.source_value,
                "note": self.note,
            },
        )


NPC_STATE_MAPPINGS = {
    "idle": XiaoQCompatibilityMapping("npc_state", "idle", "IDLE", "legacy_idle"),
    "observe": XiaoQCompatibilityMapping("npc_state", "observe", "AWARE", "legacy_observe"),
    "engaged": XiaoQCompatibilityMapping(
        "npc_state",
        "engaged",
        "LISTENING",
        "legacy_engaged",
        "Use voice state when the product can tell listening from speaking.",
    ),
    "warn": XiaoQCompatibilityMapping("npc_state", "warn", "CONCERNED", "legacy_warn"),
    "sleep": XiaoQCompatibilityMapping("npc_state", "sleep", "SLEEP", "legacy_sleep"),
}

VOICE_STATE_MAPPINGS = {
    "idle": XiaoQCompatibilityMapping("voice_state", "idle", "IDLE", "voice_idle"),
    "listening": XiaoQCompatibilityMapping(
        "voice_state", "listening", "LISTENING", "voice_listening"
    ),
    "thinking": XiaoQCompatibilityMapping(
        "voice_state", "thinking", "THINKING", "voice_thinking"
    ),
    "speaking": XiaoQCompatibilityMapping(
        "voice_state", "speaking", "SPEAKING", "voice_speaking"
    ),
}

LEGACY_EXPRESSION_MAPPINGS = {
    key: XiaoQCompatibilityMapping("legacy_expression", key, value, f"legacy_{key}")
    for key, value in LEGACY_EXPRESSION_STATE.items()
}

LEGACY_SET_STATE_MAPPINGS = {
    key: XiaoQCompatibilityMapping("legacy_set_state", key, value, f"legacy_{key}")
    for key, value in LEGACY_SET_STATE.items()
}

LEGACY_MOOD_MAPPINGS = {
    key: XiaoQCompatibilityMapping("legacy_mood", key, value, f"legacy_{key}")
    for key, value in LEGACY_MOOD_STATE.items()
}

MAPPING_TABLES = {
    "npc_state": NPC_STATE_MAPPINGS,
    "voice_state": VOICE_STATE_MAPPINGS,
    "legacy_expression": LEGACY_EXPRESSION_MAPPINGS,
    "legacy_set_state": LEGACY_SET_STATE_MAPPINGS,
    "legacy_mood": LEGACY_MOOD_MAPPINGS,
}


class XiaoQCompatibilityMapper:
    """Resolve legacy XiaoQ inputs to canonical expression intents."""

    def resolve(self, source_layer: str, value: object) -> XiaoQCompatibilityMapping:
        layer = str(source_layer or "").strip().lower()
        key = str(value or "").strip().lower()
        try:
            return MAPPING_TABLES[layer][key]
        except KeyError as exc:
            raise KeyError(f"Unknown XiaoQ compatibility input: {layer}={key}") from exc

    def resolve_intent(self, value: object) -> ExpressionIntent:
        if not isinstance(value, dict):
            raise TypeError("XiaoQ compatibility value must be a dict")
        return self.resolve(
            str(value.get("source_layer") or ""),
            value.get("value"),
        ).to_intent()
