"""MOA_Hermes技能 - 查询MOA聊天记录（一级摘要+二级原文）"""
import json
import logging
import re
import sqlite3
from pathlib import Path

from hermes_skills.base import HermesSkill

log = logging.getLogger("hermes_skills.moa")

MOA_DB = Path.home() / ".hermes" / "skills" / "moa" / "data" / "moa.db"
MOA_CHATS_DIR = Path.home() / "moa_chats" / "export"


class MoaHermesSkill(HermesSkill):
    name = "moa"
    description = "MOA聊天记录：查聊天摘要、找聊天记录、看原文"

    def prepare(self, text: str) -> dict:
        query = self._clean_query(text)
        if not query:
            return {"context": "", "action": None, "skip_llm": True,
                    "reply": "你想查什么MOA聊天内容？"}

        if not MOA_DB.exists():
            return {"context": "", "action": None, "skip_llm": True,
                    "reply": "MOA知识库尚未就绪"}

        # 检测是否要查看原文（二级检索）
        want_raw = any(kw in text for kw in ["详细", "原文", "原始", "原话", "具体", "展开"])
        # 去掉 trigger 词，避免干扰搜索
        if want_raw:
            query = re.sub(r"详细|展开|原话|原文|原始|具体", "", query).strip()

        try:
            if want_raw:
                result = self._search_raw(query)
            else:
                # 先查一级摘要
                result = self._search_summary(query)
                # 一级没查到，自动降级到二级原文
                if not result:
                    result = self._search_raw(query)
                # 二级还没查到，直接按日期搜 chat.md
                if not result:
                    result = self._search_chatmd_direct(query)

            if result:
                # 直接生成 TTS 口语回复和卡片内容，不走 LLM（DeepSeek 余额不足）
                tts_text, card_text = self._format_reply(result, want_raw)
                return {"context": card_text, "action": None, "skip_llm": True,
                        "reply": tts_text}
            else:
                return {"context": "", "action": None, "skip_llm": True,
                        "reply": f"没有找到关于「{query}」的MOA聊天记录"}
        except Exception as e:
            return {"context": "", "action": None, "skip_llm": True,
                    "reply": f"MOA查询失败: {e}"}

    def _format_reply(self, result_text: str, is_raw: bool) -> tuple:
        """将检索结果格式化为 (tts_text, card_text)"""
        lines = [l.strip() for l in result_text.split("\n") if l.strip()]
        if not lines:
            return ("没有找到相关记录", "没有找到相关记录")

        # 提取摘要行
        items = []
        for l in lines:
            if l.startswith("●"):
                # 格式: ● [群名] 日期 | 话题
                #      摘要: xxx
                #      决策: xxx
                items.append(l)
        
        if is_raw:
            count = len([l for l in lines if "📁" in l])
            tts_text = f"找到{count}条原始聊天记录"
            if items:
                first = items[0].replace("●", "").replace("[", "").split("]")[0].strip()
                tts_text += f"，来自{first}的聊天"
        else:
            count = len(items)
            if count == 0:
                tts_text = "找到相关记录"
            else:
                # 第一条摘要概要
                first = items[0]
                # 提取群名
                name_match = re.search(r'\[([^\]]+)\]', first)
                name = name_match.group(1) if name_match else ""
                # 提取话题
                topic = first.split("|")[-1].strip() if "|" in first else ""
                tts_parts = [f"找到{count}条记录"]
                if name:
                    tts_parts.append(f"来自{name}")
                if topic:
                    tts_parts.append(f"关于{topic}")
                tts_text = "，".join(tts_parts)
                if count > 1:
                    # 再提第二条
                    second = items[1] if len(items) > 1 else None
                    if second:
                        name2 = re.search(r'\[([^\]]+)\]', second)
                        if name2 and name2.group(1) != name:
                            tts_text += f"，还有{name2.group(1)}"
        
        tts_text = tts_text.strip("。，") + "。"
        return (tts_text, result_text)

    def _clean_query(self, text: str) -> str:
        """清洗查询文本"""
        return re.sub(
            r"查查|查一下|查看|查询一下|帮我|搜一下|翻一下|看看|找找|MOA|moa|聊天|记录|的|关于|[，。！？、；：.,!?;:（）【】《》]",
            "", text
        ).strip()

    def _search_chatmd_direct(self, query: str, max_dirs: int = 20) -> str:
        """三级检索：直接扫描最近 chat.md 文件全文"""
        import os
        from datetime import datetime, timedelta

        export_dir = MOA_CHATS_DIR
        if not export_dir.exists():
            return ""

        # 获取所有子目录（按修改时间倒序）
        dirs = [d for d in export_dir.iterdir() if d.is_dir() and (d / 'chat.md').exists()]
        dirs.sort(key=lambda d: (d / 'chat.md').stat().st_mtime, reverse=True)
        dirs = dirs[:max_dirs]

        # 解析查询
        tokens = re.split(r'[\s,，、]+', query)
        keywords = []
        for t in tokens:
            subtokens = re.split(r'(?<=[a-zA-Z0-9])(?=[\u4e00-\u9fff])|(?<=[\u4e00-\u9fff])(?=[a-zA-Z0-9])', t)
            for st in subtokens:
                st = st.strip()
                if not st or len(st) < 2:
                    continue
                keywords.append(st.lower())
        if not keywords:
            keywords = [query]

        today = datetime.now().strftime("%Y-%m-%d")
        results = []

        for d in dirs:
            chat_name = d.name
            chat_md = d / "chat.md"
            raw_text = chat_md.read_text(encoding="utf-8", errors="ignore")

            # 匹配关键词
            raw_lower = raw_text.lower()
            if not any(kw.lower() in raw_lower for kw in keywords):
                continue

            # 提取今天或最近的消息
            date_blocks = re.split(r"^## ", raw_text, flags=re.MULTILINE)
            for block in date_blocks:
                block = block.strip()
                if not block:
                    continue
                first_line = block.split(chr(10))[0].strip()
                date_str = first_line
                # 只取今天或昨天的
                if today not in date_str:
                    continue

                # 提取消息
                msgs = []
                for line in block.split(chr(10))[1:]:
                    mm = re.match(r"^-\s+\*\*([^*]+)\*\*\s+[\d:]+\s*:\s*(.*)", line)
                    if mm:
                        person = mm.group(1).strip()
                        msg_text = mm.group(2).strip()
                        if person not in ("1252000199",) and not msg_text.startswith("["):
                            # 检查是否匹配关键词
                            if any(kw in msg_text.lower() or kw in person.lower() for kw in keywords):
                                msgs.append(f"    {person}: {msg_text}")

                if msgs:
                    results.append(f"  📁 {chat_name} ({date_str}):")
                    results.extend(msgs[:5])

        if not results:
            return ""

        header = f"【MOA聊天记录直接搜索（{len(results)}条）】"
        return chr(10).join([header] + results[:30])

    def _search_summary(self, query: str, limit: int = 8) -> str:
        """一级检索：分词模糊搜索"""
        conn = sqlite3.connect(str(MOA_DB))
        conn.row_factory = sqlite3.Row

        # 拆成单个关键词
        tokens = re.split(r'[\s,，、]+', query)
        keywords = []
        for t in tokens:
            # 按中英文边界拆
            subtokens = re.split(r'(?<=[a-zA-Z0-9])(?=[\u4e00-\u9fff])|(?<=[\u4e00-\u9fff])(?=[a-zA-Z0-9])', t)
            for st in subtokens:
                st = st.strip()
                if not st:
                    continue
                if len(st) >= 2:
                    keywords.append(st)
                # 单个字母数字不参与搜索
        # 对纯中文长词拆2-gram，如"说李刚"→"李刚"
        extra = []
        for kw in keywords:
            if all('\u4e00' <= c <= '\u9fff' for c in kw) and len(kw) >= 3:
                for i in range(len(kw) - 1):
                    extra.append(kw[i:i+2])
        keywords.extend(extra)
        # 去重保留顺序
        seen = set()
        keywords = [k for k in keywords if not (k in seen or seen.add(k))]
        if not keywords:
            keywords = [query]

        conditions = []
        params = []
        for kw in keywords:
            like = f"%{kw}%"
            conditions.append("(summary LIKE ? OR topic LIKE ? OR decisions LIKE ?)")
            params.extend([like, like, like])

        sql = f"SELECT chat_name, date, summary, topic, decisions, action_items, people "
        sql += f"FROM segments WHERE {' OR '.join(conditions)} "
        sql += f"ORDER BY id DESC LIMIT ?"
        params.append(limit)

        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return ""

        parts = [f"【MOA聊天记录检索结果（{len(rows)}条）】"]
        for r in rows:
            chat_name = r["chat_name"] or "?"
            date = r["date"] or "?"
            summary = (r["summary"] or "")[:80]
            topic = r["topic"] or ""
            decisions = r["decisions"] or ""
            actions = r["action_items"] or ""

            line = f"  ● [{chat_name}] {date}"
            if topic:
                line += f" | {topic}"
            line += f"\n    摘要: {summary}"
            if decisions:
                line += f"\n    决策: {decisions[:80]}"
            if actions:
                line += f"\n    待办: {actions[:80]}"
            parts.append(line)

        return chr(10).join(parts)

    def _search_raw(self, query: str) -> str:
        """二级检索：从原始聊天文件提取原文"""
        conn = sqlite3.connect(str(MOA_DB))
        conn.row_factory = sqlite3.Row
        # 拆成单个关键词
        tokens = re.split(r'[\s,，、]+', query)
        keywords = []
        for t in tokens:
            # 按中英文边界拆
            subtokens = re.split(r'(?<=[a-zA-Z0-9])(?=[\u4e00-\u9fff])|(?<=[\u4e00-\u9fff])(?=[a-zA-Z0-9])', t)
            for st in subtokens:
                st = st.strip()
                if not st:
                    continue
                if len(st) >= 2:
                    keywords.append(st)
                # 单个字母数字不参与搜索
        # 对纯中文长词拆2-gram，如"说李刚"→"李刚"
        extra = []
        for kw in keywords:
            if all('\u4e00' <= c <= '\u9fff' for c in kw) and len(kw) >= 3:
                for i in range(len(kw) - 1):
                    extra.append(kw[i:i+2])
        keywords.extend(extra)
        # 去重保留顺序
        seen = set()
        keywords = [k for k in keywords if not (k in seen or seen.add(k))]
        if not keywords:
            keywords = [query]

        conditions = []
        params = []
        for kw in keywords:
            like = f"%{kw}%"
            conditions.append("(summary LIKE ? OR topic LIKE ? OR decisions LIKE ?)")
            params.extend([like, like, like])

        sql = f"SELECT chat_id, chat_name, date, summary FROM segments "
        sql += f"WHERE {' OR '.join(conditions)} ORDER BY id DESC LIMIT 3"
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return ""

        parts = [f"【MOA聊天原文（{len(rows)}条）】"]
        for r in rows:
            chat_id = r["chat_id"]
            chat_name = r["chat_name"] or "?"
            date = r["date"] or ""

            # 读取原始 chat.md
            chat_path = MOA_CHATS_DIR / chat_id / "chat.md"
            if not chat_path.exists():
                parts.append(f"  [{chat_name}] {date} — 原文文件不存在")
                continue

            raw_text = chat_path.read_text(encoding="utf-8", errors="ignore")

            # 提取该日期的消息
            date_block = ""
            in_date = False
            for line in raw_text.split("\n"):
                if line.startswith(f"## {date}"):
                    in_date = True
                    continue
                if in_date:
                    if line.startswith("## ") and not line.startswith(f"## {date}"):
                        break
                    # 过滤系统消息
                    mm = re.match(r"^-\s+\*\*([^*]+)\*\*\s+[\d:]+\s*:\s*(.*)", line)
                    if mm:
                        person = mm.group(1).strip()
                        msg = mm.group(2).strip()
                        if person not in ("1252000199",) and not msg.startswith("["):
                            date_block += f"  {person}: {msg}\n"

            if date_block:
                parts.append(f"\n  📁 {chat_name} ({date}):")
                parts.append(date_block.strip())
            else:
                parts.append(f"\n  [{chat_name}] {date} — 该日期无有效文本消息")

        return chr(10).join(parts)
