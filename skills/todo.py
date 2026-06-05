"""
skills/todo.py — 待办清单技能 (本地待办+灵畿任务+提醒)

数据源：
  1. 本地JSON: data/todos.json — 语音添加的待办（支持提醒时间）
  2. 灵畿任务: 实时 lc req list

语音操作:
  - "待办" / "任务" → 列出所有待办
  - "添加待办:xxx" → 添加待办
  - "添加待办 下午3点开会" → 添加带提醒的待办
  - "完成第一个" / "第二个已完成" → 标记完成
"""

import json
import logging
import re
import subprocess
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta, timezone
from skills.base import Skill, SkillResult, SideEffect

log = logging.getLogger("skills.todo")
SHANGHAI = timezone(timedelta(hours=8))

# ── 时间解析 ──

def parse_remind_time(text: str) -> tuple:
    """从 ASR 文本解析提醒时间，返回 (remind_at_iso, remind_text)"""
    now = datetime.now(SHANGHAI)
    text = text.strip()

    CN_NUM = {"零":0,"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
    def _to_num(s):
        s = s.strip()
        if s.isdigit(): return int(s)
        return CN_NUM.get(s, 0)

    # 相对时间
    m = re.search(r'([0-9一二三四五六七八九十]+)\s*分[钟]?\s*后', text)
    if m:
        n = _to_num(m.group(1))
        dt = now + timedelta(minutes=n)
        return (dt.isoformat(), f"{n}分钟后")

    m = re.search(r'半\s*小\s*时\s*后', text)
    if m:
        dt = now + timedelta(minutes=30)
        return (dt.isoformat(), "半小时后")

    m = re.search(r'一?\s*小\s*时\s*后', text)
    if m:
        dt = now + timedelta(hours=1)
        return (dt.isoformat(), "1小时后")

    m = re.search(r'([0-9一二三四五六七八九十]+)\s*小\s*时\s*后', text)
    if m:
        n = _to_num(m.group(1))
        dt = now + timedelta(hours=n)
        return (dt.isoformat(), f"{n}小时后")

    # 绝对时间
    is_tomorrow = "明天" in text or "次日" in text
    base_date = now + timedelta(days=1) if is_tomorrow else now

    # "下午3点" / "三点" / "九点过五分" / "两点半"
    m = re.search(r'(下午|晚上|上午|早上|早晨)?\s*([0-9一二三四五六七八九十]+)\s*点\s*(过\s*[0-9一二三四五六七八九十]+|半|[0-9一二三四五六七八九十]+)?\s*分?', text)
    if m:
        period = m.group(1) or ""
        hour = _to_num(m.group(2))
        minute_raw = m.group(3) or ""

        minute = 0
        if minute_raw == "半":
            minute = 30
        elif minute_raw.startswith("过"):
            minute = _to_num(minute_raw[1:].strip())
        elif minute_raw:
            minute = _to_num(minute_raw.strip())

        if period in ("下午", "晚上") and hour < 12:
            hour += 12
        if period in ("上午", "早上", "早晨") and hour == 12:
            hour = 0

        remind_time = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if remind_time <= now and not is_tomorrow:
            remind_time += timedelta(days=1)
        text_friendly = remind_time.strftime("%H:%M")
        return (remind_time.isoformat(), text_friendly)

    # "15:00" / "15:30" 格式
    m = re.search(r'(\d{1,2}):(\d{2})', text)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        remind_time = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if remind_time <= now and not is_tomorrow:
            remind_time += timedelta(days=1)
        return (remind_time.isoformat(), remind_time.strftime("%H:%M"))

    return (None, None)


# ── TodoSkill ──

class TodoSkill(Skill):
    """待办清单技能: 本地待办 + 灵畿任务 + 提醒"""

    name = "todo"
    description = "待办清单"

    def __init__(self, cfg: dict = None):
        super().__init__(cfg)
        cfg = cfg or {}
        self.lingji_workspace = cfg.get("lingji_workspace", "CMIOTonemoredcap")
        self.data_dir = Path(__file__).parent.parent / "data"
        self.todos_file = self.data_dir / "todos.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._load()
        self._last_items = []

    # ── JSON 持久化 ──

    def _load(self):
        if self.todos_file.exists():
            try:
                with open(self.todos_file) as f:
                    self.todos = json.load(f)
            except Exception:
                self.todos = []
        else:
            self.todos = []

    def _save(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with open(self.todos_file, "w", encoding="utf-8") as f:
            json.dump(self.todos, f, ensure_ascii=False, indent=2)

    def add(self, title: str, remind_at: str = None, remind_text: str = None) -> dict:
        entry = {
            "id": int(time.time() * 1000),
            "title": title,
            "done": False,
            "created_at": datetime.now(SHANGHAI).isoformat(),
            "type": "manual",
        }
        if remind_at:
            entry["remind_at"] = remind_at
            entry["remind_text"] = remind_text or remind_at
            entry["notified"] = False
        self.todos.append(entry)
        self._save()
        return entry

    def mark_done(self, todo_id: int):
        for t in self.todos:
            if t["id"] == todo_id and not t["done"]:
                t["done"] = True
                t["remind_at"] = None
                t["notified"] = True
                self._save()
                return True
        return False

    def get_due_reminders(self) -> list:
        self._load()
        now = datetime.now(SHANGHAI)
        due = []
        for t in self.todos:
            if t.get("done") or t.get("notified"):
                continue
            ra = t.get("remind_at")
            if ra:
                try:
                    dt = datetime.fromisoformat(ra)
                    if dt <= now:
                        due.append(t)
                except Exception:
                    pass
        return due

    def mark_notified(self, todo_id: int):
        for t in self.todos:
            if t["id"] == todo_id:
                t["notified"] = True
                self._save()
                break

    # ── 主逻辑 ──

    def _list_all(self, asr_text: str = "") -> SkillResult:
        self._load()
        all_items = []
        self._last_items = []

        # 1. 本地手工待办
        for t in self.todos:
            if not t.get("done"):
                remind = ""
                if t.get("remind_at"):
                    try:
                        rt = datetime.fromisoformat(t["remind_at"])
                        remind = f" ⏰{rt.strftime('%H:%M')}"
                    except Exception:
                        remind = f" ⏰{t.get('remind_text','?')}"
                all_items.append({
                    "type": "manual", "title": t["title"],
                    "status": f"待办{remind}", "source": "本地",
                    "id": t["id"], "sort_key": 0,
                })

        # 2. 灵畿任务 (实时查询)
        try:
            r = subprocess.run(
                ["lc", "req", "list", "-w", self.lingji_workspace, "-l", "30"],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0 and r.stdout.strip():
                data = json.loads(r.stdout)
                items = data.get("data", {}).get("items") or []
                for t in items:
                    if t.get("assignee") != "傅强":
                        continue
                    if t.get("status") not in ("已完成", "已关闭", "取消"):
                        all_items.append({
                            "type": "lingji", "title": t.get("name", "?"),
                            "status": f"[灵畿]{t.get('status','?')}",
                            "source": "灵畿", "sort_key": 1,
                        })
        except Exception as e:
            log.warning(f"Lingji fetch error: {e}")

        # 3. 排序：本地待办在前，灵畿在后
        all_items.sort(key=lambda x: (x["sort_key"], x["title"]))

        self._last_items = all_items[:]

        if not all_items:
            return SkillResult(success=True, data={"count": 0},
                side_effects=[
                    SideEffect("card_show", {"title": "待办清单", "lines": ["(没有待办事项)"], "card_type": "todo"}),
                    SideEffect("voice_tts", {"text": "没有待办事项"}),
                ])

        manual_count = sum(1 for x in all_items if x["type"] == "manual")
        lingji_count = len(all_items) - manual_count

        lines = []
        for i, item in enumerate(all_items, 1):
            title = item["title"]
            status = item["status"]
            lines.append(f"{i}. [ ] {title} ({status})")

        tts_parts = []
        if manual_count:
            tts_parts.append(f"{manual_count}个本地待办")
        if lingji_count:
            tts_parts.append(f"{lingji_count}个灵畿任务")
        tts = f"你有{'，'.join(tts_parts)}" if tts_parts else "没有待办"

        return SkillResult(success=True, data={"items": all_items},
            side_effects=[
                SideEffect("card_show", {
                    "title": f"待办清单 ({len(all_items)}项)",
                    "lines": lines,
                    "card_type": "todo",
                }),
                SideEffect("voice_tts", {"text": tts}),
            ])

    def execute(self, params: dict = None) -> SkillResult:
        params = params or {}
        action = params.get("action", "list")
        asr_text = params.get("_asr_text", "")

        # 标记完成
        if action == "mark_done" or "完成" in asr_text:
            idx = 0
            if asr_text:
                m = re.search(r'第([一二三四五六七八九十0-9]+)[个项条]', asr_text)
                if m:
                    cn = m.group(1)
                    cn_map = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
                    idx = cn_map.get(cn, int(cn) if cn.isdigit() else 0)
            if idx > 0 and self._last_items and idx <= len(self._last_items):
                item = self._last_items[idx - 1]
                if item["type"] == "manual":
                    self.mark_done(item["id"])
                    return SkillResult(success=True,
                        side_effects=[SideEffect("voice_tts", {"text": f"已完成第{idx}项: {item['title'][:20]}"})])
                elif item["type"] == "lingji":
                    return SkillResult(success=True,
                        side_effects=[SideEffect("voice_tts", {"text": "灵畿任务请登录平台处理"})])
            elif idx > 0:
                pass  # fall through to list

        # 添加待办
        if "添加" in asr_text or "新增" in asr_text:
            title = re.sub(r'添加|新增|创建|待办|事项|一个|一条', '', asr_text).strip()
            if title:
                remind_at, remind_text = parse_remind_time(asr_text)
                entry = self.add(title, remind_at=remind_at, remind_text=remind_text)
                reply = f"已添加待办：{title}"
                if remind_at and remind_text:
                    reply += f"，将在{remind_text}提醒您"
                return SkillResult(success=True,
                    side_effects=[SideEffect("voice_tts", {"text": reply})])

        # 默认：列出所有待办
        return self._list_all(asr_text=asr_text)


# ── 提醒后台线程 ──

class ReminderWatcher:
    def __init__(self, skill_ref, notify_callback, interval: float = 30.0):
        self._skill = skill_ref
        self._callback = notify_callback
        self._interval = interval
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="reminder-watcher")
        self._thread.start()
        log.info("ReminderWatcher started")

    def _run(self):
        while not self._stop.is_set():
            try:
                due = self._skill.get_due_reminders()
                for item in due:
                    tts = f"提醒您：{item.get('title', '待办事项')}"
                    self._callback(tts)
                    self._skill.mark_notified(item["id"])
            except Exception as e:
                log.warning(f"[Reminder] Error: {e}")
            self._stop.wait(self._interval)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
