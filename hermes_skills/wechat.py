"""微信_Hermes技能 - 查询微信聊天知识库"""
import logging
import re
import sqlite3
from pathlib import Path

from hermes_skills.base import HermesSkill

log = logging.getLogger("hermes_skills.wechat")
WECHAT_DB = Path.home() / ".hermes" / "skills" / "wechat" / "wechat-knowledge" / "data" / "wechat.db"

class WechatHermesSkill(HermesSkill):
    name = "wechat_knowledge"
    description = "微信聊天记录查询"

    def prepare(self, text: str) -> dict:
        query = re.sub(
            r"微信|微信聊天|翻聊天|查查|查一下|查看|查询一下|帮我|看看|找找|[，。！？、；：.,!?;:（）【】《》]",
            "", text
        ).strip()
        
        if not query:
            return {"context": "", "action": None, "skip_llm": True, "reply": "你想查什么微信聊天内容？"}

        if not WECHAT_DB.exists():
            return {"context": "", "action": None, "skip_llm": True, "reply": "微信知识库尚未就绪"}

        try:
            conn = sqlite3.connect(str(WECHAT_DB))
            cur = conn.execute(
                "SELECT date, summary FROM segments "
                "WHERE summary LIKE ? ORDER BY date DESC LIMIT 10",
                (f"%{query}%",)
            )
            rows = cur.fetchall()
            conn.close()
            
            if rows:
                context = "【微信聊天记录】\n"
                for row in rows:
                    date_str = (row[0] or "")[:10]
                    summary = (row[1] or "")[:60]
                    context += f"  [{date_str}] {summary}\n"
                return {"context": context, "action": None, "skip_llm": False, "reply": ""}
            else:
                return {"context": "", "action": None, "skip_llm": True, "reply": f"没有找到关于\"{query}\"的微信聊天记录"}
        except Exception as e:
            return {"context": "", "action": None, "skip_llm": True, "reply": f"微信查询失败: {e}"}
