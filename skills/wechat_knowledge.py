"""
skills/wechat_knowledge.py — 微信聊天知识库查询技能

本地搜索已提炼的微信聊天知识库（SQLite + FTS5）。
通过关键词 "微信" 触发，不参与语义匹配。

side_effects: card_show(type="todo") + voice_tts(简短摘要)
"""

import logging
import re
import subprocess

from skills.base import Skill, SkillResult, SideEffect

log = logging.getLogger("skills.wechat_knowledge")

QUERY_SCRIPT = "/home/johnf/.hermes/skills/wechat/wechat-knowledge/query.py"
QUERY_TIMEOUT = 25


class WechatKnowledgeSkill(Skill):
    """微信聊天知识库查询 — 搜历史聊天记录"""

    name = "wechat_knowledge"
    description = "微信聊天知识库查询"

    def __init__(self, cfg: dict = None):
        super().__init__(cfg)
        self._last_items = []

    def execute(self, params: dict = None) -> SkillResult:
        params = params or {}
        asr_text = params.get("_asr_text", "")

        # 清理查询文本（去掉触发词"微信"）
        query = re.sub(r"微信|聊天|记录|查|看|翻", "", asr_text).strip()
        if not query:
            query = asr_text

        if not query:
            return SkillResult(
                success=True,
                side_effects=[SideEffect("voice_tts", {"text": "你想查微信里的什么内容？"})],
            )

        # 调用 query.py
        try:
            result = subprocess.run(
                ["/usr/bin/python3", QUERY_SCRIPT, query],
                capture_output=True, text=True, timeout=QUERY_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return SkillResult(
                success=True,
                side_effects=[SideEffect("voice_tts", {"text": "微信知识库查询超时"})],
            )
        except Exception as e:
            log.warning(f"wechat_knowledge query error: {e}")
            return SkillResult(
                success=True,
                side_effects=[SideEffect("voice_tts", {"text": "微信知识库查询失败"})],
            )

        output = result.stdout.strip()
        lines = [l for l in output.split("\n") if l.strip()]

        # 提取数量
        count = 0
        for l in lines:
            m = re.search(r"找到 (\d+) 段", l)
            if m:
                count = int(m.group(1))
                break

        if count == 0:
            return SkillResult(
                success=True,
                side_effects=[
                    SideEffect("card_show", {
                        "title": f"微信聊天: {query[:20]}",
                        "lines": ["(没有找到相关聊天记录)"],
                        "card_type": "todo",
                    }),
                    SideEffect("voice_tts", {"text": f"没有找到相关微信聊天记录"}),
                ],
            )

        # 提取 LLM 汇总内容
        body_start = 0
        for i, l in enumerate(lines):
            if l.startswith("好的") or l.startswith("根据") or l.startswith("这是") or l.startswith("以下") or l.startswith("用户"):
                body_start = i
                break
        if body_start == 0:
            body_start = 3

        card_lines = lines[body_start:] if body_start < len(lines) else lines[-10:]

        # TTS 摘要
        tts = f"找到{count}段相关聊天记录"
        first_few = [l for l in card_lines if l.strip() and not l.startswith("---") and not l.startswith("|")]
        if first_few:
            for l in first_few[:3]:
                if "：" in l or ":" in l or "摘要" in l:
                    clean = l.split("：")[-1].split(":")[-1][:30]
                    tts += f"，{clean}"
                    break

        return SkillResult(
            success=True, data={"count": count, "output": output},
            side_effects=[
                SideEffect("card_show", {
                    "title": f"微信聊天: {query[:20]}",
                    "lines": card_lines,
                    "card_type": "todo",
                }),
                SideEffect("voice_tts", {"text": tts}),
            ],
        )
