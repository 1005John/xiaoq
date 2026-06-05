"""
skills/base.py — Skill基类 + SkillManager + SkillResult(含side_effects)

按《重构建议_v10与Sidecar融合方案.md》§九设计：
- Skill.execute() 返回 SkillResult
- SkillResult.data: dict (技能数据)
- SkillResult.side_effects: list[SideEffect] (驱动v10表情/卡片/TTS/ambient等)
- SideEffect 禁止WS回环：v10内部直接调内部API，Sidecar走WS
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger("skills.base")


@dataclass
class SideEffect:
    """技能执行的副作用指令
    
    type: 指令类型 (与v10 WS协议一致)
      - card_show: 显示卡片
      - card_hide: 隐藏卡片
      - expression: 切换表情
      - set_mood: 设置心情
      - voice_tts: TTS播报
      - trigger_squash: 弹性动画
      - trigger_vfx: 触发粒子效果
      - set_ambient: 设置环境粒子模式
      - npc_interact: NPC交互
      - set_pupil_mode: 瞳孔模式
    params: dict 指令参数
    """
    type: str
    params: Dict = field(default_factory=dict)


@dataclass
class SkillResult:
    """Skill.execute() 返回值
    
    success: 是否成功
    data: 技能数据 (用于TTS模板渲染等)
    side_effects: 副作用列表 (由调用方执行)
    error: 失败时的错误信息
    """
    success: bool = True
    data: Dict = field(default_factory=dict)
    side_effects: List = field(default_factory=list)
    error: str = ""


class Skill:
    """技能基类
    
    子类须实现:
      name: str — 技能名 (与意图表INTENT_SKILL_MAP对齐)
      description: str — 技能描述
    
    子类须实现:
      execute(params: dict) -> SkillResult
    """
    name: str = ""
    description: str = ""
    
    def __init__(self, cfg: dict = None):
        self.cfg = cfg or {}
    
    def execute(self, params: dict = None) -> SkillResult:
        """执行技能。params由意图层或编排器传入。"""
        raise NotImplementedError(f"{self.__class__.__name__}.execute() not implemented")


class SkillManager:
    """技能注册表 + 执行器"""
    
    def __init__(self):
        self._skills: dict[str, Skill] = {}
    
    def register(self, skill: Skill):
        if not skill.name:
            raise ValueError(f"Skill {skill.__class__.__name__} has no name")
        self._skills[skill.name] = skill
        log.info(f"Skill registered: {skill.name}")
    
    def execute(self, skill_name: str, params: dict = None) -> SkillResult:
        skill = self._skills.get(skill_name)
        if not skill:
            log.warning(f"Skill not found: {skill_name}")
            return SkillResult(success=False, error=f"Skill '{skill_name}' not registered")
        try:
            result = skill.execute(params or {})
            if not isinstance(result, SkillResult):
                log.warning(f"Skill {skill_name} returned {type(result)}, expected SkillResult")
                return SkillResult(success=False, error="Invalid return type")
            return result
        except Exception as e:
            log.error(f"Skill {skill_name} execute error: {e}")
            return SkillResult(success=False, error=str(e))
    
    def has(self, skill_name: str) -> bool:
        return skill_name in self._skills
    
    def list_skills(self) -> List[str]:
        return list(self._skills.keys())
    
    def create_minimal(self, cfg: dict = None) -> "SkillManager":
        """工厂方法: 创建L3最小注册集"""
        from .todo import TodoSkill
        from .weather import WeatherSkill
        from .news import NewsSkill
        from .relax import RelaxSkill
        from .bgm import BgmSkill
        from .lingji import LingjiSkill
        from .bug import BugSkill
        from .ingest import IngestSkill
        from .email_knowledge import EmailKnowledgeSkill
        from .wechat_knowledge import WechatKnowledgeSkill

        cfg = cfg or {}
        self.register(TodoSkill(cfg.get("todo", {})))
        self.register(WeatherSkill(cfg.get("weather", {})))
        self.register(NewsSkill(cfg.get("news", {})))
        self.register(RelaxSkill(cfg.get("relax", {})))
        self.register(BgmSkill(cfg.get("eod_bgm", {})))
        self.register(LingjiSkill(cfg.get("lingji", {})))
        self.register(BugSkill(cfg.get("bug", {})))
        self.register(IngestSkill(cfg.get("ingest", {})))
        self.register(EmailKnowledgeSkill(cfg.get("email_knowledge", {})))
        self.register(WechatKnowledgeSkill(cfg.get("wechat_knowledge", {})))
        return self
