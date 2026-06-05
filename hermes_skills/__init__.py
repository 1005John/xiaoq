"""Hermes Skills - 给 LLM 提供上下文数据的技能包"""
from hermes_skills.weather import WeatherHermesSkill
from hermes_skills.todo import TodoHermesSkill
from hermes_skills.bug import BugHermesSkill
from hermes_skills.email import EmailHermesSkill
from hermes_skills.wechat import WechatHermesSkill
from hermes_skills.ingest import IngestHermesSkill
from hermes_skills.others import NewsHermesSkill, ChatHermesSkill, BgmHermesSkill
from hermes_skills.moa import MoaHermesSkill

SKILL_MAP = {
    "weather": WeatherHermesSkill,
    "todo": TodoHermesSkill,
    "lingji": TodoHermesSkill,    # 灵畿任务 = 待办
    "bug": BugHermesSkill,
    "email_knowledge": EmailHermesSkill,
    "wechat_knowledge": WechatHermesSkill,
    "ingest": IngestHermesSkill,
    "news": NewsHermesSkill,
    "relax": ChatHermesSkill,
    "bgm": BgmHermesSkill,
    "moa": MoaHermesSkill,
}

def get_skill(name: str):
    cls = SKILL_MAP.get(name)
    if cls:
        return cls()
    return None
