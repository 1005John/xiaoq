"""
skills/news.py — 新闻技能

从 weather_news.py NewsService 迁移。
Sidecar编排和v10 L3均可调用。

L3意图: news → Skill "news", params: {"count": N}
TTS模板: 「最新消息：{title}。」
side_effects: card_show(type="news")
"""

import json
import logging
from pathlib import Path
from .base import Skill, SkillResult, SideEffect

log = logging.getLogger("skills.news")

try:
    import aiohttp
    _aiohttp = True
except ImportError:
    _aiohttp = False

MOCK_NEWS = [
    {"title": "科技前沿：AI助手技术持续突破", "summary": "新一代智能助手在多模态理解上取得重要进展"},
    {"title": "健康提醒：久坐危害不可忽视", "summary": "研究显示每小时起身活动5分钟可显著降低健康风险"},
    {"title": "生活小贴士：保持专注的好方法", "summary": "番茄工作法搭配适当休息，提升工作效率30%"},
]


class NewsSkill(Skill):
    """新闻查询技能 — RSS + mock fallback"""
    
    name = "news"
    description = "新闻资讯 (RSS + mock fallback)"
    
    def __init__(self, cfg: dict = None):
        super().__init__(cfg)
        self.rss_urls = self.cfg.get("rss_urls", [])
        self.timeout = self.cfg.get("timeout", 10)
        self.mock_path = Path(self.cfg.get("mock_path", "data/mock_news.json"))
    
    async def fetch(self, count: int = 10) -> list:
        """获取新闻：先RSS，失败再mock"""
        if _aiohttp and self.rss_urls:
            for url in self.rss_urls:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=self.timeout)) as resp:
                            if resp.status == 200:
                                text = await resp.text()
                                items = self._parse_rss(text)
                                if items:
                                    log.info(f"Got {len(items)} news from {url}")
                                    return items[:count]
                except Exception as e:
                    log.warning(f"RSS fetch failed ({url}): {e}")
        else:
            if not _aiohttp:
                log.warning("aiohttp not available")
            if not self.rss_urls:
                log.warning("no RSS urls configured")

        # 失败/无网时：先试mock文件，再硬编码mock
        if self.mock_path.exists():
            try:
                return json.loads(self.mock_path.read_text())[:count]
            except Exception:
                pass
        return self._mock()[:count]

    def _mock(self) -> list:
        log.info("Using mock news (fallback)")
        return list(MOCK_NEWS)

    def _parse_rss(self, text: str) -> list:
        items = []
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(text)
            for item in root.iter("item"):
                title = ""
                desc = ""
                for child in item:
                    if child.tag == "title" and child.text:
                        title = child.text.strip()
                    elif child.tag in ("description", "summary") and child.text:
                        desc = child.text.strip()[:100]
                if title:
                    items.append({"title": title, "summary": desc})
        except Exception as e:
            log.debug(f"RSS parse error: {e}")
        return items

    def format_summary(self, news_items: list) -> str:
        """短口播模板"""
        if not news_items:
            return "暂时没有新闻。"
        t = news_items[0].get("title", "")
        return f"最新消息：{t}。"

    def execute(self, params: dict = None) -> SkillResult:
        """同步接口: 优先读缓存，无缓存再调 API"""
        params = params or {}
        max_age = params.get("max_age", 3600)
        count = params.get("count", 10)

        # 优先读本地缓存
        from .data_collector import get_cached_news
        cached = get_cached_news(max_age)
        if cached:
            log.info("News: using cached data")
            return self._build_result(cached[:count])

        # 无缓存/过期才调 API
        try:
            items = asyncio.get_event_loop().run_until_complete(self.fetch(count))
        except RuntimeError:
            import asyncio as _a
            items = _a.run(self.fetch(count))
        return self._build_result(items)

    async def execute_async(self, params: dict = None) -> SkillResult:
        """异步接口: 实际请求RSS"""
        params = params or {}
        count = params.get("count", 1)
        items = await self.fetch(count)
        return self._build_result(items)

    def _build_result(self, items: list) -> SkillResult:
        tts_text = self.format_summary(items)
        lines = []
        for i, n in enumerate(items, 1):
            lines.append(f"{i}. {n.get('title', '')}")
        if not lines:
            lines.append("(暂无新闻)")
        return SkillResult(
            success=True,
            data={"items": items, "count": len(items)},
            side_effects=[
                SideEffect("card_show", {"title": "最新资讯", "lines": lines, "card_type": "todo"}),
                SideEffect("voice_tts", {"text": tts_text}),
            ],
        )


import asyncio
