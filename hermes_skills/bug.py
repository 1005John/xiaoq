"""缺陷_Hermes技能 - 获取灵畿缺陷（解析JSON）+ 邮件上下文"""
import json
import logging
import re
import sqlite3
import subprocess
from pathlib import Path
from hermes_skills.base import HermesSkill

log = logging.getLogger("hermes_skills.bug")

LC_WORKSPACE = "CMIOTonemoredcap"
EMAIL_DB = Path.home() / ".hermes" / "skills" / "email" / "email-knowledge" / "data" / "emails.db"
_PRODUCT_MAP = [("307C","ML307C"),("307H","ML307H"),("307X","ML307X"),("307N","ML307N"),("38022","MR380R"),("3802","MR380R"),("380R","MR380R"),("380","MR380R")]

class BugHermesSkill(HermesSkill):
    name = "bug"
    description = "缺陷管理：查缺陷、测试进展、产品问题"

    def prepare(self, text: str) -> dict:
        context_parts = []

        # 1. 检测产品名
        product = ""
        for short, full in _PRODUCT_MAP:
            if short in text or full in text:
                product = full
                break

        # 2. 获取缺陷列表（JSON解析）
        try:
            r = subprocess.run(["lc","bug","list","-w",LC_WORKSPACE], capture_output=True, text=True, timeout=15)
            data = json.loads(r.stdout)
            items = data.get("data",{}).get("items") or []
            open_bugs = [b for b in items if b.get("status") not in ("已关闭",)]
            my_bugs = [b for b in open_bugs if "傅强" in (b.get("handlerName") or "")]
            
            # 按产品筛选
            if product:
                filtered = []
                for b in my_bugs:
                    name = b.get("defectName","")
                    if product.lower() in name.lower():
                        filtered.append(b)
                my_bugs = filtered

            if my_bugs:
                title = f"【灵畿缺陷（{'全部' if not product else product}）共{len(my_bugs)}个】"
                context_parts.append(title)
                for b in my_bugs:
                    name = b.get("defectName","")
                    status = b.get("status","")
                    level = b.get("defectLevelDes","")
                    priority = b.get("priorityDesc","")
                    context_parts.append(f"  [{level}/{priority}] {name} ({status})")
            else:
                context_parts.append(f"【灵畿缺陷】{'全部' if not product else product}暂无未关闭缺陷")
        except Exception as e:
            context_parts.append(f"【灵畿缺陷】获取失败: {e}")

        # 3. 相关邮件
        search_term = product or "ML307"
        if EMAIL_DB.exists():
            try:
                conn = sqlite3.connect(str(EMAIL_DB))
                cur = conn.execute(
                    "SELECT date, subject, summary FROM emails WHERE "
                    "(summary LIKE ? OR subject LIKE ?) ORDER BY date DESC LIMIT 8",
                    (f"%{search_term}%", f"%{search_term}%")
                )
                emails = cur.fetchall()
                conn.close()
                if emails:
                    context_parts.append(f"\n【相关邮件（{len(emails)}封）】")
                    for row in emails:
                        ds = (row[0] or "")[:10]
                        subj = (row[1] or row[2] or "")[:50]
                        context_parts.append(f"  [{ds}] {subj}")
            except Exception as e:
                pass

        context = "\n".join(context_parts)
        return {"context": context, "action": None, "skip_llm": False, "reply": ""}
