"""
skills/lingji.py — 灵畿平台任务技能 (实时查询)

每次执行都实时调用 lc req list 获取最新数据。
不依赖缓存。

L3意图: lingji_tasks → Skill "lingji", params: {}
TTS模板: 「你有{count}个灵畿任务需要处理。」
side_effects: card_show(type="lingji")
"""

import json
import logging
import subprocess

from .base import Skill, SkillResult, SideEffect

log = logging.getLogger("skills.lingji")

WORKSPACE = "CMIOTonemoredcap"


class LingjiSkill(Skill):
    """灵畿平台任务查询技能 — 实时查询"""

    name = "lingji"
    description = "灵畿平台任务查询"

    def __init__(self, cfg: dict = None):
        super().__init__(cfg)
        self.workspace = (cfg or {}).get("lingji_workspace", WORKSPACE)

    def _fetch_live(self) -> list:
        """实时查询灵畿任务，仅返回傅强负责的非关闭任务"""
        try:
            cmd = ["lc", "req", "list", "-l", "30", "--pretty"]
            if self.workspace:
                cmd.extend(["-w", self.workspace])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0 or not result.stdout.strip():
                return []
            data = json.loads(result.stdout)
            raw_items = data
            if isinstance(data, dict):
                inner = data.get("data", data)
                if isinstance(inner, dict):
                    raw_items = inner.get("items", inner)
                else:
                    raw_items = inner
            items = raw_items if isinstance(raw_items, list) else []
            # 只保留傅强负责 + 非已完成/关闭/取消
            skip_status = {"已完成", "已关闭", "取消"}
            filtered = []
            for t in items:
                if t.get("assignee") != "傅强":
                    continue
                status = t.get("status", "")
                if status in skip_status:
                    continue
                filtered.append({
                    "id": t.get("key", t.get("id", "")),
                    "title": t.get("name", t.get("title", "?")),
                    "status": status,
                    "key": t.get("key", ""),
                })
            return filtered
        except Exception as e:
            log.warning(f"Lingji live query error: {e}")
            return []

    def execute(self, params: dict = None) -> SkillResult:
        params = params or {}
        data = self._fetch_live()

        if not data:
            return SkillResult(
                success=True,
                data={},
                side_effects=[
                    SideEffect("voice_tts", {"text": "灵畿平台暂时没有待处理任务。"}),
                ],
            )

        count = len(data)
        titles = [t.get("title", "?") for t in data[:5]]
        items_text = "、".join(titles) if titles else ""

        # 构建卡片行
        lines = []
        for i, t in enumerate(data[:10], 1):
            status = t.get("status", "")
            title = t.get("title", "?")
            tag = f"[{status}]" if status else ""
            lines.append(f"{i}. {tag} {title}")

        if count > 5:
            lines.append(f"…以及另外 {count - 5} 项")

        tts_text = f"你有{count}个灵畿任务需要处理。{items_text}" if count else "灵畿平台暂时没有待处理任务。"

        return SkillResult(
            success=True,
            data={"count": count, "items": data},
            side_effects=[
                SideEffect("card_show", {
                    "title": f"灵畿任务 ({count})",
                    "lines": lines,
                    "card_type": "todo",
                }),
                SideEffect("voice_tts", {"text": tts_text}),
            ],
        )
