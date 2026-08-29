"""会议区人体检测 Hermes 技能：查询 ESP32 PIR 传感器。"""

import json
import logging
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from hermes_skills.base import HermesSkill

log = logging.getLogger("hermes_skills.pir")

# ESP32 位于 CMCC-IOT，树莓派通过 PC 网关跨网段访问。
# 固定 IP 优先，mDNS 仅作为同网段时的备用方式。
_ESP32_HOSTS = ["172.20.171.176", "xiaoq-pir.local"]
_ESP32_PORT = 80
_ESP32_TOKEN = "2f1246740c665dbfa5e170e49b946ef22ffa27d42f17c7e8c6ffa3e11e57653e"
_TIMEOUT = 5
_DEFAULT_MONITOR_INTERVAL = 5
_DEFAULT_ABSENCE_CONFIRMATIONS = 1
_monitor_lock = threading.RLock()
_monitor_service = None


def _query_esp32():
    for host in _ESP32_HOSTS:
        try:
            request = urllib.request.Request(
                f"http://{host}:{_ESP32_PORT}/api/pir",
                headers={"X-XiaoQ-Token": _ESP32_TOKEN},
            )
            with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as error:
            log.debug("PIR query failed on %s: %s", host, error)
    return None


def _now():
    return datetime.now(timezone.utc).isoformat()


class PirMonitorService:
    """后台等待会议区从有人变为无人，并只提醒一次。"""

    def __init__(self):
        self._state_path = Path(os.environ.get("XIAOQ_PIR_MONITOR_STATE", "data/pir_monitor.json"))
        self._lock = threading.RLock()
        self._worker = None
        self._stop_event = None
        self._alert_callback = None

    def set_alert_callback(self, callback):
        self._alert_callback = callback

    def _load(self):
        try:
            value = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            value = {}
        return value if isinstance(value, dict) else {}

    def _save(self, value):
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self._state_path)

    def snapshot(self):
        with self._lock:
            return self._load()

    def start(self, interval_seconds=_DEFAULT_MONITOR_INTERVAL, confirmations=_DEFAULT_ABSENCE_CONFIRMATIONS):
        try:
            interval = max(2, min(300, int(interval_seconds)))
            required = max(1, min(3, int(confirmations)))
        except (TypeError, ValueError):
            return False, "监控间隔或确认次数无效。", {}

        with self._lock:
            current = self._load()
            if current.get("active"):
                return True, f"会议区无人监控已经在运行中，每{current.get('interval_seconds', interval)}秒检查一次。", current

            initial = _query_esp32()
            if initial is None:
                return False, "会议区人体传感器目前无法连接，暂时不能启动监控。", {}
            if not bool(initial.get("present", False)):
                return True, "会议区当前已经无人，已确认，不需要继续等待。", {
                    "active": False, "status": "already_absent", "last_checked_at": _now(),
                }

            task = {
                "active": True, "status": "waiting_for_absence", "created_at": _now(),
                "interval_seconds": interval, "confirmations_required": required,
                "consecutive_absent": 0, "checks_completed": 0,
                "last_checked_at": _now(), "last_error": "",
            }
            self._save(task)
            self._stop_event = threading.Event()
            self._worker = threading.Thread(target=self._run, name="xiaoq-pir-monitor", daemon=True)
            self._worker.start()
            return True, f"已开始监控会议区。当前有人；每{interval}秒检查一次，没人后我会主动告诉你。", task

    def stop(self):
        with self._lock:
            task = self._load()
            if not task.get("active"):
                return True, "当前没有运行中的会议区无人监控。", task
            task.update({"active": False, "status": "stopped", "stopped_at": _now()})
            self._save(task)
            if self._stop_event:
                self._stop_event.set()
            return True, "已停止会议区无人监控。", task

    def status(self):
        task = self.snapshot()
        if task.get("active"):
            return f"会议区无人监控正在运行，每{task.get('interval_seconds', _DEFAULT_MONITOR_INTERVAL)}秒检查一次。", task
        if task.get("status") == "completed":
            return "会议区无人监控已触发提醒并自动结束。", task
        return "当前没有运行中的会议区无人监控。", task

    def resume(self, alert_callback=None):
        with self._lock:
            task = self._load()
            if not task.get("active"):
                return False
            if self._worker and self._worker.is_alive():
                return True
            self._stop_event = threading.Event()
            self._worker = threading.Thread(
                target=self._run, args=(alert_callback,), name="xiaoq-pir-monitor", daemon=True,
            )
            self._worker.start()
            return True

    def _run(self, alert_callback=None):
        alert_callback = alert_callback or self._alert_callback
        while True:
            with self._lock:
                task = self._load()
                stop_event = self._stop_event
            if not task.get("active") or (stop_event and stop_event.is_set()):
                return
            if stop_event and stop_event.wait(float(task.get("interval_seconds", _DEFAULT_MONITOR_INTERVAL))):
                return

            data = _query_esp32()
            with self._lock:
                current = self._load()
                if not current.get("active"):
                    return
                current["checks_completed"] = int(current.get("checks_completed", 0)) + 1
                current["last_checked_at"] = _now()
                if data is None:
                    current["last_error"] = "传感器查询失败"
                    self._save(current)
                    continue

                current["last_error"] = ""
                if bool(data.get("present", False)):
                    current["consecutive_absent"] = 0
                    self._save(current)
                    continue

                current["consecutive_absent"] = int(current.get("consecutive_absent", 0)) + 1
                if current["consecutive_absent"] < int(current.get("confirmations_required", 1)):
                    self._save(current)
                    continue

                current.update({
                    "active": False, "status": "completed", "completed_at": _now(),
                    "alert_text": "会议区现在没人了。",
                })
                self._save(current)

            if alert_callback:
                try:
                    alert_callback("会议区现在没人了。", current)
                except Exception as error:
                    log.warning("PIR alert callback failed: %s", error)
            return


def get_pir_monitor_service():
    global _monitor_service
    with _monitor_lock:
        if _monitor_service is None:
            _monitor_service = PirMonitorService()
        return _monitor_service


class PirHermesSkill(HermesSkill):
    name = "pir"
    description = "查询会议区是否有人，或持续监控会议区，没人后主动语音提醒"

    def prepare(self, text: str, options=None) -> dict:
        options = options or {}
        normalized = "".join(str(text or "").lower().split())
        action = str(options.get("action", "")).lower()
        monitor = get_pir_monitor_service()
        if action in {"stop", "stop_monitor"} or ("停止" in normalized and "监控" in normalized and "会议区" in normalized):
            ok, reply, task = monitor.stop()
            return {"context": "【会议区无人监控】" + reply, "action": None, "skip_llm": True, "reply": reply, "monitor_task": task}
        if action in {"status", "query_monitor"} or ("监控" in normalized and "会议区" in normalized and "任务" in normalized):
            reply, task = monitor.status()
            return {"context": "【会议区无人监控】" + reply, "action": None, "skip_llm": True, "reply": reply, "monitor_task": task}
        monitor_requested = action in {"monitor", "monitor_absence", "start"} or (
            "会议区" in normalized and "监控" in normalized
            and any(phrase in normalized for phrase in ("没人", "无人", "离开", "告诉我"))
        )
        if monitor_requested:
            ok, reply, task = monitor.start(
                options.get("interval_seconds", _DEFAULT_MONITOR_INTERVAL),
                options.get("confirmations", _DEFAULT_ABSENCE_CONFIRMATIONS),
            )
            return {"context": "【会议区无人监控】" + reply, "action": None, "skip_llm": True, "reply": reply, "monitor_task": task}
        data = _query_esp32()
        if data is None:
            return {
                "context": "【会议区人体检测】传感器离线或无法连接。",
                "action": None,
                "skip_llm": True,
                "reply": "抱歉，会议区的人体传感器目前无法连接，请检查 ESP32 是否在线。",
            }

        present = bool(data.get("present", False))
        count = data.get("presentCount", 0)
        last_motion_ago = int(data.get("lastMotionAgoMs", 0)) // 1000
        uptime_s = int(data.get("uptimeMs", 0)) // 1000
        absent_threshold = int(data.get("absentThresholdMs", 30000)) // 1000
        if present:
            context = (
                f"【会议区人体检测】当前会议区有人。累计检测到 {count} 次运动，"
                f"最近一次运动在 {last_motion_ago} 秒前，传感器已运行 {uptime_s} 秒。"
            )
            reply = "会议区现在有人。"
        else:
            context = (
                f"【会议区人体检测】当前会议区无人。已连续 {absent_threshold} 秒未检测到运动，"
                f"最后一次运动在 {last_motion_ago} 秒前，传感器已运行 {uptime_s} 秒。"
            )
            reply = "会议区现在没有人。"
        return {"context": context, "action": None, "skip_llm": True, "reply": reply}
