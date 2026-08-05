"""Authenticated LAN control for the XiaoQ ESP32 RGB LED."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .base import SideEffect, Skill, SkillResult


DEFAULT_URL = "http://xiaoq-led.local"
SUPPORTED_COLORS = {"red", "green", "blue", "white", "yellow", "purple", "off"}


class Esp32LedSkill(Skill):
    name = "esp32_led"
    description = "控制小Q局域网 ESP32 RGB 灯颜色"

    def _config(self) -> dict[str, str]:
        path = Path(os.environ.get("XIAOQ_ESP32_LED_CONFIG", "data/esp32_led.json"))
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            value = {}
        return {
            "url": str(value.get("url") or os.environ.get("XIAOQ_ESP32_LED_URL") or DEFAULT_URL).rstrip("/"),
            "token": str(value.get("token") or os.environ.get("XIAOQ_ESP32_LED_TOKEN") or ""),
        }

    def execute(self, params: dict = None) -> SkillResult:
        color = str((params or {}).get("color", "green")).lower()
        if color not in SUPPORTED_COLORS:
            return SkillResult(success=False, error="unsupported LED color")
        config = self._config()
        if not config["token"]:
            return SkillResult(success=False, error="ESP32 LED token is not configured")
        url = f"{config['url']}/api/led?{urllib.parse.urlencode({'color': color})}"
        request = urllib.request.Request(url, data=b"", method="POST", headers={
            "X-XiaoQ-Token": config["token"],
        })
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            return SkillResult(success=False, error=f"ESP32 LED request failed: {exc}")
        if not result.get("ok"):
            return SkillResult(success=False, error=str(result.get("error", "ESP32 LED rejected request")))
        spoken = "已关灯" if color == "off" else f"已把小Q灯光调成{self._color_name(color)}"
        return SkillResult(
            success=True,
            data={"color": color},
            side_effects=[SideEffect("voice_tts", {"text": spoken})],
        )

    @staticmethod
    def _color_name(color: str) -> str:
        return {
            "red": "红色", "green": "绿色", "blue": "蓝色", "white": "白色",
            "yellow": "黄色", "purple": "紫色",
        }.get(color, color)
