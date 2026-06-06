#!/usr/bin/env python3
"""添加待办事项"""
import json, sys, os, re
from pathlib import Path
from datetime import datetime, timedelta, timezone

SHANGHAI = timezone(timedelta(hours=8))
TODOS_FILE = Path.home() / "Little_Q_new" / "pi_reference_exp" / "data" / "todos.json"


_CN_NUM = {"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10,"半":0.5}

_CN_DIGIT = {"零":0,"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
def _cn_to_int(s):
    """Chinese number to int: 十一->11, 二十->20, 三十五->35"""
    s = s.strip()
    if not s: return None
    if s.isdigit(): return int(s)
    if s == '十': return 10
    if s.startswith('十') and len(s) > 1:
        return 10 + _CN_DIGIT.get(s[1], 0)
    if s.endswith('十') and len(s) > 1:
        return _CN_DIGIT.get(s[0], 0) * 10
    parts = s.split('十')
    if len(parts) == 2:
        return (_CN_DIGIT.get(parts[0], 1) if parts[0] else 10) * 10 + _CN_DIGIT.get(parts[1], 0)
    return _CN_DIGIT.get(s)

def _parse_num(s):
    """解析中文或阿拉伯数字"""
    s = s.strip()
    if s.isdigit():
        return int(s)
    if s in _CN_NUM:
        return _CN_NUM[s]
    return None

def parse_remind_time(text):
    """解析提醒时间"""
    now = datetime.now(SHANGHAI)
    
    # X分钟后 / X分钟后提醒我
    m = re.search(r'(\d+|[一二两三四五六七八九十半])\s*分钟\s*(之?后|后)', text)
    if m:
                n = _parse_num(m.group(1)); return (now + timedelta(minutes=n), text) if n is not None else (None, text)
    
    # X小时后
    m = re.search(r'(\d+)\s*小时\s*后', text)
    if m:
        return now + timedelta(hours=int(m.group(1))), text
    
    # 明天X点 / 明天上午X点 / 明天下午X点
    m = re.search(r'明天\s*(上午|下午)?(\d{1,2})\s*点', text)
    if m:
        hour = _cn_to_int(m.group(2))
        if m.group(1) == '下午' and hour < 12:
            hour += 12
        target = now.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return target, text
    
    # 今天X点 / 晚上X点X分 / 下午X点X分
    m = re.search(r'(今天|今晚|晚上|下午|上午|中午)?\s*([\d一二三四五六七八九十两]+)\s*点\s*([\d一二三四五六七八九十两]+)?\s*分?', text)
    if m:
        hour = _cn_to_int(m.group(2))
        minute = _cn_to_int(m.group(3)) if m.group(3) else 0
        prefix = m.group(1) or ''
        if prefix in ('下午','中午') and hour < 12:
            hour += 12
        elif prefix in ('晚上','今晚') and hour < 12:
            hour += 12
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)  # 如果时间已过，设为明天
        # 保留原始文本（不要截断）
        return target, m.group(0)
    
    # YYYY-MM-DD HH:MM
    m = re.search(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})', text)
    if m:
        return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M").replace(tzinfo=SHANGHAI), text
    
    return None, text

if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    if not text:
        print("用法: add.py 待办内容 [提醒时间]")
        sys.exit(1)
    
    # 分离待办内容和提醒时间
    remind_at = None
    remind_text = None
    
    # 尝试解析提醒时间
    remind_at, remind_text = parse_remind_time(text)
    if remind_at:
        # 去掉时间部分，保留纯待办内容
        clean = re.sub(r'\d+分钟后|\d+小时后|明天.*点|今天.*点|提醒我', '', text).strip()
        if clean:
            text = clean
    
    # 加载现有
    todos = []
    if TODOS_FILE.exists():
        try:
            todos = json.loads(TODOS_FILE.read_text())
        except:
            pass
    
    todo = {
        "id": str(int(datetime.now().timestamp() * 1000)),
        "text": text,
        "done": False,
        "notified": False,
    }
    if remind_at:
        todo["remind_at"] = remind_at.isoformat()
        todo["remind_text"] = remind_text
    
    todos.append(todo)
    
    TODOS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TODOS_FILE.write_text(json.dumps(todos, ensure_ascii=False, indent=2))
    
    msg = f"已添加待办: {text}"
    if remind_at:
        msg += f"，将在 {remind_at.strftime('%H:%M')} 提醒你"
    print(msg)
