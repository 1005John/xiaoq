"""Xiaomi IoT skill for XiaoQ.

Wraps the Xiaomi cloud API (micloud) to control and query Xiaomi smart home
devices — bathroom heater, motion/presence sensors, smart plugs, gateways, etc.

The skill loads credentials from data/xiaomi_iot_config.json and the device
list from data/xiaomi_iot_devices.json (both produced by the token extraction
flow).  A background poller can watch motion/presence sensors and trigger a
voice + card alert when the state changes, reusing the same callback pattern
as vision_monitor.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

from .base import SideEffect, Skill, SkillResult

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
_CFG_DIR = Path(os.environ.get("XIAOQ_ROOT", os.path.expanduser("~/xiaoq-face-auth-demo"))) / "data"
_CONFIG_PATH = _CFG_DIR / "xiaomi_iot_config.json"
_DEVICES_PATH = _CFG_DIR / "xiaomi_iot_devices.json"
_MONITOR_STATE_PATH = _CFG_DIR / "xiaomi_iot_monitor.json"
_SCENE_PATH = _CFG_DIR / "xiaomi_iot_scenes.json"
_API_BASE = "https://api.io.mi.com/app"
_service_lock = threading.Lock()
_service: "XiaomiIoTService | None" = None

# ---------------------------------------------------------------------------
# Device model specs — siid/piid mappings for common Xiaomi MIoT Spec models.
# Each entry maps a model-prefix to a dict of property→(siid, piid, type).
# "type" can be "bool" (on/off), "int", or "str".
# These are the standard MIoT Spec positions; devices that follow the spec
# will work.  Unknown devices fall back to siid=2/piid=1 (the universal switch).
# ---------------------------------------------------------------------------
MODEL_SPECS: dict[str, dict[str, tuple[int, int, str]]] = {
    # Smart plugs / switches — power on/off
    "chuangmi.plug.":       {"power": (2, 1, "bool")},
    "zimi.plug.":           {"power": (2, 1, "bool")},
    "giot.switch.":         {"power": (2, 1, "bool")},
    # Bathroom heater — power + mode
    "topwit.bhf_light.":    {"power": (2, 1, "bool"), "mode": (2, 2, "int")},
    # PIR motion sensor — motion (bool, event-type)
    "xiaomi.motion.":       {"motion": (3, 1, "bool")},
    # Human presence sensors (mmWave)
    "linp.sensor_occupy.":  {"presence": (2, 1, "bool"), "occupancy": (2, 1, "bool")},
    # Curtain motor
    "lumi.curtain.":        {"motor_status": (2, 1, "int"), "target_position": (2, 2, "int")},
    # Magnet / door sensor
    "isa.magnet.":          {"contact": (2, 1, "bool")},
    # Safe box
    "loock.safe.":          {"state": (2, 1, "int")},
    # Camera
    "chuangmi.camera.":     {"power": (2, 1, "bool")},
}

# Properties whose change is interesting enough to trigger an alert.
SENSOR_PROPERTIES = {"motion", "presence", "occupancy", "contact"}


def _match_spec(model: str) -> dict[str, tuple[int, int, str]]:
    """Return the property spec for *model* by prefix matching."""
    for prefix, spec in MODEL_SPECS.items():
        if model.startswith(prefix):
            return spec
    return {}


class XiaomiIoTService:
    """Singleton service: cloud connection, device cache, MIoT Spec calls."""

    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self._devices: list[dict[str, Any]] = []
        self._mc = None  # MiCloud instance
        self._lock = threading.RLock()
        self._alert_callback: Callable[[str, dict[str, Any]], None] | None = None
        self._workers: dict[str, tuple[threading.Thread, threading.Event]] = {}
        self._scenes: dict[str, dict[str, Any]] = {}
        self._scene_workers: dict[str, tuple[threading.Thread, threading.Event]] = {}
        self._load()
        self._load_scenes()

    # -- config & devices --------------------------------------------------

    def _load(self) -> None:
        try:
            self._config = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._config = {}
        try:
            self._devices = json.loads(_DEVICES_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._devices = []

    def _cloud(self):
        """Lazily create / refresh the MiCloud wrapper."""
        if self._mc is not None:
            return self._mc
        if not self._config:
            return None
        try:
            from micloud import MiCloud
        except ImportError:
            return None
        mc = MiCloud(self._config.get("username", ""), "")
        mc.default_server = self._config.get("server", "cn")
        mc.user_id = str(self._config.get("user_id", ""))
        mc.service_token = str(self._config.get("service_token", ""))
        mc.ssecurity = str(self._config.get("ssecurity", ""))
        mc._init_session()
        mc.session.cookies.update({
            "userId": mc.user_id,
            "serviceToken": mc.service_token,
            "yetAnotherServiceToken": mc.service_token,
            "locale": "zh_CN",
            "timezone": "GMT+08:00",
            "is_daylight": "0",
            "dst_offset": "0",
            "channel": "MI_APP_STORE",
        })
        self._mc = mc
        return mc

    def reload_devices(self) -> list[dict[str, Any]]:
        """Re-fetch the device list from the cloud and cache it."""
        mc = self._cloud()
        if mc is None:
            return self._devices
        try:
            devices = mc.get_devices(country=self._config.get("server", "cn"))
            if devices:
                self._devices = devices
                _DEVICES_PATH.parent.mkdir(parents=True, exist_ok=True)
                _DEVICES_PATH.write_text(
                    json.dumps(devices, ensure_ascii=False, indent=2), encoding="utf-8")
                os.chmod(_DEVICES_PATH, 0o600)
        except Exception as exc:
            print(f"[XIAOQ-IOT] reload_devices failed: {exc}")
        return self._devices

    # -- device lookup -----------------------------------------------------

    def devices(self) -> list[dict[str, Any]]:
        return self._devices

    def find_device(self, name: str) -> dict[str, Any] | None:
        """Find a device by fuzzy name match (case-insensitive substring)."""
        name = name.strip().lower()
        if not name:
            return None
        # exact match first
        for d in self._devices:
            if str(d.get("name", "")).strip().lower() == name:
                return d
        # substring match — prefer online devices
        offline_matches = []
        online_matches = []
        for d in self._devices:
            dname = str(d.get("name", "")).strip().lower()
            if name in dname or dname in name:
                if d.get("isOnline"):
                    online_matches.append(d)
                else:
                    offline_matches.append(d)
        if online_matches:
            return online_matches[0]
        if offline_matches:
            return offline_matches[0]
        return None

    def find_devices(self, name: str) -> list[dict[str, Any]]:
        """Find ALL devices matching a fuzzy name. Uses keyword matching."""
        name = name.strip().lower()
        if not name:
            return []
        matches = []
        for d in self._devices:
            dname = str(d.get("name", "")).strip().lower()
            # Direct substring either direction
            if name in dname or dname in name:
                matches.append(d)
                continue
            # Keyword matching: split query into 2+ char keywords and match any
            keywords = [name[i:i+2] for i in range(len(name) - 1)]
            if any(kw in dname for kw in keywords if len(kw) >= 2):
                matches.append(d)
        # dedupe by did
        seen = set()
        unique = []
        for d in matches:
            did = d.get("did", id(d))
            if did not in seen:
                seen.add(did)
                unique.append(d)
        # sort online first
        unique.sort(key=lambda d: not d.get("isOnline", False))
        return unique

    # -- MIoT Spec property read/write ------------------------------------

    def get_property(self, did: str, siid: int, piid: int) -> Any:
        """Read a single device property via the MIoT Spec cloud API."""
        mc = self._cloud()
        if mc is None:
            return None
        params = {"data": json.dumps({"params": [{"did": did, "siid": siid, "piid": piid}]})}
        try:
            resp = mc.request(f"{_API_BASE}/miotspec/prop/get", params)
            if not resp:
                return None
            data = json.loads(resp) if isinstance(resp, (str, bytes)) else resp
            results = data.get("result", []) if isinstance(data, dict) else data
            if isinstance(results, list) and results:
                entry = results[0]
                return entry.get("value") if isinstance(entry, dict) else None
            print(f"[XIAOQ-IOT] get_property response: {str(data)[:200]}")
            return None
        except Exception as exc:
            print(f"[XIAOQ-IOT] get_property error: {exc}")
            return None

    def set_property(self, did: str, siid: int, piid: int, value: Any) -> bool:
        """Write a single device property via the MIoT Spec cloud API."""
        mc = self._cloud()
        if mc is None:
            return False
        params = {"data": json.dumps({"params": [
            {"did": did, "siid": siid, "piid": piid, "value": value}]})}
        try:
            resp = mc.request(f"{_API_BASE}/miotspec/prop/set", params)
            if not resp:
                return False
            data = json.loads(resp) if isinstance(resp, (str, bytes)) else resp
            results = data.get("result", []) if isinstance(data, dict) else data
            if isinstance(results, list) and results:
                entry = results[0]
                if isinstance(entry, dict) and entry.get("code", 0) == 0:
                    return True
                err = entry.get("message", "") if isinstance(entry, dict) else str(entry)
                print(f"[XIAOQ-IOT] set_property rejected: {err}")
                return False
            if isinstance(data, dict) and data.get("code") == 0:
                return True
            print(f"[XIAOQ-IOT] set_property response: {str(data)[:200]}")
            return False
        except Exception as exc:
            print(f"[XIAOQ-IOT] set_property error: {exc}")
            return False

    # -- high-level helpers ------------------------------------------------

    def read_spec_property(self, device: dict[str, Any], prop_name: str) -> Any:
        """Read *prop_name* from *device* using its model spec."""
        spec = _match_spec(str(device.get("model", "")))
        entry = spec.get(prop_name)
        if not entry:
            return None
        siid, piid, _ = entry
        return self.get_property(str(device.get("did", "")), siid, piid)

    def write_spec_property(self, device: dict[str, Any], prop_name: str, value: Any) -> bool:
        spec = _match_spec(str(device.get("model", "")))
        entry = spec.get(prop_name)
        if not entry:
            # fallback: universal switch at siid=2, piid=1
            siid, piid, ptype = 2, 1, "bool"
        else:
            siid, piid, ptype = entry
        if ptype == "bool":
            value = True if str(value).lower() in ("on", "true", "1", "开") else False
        return self.set_property(str(device.get("did", "")), siid, piid, value)

    def control_device(self, device_name: str, action: str, value: str = "") -> dict[str, Any]:
        """High-level control: turn on/off a device."""
        device = self.find_device(device_name)
        if not device:
            return {"ok": False, "error": f"未找到设备：{device_name}"}
        if not device.get("isOnline"):
            return {"ok": False, "error": f"设备{device.get('name','?')}离线"}
        spec = _match_spec(str(device.get("model", "")))
        # map action words to property + value
        prop = "power"
        val = value
        if action in ("on", "打开", "开启", "开"):
            val = "on"
        elif action in ("off", "关闭", "关掉", "关"):
            val = "off"
        ok = self.write_spec_property(device, prop, val)
        name = device.get("name", "?")
        spoken = f"已{'打开' if val == 'on' else '关闭'}{name}" if ok else f"{name}控制失败"
        return {"ok": ok, "device": name, "action": action, "value": val, "spoken": spoken}

    def query_device(self, device_name: str, prop_name: str = "") -> dict[str, Any]:
        """High-level query: read device property(ies). Supports multi-sensor summary."""
        all_matches = self.find_devices(device_name)

        # Smart fallback: if query is about people ("人") but no matches,
        # automatically query all human-presence/motion sensors
        if not all_matches and "人" in device_name:
            all_matches = [d for d in self._devices
                           if any(p in _match_spec(str(d.get("model", "")))
                                  for p in ("motion", "presence", "occupancy"))]
            if all_matches:
                device_name = "人体传感器"  # for display

        # If matches include non-sensor devices, filter to sensors when query
        # is about "人" (human presence)
        if "人" in device_name and len(all_matches) > 1:
            sensor_matches = [d for d in all_matches
                              if any(p in _match_spec(str(d.get("model", "")))
                                     for p in ("motion", "presence", "occupancy", "contact"))]
            if sensor_matches:
                all_matches = sensor_matches

        if not all_matches:
            return {"ok": False, "error": f"未找到设备：{device_name}"}

        # If multiple matches, query all sensor-type devices and summarize
        if len(all_matches) > 1:
            summaries = []
            for device in all_matches:
                model = str(device.get("model", ""))
                spec = _match_spec(model)
                if not spec:
                    continue
                name = device.get("name", "?")
                if not device.get("isOnline"):
                    summaries.append(f"{name}离线")
                    continue
                # read key sensor property
                sensor_prop = next((p for p in spec if p in SENSOR_PROPERTIES), "")
                if not sensor_prop:
                    sensor_prop = list(spec.keys())[0]
                siid, piid, _ = spec[sensor_prop]
                raw = self.get_property(str(device.get("did", "")), siid, piid)
                if raw is None:
                    summaries.append(f"{name}读取失败")
                elif sensor_prop in ("motion", "presence", "occupancy"):
                    summaries.append(f"{name}{'有人' if raw else '无人'}")
                elif sensor_prop == "contact":
                    summaries.append(f"{name}{'开门' if raw else '关门'}")
                elif sensor_prop == "power":
                    summaries.append(f"{name}{'开启' if raw else '关闭'}")
                else:
                    summaries.append(f"{name}={raw}")
            if not summaries:
                # No sensor devices found among matches, fall back to single query
                device = all_matches[0]
            else:
                spoken = "；".join(summaries)
                # For "有人吗" type queries, give a clear answer
                any_person = any("有人" in s for s in summaries)
                if any_person:
                    spoken = "家里有人。" + spoken
                else:
                    all_empty = all("无人" in s or "离线" in s or "失败" in s for s in summaries)
                    if all_empty:
                        spoken = "家里没人。" + spoken
                return {"ok": True, "device": device_name, "summaries": summaries,
                        "spoken": spoken}

        # Single device query
        device = all_matches[0]
        name = device.get("name", "?")
        model = str(device.get("model", ""))
        spec = _match_spec(model)
        if not spec:
            return {"ok": True, "device": name, "online": device.get("isOnline"),
                    "model": model, "spoken": f"{name}是{model}，暂不支持属性查询"}
        if not device.get("isOnline"):
            return {"ok": True, "device": name, "online": False,
                    "spoken": f"{name}离线，无法查询"}
        props_to_read = [prop_name] if prop_name and prop_name in spec else list(spec.keys())
        results = {}
        for pn in props_to_read:
            siid, piid, _ = spec[pn]
            raw = self.get_property(str(device.get("did", "")), siid, piid)
            results[pn] = raw
        parts = []
        for pn, val in results.items():
            if val is None:
                parts.append(f"{pn}未知")
            elif pn in ("power",):
                parts.append("开启" if val else "关闭")
            elif pn in ("motion", "presence", "occupancy"):
                parts.append("有人" if val else "无人")
            elif pn in ("contact",):
                parts.append("开门" if val else "关门")
            else:
                parts.append(f"{pn}={val}")
        spoken = f"{name}：{', '.join(parts)}" if parts else f"{name}无可用数据"
        return {"ok": True, "device": name, "properties": results, "spoken": spoken}

    # -- background sensor monitoring --------------------------------------

    def set_alert_callback(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        self._alert_callback = callback

    def start_monitor(self, device_name: str, prop_name: str = "",
                       interval: int = 5) -> tuple[bool, str]:
        """Start polling a sensor; trigger callback on state change."""
        device = self.find_device(device_name)
        if not device:
            return False, f"未找到设备：{device_name}"
        spec = _match_spec(str(device.get("model", "")))
        if not spec:
            return False, f"设备{device.get('name','?')}不支持传感器监控"
        # pick a sensor property if not specified
        if not prop_name:
            sensor_props = [p for p in spec if p in SENSOR_PROPERTIES]
            if not sensor_props:
                return False, f"设备{device.get('name','?')}没有可监控的传感器属性"
            prop_name = sensor_props[0]
        if prop_name not in spec:
            return False, f"设备{device.get('name','?')}没有属性{prop_name}"
        task_id = f"{device.get('did','?')}_{prop_name}"
        with self._lock:
            if task_id in self._workers:
                return True, f"已经在监控{device.get('name','?')}的{prop_name}"
            stop = threading.Event()
            t = threading.Thread(target=self._run_monitor,
                args=(task_id, device, prop_name, interval, stop),
                name=f"xiaomi-iot-{task_id}", daemon=True)
            self._workers[task_id] = (t, stop)
            t.start()
        name = device.get("name", "?")
        self._save_monitor_state()
        return True, f"已开始监控{name}的{prop_name}，每{interval}秒检查"

    def stop_monitor(self, device_name: str = "") -> tuple[bool, str]:
        with self._lock:
            if not device_name:
                for tid, (t, ev) in self._workers.items():
                    ev.set()
                self._workers.clear()
                self._save_monitor_state()
                return True, "已停止所有小米设备监控"
            device = self.find_device(device_name)
            if not device:
                return True, "未找到设备"
            did = device.get("did", "")
            stopped = []
            for tid in list(self._workers):
                if tid.startswith(f"{did}_"):
                    self._workers[tid][1].set()
                    stopped.append(tid)
                    del self._workers[tid]
            self._save_monitor_state()
            if stopped:
                return True, f"已停止监控{device.get('name','?')}"
            return True, f"没有运行中的{device.get('name','?')}监控"

    def monitor_status(self) -> list[dict[str, Any]]:
        with self._lock:
            return [{"task_id": tid, "device": None} for tid in self._workers]

    def _run_monitor(self, task_id: str, device: dict, prop_name: str,
                     interval: int, stop: threading.Event) -> None:
        siid, piid, _ = _match_spec(str(device.get("model", "")))[prop_name]
        did = str(device.get("did", ""))
        name = device.get("name", "?")
        last_value = None
        next_check = time.monotonic()
        while not stop.is_set():
            delay = next_check - time.monotonic()
            if delay > 0 and stop.wait(delay):
                return
            value = self.get_property(did, siid, piid)
            now = time.monotonic()
            if value is not None and value != last_value:
                state = {
                    "device": name, "did": did, "property": prop_name,
                    "old_value": last_value, "new_value": value,
                    "changed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                if prop_name in ("motion", "presence", "occupancy"):
                    text = f"监控报警：{name}{'检测到人' if value else '已无人'}。"
                elif prop_name == "contact":
                    text = f"监控报警：{name}{'已开门' if value else '已关门'}。"
                else:
                    text = f"监控报警：{name}的{prop_name}变为{value}。"
                if self._alert_callback:
                    self._alert_callback(text, state)
                last_value = value
            next_check = now + max(3, interval)

    def _save_monitor_state(self) -> None:
        try:
            state = {"tasks": list(self._workers.keys())}
            _MONITOR_STATE_PATH.write_text(
                json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    # -- scene automation (trigger → action) -------------------------------

    def _load_scenes(self) -> None:
        try:
            self._scenes = json.loads(_SCENE_PATH.read_text(encoding="utf-8"))
            if not isinstance(self._scenes, dict):
                self._scenes = {}
        except (OSError, json.JSONDecodeError):
            self._scenes = {}

    def _save_scenes(self) -> None:
        try:
            _SCENE_PATH.write_text(
                json.dumps(self._scenes, ensure_ascii=False, indent=2), encoding="utf-8")
            os.chmod(_SCENE_PATH, 0o600)
        except OSError:
            pass

    def start_scene(self, params: dict) -> tuple[bool, str, str]:
        """Create and start a scene: when trigger condition met, execute action + alert."""
        trigger_name = str(params.get("trigger_device", "")).strip()
        action_name = str(params.get("action_device", "")).strip()
        action_cmd = str(params.get("action_command", "on")).strip()
        interval = max(3, int(params.get("interval_seconds", 3)))
        one_shot = bool(params.get("one_shot", False))
        spoken = str(params.get("spoken", "")).strip()

        if not trigger_name or not action_name:
            return False, "", "需要指定触发设备和执行设备"

        trigger_device = self.find_device(trigger_name)
        if not trigger_device:
            return False, "", f"未找到触发设备：{trigger_name}"
        action_device = self.find_device(action_name)
        if not action_device:
            return False, "", f"未找到执行设备：{action_name}"

        trigger_spec = _match_spec(str(trigger_device.get("model", "")))
        if not trigger_spec:
            return False, "", f"设备{trigger_device.get('name','?')}不支持场景触发"

        # Pick a sensor property for trigger
        trigger_prop = str(params.get("trigger_property", "")).strip()
        if not trigger_prop:
            sensor_props = [p for p in trigger_spec if p in SENSOR_PROPERTIES]
            trigger_prop = sensor_props[0] if sensor_props else list(trigger_spec.keys())[0]
        if trigger_prop not in trigger_spec:
            return False, "", f"设备{trigger_device.get('name','?')}没有属性{trigger_prop}"

        trigger_siid, trigger_piid, _ = trigger_spec[trigger_prop]
        # Determine trigger value (default: True for sensors, "on" for switches)
        trigger_value = params.get("trigger_value")
        if trigger_value is None:
            trigger_value = True if trigger_prop in SENSOR_PROPERTIES else "on"

        scene_id = f"scene_{int(time.time())}"
        t_name = trigger_device.get("name", "?")
        a_name = action_device.get("name", "?")

        if not spoken:
            if trigger_prop == "contact":
                spoken = f"{t_name}已打开，已自动{'打开' if action_cmd == 'on' else '关闭'}{a_name}"
            elif trigger_prop in ("motion", "presence", "occupancy"):
                spoken = f"{t_name}{'检测到人' if trigger_value else '已无人'}，已自动{'打开' if action_cmd == 'on' else '关闭'}{a_name}"
            else:
                spoken = f"{t_name}触发，已{'打开' if action_cmd == 'on' else '关闭'}{a_name}"

        scene = {
            "scene_id": scene_id,
            "trigger_device": t_name, "trigger_did": str(trigger_device.get("did", "")),
            "trigger_property": trigger_prop, "trigger_siid": trigger_siid,
            "trigger_piid": trigger_piid, "trigger_value": trigger_value,
            "action_device": a_name, "action_did": str(action_device.get("did", "")),
            "action_command": action_cmd, "spoken": spoken,
            "interval_seconds": interval, "one_shot": one_shot,
            "active": True, "triggered": False,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

        with self._lock:
            self._scenes[scene_id] = scene
            self._save_scenes()
            stop = threading.Event()
            t = threading.Thread(target=self._run_scene,
                args=(scene_id, scene, stop),
                name=f"xiaomi-scene-{scene_id}", daemon=True)
            self._scene_workers[scene_id] = (t, stop)
            t.start()

        summary = (f"已创建场景：{t_name}{'开门' if trigger_prop == 'contact' and trigger_value else ''}"
                   f"{'有人' if trigger_prop in ('motion','presence','occupancy') and trigger_value else ''}"
                   f"时 → {'打开' if action_cmd == 'on' else '关闭'}{a_name}，每{interval}秒检查")
        return True, summary, scene_id

    def stop_scene(self, scene_id_or_device: str = "") -> tuple[bool, str]:
        """Stop (pause) a scene: thread stops but scene config is kept for later resume."""
        with self._lock:
            if not scene_id_or_device:
                count = 0
                for sid in list(self._scene_workers):
                    self._scene_workers[sid][1].set()
                    if sid in self._scenes:
                        self._scenes[sid]["active"] = False
                        self._scenes[sid]["triggered"] = False
                        self._scenes[sid].pop("triggered_at", None)
                    count += 1
                self._scene_workers.clear()
                self._save_scenes()
                return True, f"已关闭全部{count}个场景"
            # Match by scene_id or device name
            stopped = []
            for sid in list(self._scene_workers):
                scene = self._scenes.get(sid, {})
                if sid == scene_id_or_device or scene.get("trigger_device") == scene_id_or_device or scene.get("action_device") == scene_id_or_device:
                    self._scene_workers[sid][1].set()
                    scene["active"] = False
                    scene["triggered"] = False
                    scene.pop("triggered_at", None)
                    stopped.append(scene.get("trigger_device", sid))
                    del self._scene_workers[sid]
            self._save_scenes()
            if stopped:
                return True, f"已关闭场景：{', '.join(stopped)}"
            return True, "没有找到匹配的运行中场景"

    def resume_scene(self, scene_id_or_device: str = "") -> tuple[bool, str]:
        """Resume a previously stopped (but not deleted) scene."""
        with self._lock:
            resumed = []
            for sid, scene in self._scenes.items():
                if scene.get("active"):
                    continue  # already running
                if scene.get("triggered"):
                    continue  # one-shot already triggered
                if scene_id_or_device and sid != scene_id_or_device and scene.get("trigger_device") != scene_id_or_device and scene.get("action_device") != scene_id_or_device:
                    continue
                scene["active"] = True
                if sid not in self._scene_workers:
                    stop = threading.Event()
                    t = threading.Thread(target=self._run_scene,
                        args=(sid, scene, stop),
                        name=f"xiaomi-scene-{sid}", daemon=True)
                    self._scene_workers[sid] = (t, stop)
                    t.start()
                resumed.append(scene.get("trigger_device", sid))
            self._save_scenes()
            if resumed:
                return True, f"已恢复场景：{', '.join(resumed)}"
            return False, "没有找到已关闭的场景可恢复"

    def delete_scene(self, scene_id_or_device: str = "") -> tuple[bool, str]:
        """Permanently delete a scene."""
        with self._lock:
            if not scene_id_or_device:
                count = len(self._scenes)
                for sid in list(self._scene_workers):
                    self._scene_workers[sid][1].set()
                self._scene_workers.clear()
                self._scenes.clear()
                self._save_scenes()
                return True, f"已删除全部{count}个场景"
            deleted = []
            for sid in list(self._scenes):
                scene = self._scenes[sid]
                if sid == scene_id_or_device or scene.get("trigger_device") == scene_id_or_device or scene.get("action_device") == scene_id_or_device:
                    if sid in self._scene_workers:
                        self._scene_workers[sid][1].set()
                        del self._scene_workers[sid]
                    deleted.append(scene.get("trigger_device", sid))
                    del self._scenes[sid]
            self._save_scenes()
            if deleted:
                return True, f"已删除场景：{', '.join(deleted)}"
            return False, "没有找到匹配的场景"

    def scene_status(self) -> list[dict[str, Any]]:
        """List ALL scenes (including stopped ones), not just active."""
        with self._lock:
            return list(self._scenes.values())

    def resume_scenes(self) -> None:
        """Resume active scenes after service restart."""
        with self._lock:
            for sid, scene in self._scenes.items():
                if not scene.get("active") or scene.get("triggered"):
                    continue
                if sid in self._scene_workers:
                    continue
                stop = threading.Event()
                t = threading.Thread(target=self._run_scene,
                    args=(sid, scene, stop),
                    name=f"xiaomi-scene-{sid}", daemon=True)
                self._scene_workers[sid] = (t, stop)
                t.start()
                print(f"[XIAOQ-IOT] resumed scene: {scene.get('trigger_device')} → {scene.get('action_device')}")

    def _run_scene(self, scene_id: str, scene: dict, stop: threading.Event) -> None:
        did = scene["trigger_did"]
        siid = scene["trigger_siid"]
        piid = scene["trigger_piid"]
        interval = scene.get("interval_seconds", 3)
        one_shot = scene.get("one_shot", True)
        action_device = scene["action_device"]
        action_cmd = scene["action_command"]
        spoken = scene["spoken"]
        t_name = scene["trigger_device"]

        last_value = None
        first_poll = True
        next_check = time.monotonic()
        while not stop.is_set():
            delay = next_check - time.monotonic()
            if delay > 0 and stop.wait(delay):
                return
            value = self.get_property(did, siid, piid)
            now = time.monotonic()
            print(f"[XIAOQ-IOT] scene poll: {t_name} value={value} last={last_value} first={first_poll}")
            if value is not None:
                if first_poll:
                    # Record initial state without triggering
                    last_value = value
                    first_poll = False
                elif value != last_value:
                    # Value changed — trigger in both directions
                    if value > last_value:
                        # Increase: someone appeared / door opened → turn ON
                        cmd = action_cmd
                        a_name = scene["action_device"]
                        t_name = scene["trigger_device"]
                        alert_text = spoken
                    else:
                        # Decrease: someone left / door closed → turn OFF
                        cmd = "off" if action_cmd == "on" else "on"
                        a_name = scene["action_device"]
                        t_name = scene["trigger_device"]
                        prop = scene.get("trigger_property", "")
                        if prop in ("motion", "presence", "occupancy"):
                            alert_text = f"{t_name}已无人，已自动关闭{a_name}"
                        elif prop == "contact":
                            alert_text = f"{t_name}已关门，已自动关闭{a_name}"
                        else:
                            alert_text = f"{t_name}状态变化，已关闭{a_name}"
                    result = self.control_device(action_device, cmd)
                    ok = result.get("ok", False)
                    state = {
                        "scene_id": scene_id,
                        "trigger_device": t_name,
                        "old_value": last_value,
                        "new_value": value,
                        "action_device": action_device,
                        "action_result": ok,
                        "changed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    }
                    if not ok:
                        alert_text = f"场景触发但{action_device}控制失败"
                    if self._alert_callback:
                        self._alert_callback(alert_text, state)
                    print(f"[XIAOQ-IOT] scene {scene_id} triggered: {t_name} {last_value}→{value} → {action_device} {cmd} ok={ok}")
                    last_value = value
                    if one_shot:
                        with self._lock:
                            scene["triggered"] = True
                            scene["active"] = False
                            scene["triggered_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                            self._save_scenes()
                        return
            next_check = now + max(3, interval)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
def get_xiaomi_iot_service() -> XiaomiIoTService:
    global _service
    with _service_lock:
        if _service is None:
            _service = XiaomiIoTService()
        return _service


# ---------------------------------------------------------------------------
# Skill
# ---------------------------------------------------------------------------
class XiaomiIoTSkill(Skill):
    name = "xiaomi_iot"
    description = "控制小米智能家居设备（浴霸、插座、传感器等）并查询设备状态"

    def __init__(self, service: XiaomiIoTService):
        super().__init__()
        self.service = service

    def execute(self, params: dict = None) -> SkillResult:
        params = params or {}
        action = str(params.get("action", "list")).lower()

        if action == "list":
            return self._list_devices()
        if action == "control":
            return self._control(params)
        if action == "query":
            return self._query(params)
        if action == "monitor":
            return self._monitor(params)
        if action == "scene":
            return self._scene(params)
        if action == "reload":
            devices = self.service.reload_devices()
            return SkillResult(success=True, data={"count": len(devices)},
                side_effects=[SideEffect("voice_tts",
                    {"text": f"已刷新设备列表，共{len(devices)}台设备"})])
        return SkillResult(success=False, error=f"unknown action: {action}")

    def _list_devices(self) -> SkillResult:
        devices = self.service.devices()
        online = [d for d in devices if d.get("isOnline")]
        lines = []
        for d in devices:
            status = "在线" if d.get("isOnline") else "离线"
            lines.append(f"{d.get('name','?')}（{status}）")
        text = (f"共{len(devices)}台设备，{len(online)}台在线。"
                if devices else "没有找到小米设备。")
        return SkillResult(success=True, data={"count": len(devices)},
            side_effects=[
                SideEffect("card_show", {"title": "小米设备", "lines": lines[:12], "card_type": "todo"}),
                SideEffect("voice_tts", {"text": text}),
            ])

    def _control(self, params: dict) -> SkillResult:
        device_name = str(params.get("device", "")).strip()
        action = str(params.get("command", params.get("value", ""))).strip()
        if not device_name:
            return SkillResult(success=True,
                side_effects=[SideEffect("voice_tts", {"text": "请告诉我要控制哪个设备"})])
        result = self.service.control_device(device_name, action)
        return SkillResult(
            success=result.get("ok", False),
            data=result,
            error=result.get("error", ""),
            side_effects=[
                SideEffect("card_show", {"title": "设备控制", "lines": [result.get("spoken", "")], "card_type": "todo"}),
                SideEffect("voice_tts", {"text": result.get("spoken", "控制失败")}),
            ])

    def _query(self, params: dict) -> SkillResult:
        device_name = str(params.get("device", "")).strip()
        prop_name = str(params.get("property", "")).strip()
        if not device_name:
            return SkillResult(success=True,
                side_effects=[SideEffect("voice_tts", {"text": "请告诉我要查询哪个设备"})])
        result = self.service.query_device(device_name, prop_name)
        lines = [result.get("spoken", "查询失败")]
        if result.get("properties"):
            for k, v in result["properties"].items():
                lines.append(f"{k}：{v}")
        return SkillResult(
            success=result.get("ok", False),
            data=result,
            error=result.get("error", ""),
            side_effects=[
                SideEffect("card_show", {"title": "设备状态", "lines": lines, "card_type": "todo"}),
                SideEffect("voice_tts", {"text": result.get("spoken", "查询失败")}),
            ])

    def _monitor(self, params: dict) -> SkillResult:
        sub = str(params.get("sub_action", "start")).lower()
        if sub == "stop":
            ok, text = self.service.stop_monitor(str(params.get("device", "")))
        elif sub == "status":
            tasks = self.service.monitor_status()
            text = f"当前有{len(tasks)}个监控任务在运行" if tasks else "没有运行中的监控任务"
            return SkillResult(success=True, data={"tasks": tasks},
                side_effects=[SideEffect("voice_tts", {"text": text})])
        else:
            device_name = str(params.get("device", "")).strip()
            interval = int(params.get("interval_seconds", 5))
            prop = str(params.get("property", "")).strip()
            ok, text = self.service.start_monitor(device_name, prop, interval)
        return SkillResult(success=ok, data={},
            side_effects=[
                SideEffect("card_show", {"title": "设备监控", "lines": [text], "card_type": "todo"}),
                SideEffect("voice_tts", {"text": text}),
            ])

    def _scene(self, params: dict) -> SkillResult:
        sub = str(params.get("sub_action", "start")).lower()
        if sub == "stop":
            target = str(params.get("scene_id", params.get("device", ""))).strip()
            ok, text = self.service.stop_scene(target)
        elif sub == "resume":
            target = str(params.get("scene_id", params.get("device", ""))).strip()
            ok, text = self.service.resume_scene(target)
        elif sub == "delete":
            target = str(params.get("scene_id", params.get("device", ""))).strip()
            ok, text = self.service.delete_scene(target)
        elif sub == "status":
            scenes = self.service.scene_status()
            if not scenes:
                text = "没有任何场景"
                lines = ["暂无场景"]
            else:
                lines = []
                for s in scenes:
                    if s.get("triggered"):
                        status = "已触发"
                    elif s.get("active"):
                        status = "运行中"
                    else:
                        status = "已关闭"
                    lines.append(f"{s.get('trigger_device','?')} → {s.get('action_device','?')}（{status}）")
                text = f"共有{len(scenes)}个场景，其中{sum(1 for s in scenes if s.get('active'))}个运行中"
            return SkillResult(success=True, data={"scenes": scenes},
                side_effects=[
                    SideEffect("card_show", {"title": "场景列表", "lines": lines, "card_type": "todo"}),
                    SideEffect("voice_tts", {"text": text}),
                ])
        else:
            ok, text, scene_id = self.service.start_scene(params)
            if not ok:
                return SkillResult(success=False, error=text,
                    side_effects=[SideEffect("voice_tts", {"text": text})])
        return SkillResult(success=ok, data={},
            side_effects=[
                SideEffect("card_show", {"title": "场景管理", "lines": [text], "card_type": "todo"}),
                SideEffect("voice_tts", {"text": text}),
            ])
