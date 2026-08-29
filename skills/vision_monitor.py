"""Concurrent MiMo visual monitoring for XiaoQ.

Each task owns its own sample cadence and completion state.  The camera frame
is shared read-only, so independent targets can be judged in parallel without
opening another camera pipeline.
"""

from __future__ import annotations

import base64
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .base import SideEffect, Skill, SkillResult
from .esp32_led import Esp32LedSkill


DEFAULT_STATE_PATH = Path("data/vision_monitor.json")
DEFAULT_CONTEXT_PATH = Path("data/vision_context.json")
FRAME_PATH = Path("/dev/shm/xiaoq_camera_latest.jpg")
MIMO_URL = "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
MIMO_TIMEOUT_SECONDS = 20
_service_lock = threading.Lock()
_service: "VisionMonitorService | None" = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def remember_visual_context(question: str, reply: str, source: str) -> None:
    if not reply or reply.startswith("视觉回答失败"):
        return
    path = Path(os.environ.get("XIAOQ_VISION_CONTEXT", str(DEFAULT_CONTEXT_PATH)))
    payload = _read_json(path)
    history = payload.get("history", [])
    if not isinstance(history, list):
        history = []
    history.append({
        "question": str(question)[:500], "reply": str(reply)[:1800],
        "source": str(source)[:40], "observed_at": _now(),
    })
    payload["history"] = history[-5:]
    _write_json(path, payload)


def recent_visual_context() -> str:
    path = Path(os.environ.get("XIAOQ_VISION_CONTEXT", str(DEFAULT_CONTEXT_PATH)))
    history = _read_json(path).get("history", [])
    if not isinstance(history, list):
        return ""
    lines = []
    for item in history[-5:]:
        if isinstance(item, dict) and item.get("reply"):
            lines.append(f"{item.get('observed_at', '?')}: {str(item['reply']).replace(chr(10), ' ')[:600]}")
    return "\n".join(lines)[-3000:]


def _content_text(message: object) -> str:
    if isinstance(message, str):
        return message.strip()
    if isinstance(message, list):
        return "".join(str(item.get("text") or item.get("content") or "") for item in message if isinstance(item, dict)).strip()
    if isinstance(message, dict):
        return str(message.get("text") or message.get("content") or "").strip()
    return ""


class VisionMonitorService:
    """Persistent collection of independent, one-shot visual alarm tasks."""

    def __init__(self, alert_callback: Callable[[str, dict], None] | None = None):
        self._state_path = Path(os.environ.get("XIAOQ_VISION_MONITOR_STATE", str(DEFAULT_STATE_PATH)))
        self._alert_callback = alert_callback
        self._lock = threading.RLock()
        self._workers: dict[str, tuple[threading.Thread, threading.Event]] = {}

    def set_alert_callback(self, callback: Callable[[str, dict], None]) -> None:
        self._alert_callback = callback

    def _load(self) -> dict:
        value = _read_json(self._state_path)
        # Migrate the former single-task format without losing its history.
        if "tasks" not in value:
            if value.get("target"):
                legacy_id = str(value.get("task_id") or "legacy")
                value = {"version": 2, "tasks": {legacy_id: value}}
            else:
                value = {"version": 2, "tasks": {}}
        if not isinstance(value.get("tasks"), dict):
            value["tasks"] = {}
        # Give pre-management tasks a stable, spoken ID as well.  Sorting by
        # creation time avoids changing the ID between status queries.
        assigned_numbers = set()
        for task in value["tasks"].values():
            if isinstance(task, dict):
                match = re.fullmatch(r"M(\d+)", str(task.get("display_id", "")))
                if match:
                    assigned_numbers.add(int(match.group(1)))
        next_number = max(assigned_numbers, default=0) + 1
        for task in sorted(
            (item for item in value["tasks"].values() if isinstance(item, dict)),
            key=lambda item: str(item.get("created_at", "")),
        ):
            if not task.get("display_id"):
                task["display_id"] = f"M{next_number}"
                assigned_numbers.add(next_number)
                next_number += 1
        configured_next = value.get("next_task_number")
        value["next_task_number"] = max(
            (configured_next if isinstance(configured_next, int) else 1),
            max(assigned_numbers, default=0) + 1,
        )
        # A successful one-shot alarm is terminal.  Older state files kept
        # active=true after triggering; normalize them on every load.
        for task in value["tasks"].values():
            if isinstance(task, dict) and task.get("triggered") and task.get("alarm_result"):
                task["active"] = False
                task["status"] = "completed"
        value["version"] = 2
        return value

    def _save(self, payload: dict) -> None:
        _write_json(self._state_path, payload)

    def snapshot(self) -> dict:
        with self._lock:
            return self._load()

    def _task(self, task_id: str) -> dict | None:
        data = self._load()
        task = data["tasks"].get(task_id)
        return dict(task) if isinstance(task, dict) else None

    def _put_task(self, task_id: str, task: dict) -> None:
        data = self._load()
        data["tasks"][task_id] = task
        self._save(data)

    def _start_worker(self, task_id: str) -> None:
        running = self._workers.get(task_id)
        if running and running[0].is_alive():
            return
        stop_event = threading.Event()
        worker = threading.Thread(target=self._run_task, args=(task_id, stop_event), name=f"xiaoq-vision-{task_id}", daemon=True)
        self._workers[task_id] = (worker, stop_event)
        worker.start()

    def start(self, config: dict) -> tuple[bool, str, dict]:
        target = str(config.get("target", "")).strip()
        condition = str(config.get("condition", "")).strip()
        if not target or not condition:
            return False, "需要明确要观察的物品和触发报警的条件。", {}
        try:
            interval = max(3, min(3600, int(config.get("interval_seconds", 5))))
            confirmations = max(1, min(5, int(config.get("confirmations", 2))))
        except (TypeError, ValueError):
            return False, "监控间隔或确认次数无效。", {}
        color = str(config.get("alarm_color", "red")).lower()
        if color not in {"red", "green", "blue", "white", "yellow", "purple", "off"}:
            return False, "报警灯颜色无效。", {}
        task_id = uuid.uuid4().hex[:8]
        task = {
            "task_id": task_id, "status": "active", "active": True, "triggered": False,
            "target": target[:800], "condition": condition[:800],
            "baseline_observation": str(config.get("baseline_observation", ""))[:3000],
            "interval_seconds": interval, "confirmations_required": confirmations,
            "consecutive_matches": 0, "alarm_device_id": str(config.get("alarm_device_id", "1")),
            "alarm_color": color, "created_at": _now(), "last_checked_at": "",
            "last_observation": "", "last_error": "", "checks_completed": 0,
        }
        with self._lock:
            data = self._load()
            task["display_id"] = f"M{data['next_task_number']}"
            data["next_task_number"] += 1
            data["tasks"][task_id] = task
            self._save(data)
            self._start_worker(task_id)
        return True, "视觉监控已启动。", task

    def resume(self) -> bool:
        with self._lock:
            resumed = False
            data = self._load()
            for task_id, task in data["tasks"].items():
                if not isinstance(task, dict):
                    continue
                if task.get("triggered") and not task.get("alarm_result"):
                    task.update({"triggered": False, "active": True, "status": "active", "alarm_pending": True})
                    task["consecutive_matches"] = max(int(task.get("consecutive_matches", 0)), int(task.get("confirmations_required", 2)))
                    data["tasks"][task_id] = task
                if task.get("active") and not task.get("triggered"):
                    if not task.get("baseline_observation"):
                        task["baseline_observation"] = recent_visual_context()
                    self._start_worker(task_id)
                    resumed = True
            self._save(data)
            return resumed

    def _matching_task_ids(self, data: dict, task_id: str = "", target: str = "") -> list[str]:
        """Resolve a spoken display id or target description to active tasks."""
        tasks = data["tasks"]
        task_id = str(task_id).strip().lower()
        target = str(target).strip().lower()
        if task_id:
            matches = [item_id for item_id, task in tasks.items() if isinstance(task, dict) and (
                item_id.lower() == task_id or str(task.get("display_id", "")).lower() == task_id
            )]
            if matches:
                return matches
        if target:
            exact = [item_id for item_id, task in tasks.items() if isinstance(task, dict) and task.get("active") and target in str(task.get("target", "")).lower()]
            if exact:
                return exact
            # The router may retain only a salient noun, so accept the inverse
            # containment direction only for a single unambiguous active task.
            reverse = [item_id for item_id, task in tasks.items() if isinstance(task, dict) and task.get("active") and str(task.get("target", "")).lower() in target]
            if len(reverse) == 1:
                return reverse
            return []
        return [item_id for item_id, task in tasks.items() if isinstance(task, dict) and task.get("active")]

    def stop(self, task_id: str = "", target: str = "") -> tuple[bool, str, dict]:
        with self._lock:
            data = self._load()
            targets = self._matching_task_ids(data, task_id, target)
            stopped = 0
            stopped_labels = []
            for item_id in targets:
                task = data["tasks"].get(item_id)
                if not isinstance(task, dict) or not task.get("active"):
                    continue
                task.update({"active": False, "status": "stopped", "stopped_at": _now()})
                event = self._workers.get(item_id, (None, None))[1]
                if event:
                    event.set()
                stopped += 1
                stopped_labels.append(str(task.get("display_id") or item_id))
            self._save(data)
        if stopped:
            return True, f"已停止监控任务{'、'.join(stopped_labels)}。", self.snapshot()
        if task_id or target:
            return True, "没有找到匹配的运行中监控任务。请先查询任务清单。", self.snapshot()
        return True, "当前没有运行中的视觉监控任务。", self.snapshot()

    def task_lines(self, limit: int = 8) -> list[str]:
        """Human-sized rows for voice/card status, newest task first."""
        tasks = list(self.snapshot().get("tasks", {}).values())
        tasks = [task for task in tasks if isinstance(task, dict)]
        tasks.sort(key=lambda task: str(task.get("created_at", "")), reverse=True)
        lines = []
        for task in tasks[:limit]:
            status = {"active": "运行中", "completed": "已报警完成", "stopped": "已停止"}.get(str(task.get("status", "")), "未知")
            lines.append(f"{task.get('display_id', task.get('task_id', '?'))} {status}：{str(task.get('target', ''))[:36]}")
        return lines

    def _api_key(self) -> str:
        for path in (Path("data/settings.json"), Path.home() / ".hermes" / ".env", Path.home() / ".hermes" / "hermes-desktop-assistant" / "config.json"):
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if path.suffix == ".json":
                try:
                    data = json.loads(content)
                    key = data.get("llm", {}).get("api_key") or data.get("xiaomi_mimo_api_key") or data.get("aliyun_api_key")
                    if key:
                        return str(key).strip()
                except (ValueError, TypeError):
                    pass
            else:
                for line in content.splitlines():
                    if line.startswith(("XIAOMI_MIMO_API_KEY=", "MIMO_API_KEY=")):
                        return line.split("=", 1)[1].strip().strip('"')
        return os.environ.get("XIAOMI_MIMO_API_KEY", "").strip()

    def _evaluate(self, task: dict) -> tuple[bool, str, str]:
        started = time.monotonic()
        try:
            if not FRAME_PATH.exists() or time.time() - FRAME_PATH.stat().st_mtime > 4:
                raise RuntimeError("当前没有新鲜的摄像头画面")
            key = self._api_key()
            if not key:
                raise RuntimeError("MiMo API 密钥未配置")
            instruction = (
                "你是实时视觉监控判定器。只依据当前图片，禁止解释或思考过程。"
                "仅输出两行：第一行 RESULT: TRUE 或 RESULT: FALSE；第二行不超过40字的客观描述。"
                "画面遮挡、模糊、视角明显改变或证据不足必须 FALSE。\n"
                f"目标：{task['target']}\n报警条件：{task['condition']}\n"
                f"启动基准（目标当时已确认存在）：{task.get('baseline_observation') or '用户已确认'}\n"
                "当前画面清晰且未见已确认目标时，若条件是目标消失则必须 TRUE。"
            )
            payload = json.dumps({
                "model": "mimo-v2.5", "messages": [{"role": "system", "content": instruction}, {"role": "user", "content": [
                    {"type": "text", "text": "判断当前画面。"},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(FRAME_PATH.read_bytes()).decode("ascii")}},
                ]}], "max_tokens": 160,
            }, ensure_ascii=False).encode("utf-8")
            request = urllib.request.Request(MIMO_URL, data=payload, headers={"Content-Type": "application/json; charset=utf-8", "Authorization": f"Bearer {key}", "api-key": key})
            with urllib.request.urlopen(request, timeout=MIMO_TIMEOUT_SECONDS) as response:
                message = json.loads(response.read().decode("utf-8"))["choices"][0]["message"]
            content = _content_text(message.get("content")) or _content_text(message.get("reasoning_content"))
            markers = list(re.finditer(r"RESULT\s*:\s*(TRUE|FALSE)", content, flags=re.IGNORECASE))
            if not markers:
                raise ValueError(f"视觉模型未给出监控标记: {content[:120]}")
            marker = markers[-1]
            met = marker.group(1).upper() == "TRUE"
            observation = content[marker.end():].strip()[:300]
            elapsed = round(time.monotonic() - started, 2)
            print(f"[VISION-MONITOR] task={task['task_id']} met={met} elapsed={elapsed}s observation={observation[:80]}")
            return met, observation, ""
        except (OSError, RuntimeError, ValueError, KeyError, TypeError, urllib.error.URLError, TimeoutError) as error:
            elapsed = round(time.monotonic() - started, 2)
            print(f"[VISION-MONITOR] task={task['task_id']} evaluation failed after {elapsed}s: {error}")
            return False, "", str(error)[:300]

    def _dispatch_alarm(self, task_id: str, task: dict) -> bool:
        try:
            result = Esp32LedSkill().execute({"device_id": task["alarm_device_id"], "color": task["alarm_color"]})
            if not result.success:
                raise RuntimeError(result.error or "ESP32 报警灯执行失败")
            task.update({
                "triggered": True, "active": False, "status": "completed", "alarm_pending": False,
                "alarm_result": "报警灯已执行", "alarm_ip": str(result.data.get("ip", "")), "triggered_at": _now(), "completed_at": _now(),
            })
            with self._lock:
                self._put_task(task_id, task)
            print(f"[VISION-MONITOR] task={task_id} alarm LED succeeded ip={task.get('alarm_ip')}")
            if self._alert_callback:
                self._alert_callback(f"监控报警：{task['condition']}。{task.get('last_observation') or '已确认触发条件。'}", task)
            return True
        except Exception as error:
            task.update({"alarm_pending": True, "alarm_result": f"报警灯执行失败: {str(error)[:240]}", "last_error": f"报警灯执行失败: {str(error)[:240]}"})
            with self._lock:
                self._put_task(task_id, task)
            print(f"[VISION-MONITOR] task={task_id} alarm LED failed: {error}")
            return False

    def _run_task(self, task_id: str, stop_event: threading.Event) -> None:
        next_sample = time.monotonic()
        while not stop_event.is_set():
            delay = next_sample - time.monotonic()
            if delay > 0 and stop_event.wait(delay):
                return
            # Schedule by sample start, so model latency is not added to the requested interval.
            task = self._task(task_id)
            if not task or not task.get("active") or task.get("triggered"):
                return
            started = time.monotonic()
            met, observation, error = self._evaluate(task)
            with self._lock:
                current = self._task(task_id)
                if not current or not current.get("active"):
                    return
                current.update({"last_checked_at": _now(), "last_observation": observation, "last_error": error, "checks_completed": int(current.get("checks_completed", 0)) + 1})
                current["consecutive_matches"] = int(current.get("consecutive_matches", 0)) + 1 if met else 0
                should_alert = current["consecutive_matches"] >= int(current.get("confirmations_required", 2))
                if should_alert:
                    current["alarm_pending"] = True
                self._put_task(task_id, current)
            if should_alert and self._dispatch_alarm(task_id, current):
                return
            next_sample += float(task.get("interval_seconds", 5))
            while next_sample <= time.monotonic():
                next_sample += float(task.get("interval_seconds", 5))
            print(f"[VISION-MONITOR] task={task_id} next check in {round(max(0, next_sample - time.monotonic()), 2)}s; request took {round(time.monotonic() - started, 2)}s")


class VisionMonitorSkill(Skill):
    name = "vision_monitor"
    description = "按自然语言任务持续观察摄像头画面并在条件满足时触发报警灯"

    def __init__(self, service: VisionMonitorService):
        super().__init__()
        self.service = service

    def execute(self, params: dict = None) -> SkillResult:
        params = params or {}
        action = str(params.get("action", "start")).lower()
        if action == "stop":
            _, text, state = self.service.stop(str(params.get("task_id", "")), str(params.get("target", "")))
            return SkillResult(success=True, data=state, side_effects=[SideEffect("voice_tts", {"text": text})])
        if action in {"status", "query"}:
            state = self.service.snapshot()
            active = [task for task in state.get("tasks", {}).values() if isinstance(task, dict) and task.get("active")]
            lines = self.service.task_lines()
            text = "当前没有运行中的视觉监控任务。" if not active else f"当前有{len(active)}个视觉监控任务在运行。"
            if lines:
                text += " " + "；".join(lines)
            return SkillResult(success=True, data=state, side_effects=[
                SideEffect("card_show", {"title": "视觉监控任务", "lines": lines or ["暂无监控任务"], "card_type": "todo"}),
                SideEffect("voice_tts", {"text": text}),
            ])
        config = dict(params)
        if not str(config.get("baseline_observation", "")).strip():
            config["baseline_observation"] = recent_visual_context()
        ok, text, task = self.service.start(config)
        if not ok:
            return SkillResult(success=True, data=task, side_effects=[SideEffect("voice_tts", {"text": text})])
        spoken = f"已开始{task['display_id']}监控：每{task['interval_seconds']}秒检查{task['target']}；{task['condition']}时让{task['alarm_device_id']}号ESP32变成{self._color_name(task['alarm_color'])}。"
        return SkillResult(success=True, data=task, side_effects=[SideEffect("card_show", {"title": "视觉监控", "lines": [f"任务：{task['display_id']}", f"目标：{task['target']}", f"条件：{task['condition']}", f"间隔：{task['interval_seconds']}秒"], "card_type": "todo"}), SideEffect("voice_tts", {"text": spoken})])

    @staticmethod
    def _color_name(color: str) -> str:
        return {"red": "红色", "green": "绿色", "blue": "蓝色", "white": "白色", "yellow": "黄色", "purple": "紫色", "off": "关闭"}.get(color, color)


def get_vision_monitor_service() -> VisionMonitorService:
    global _service
    with _service_lock:
        if _service is None:
            _service = VisionMonitorService()
        return _service
