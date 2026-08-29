#!/usr/bin/env python3
"""标记待办完成"""
import json, sys, os
from datetime import datetime, timedelta, timezone
from pathlib import Path

TODOS_FILE = Path(os.environ.get("XIAOQ_ROOT", Path(__file__).resolve().parents[1])) / "data" / "todos.json"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: done.py 索引")
        sys.exit(1)
    
    idx = int(sys.argv[1]) - 1  # 转为0-based索引
    
    todos = []
    if TODOS_FILE.exists():
        try:
            todos = json.loads(TODOS_FILE.read_text())
        except:
            pass
    
    active = [t for t in todos if not t.get('done') and not t.get('deleted')]
    
    if 0 <= idx < len(active):
        target = active[idx]
        target['done'] = True
        target['completed_at'] = datetime.now(timezone(timedelta(hours=8))).isoformat()
        TODOS_FILE.write_text(json.dumps(todos, ensure_ascii=False, indent=2))
        print(f"已完成: {target.get('text') or target.get('title') or '待办事项'}")
    else:
        print(f"没有第{idx+1}项待办")
