"""待办_Hermes技能 - 本地待办添加/完成 + 灵畿任务查询 + 时间提醒"""
import json
import logging
import re
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from hermes_skills.base import HermesSkill

log = logging.getLogger("hermes_skills.todo")

SHANGHAI = timezone(timedelta(hours=8))
LC_WORKSPACE = "CMIOTonemoredcap"
TODOS_FILE = Path.home() / ".hermes" / "skills" / "todo" / "data" / "todos.json"

# ── 数字中文转阿拉伯 ──
CN_NUM = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10,
          "两":2,"半":30,"零":0}
def _to_num(s):
    s = s.strip()
    if not s: return 0
    if s.isdigit(): return int(s)
    return CN_NUM.get(s, 0)


# ── 时间解析 ──
def parse_remind_time(text: str) -> tuple:
    """从文本解析提醒时间，返回 (remind_at_iso, remind_text)"""
    now = datetime.now(SHANGHAI)

    # X分钟后
    m = re.search(r"(\d+|[一二两三四五六七八九十半])\s*分(钟)?(后|钟)?", text)
    if m:
        n = _to_num(m.group(1))
        if n <= 0: n = 1
        dt = now + timedelta(minutes=n)
        return (dt.isoformat(), f"{n}分钟后")

    # 半小时后
    if "半小时" in text or "30分" in text:
        dt = now + timedelta(minutes=30)
        return (dt.isoformat(), "30分钟后")

    # 一小时后
    m = re.search(r"(\d+|[一二两三四五六七八九十])\s*小[时]", text)
    if m:
        n = _to_num(m.group(1))
        dt = now + timedelta(hours=n)
        return (dt.isoformat(), f"{n}小时后")

    # X点Y分 / X点过Y / X点半
    m = re.search(r"(明天|今天|晚上)?\s*(\d+|[一二两三四五六七八九十]+)\s*点(?:(\d+|[半]|过\s*\d+|[一二两三四五六七八九十]+))?", text)
    if m:
        is_tomorrow = "明天" in (m.group(1) or "")
        base_date = now + timedelta(days=1) if is_tomorrow else now
        hour = _to_num(m.group(2))
        min_part = m.group(3) or ""
        minute = 0
        if min_part == "半":
            minute = 30
        elif min_part.startswith("过"):
            minute = _to_num(min_part[1:].strip())
        elif min_part:
            minute = _to_num(min_part.strip())
        remind_time = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if remind_time <= now and not is_tomorrow:
            remind_time += timedelta(days=1)
        text_friendly = remind_time.strftime("%H:%M")
        return (remind_time.isoformat(), text_friendly)

    return ("", "")


# ── 本地待办存储 ──
def _load_todos():
    if TODOS_FILE.exists():
        try:
            with open(TODOS_FILE) as f:
                return json.load(f)
        except: pass
    return []

def _save_todos(todos):
    TODOS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TODOS_FILE, "w") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)

def _get_active_todos():
    return [t for t in _load_todos() if not t.get("done")]


# ── 提醒监视器 ──
_reminder_watcher = None
_reminder_callback = None

def set_reminder_callback(cb):
    global _reminder_callback
    _reminder_callback = cb

def start_reminder_watcher():
    global _reminder_watcher
    if _reminder_watcher:
        return
    def _run():
        while True:
            try:
                todos = _load_todos()
                now = datetime.now(SHANGHAI).isoformat()
                due = [t for t in todos if not t.get("done") and not t.get("notified")
                       and t.get("remind_at") and t.get("remind_at") <= now]
                for item in due:
                    text = f"提醒您：{item.get('text', '待办事项')}"
                    log.info(f"[Reminder] Due: {text}")
                    if _reminder_callback:
                        _reminder_callback(text)
                    item["notified"] = True
                    _save_todos(todos)
            except Exception as e:
                log.warning(f"[Reminder] Error: {e}")
            time.sleep(30)
    _reminder_watcher = threading.Thread(target=_run, daemon=True, name="reminder-watcher")
    _reminder_watcher.start()
    log.info("[Reminder] Watcher started")


class TodoHermesSkill(HermesSkill):
    name = "todo"
    description = "待办事项：查任务、添加待办、标记完成、设置提醒"

    def prepare(self, text: str) -> dict:
        # 检测添加待办
        add_match = re.search(r"添加[一个条]?待办[：:]?\s*(.*)", text)
        if add_match:
            todo_text = add_match.group(1).strip()
            if not todo_text:
                # 直接"添加待办"后面没有文字
                return {"context": "", "action": None, "skip_llm": True,
                        "reply": "你想添加什么待办内容？"}
            
            remind_at, remind_text = parse_remind_time(todo_text)
            # 从待办文本中去掉时间部分
            clean_text = re.sub(r"\d+分钟[后钟]|半小时|30分钟|\d+小[时]|明天|今天.*点.*|晚上.*点.*", "", todo_text).strip()
            if not clean_text:
                clean_text = todo_text
            
            new_todo = {
                "id": str(int(time.time() * 1000)),
                "text": clean_text,
                "done": False,
                "notified": False,
            }
            if remind_at:
                new_todo["remind_at"] = remind_at
                new_todo["remind_text"] = remind_text
            
            todos = _load_todos()
            todos.append(new_todo)
            _save_todos(todos)
            
            if remind_at:
                reply = f"已添加待办：{clean_text}，{remind_text}提醒你"
            else:
                reply = f"已添加待办：{clean_text}"
            return {"context": "", "action": None, "skip_llm": True, "reply": reply}

        # 标记完成
        m = re.search(r"完成第(\d+)", text)
        if m:
            idx = int(m.group(1))
            active = _get_active_todos()
            if 1 <= idx <= len(active):
                done = active[idx-1]
                done["done"] = True
                todos = _load_todos()
                for t in todos:
                    if t.get("id") == done.get("id"):
                        t["done"] = True
                _save_todos(todos)
                return {"context": "", "action": None, "skip_llm": True,
                        "reply": f"已完成：{done.get('text', '')}"}
            else:
                return {"context": "", "action": None, "skip_llm": True,
                        "reply": f"没有第{idx}项待办，请先查一下你的待办列表"}

        # 查询待办：返回上下文数据
        context_parts = []
        active = _get_active_todos()
        if active:
            context_parts.append(f"【本地待办（{len(active)}项）】")
            for i, t in enumerate(active, 1):
                remind = f" ⏰{t.get('remind_text','')}" if t.get("remind_at") else ""
                context_parts.append(f"  {i}. {t.get('text','')}{remind}")
        else:
            context_parts.append("【本地待办】无")

        # 灵畿任务
        try:
            r = subprocess.run(["lc","req","list","-w",LC_WORKSPACE], capture_output=True, text=True, timeout=15)
            data = json.loads(r.stdout)
            items = data.get("data",{}).get("items") or []
            my_tasks = [t for t in items if "傅强" in (t.get("assignee") or "")]
            if my_tasks:
                context_parts.append(f"\n【灵畿任务（{len(my_tasks)}项）】")
                for t in my_tasks[:15]:
                    kw = t.get("key","")
                    name = t.get("name","")
                    status = t.get("status","")
                    context_parts.append(f"  [{kw}] {name} ({status})")
        except Exception as e:
            context_parts.append(f"\n【灵畿任务】获取失败: {e}")

        # 灵畿缺陷概览
        try:
            r = subprocess.run(["lc","bug","list","-w",LC_WORKSPACE], capture_output=True, text=True, timeout=15)
            data = json.loads(r.stdout)
            items = data.get("data",{}).get("items") or []
            open_bugs = [b for b in items if b.get("status") not in ("已关闭",)]
            my_bugs = [b for b in open_bugs if "傅强" in (b.get("handlerName") or "")]
            context_parts.append(f"\n【灵畿缺陷】共{len(open_bugs)}个未关闭（你{len(my_bugs)}个）")
        except Exception as e:
            context_parts.append(f"\n【灵畿缺陷】获取失败: {e}")

        return {"context": "\n".join(context_parts), "action": None, "skip_llm": False, "reply": ""}
