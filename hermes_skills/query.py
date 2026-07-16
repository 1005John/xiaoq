#!/usr/bin/env python3
"""查询待办"""
import json
from pathlib import Path

TODOS_FILE = Path.home() / "xiaoq" / "data" / "todos.json"

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
            print(f"{i}. {t.get('text', '')}{m}")
    else:
        print("暂无待办")
