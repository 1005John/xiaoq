"""刷新_Hermes技能 - 刷新邮件知识库（后台执行）"""
import logging
import subprocess
import threading
from pathlib import Path

from hermes_skills.base import HermesSkill

log = logging.getLogger("hermes_skills.ingest")
INGEST_SCRIPT = Path.home() / ".hermes" / "skills" / "email" / "email-knowledge" / "ingest.py"

class IngestHermesSkill(HermesSkill):
    name = "ingest"
    description = "刷新邮件、拉取最新邮件、更新邮件数据"

    def prepare(self, text: str) -> dict:
        """启动后台刷新线程"""
        def _run():
            try:
                subprocess.run(
                    ["/usr/bin/python3", str(INGEST_SCRIPT), "--since", "2"],
                    capture_output=True, text=True, timeout=120,
                )
            except Exception as e:
                log.warning(f"ingest error: {e}")
        
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        
        return {
            "context": "",
            "action": None,
            "skip_llm": True,
            "reply": "好的，正在后台刷新邮件数据，稍后会通知你。"
        }
