"""每日下班总结提醒：到点播报今日待办和明日安排。"""

import json
import logging
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .base import SideEffect, Skill, SkillResult

log = logging.getLogger("skills.off_work")
SHANGHAI = timezone(timedelta(hours=8))
_service = None
_service_lock = threading.Lock()


def _cn_number(value):
    value = str(value or "").strip()
    if value.isdigit():
        return int(value)
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if value == "十":
        return 10
    if value.startswith("十"):
        return 10 + digits.get(value[1:], 0)
    if value.endswith("十") and len(value) == 2:
        return digits.get(value[0], 0) * 10
    if "十" in value:
        left, right = value.split("十", 1)
        return (digits.get(left, 1) * 10) + digits.get(right, 0)
    return digits.get(value)


def parse_off_work_time(text):
    """Parse a daily clock time, defaulting bare small hours to afternoon."""
    text = str(text or "")
    clock = re.search(r"(?<!\d)(\d{1,2})\s*:\s*(\d{2})(?!\d)", text)
    if clock:
        hour, minute = int(clock.group(1)), int(clock.group(2))
    else:
        match = re.search(
            r"(下午|晚上|傍晚|上午|早上|早晨|中午)?\s*"
            r"([0-9一二两三四五六七八九十〇零]{1,3})\s*点"
            r"(?:\s*(?:过|加)?\s*(半|[0-9一二两三四五六七八九十〇零]{1,3})\s*分?)?",
            text,
        )
        if not match:
            return None
        hour = _cn_number(match.group(2))
        minute = 30 if match.group(3) == "半" else (_cn_number(match.group(3)) if match.group(3) else 0)
        if hour is None or minute is None or hour > 23 or minute > 59:
            return None
        period = match.group(1) or ""
        if period in ("下午", "晚上", "傍晚") and hour < 12:
            hour += 12
        elif period in ("上午", "早上", "早晨") and hour == 12:
            hour = 0
        elif not period and hour < 12:
            # “下班六点” is conventionally 18:00.
            hour += 12
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _parse_iso(value):
    try:
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=SHANGHAI)
        return parsed.astimezone(SHANGHAI)
    except (TypeError, ValueError):
        return None


def _item_text(item):
    return str(item.get("text") or item.get("title") or "待办事项").strip()


def summarize_todos(now=None):
    """Return concise spoken/card data for today and tomorrow."""
    now = now or datetime.now(SHANGHAI)
    today = now.date()
    tomorrow = today + timedelta(days=1)
    path = Path(__file__).parent.parent / "data" / "todos.json"
    try:
        items = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except (OSError, ValueError, TypeError):
        items = []
    if not isinstance(items, list):
        items = []

    completed_today = []
    pending_today = []
    tomorrow_items = []
    undated_pending = []
    for item in items:
        if not isinstance(item, dict) or item.get("deleted"):
            continue
        text = _item_text(item)
        created = _parse_iso(item.get("created_at"))
        reminded = _parse_iso(item.get("remind_at"))
        completed = _parse_iso(item.get("completed_at") or item.get("done_at") or item.get("finished_at"))
        planned_date = str(item.get("plan_date") or item.get("scheduled_date") or "").strip()
        relevant_today = bool(
            (created and created.date() == today)
            or (reminded and reminded.date() == today)
            or (completed and completed.date() == today)
            or planned_date == today.isoformat()
        )
        if item.get("done"):
            # Legacy entries without a completion timestamp are only counted
            # when they were created or due today, never as historical work.
            if completed and completed.date() == today or (not completed and relevant_today):
                completed_today.append(text)
            continue
        if relevant_today:
            pending_today.append(text)
        if (reminded and reminded.date() == tomorrow) or planned_date == tomorrow.isoformat():
            tomorrow_items.append(text)
        elif not reminded:
            undated_pending.append(text)

    # Undated active items are useful for confirming tomorrow's plan, but keep
    # the spoken summary bounded and distinguish them from date-bound items.
    tomorrow_lines = tomorrow_items[:6]
    if undated_pending:
        tomorrow_lines.extend(f"待确认：{text}" for text in undated_pending[: max(0, 6 - len(tomorrow_lines))])

    if completed_today:
        today_text = f"今天完成了{len(completed_today)}项：" + "、".join(completed_today[:5])
    else:
        today_text = "今天还没有完成的待办记录"
    if pending_today:
        today_text += f"；还有{len(pending_today)}项未完成：" + "、".join(pending_today[:5])
    else:
        today_text += "；今天没有未完成的待办"
    if tomorrow_lines:
        tomorrow_text = "明日安排有：" + "、".join(tomorrow_lines)
    else:
        tomorrow_text = "明日暂时没有明确安排的待办"
    spoken = f"下班时间到了。{today_text}。{tomorrow_text}。今天辛苦了，工作到这里，明天继续加油。"
    card_lines = [
        f"今日完成：{len(completed_today)}项",
        f"今日未完成：{len(pending_today)}项",
        "明日待办：" + ("、".join(tomorrow_lines[:5]) if tomorrow_lines else "暂无明确安排"),
    ]
    return {"spoken": spoken, "card_lines": card_lines, "completed_today": completed_today,
            "pending_today": pending_today, "tomorrow_items": tomorrow_lines}


class OffWorkReminderService:
    def __init__(self):
        self.state_path = Path("data/off_work_reminder.json")
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._callback = None

    def _load(self):
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            value = {}
        return value if isinstance(value, dict) else {}

    def _save(self, state):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.state_path)

    def set_callback(self, callback):
        self._callback = callback

    def configure(self, clock_time):
        now = datetime.now(SHANGHAI)
        hour, minute = (int(part) for part in clock_time.split(":", 1))
        next_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_at <= now:
            next_at += timedelta(days=1)
        state = {
            "enabled": True, "time": clock_time, "next_at": next_at.isoformat(),
            "last_fired_date": "", "updated_at": now.isoformat(),
        }
        with self._lock:
            self._save(state)
            self._ensure_thread()
        return f"已设置每天{clock_time}下班提醒。到点我会总结今天的待办，并确认明日安排。", state

    def stop(self):
        with self._lock:
            state = self._load()
            state.update({"enabled": False, "updated_at": datetime.now(SHANGHAI).isoformat()})
            self._save(state)
        return "已关闭下班提醒。", state

    def status(self):
        state = self._load()
        if state.get("enabled") and state.get("time"):
            return f"下班提醒已开启，每天{state['time']}播报。", state
        return "下班提醒目前未开启。", state

    def resume(self):
        with self._lock:
            if self._load().get("enabled"):
                self._ensure_thread()

    def _ensure_thread(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="off-work-reminder", daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            fired = self.check_once()
            if fired:
                self._stop.wait(15)
            else:
                self._stop.wait(10)

    def check_once(self, now=None):
        now = now or datetime.now(SHANGHAI)
        with self._lock:
            state = self._load()
            if not state.get("enabled") or not state.get("time"):
                return False
            scheduled = _parse_iso(state.get("next_at"))
            if scheduled and now < scheduled:
                return False
            if state.get("last_fired_date") == now.date().isoformat():
                return False
            summary = summarize_todos(now)
            state.update({
                "last_fired_date": now.date().isoformat(),
                "next_at": (now + timedelta(days=1)).replace(
                    hour=int(state["time"][:2]), minute=int(state["time"][3:]),
                    second=0, microsecond=0,
                ).isoformat(),
                "last_summary": summary,
            })
            self._save(state)
        if self._callback:
            try:
                self._callback(summary["spoken"], summary)
            except Exception as error:
                log.warning("off-work reminder callback failed: %s", error)
        return True


def get_off_work_service():
    global _service
    with _service_lock:
        if _service is None:
            _service = OffWorkReminderService()
        return _service


class OffWorkSkill(Skill):
    name = "off_work"
    description = "设置每日下班提醒，播报今日待办完成情况并确认明日待办"

    def __init__(self, cfg=None):
        super().__init__(cfg)
        self.service = get_off_work_service()

    def execute(self, params=None):
        params = params or {}
        action = str(params.get("action", "set")).lower()
        if action in {"stop", "disable"}:
            reply, state = self.service.stop()
            return SkillResult(success=True, data=state, side_effects=[SideEffect("voice_tts", {"text": reply})])
        if action in {"status", "query"}:
            reply, state = self.service.status()
            return SkillResult(success=True, data=state, side_effects=[SideEffect("voice_tts", {"text": reply})])

        asr_text = str(params.get("_asr_text", ""))
        clock_time = parse_off_work_time(params.get("time") or asr_text)
        if not clock_time:
            reply = "请告诉我下班提醒时间，例如每天晚上六点或18点。"
            return SkillResult(success=True, data={}, side_effects=[SideEffect("voice_tts", {"text": reply})])
        reply, state = self.service.configure(clock_time)
        return SkillResult(success=True, data=state, side_effects=[SideEffect("voice_tts", {"text": reply})])
