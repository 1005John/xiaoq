"""新闻/闲聊/音乐 Hermes 技能 — 新闻从缓存读取，其余直通 LLM"""
import json
import logging
import time
from pathlib import Path
from hermes_skills.base import HermesSkill

log = logging.getLogger("hermes_skills.others")

# 缓存路径：hermes_skills/../data/news_cache.json
_NEWS_CACHE_PATH = Path(__file__).parent.parent / "data" / "news_cache.json"

class NewsHermesSkill(HermesSkill):
    name = "news"
    description = "查看新闻、热点资讯"

    def prepare(self, text: str) -> dict:
        """读取缓存的新闻数据，由 data_collector 后台每30分钟更新"""
        context = ""
        try:
            if _NEWS_CACHE_PATH.exists():
                with open(_NEWS_CACHE_PATH, encoding="utf-8") as f:
                    cache = json.load(f)
                ts = cache.get("timestamp", 0)
                age_min = int((time.time() - ts) / 60)
                items = cache.get("data", [])

                if items:
                    lines = [f"【最新新闻（{age_min}分钟前更新，共{len(items)}条）】"]
                    for i, item in enumerate(items[:10], 1):
                        title = item.get("title", "")
                        # 清洗 HTML 标签
                        import re
                        title = re.sub(r'<[^>]+>', '', title)
                        lines.append(f"{i}. {title}")
                    context = "\n".join(lines)
                else:
                    context = "【新闻】暂无新闻数据"
            else:
                context = "【新闻】缓存文件不存在，等待后台采集..."
        except Exception as e:
            context = f"【新闻】读取缓存失败: {e}"

        return {"context": context, "action": None, "skip_llm": False, "reply": ""}


class ChatHermesSkill(HermesSkill):
    name = "relax"
    description = "闲聊、放松、聊天"
    def prepare(self, text: str) -> dict:
        return {"context": "", "action": None, "skip_llm": False, "reply": ""}


class BgmHermesSkill(HermesSkill):
    name = "bgm"
    description = "播放音乐、背景音乐"
    def prepare(self, text: str) -> dict:
        return {"context": "", "action": None, "skip_llm": False, "reply": ""}
