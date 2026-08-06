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
DEFAULT_DEVICE_ID = "1"
SUPPORTED_COLORS = {"red", "green", "blue", "white", "yellow", "purple", "off"}


class Esp32LedSkill(Skill):
    name = "esp32_led"
    description = "控制小Q局域网 ESP32 RGB 灯颜色"

    def _read_config(self, path: Path) -> dict:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            value = {}
        return value if isinstance(value, dict) else {}

    def _config(self, device_id: str) -> dict[str, str]:
        registry_path = Path(os.environ.get(
            "XIAOQ_ESP32_DEVICES_CONFIG", "data/esp32_devices.json"
        ))
        registry = self._read_config(registry_path)
        devices = registry.get("devices", {})
        device = devices.get(device_id) if isinstance(devices, dict) else None
        if device is not None and not isinstance(device, dict):
            device = None

        # Backward compatibility for the original single-device configuration.
        legacy = self._read_config(Path(os.environ.get(
            "XIAOQ_ESP32_LED_CONFIG", "data/esp32_led.json"
        )))
        device = device or {}
        return {
            "id": device_id,
            "name": str(device.get("name") or f"{device_id}号ESP32"),
            "url": str(device.get("url") or legacy.get("url") or os.environ.get("XIAOQ_ESP32_LED_URL") or DEFAULT_URL).rstrip("/"),
            "fallback_url": str(device.get("fallback_url") or "").rstrip("/"),
            "token": str(device.get("token") or legacy.get("token") or os.environ.get("XIAOQ_ESP32_LED_TOKEN") or ""),
        }

    def execute(self, params: dict = None) -> SkillResult:
        color = str((params or {}).get("color", "green")).lower()
        device_id = str((params or {}).get("device_id", DEFAULT_DEVICE_ID))
        if color not in SUPPORTED_COLORS:
            return SkillResult(success=False, error="unsupported LED color")
        config = self._config(device_id)
        if not config["token"]:
            return SkillResult(success=False, error="ESP32 LED token is not configured")
        result = None
        errors = []
        endpoints = [config["url"]]
        if config["fallback_url"] and config["fallback_url"] != config["url"]:
            endpoints.append(config["fallback_url"])
        for endpoint in endpoints:
            url = f"{endpoint}/api/led?{urllib.parse.urlencode({'color': color})}"
            request = urllib.request.Request(url, data=b"", method="POST", headers={
                "X-XiaoQ-Token": config["token"],
            })
            try:
                with urllib.request.urlopen(request, timeout=5) as response:
                    result = json.loads(response.read().decode("utf-8"))
                break
            except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
                errors.append(str(exc))
        if result is None:
            return SkillResult(success=False, error=f"ESP32 LED request failed: {'; '.join(errors)}")
        if not result.get("ok"):
            return SkillResult(success=False, error=str(result.get("error", "ESP32 LED rejected request")))
        target = config["name"]
        spoken = f"已关闭{target}灯光" if color == "off" else f"已把{target}调成{self._color_name(color)}"
        return SkillResult(
            success=True,
            data={"device_id": device_id, "device_name": target, "color": color},
            side_effects=[SideEffect("voice_tts", {"text": spoken})],
        )

    @staticmethod
    def _color_name(color: str) -> str:
        return {
            "red": "红色", "green": "绿色", "blue": "蓝色", "white": "白色",
            "yellow": "黄色", "purple": "紫色",
        }.get(color, color)
