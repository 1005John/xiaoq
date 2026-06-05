"""
skills/email_knowledge.py — 邮件知识库查询技能

本地搜索已提炼的邮件知识库（SQLite + FTS5）。
调用 ~/email-knowledge/query.py 获取结果。

side_effects: card_show(type="todo") + voice_tts(简短摘要)
"""

import logging
import re
import subprocess

from skills.base import Skill, SkillResult, SideEffect

log = logging.getLogger("skills.email_knowledge")

QUERY_SCRIPT = "/home/johnf/.hermes/skills/email/email-knowledge/query.py"
QUERY_TIMEOUT = 25


class EmailKnowledgeSkill(Skill):
    """邮件知识库查询 — 搜历史邮件"""

    name = "email_knowledge"
    description = "邮件知识库查询"

    def __init__(self, cfg: dict = None):
        super().__init__(cfg)
        self._last_items = []

    def execute(self, params: dict = None) -> SkillResult:
        params = params or {}
        asr_text = params.get("_asr_text", "")

        # 清理查询文本（产品名扩展已在 query.py 中处理）
        query = re.sub(
            r"查查|查一下|查看|查询一下|帮我|搜一下|翻一下|看看|找找|邮件|发的|关于|[，。！？、；：.,!?;:（）【】《》]",
            "", asr_text
        ).strip()

        if not query:
            return SkillResult(
                success=True,
                side_effects=[SideEffect("voice_tts", {"text": "你想查什么邮件内容？"})],
            )

        log.info(f"email_knowledge query: '{query}'")

        # 调用 query.py
        try:
            result = subprocess.run(
                ["/usr/bin/python3", QUERY_SCRIPT, query],
                capture_output=True, text=True, timeout=QUERY_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return SkillResult(
                success=True,
                side_effects=[SideEffect("voice_tts", {"text": "邮件知识库查询超时"})],
            )
        except Exception as e:
            log.warning(f"email_knowledge query error: {e}")
            return SkillResult(
                success=True,
                side_effects=[SideEffect("voice_tts", {"text": "邮件知识库查询失败"})],
            )

        output = result.stdout.strip()
        lines = [l for l in output.split("\n") if l.strip()]

        # 提取邮件数量
        count = 0
        for l in lines:
            m = re.search(r"找到 (\d+) 封", l)
            if m:
                count = int(m.group(1))
                break

        if count == 0:
            return SkillResult(
                success=True,
                side_effects=[
                    SideEffect("card_show", {
                        "title": f"邮件知识库: {query[:20]}",
                        "lines": ["(没有找到相关邮件)"],
                        "card_type": "todo",
                    }),
                    SideEffect("voice_tts", {"text": f"没有找到关于 {query[:15]} 的邮件"}),
                ],
            )

        # 提取 LLM 汇总内容
        body_start = 0
        for i, l in enumerate(lines):
            if l.startswith("好的") or l.startswith("根据") or l.startswith("这是") or l.startswith("以下"):
                body_start = i
                break
        if body_start == 0:
            body_start = 3

        card_lines = lines[body_start:] if body_start < len(lines) else lines[-10:]

        # 生成 TTS 摘要
        tts = f"找到{count}封相关邮件"
        first_few = [l for l in card_lines if l.strip() and not l.startswith("---") and not l.startswith("|")]
        if first_few:
            for l in first_few[:5]:
                if "：" in l or ":" in l or l.startswith("ML") or l.startswith("第"):
                    tts += f"，{l[:40]}"
                    break

        return SkillResult(
            success=True, data={"count": count, "output": output},
            side_effects=[
                SideEffect("card_show", {
                    "title": f"邮件知识库: {query[:20]}",
                    "lines": card_lines,
                    "card_type": "todo",
                }),
                SideEffect("voice_tts", {"text": tts}),
            ],
        )