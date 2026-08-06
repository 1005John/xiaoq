"""
skills/email_knowledge.py — 邮件知识库查询技能

本地搜索已提炼的邮件知识库（SQLite + FTS5）。
调用 ~/email-knowledge/query.py 获取结果。

side_effects: card_show(type="todo") + voice_tts(简短摘要)
"""

import logging
import json
import re
import sqlite3
import subprocess
import time
from datetime import date, timedelta
from pathlib import Path

from skills.base import Skill, SkillResult, SideEffect

log = logging.getLogger("skills.email_knowledge")

QUERY_SCRIPT = "/home/johnf/.hermes/skills/email/email-knowledge/query.py"
QUERY_TIMEOUT = 25
LLM_CONFIG_FILE = Path(QUERY_SCRIPT).parent / "config" / "llm.json"
EMAIL_CONTEXT_FILE = Path("/home/johnf/xiaoq/data/email_context.json")
EMAIL_CONTEXT_TTL_SECONDS = 30 * 60


class EmailKnowledgeSkill(Skill):
    """邮件知识库查询 — 搜历史邮件"""

    name = "email_knowledge"
    description = "邮件知识库查询"

    def __init__(self, cfg: dict = None):
        super().__init__(cfg)
        self._last_items = self._load_previous_items()
        self._last_analysis = self._load_previous_analysis()

    @staticmethod
    def _load_previous_items():
        try:
            payload = json.loads(EMAIL_CONTEXT_FILE.read_text(encoding="utf-8"))
            if time.time() - float(payload.get("saved_at", 0)) > EMAIL_CONTEXT_TTL_SECONDS:
                return []
            items = payload.get("items", [])
            return items if isinstance(items, list) else []
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return []

    @staticmethod
    def _load_previous_analysis():
        try:
            payload = json.loads(EMAIL_CONTEXT_FILE.read_text(encoding="utf-8"))
            if time.time() - float(payload.get("saved_at", 0)) > EMAIL_CONTEXT_TTL_SECONDS:
                return ""
            analysis = payload.get("last_analysis", "")
            return analysis if isinstance(analysis, str) else ""
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return ""

    def _save_previous_items(self, analysis=None):
        try:
            EMAIL_CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
            temporary = EMAIL_CONTEXT_FILE.with_suffix(".tmp")
            temporary.write_text(
                json.dumps({
                    "saved_at": time.time(),
                    "items": self._last_items,
                    "last_analysis": self._last_analysis if analysis is None else analysis,
                }, ensure_ascii=False),
                encoding="utf-8",
            )
            temporary.replace(EMAIL_CONTEXT_FILE)
        except OSError as exc:
            log.warning("could not save email context: %s", exc)

    def _analyze_previous(self, question: str):
        """Answer a follow-up from the previous date result semantically."""
        if not self._last_items or not LLM_CONFIG_FILE.exists():
            return None
        try:
            from openai import OpenAI

            cfg = json.loads(LLM_CONFIG_FILE.read_text(encoding="utf-8")).get("llm", {})
            client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
            records = json.dumps(self._last_items[:50], ensure_ascii=False)
            response = client.chat.completions.create(
                model=cfg.get("model", "mimo-v2.5-pro"),
                temperature=0.1,
                max_tokens=700,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是邮件助理。用户正在追问上一轮邮件集合。"
                            "只根据提供的邮件记录判断是否需要重点关注，关注截止日期、"
                            "明确待办、会议评审、测试风险、账号安全和需要回复的事项。"
                            "列出邮件主题并说明原因，不要编造记录中没有的信息。"
                            "如果用户其实提出了与上一轮无关的新邮件问题，只输出 NEW_EMAIL_QUERY。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"上一轮邮件记录：\n{records}\n\n用户追问：{question}",
                    },
                ],
            )
            text = (response.choices[0].message.content or "").strip()
            if not text or text == "NEW_EMAIL_QUERY":
                return None
            self._last_analysis = text
            self._save_previous_items(analysis=text)
            return text
        except Exception as exc:
            log.warning("previous email analysis failed: %s", exc)
            return None

    def execute(self, params: dict = None) -> SkillResult:
        params = params or {}
        asr_text = params.get("_asr_text", "")

        # Time-range questions are best served by the local date index rather
        # than full-text search, which can omit otherwise recent messages.
        recent_periods = ("最近一周", "近一周", "过去一周", "最近7天", "近7天", "过去7天")
        date_hint = (
            any(word in asr_text for word in ("昨天", "今天", "前天", "最近", "近7天", "过去7天"))
            or re.search(r"\d{1,2}月\d{1,2}(?:日|号)?", asr_text)
        )

        # Continue the previous date query before treating a follow-up as a
        # new full-text search. The model decides whether it is a true
        # follow-up, so phrases such as "这里面" do not need keyword rules.
        if self._last_items and not date_hint:
            previous_analysis = self._analyze_previous(asr_text)
            if previous_analysis:
                return SkillResult(
                    success=True,
                    side_effects=[
                        SideEffect("card_show", {
                            "title": "邮件重点关注分析",
                            "lines": previous_analysis.splitlines(),
                            "card_type": "todo",
                        }),
                        SideEffect("voice_tts", {"text": previous_analysis[:500]}),
                    ],
                )
            return SkillResult(success=False, error="not an email follow-up")

        target_day = None
        if any(word in asr_text for word in ("昨天", "最近一天", "最近1天", "过去一天")):
            target_day = date.today() - timedelta(days=1)
        else:
            month_day = re.search(r"(\d{1,2})月(\d{1,2})(?:日|号)?", asr_text)
            if month_day:
                month, day = (int(value) for value in month_day.groups())
                year = date.today().year
                if month > date.today().month:
                    year -= 1
                try:
                    target_day = date(year, month, day)
                except ValueError:
                    target_day = None

        if target_day or any(period in asr_text for period in recent_periods):
            try:
                db_path = Path(QUERY_SCRIPT).parent / "data" / "emails.db"
                with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
                    if target_day:
                        rows = conn.execute(
                            "SELECT date, sender, subject, summary, needs_action, action_items "
                            "FROM emails WHERE date = ? ORDER BY date DESC",
                            (target_day.isoformat(),),
                        ).fetchall()
                    else:
                        rows = conn.execute(
                            "SELECT date, sender, subject, summary, needs_action, action_items FROM emails "
                            "WHERE date >= date('now', '-7 days') ORDER BY date DESC"
                        ).fetchall()
                if rows:
                    self._last_analysis = ""
                    self._last_items = [
                        {
                            "date": row[0], "sender": row[1], "subject": row[2],
                            "summary": row[3], "needs_action": row[4],
                            "action_items": row[5],
                        }
                        for row in rows
                    ]
                    self._save_previous_items()
                    lines = [f"{row[0]}: {row[2]}" for row in rows]
                    preview = "；".join(row[2] for row in rows[:3])
                    title = f"{target_day.isoformat()}邮件 ({len(rows)}封)" if target_day else f"最近一周邮件 ({len(rows)}封)"
                    period = f"{target_day.month}月{target_day.day}日" if target_day else "最近一周"
                    return SkillResult(
                        success=True,
                        data={"count": len(rows), "emails": lines},
                        side_effects=[
                            SideEffect("card_show", {
                                "title": title,
                                "lines": lines,
                                "card_type": "todo",
                            }),
                            SideEffect("voice_tts", {
                                "text": f"{period}有{len(rows)}封邮件，最新包括：{preview[:100]}"
                            }),
                        ],
                    )
            except (OSError, sqlite3.Error) as exc:
                log.warning("recent email lookup failed: %s", exc)

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
