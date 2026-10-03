"""Deterministic two-step AT dispatch flow for the XiaoQ demo runtime."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


HELPER = Path.home() / ".hermes/skills/at-test-dispatch/scripts/dispatch_helper.py"
PENDING = Path.home() / ".hermes/at_dispatch_pending.json"
PENDING_TESTS = Path.home() / ".hermes/pending_tests.json"
DEFAULT_HOSTNAME = "52467"
CHINESE_DIGITS = str.maketrans("零〇一二三四五六七八九", "00123456789")


def _run_helper(*args: str, timeout: int = 120) -> str:
    result = subprocess.run(
        [sys.executable, str(HELPER), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "AT辅助脚本执行失败")
    return result.stdout.strip()


def _parse_json_output(output: str, expected_type):
    decoder = json.JSONDecoder()
    for match in re.finditer(r"[\[{]", output or ""):
        try:
            value, _ = decoder.raw_decode(output[match.start():])
        except ValueError:
            continue
        if isinstance(value, expected_type):
            return value
    raise RuntimeError("AT辅助脚本返回内容无法解析")


def _normalize_project(text: str) -> str:
    normalized = str(text or "").upper().translate(CHINESE_DIGITS)
    normalized = normalized.replace("杠", "-")
    normalized = re.sub(r"\s+", "", normalized)
    # Project identifiers are conventionally hyphen-delimited. This also
    # handles arbitrary future projects instead of hardcoding ML307C only.
    match = re.search(r"[A-Z]{2,}[A-Z0-9]*(?:-[A-Z0-9]+)+", normalized)
    return match.group(0) if match else ""


def is_confirmation(text: str) -> bool:
    normalized = re.sub(r"\s+", "", str(text or "").lower())
    return any(
        phrase in normalized
        for phrase in ("确认下发", "同意执行", "按这个下发", "确认执行", "可以下发", "就这样下发")
    )


def _choose_module(modules: list[dict]) -> dict:
    industrial = [
        item for item in modules
        if not item.get("is_esp32") and str(item.get("is_networked", "")).lower() == "true"
    ]
    if industrial:
        return industrial[0]
    esp32_online = [
        item for item in modules
        if item.get("is_esp32") and str(item.get("is_networked", "true")).lower() != "false"
    ]
    if esp32_online:
        return esp32_online[0]
    esp32 = [item for item in modules if item.get("is_esp32")]
    if esp32:
        return esp32[0]
    raise RuntimeError("没有匹配项目的空闲 AT 模组")


def prepare(text: str) -> str:
    project = _normalize_project(text)
    if not project:
        return "请先告诉我测试项目名，例如 ML307C-DC-CN。"

    modules = _parse_json_output(_run_helper("query_idle", project), list)
    module = _choose_module(modules)
    is_esp32 = bool(module.get("is_esp32"))
    branch = _run_helper("get_branch", project, "--esp32" if is_esp32 else "").strip()
    if not branch:
        branch = "esp32_ML307C" if is_esp32 else "ML307C"
    platform = _run_helper("get_platform", project).strip() or "ASR"
    script_output = _run_helper("get_scripts", "AT", branch, "--esp32" if is_esp32 else "")
    scripts = _parse_json_output(script_output, list)
    scripts = [str(item) for item in scripts if str(item) != "test_lwm2m.py"]
    if is_esp32 and "test_upgrade_mqtt.py" in scripts:
        scripts.remove("test_upgrade_mqtt.py")
        scripts.insert(0, "test_upgrade_mqtt.py")
    if not scripts:
        raise RuntimeError("没有可用的 AT 测试用例")

    firmware_list = _parse_json_output(_run_helper("search_firmware", project), list)
    firmware_list = [
        item for item in firmware_list
        if "opencpu" not in str(item.get("name", "")).lower()
    ]
    if not firmware_list:
        raise RuntimeError("没有可用的非 OpenCpu AT 固件")
    firmware = firmware_list[0]
    params = {
        "hostname": DEFAULT_HOSTNAME,
        "index": module["index"],
        "baudrate": 115200,
        "test_type": "AT",
        "platform": platform,
        "branch": branch,
        "robotPath": scripts,
        "tags": "auto",
        "runNum": 1,
        "runTimer": 0,
        "url": firmware["url"],
        "computer_index": module["computer_index"],
        "case_level": ["P0"],
        "logornot": True,
        "serial_type": "local",
    }
    PENDING.write_text(json.dumps({"created_at": time.time(), "project": project, "params": params,
                                   "module": module, "firmware": firmware}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    target_type = "工控机" if not is_esp32 else "ESP32"
    return (
        f"已准备 AT 测试任务，尚未下发。\n"
        f"项目：{project}\n"
        f"目标：{target_type} {module['index']}\n"
        f"固件：{firmware.get('name', '最新非 OpenCpu 固件')}\n"
        f"参数：115200，P0，1轮，默认全部用例（共{len(scripts)}个）\n"
        "请回复“确认下发”后我再执行。"
    )


def dispatch_pending() -> str:
    try:
        pending = json.loads(PENDING.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "没有待确认的 AT 测试任务，请先指定项目。"
    if time.time() - float(pending.get("created_at", 0)) > 15 * 60:
        return "待确认的 AT 任务已过期，请重新指定项目。"
    params = pending.get("params")
    if not isinstance(params, dict):
        return "待确认任务参数不完整，请重新指定项目。"
    PENDING.write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        output = _run_helper("dispatch", str(PENDING), timeout=120)
    except Exception as error:
        return f"AT 测试下发失败：{error}"
    match = re.search(r"OK\+(\d+)", output)
    if not match:
        return f"AT 测试下发失败：{output[-300:] or '远端没有返回成功标识'}"
    test_id = int(match.group(1))
    try:
        tasks = json.loads(PENDING_TESTS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        tasks = []
    tasks = [item for item in tasks if int(item.get("test_id", -1)) != test_id]
    tasks.append({
        "test_id": test_id,
        "test_config": {
            "project": pending.get("project", ""),
            "test_type": "AT",
            "platform": params.get("platform"),
            "branch": params.get("branch"),
            "module": params.get("index"),
            "computer_index": params.get("computer_index"),
            "firmware": str(pending.get("firmware", {}).get("name", "")),
            "scripts": params.get("robotPath", []),
            "case_level": params.get("case_level", ["P0"]),
            "runNum": params.get("runNum", 1),
        },
        "subscribe_time": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "status": "waiting",
    })
    PENDING_TESTS.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        PENDING.unlink()
    except OSError:
        pass
    return f"AT 测试已成功下发，测试ID：{test_id}。目标模组：{params.get('index')}。"
