"""新闻/闲聊/音乐 Hermes 技能 - 不需特殊上下文，直通 LLM"""
from hermes_skills.base import HermesSkill

class NewsHermesSkill(HermesSkill):
    name = "news"
    description = "查看新闻、热点资讯"
    def prepare(self, text: str) -> dict:
        return {"context": "", "action": None, "skip_llm": False, "reply": ""}

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
