"""Restricted SSH file operations for the user-configured laptop."""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
from pathlib import Path

from .base import SideEffect, Skill, SkillResult


DEFAULT_CONFIG_PATH = "data/remote_devices.json"
ALLOWED_EXTENSIONS = {".txt", ".md", ".log", ".csv", ".json"}


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _extract_filename(text: str) -> str | None:
    match = re.search(r"([^\s，。,。！？!?\"“”‘’「」『』]+\.(?:txt|md|log|csv|json))", text, flags=re.IGNORECASE)
    if not match:
        return None
    filename = match.group(1).replace("/", "\\")
    filename = re.sub(r"^(?:打开|查看)", "", filename)
    if filename.lower().startswith("桌面\\"):
        filename = filename[3:]
    elif filename.startswith("桌面"):
        filename = filename[2:]
    path = Path(filename)
    if path.name != filename or path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return None
    return filename


def _extract_content(text: str) -> str | None:
    match = re.search(r"(?:写上|写入|写成|添加内容|内容(?:是|为)?)\s*[：:,，]?", text)
    if not match:
        return None
    content = text[match.end():].strip()
    content = content.strip(" \t\"'“”‘’「」『』")
    content = content.rstrip("。！？!?")
    return content or None


class RemoteLaptopSkill(Skill):
    name = "remote_laptop"
    description = "通过已登记的免密 SSH 对笔记本桌面文本文件执行受限操作"

    def _config(self) -> dict:
        path = Path(os.environ.get("XIAOQ_REMOTE_DEVICES_CONFIG", DEFAULT_CONFIG_PATH))
        devices = _read_json(path).get("devices", {})
        laptop = devices.get("laptop") if isinstance(devices, dict) else None
        return laptop if isinstance(laptop, dict) else {}

    def execute(self, params: dict = None) -> SkillResult:
        params = params or {}
        text = str(params.get("_asr_text", "")).strip()
        config = self._config()
        host = str(config.get("host", ""))
        user = str(config.get("user", ""))
        if not host or not user:
            return SkillResult(success=False, error="笔记本 SSH 登记信息不完整")

        filename = _extract_filename(text)
        content = _extract_content(text)
        if not filename or content is None:
            return SkillResult(
                success=True,
                side_effects=[SideEffect("voice_tts", {"text": "请告诉我桌面文件名和要写入的内容。"})],
            )

        relative_b64 = base64.b64encode(filename.encode("utf-8")).decode("ascii")
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        # Pass only base64 data to PowerShell. User text never becomes shell syntax.
        script = (
            "$relative=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + relative_b64 + "'));"
            "$value=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + content_b64 + "'));"
            "$path=Join-Path (Join-Path $env:USERPROFILE 'Desktop') $relative;"
            "$encoding=New-Object Text.UTF8Encoding($false);"
            "[IO.File]::AppendAllText($path, $value + [Environment]::NewLine, $encoding);"
            "Write-Output 'XIAOQ_OK'"
        )
        target = f"{user}@{host}"
        command = [
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
            target, "powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script,
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return SkillResult(success=False, error=f"SSH 连接笔记本失败: {exc}")
        if result.returncode != 0 or "XIAOQ_OK" not in result.stdout:
            detail = (result.stderr or result.stdout).strip().splitlines()[-1:]
            return SkillResult(success=False, error=f"笔记本文件操作失败: {' '.join(detail)[:180]}")
        return SkillResult(
            success=True,
            data={"device": "laptop", "filename": filename},
            side_effects=[SideEffect(
                "voice_tts", {"text": f"已登录笔记本电脑，并把内容写入桌面{filename}"}
            )],
        )
