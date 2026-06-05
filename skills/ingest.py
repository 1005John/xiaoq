"""
skills/ingest.py — 邮件知识库增量更新技能

语音触发拉取最新邮件并提炼入库。
调用 ~/.hermes/skills/email/email-knowledge/ingest.py --since 2。
"""

import logging
import re
import subprocess
import threading

from skills.base import Skill, SkillResult, SideEffect

log = logging.getLogger("skills.ingest")

INGEST_SCRIPT = "/home/johnf/.hermes/skills/email/email-knowledge/ingest.py"
INGEST_TIMEOUT = 120


class IngestSkill(Skill):
    """邮件知识库增量更新"""

    name = "ingest"
    description = "拉取最新邮件"

    def execute(self, params: dict = None) -> SkillResult:
        try:
            result = subprocess.run(
                ["/usr/bin/python3", INGEST_SCRIPT, "--since", "2"],
                capture_output=True, text=True, timeout=INGEST_TIMEOUT,
            )
            output = result.stdout.strip()

            # 解析新邮件数量
            new_count = 0
            for line in output.split("\n"):
                m = re.search(r"(\d+) 封新邮件", line)
                if m:
                    new_count = int(m.group(1))
                    break
                m = re.search(r"没有新邮件", line)
                if m:
                    new_count = 0
                    break

            # 解析总邮件数
            total_count = 0
            for line in output.split("\n"):
                m = re.search(r"库中总计: (\d+)", line)
                if m:
                    total_count = int(m.group(1))
                    break

            if new_count > 0:
                tts = f"已拉取{new_count}封新邮件，知识库共{total_count}封"
            else:
                tts = "没有新邮件需要处理"
                if total_count:
                    tts += f"，知识库共{total_count}封"

            log.info(f"ingest done: new={new_count}, total={total_count}")

            return SkillResult(
                success=True, data={"new": new_count, "total": total_count},
                side_effects=[
                    SideEffect("voice_tts", {"text": tts}),
                ],
            )

        except subprocess.TimeoutExpired:
            return SkillResult(
                success=True,
                side_effects=[SideEffect("voice_tts", {"text": "邮件拉取超时，请稍后重试"})],
            )
        except Exception as e:
            log.warning(f"ingest error: {e}")
            return SkillResult(
                success=True,
                side_effects=[SideEffect("voice_tts", {"text": "邮件拉取失败"})],
            )
