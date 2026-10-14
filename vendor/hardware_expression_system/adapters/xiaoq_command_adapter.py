"""Adapter for XiaoQ product command payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..characters.xiaoq_reference import (
    XIAOQ_LEGACY_RENDER_EFFECT_COMMAND_TYPES,
    XIAOQ_PRODUCT_OWNED_COMMAND_TYPES,
)
from ..state_machine.expression_machine import resolve_legacy_command


@dataclass(frozen=True)
class AdapterResult:
    kind: str
    value: str | None = None
    payload: dict[str, Any] | None = None
    ignored: bool = False
    reason: str = ""


class XiaoQCommandAdapter:
    """Map XiaoQ product commands to expression-runtime actions."""

    def adapt(self, command: dict[str, Any]) -> AdapterResult:
        if not isinstance(command, dict):
            return AdapterResult(kind="ignored", ignored=True, reason="command must be a dict")

        command_type = str(command.get("type", "")).strip().lower()
        if not command_type:
            return AdapterResult(kind="ignored", ignored=True, reason="missing type")

        legacy = resolve_legacy_command(command)
        if legacy:
            if legacy.get("event"):
                return AdapterResult(kind="event", value=legacy["event"], payload=command)
            if legacy.get("state"):
                return AdapterResult(kind="state", value=legacy["state"], payload=command)

        if command_type == "voice_start":
            return AdapterResult(kind="event", value="VOICE_START", payload=command)
        if command_type == "voice_stop":
            return AdapterResult(kind="event", value="VOICE_END", payload=command)
        if command_type == "voice_tts":
            if str(command.get("text", "")).strip():
                return AdapterResult(kind="event", value="TTS_START", payload=command)
            return AdapterResult(kind="ignored", ignored=True, reason="empty voice_tts text")
        if command_type == "voice_inject":
            if str(command.get("text", "")).strip():
                return AdapterResult(kind="event", value="NLU_THINKING", payload=command)
            return AdapterResult(kind="ignored", ignored=True, reason="empty voice_inject text")
        if command_type == "mobile_reply":
            if str(command.get("reply", "")).strip() and bool(command.get("speak", False)):
                return AdapterResult(kind="event", value="TTS_START", payload=command)
            if str(command.get("reply", "")).strip():
                return AdapterResult(kind="state", value="FULFILLED", payload=command)
            return AdapterResult(kind="ignored", ignored=True, reason="empty mobile_reply")
        if command_type == "tts_end":
            return AdapterResult(kind="event", value="TTS_END", payload=command)
        if command_type == "set_theme":
            return AdapterResult(kind="style", value=str(command.get("theme_id") or command.get("id") or "default"), payload=command)
        if command_type == "set_personality":
            return AdapterResult(kind="persona", value=str(command.get("preset") or command.get("id") or ""), payload=command)
        if command_type == "persona_set":
            return AdapterResult(kind="persona", value=str(command.get("id") or command.get("name") or ""), payload=command)
        if command_type == "persona_toggle":
            return AdapterResult(kind="persona_toggle", value=None, payload=command, reason="debug only")
        if command_type == "character_set":
            return AdapterResult(kind="character", value=str(command.get("id") or command.get("character") or ""), payload=command)
        if command_type == "style_set":
            return AdapterResult(kind="style", value=str(command.get("id") or command.get("style") or ""), payload=command)
        if command_type == "look_at":
            return AdapterResult(kind="look_at", value=None, payload=command)
        if command_type in XIAOQ_LEGACY_RENDER_EFFECT_COMMAND_TYPES:
            return AdapterResult(kind="renderer_effect", payload=command, reason="legacy XiaoQ renderer effect")
        if command_type in XIAOQ_PRODUCT_OWNED_COMMAND_TYPES:
            return AdapterResult(kind="non_expression", payload=command, ignored=True, reason="owned by product UI")

        return AdapterResult(kind="ignored", payload=command, ignored=True, reason=f"unsupported command type: {command_type}")
