#!/usr/bin/env python3
"""查询待办"""
import json, os
from pathlib import Path

TODOS_FILE = Path(os.environ.get("XIAOQ_ROOT", Path(__file__).resolve().parents[1])) / "data" / "todos.json"

if __name__ == "__main__":
    todos = []
    if TODOS_FILE.exists():
        try:
            todos = json.loads(TODOS_FILE.read_text())
        except:
            pass
    
    active = [t for t in todos if not t.get('done') and not t.get('deleted')]
    
    if active:
        print(f"待办({len(active)}项):")
        for i, t in enumerate(active, 1):
            m = ' [已提醒]' if t.get('notified') else ''
            reminder = str(t.get('remind_at') or '未设置提醒').replace('T', ' ')[:16]
            title = t.get('text') or t.get('title') or '（无内容）'
            print(f"{i}. {title} | ⏰{reminder}{m}")
    else:
        print("暂无待办")
