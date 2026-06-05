"""邮件_Hermes技能 - 查询本地邮件知识库，给 Hermes 处理"""
import logging
import re
import subprocess
from pathlib import Path

from hermes_skills.base import HermesSkill

log = logging.getLogger("hermes_skills.email")

QUERY_SCRIPT = Path.home() / ".hermes" / "skills" / "email" / "email-knowledge" / "query.py"

class EmailHermesSkill(HermesSkill):
    name = "email_knowledge"
    description = "邮件知识库：查历史邮件、项目进展、邮件记录"

    def prepare(self, text: str) -> dict:
        """查询邮件知识库"""
        # 清洗查询文本
        query = re.sub(
            r"查查|查一下|查看|查询一下|帮我|搜一下|翻一下|看看|找找|邮件|发的|关于|的|[，。！？、；：.,!?;:（）【】《》]",
            "", text
        ).strip()

        if not query:
            return {"context": "", "action": None, "skip_llm": True, "reply": "你想查什么邮件内容？"}

        try:
            result = subprocess.run(
                ["/usr/bin/python3", str(QUERY_SCRIPT), query],
                capture_output=True, text=True, timeout=25,
            )
            output = result.stdout.strip()
            if output:
                return {"context": f"【邮件查询结果】\n{output[:1500]}", "action": None, "skip_llm": False, "reply": ""}
            else:
                return {"context": "", "action": None, "skip_llm": True, "reply": "没有找到相关邮件"}
        except Exception as e:
            return {"context": "", "action": None, "skip_llm": True, "reply": f"邮件查询失败: {e}"}
