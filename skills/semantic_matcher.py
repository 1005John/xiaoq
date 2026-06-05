"""
语义意图匹配器 — 基于 DashScope text-embedding-v2 的语义路由

用法:
    from semantic_matcher import SemanticMatcher
    matcher = SemanticMatcher(api_key="sk-xxx")
    skill_name = matcher.match("ML307C测试进展")  # bug (含产品代码时优先)
"""

import json
import logging
import math
import time
import urllib.request
from typing import Optional

log = logging.getLogger("semantic_matcher")

SKILL_DESCRIPTIONS = {
    "weather": "查询天气、温度、降水、风力、今天天气怎么样、明天天气",
    "news": "查看最新新闻、热点资讯、今天有什么新闻、科技新闻",
    "todo": "待办事项管理、添加待办、查看待办、完成待办、设置提醒、OA审批、工作台、流程、开会",
    "bug": "缺陷管理、查看缺陷、处理bug、测试问题、故障报告、缺陷分析、修复问题",
    "relax": "放松休息、娱乐、木鱼、聊天、摸鱼",
    "bgm": "播放音乐、背景音乐、听歌、放点音乐、来首歌",
    "lingji": "灵畿平台任务、项目任务、研发任务、灵畿工作",
    "ingest": "拉取最新邮件、刷新邮箱、更新邮件数据、同步邮件、拉邮件",
    "moa": "聊天记录查询、MOA聊天、找聊天记录、查群聊、看聊天、查消息、看消息、群聊记录、工作聊天、项目讨论、群消息",
    "email_knowledge": "搜历史邮件、查项目进展、找邮件记录、看邮件存档、搜测试报告、查过往沟通、查今天有几封邮件、查看邮件数量、浏览邮件列表、邮件统计",
}

WECHAT_KEYWORDS = ["微信", "微信聊天", "翻聊天"]
PRODUCT_CODES = ["307C", "307H", "307X", "307N", "38022", "3802", "380R", "380"]


class SemanticMatcher:
    def __init__(self, api_key: str, base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"):
        self.api_key = api_key
        self.embed_url = f"{base_url}/embeddings"
        self._skill_names = []
        self._skill_vectors = []
        self._init_ok = False

    def init(self) -> bool:
        try:
            names = list(SKILL_DESCRIPTIONS.keys())
            texts = [SKILL_DESCRIPTIONS[n] for n in names]
            embeds = self._batch_embed(texts)
            if not embeds or len(embeds) != len(texts):
                log.error(f"语义匹配器初始化失败")
                return False
            self._skill_names = names
            self._skill_vectors = embeds
            self._init_ok = True
            log.info(f"语义匹配器初始化完成: {len(names)} 个技能")
            return True
        except Exception as e:
            log.error(f"语义匹配器初始化异常: {e}")
            return False

    def _batch_embed(self, texts: list) -> list:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": "text-embedding-v2", "input": texts}
        req = urllib.request.Request(self.embed_url, data=json.dumps(payload).encode(), headers=headers, method="POST")
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        return [item["embedding"] for item in data["data"]]

    def _single_embed(self, text: str) -> list:
        return self._batch_embed([text])[0]

    def _cosine_similarity(self, v1: list, v2: list) -> float:
        dot = sum(a * b for a, b in zip(v1, v2))
        n1 = math.sqrt(sum(a * a for a in v1))
        n2 = math.sqrt(sum(a * a for a in v2))
        return dot / (n1 * n2) if n1 * n2 > 0 else 0

    def _has_product_code(self, text: str) -> bool:
        tu = text.upper()
        for code in PRODUCT_CODES:
            if code in tu:
                return True
        return False

    def match(self, text: str, threshold: float = 0.22) -> Optional[str]:
        if not text or not self._init_ok:
            return None

        text_lower = text.lower()
        for kw in WECHAT_KEYWORDS:
            if kw in text_lower:
                return "wechat_knowledge"

        try:
            t0 = time.time()
            q_vec = self._single_embed(text)
            best_name, best_score = None, -1
            for i, name in enumerate(self._skill_names):
                score = self._cosine_similarity(q_vec, self._skill_vectors[i])
                if score > best_score:
                    best_score = score
                    best_name = name

            elapsed = (time.time() - t0) * 1000
            product_override = self._has_product_code(text) and best_name == "bug"

            # 产品型号代码覆盖：优先走 bug 技能
            if self._has_product_code(text) and best_name != "bug":
                bug_idx = self._skill_names.index("bug")
                bug_score = self._cosine_similarity(q_vec, self._skill_vectors[bug_idx])
                relaxed = threshold * 0.7
                if bug_score >= relaxed:
                    best_name = "bug"
                    best_score = bug_score
                    product_override = True
                    log.info(f"语义匹配(产品覆盖): {text} -> bug ({bug_score:.3f}, {elapsed:.0f}ms)")
                else:
                    log.info(f"语义匹配: {text} -> {best_name} ({best_score:.3f}, {elapsed:.0f}ms)")
            else:
                log.info(f"语义匹配: {text} -> {best_name} ({best_score:.3f}, {elapsed:.0f}ms)")

            effective = threshold * 0.7 if product_override else threshold
            if best_score < effective:
                return None
            return best_name
        except Exception as e:
            log.error(f"语义匹配异常: {e}")
            return None

    def match_with_score(self, text: str) -> tuple:
        if not text or not self._init_ok:
            return None, 0
        text_lower = text.lower()
        for kw in WECHAT_KEYWORDS:
            if kw in text_lower:
                return "wechat_knowledge", 1.0
        try:
            q_vec = self._single_embed(text)
            best_name, best_score = None, -1
            for i, name in enumerate(self._skill_names):
                score = self._cosine_similarity(q_vec, self._skill_vectors[i])
                if score > best_score:
                    best_score = score
                    best_name = name
            if self._has_product_code(text) and best_name != "bug":
                bug_idx = self._skill_names.index("bug")
                bug_score = self._cosine_similarity(q_vec, self._skill_vectors[bug_idx])
                if bug_score >= 0.15:
                    return "bug", bug_score
            return best_name, best_score
        except Exception:
            return None, 0