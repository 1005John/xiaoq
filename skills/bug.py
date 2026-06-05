"""
skills/bug.py — 缺陷查询与处理技能

实时查询灵畿平台上傅强负责的非关闭缺陷。
根据查询的产品型号筛选缺陷（从缺陷详情的固件版本中提取型号），
并从邮件知识库补充相关讨论。
支持语音标记完成（自动调用 lc bug update-status 流转状态）。
"""

import json
import logging
import re
import subprocess

from skills.base import Skill, SkillResult, SideEffect

log = logging.getLogger("skills.bug")

WORKSPACE = "CMIOTonemoredcap"
EMAIL_KB_SCRIPT = "/home/johnf/.hermes/skills/email/email-knowledge/query.py"

# 产品名简写 → 全名（与 query.py 保持一致）
PRODUCT_SHORT_CODES = {
    "307C": "ML307C", "307H": "ML307H", "307X": "ML307X", "307N": "ML307N",
    "38022": "MR380R", "3802": "MR380R", "380R": "MR380R", "380": "MR380R",
}
_PRODUCT_SORTED = sorted(PRODUCT_SHORT_CODES.items(), key=lambda x: -len(x[0]))


def expand_product(query: str) -> str:
    """扩展产品简写：307C → ML307C"""
    for short, full in _PRODUCT_SORTED:
        if query.startswith(short):
            rest = query[len(short):]
            if not full.startswith(query):
                return full + rest
    return query


def extract_product_model(text: str) -> str:
    """从文本中提取产品型号全名，如 '307C测试进展' → 'ML307C'"""
    for short, full in _PRODUCT_SORTED:
        if short in text:
            return full
    return ""


def fetch_bugs(workspace: str = WORKSPACE) -> list:
    """实时获取当前用户的非关闭缺陷"""
    try:
        cmd = ["lc", "bug", "list", "-l", "50", "-w", workspace]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            items = data.get("data", {}).get("items") or []
            return [b for b in items if b.get("status") != "已关闭" and "傅强" in (b.get("handlerName") or "")]
    except Exception as e:
        log.warning(f"fetch_bugs error: {e}")
    return []


def fetch_bug_detail(bug_id: str) -> dict:
    """获取单个缺陷的详细信息（含 remark 字段里的固件版本）"""
    try:
        cmd = ["lc", "bug", "view", bug_id, "-w", WORKSPACE, "--pretty"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            return data.get("data", {})
    except Exception as e:
        log.warning(f"fetch_bug_detail error for {bug_id}: {e}")
    return {}


def get_bug_product_model(bug: dict) -> str:
    """从缺陷详情的 remark 字段中提取产品型号"""
    # 先从基本信息里查
    detail = bug
    if "remark" not in bug or not bug.get("remark"):
        # 需要拉取详情
        detail = fetch_bug_detail(bug.get("id", ""))
    remark = detail.get("remark", "") or ""
    # remark 格式示例: "固件版本: ML307C-DC-CN_4.0.14..."
    m = re.search(r"(ML307[HCNX]|MR380R)[-\w]*", remark)
    if m:
        return m.group(1)
    return ""


def fetch_related_emails(query: str) -> tuple:
    """从邮件知识库 SQLite 直接查询邮件标题（不调LLM，快速）"""
    import sqlite3
    from pathlib import Path
    db_path = Path.home() / ".hermes" / "skills" / "email" / "email-knowledge" / "data" / "emails.db"
    if not db_path.exists():
        return 0, []
    try:
        conn = sqlite3.connect(str(db_path))
        expanded = expand_product(query)
        cleaned = __import__("re").sub(r"查查|查一下|查询一下|帮我|搜一下|找一下|翻一下|看看|找找|发的|邮件|关于|[，。！？、；：.,!?;:（）【】《》]", "", expanded).strip()
        if cleaned:
            expanded = cleaned
        # LIKE 搜索 summary/topic/subject
        like = f"%{expanded}%"
        cur = conn.execute("""
            SELECT date, subject, summary FROM emails
            WHERE summary LIKE ? OR topic LIKE ? OR subject LIKE ?
            ORDER BY date DESC LIMIT 10
        """, (like, like, like))
        rows = cur.fetchall()
        conn.close()
        if not rows:
            return 0, []
        lines = []
        for r in rows:
            lines.append(f"[{r[0]}] {r[2][:60]}")
        return len(rows), lines[:8]
    except Exception as e:
        log.warning(f"fetch_related_emails direct error: {e}")
        return 0, []


class BugSkill(Skill):
    """灵畿平台缺陷查询与处理技能 — 按产品型号筛选 + 邮件补充"""

    name = "bug"
    description = "灵畿平台缺陷查询"

    def __init__(self, cfg: dict = None):
        super().__init__(cfg)
        self.workspace = (cfg or {}).get("lingji_workspace", WORKSPACE)
        self._last_items = []

    def _list_bugs(self, asr_text: str = "") -> SkillResult:
        product_model = extract_product_model(asr_text)
        model_display = product_model or "全部"

        bugs = fetch_bugs(self.workspace)

        # 按产品型号筛选缺陷（从 remark 固件版本中提取型号）
        if product_model:
            filtered = []
            for b in bugs:
                b_model = get_bug_product_model(b)
                if b_model and b_model.lower() == product_model.lower():
                    filtered.append(b)
            bugs = filtered
        # else: 无型号时显示全部缺陷

        self._last_items = bugs[:]
        card_lines = []
        bug_count = len(bugs)

        # ── 并行：邮件查询（后台线程） ──
        search_query = product_model or asr_text
        email_result = {"count": 0, "summary": []}

        def _do_email():
            if search_query:
                c, s = fetch_related_emails(search_query)
                email_result["count"] = c
                email_result["summary"] = s

        import threading
        email_thread = threading.Thread(target=_do_email, daemon=True)
        email_thread.start()

        # ── 缺陷列表（主线程） ──
        if bug_count > 0:
            card_lines.append("╔══ 灵畿缺陷 ══╗")
            for i, b in enumerate(bugs, 1):
                title = b.get("defectName", "?")[:45]
                status = b.get("status", "?")
                card_lines.append(f"{i}. {title} [{status}]")
        elif product_model:
            card_lines.append(f"(没有 {product_model} 相关的缺陷)")

        # 等待邮件查询完成
        email_thread.join(timeout=30)
        email_count = email_result["count"]
        email_summary = email_result["summary"]

        # ── 邮件知识库补充 ──
        if email_count > 0 and email_summary:
            if bug_count > 0:
                card_lines.append("")
            card_lines.append("╔══ 邮件相关讨论 ══╗")
            card_lines.extend(email_summary[:12])

        # TTS
        tts_parts = []
        if bug_count > 0:
            tts_parts.append(f"{bug_count}个缺陷")
        if email_count > 0:
            tts_parts.append(f"{email_count}封相关邮件")

        if tts_parts:
            tts = f"{model_display}：找到{'，'.join(tts_parts)}"
        else:
            tts = f"没有找到 {model_display} 相关的记录"

        title = f"{model_display}"
        if bug_count > 0 or email_count > 0:
            title += f" ({bug_count}缺陷 {email_count}邮件)"

        return SkillResult(
            success=True, data={"bugs": bugs, "email_count": email_count},
            side_effects=[
                SideEffect("card_show", {
                    "title": title,
                    "lines": card_lines,
                    "card_type": "todo",
                }),
                SideEffect("voice_tts", {"text": tts}),
            ],
        )

    def _mark_done(self, idx: int) -> SkillResult:
        if idx <= 0 or not self._last_items or idx > len(self._last_items):
            return SkillResult(
                success=True,
                side_effects=[SideEffect("voice_tts", {"text": "请说完成第几个"})],
            )

        item = self._last_items[idx - 1]
        defect_id = item.get("id", "")

        if not defect_id:
            return SkillResult(
                success=False,
                side_effects=[SideEffect("voice_tts", {"text": f"第{idx}项无法识别缺陷ID"})],
            )

        try:
            subprocess.run(["lc", "readonly", "off", "--duration", "5m"],
                           capture_output=True, timeout=10)
            cur_status = item.get("status", "")
            if "待修复" in cur_status:
                target_status = "1642790711574196230"
                tts_msg = "已更新为待验证"
            elif "待验证" in cur_status:
                target_status = "1642790711574196226"
                tts_msg = "已更新为已关闭"
            else:
                target_status = "1642790711574196230"
                tts_msg = "已更新"

            cmd = ["lc", "bug", "update-status", defect_id, target_status, "-w", self.workspace]
            sp_result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if sp_result.returncode == 0:
                return SkillResult(
                    success=True,
                    side_effects=[SideEffect("voice_tts", {"text": f"第{idx}项缺陷{tts_msg}"})],
                )
            else:
                return SkillResult(
                    success=False,
                    side_effects=[SideEffect("voice_tts", {"text": "缺陷状态更新失败"})],
                )
        except Exception as e:
            log.warning(f"Bug update error: {e}")
            return SkillResult(
                success=False,
                side_effects=[SideEffect("voice_tts", {"text": "缺陷状态更新失败"})],
            )

    def execute(self, params: dict = None) -> SkillResult:
        params = params or {}
        action = params.get("action", "list")
        asr_text = params.get("_asr_text", "")
        idx = params.get("index", 0)

        if action == "mark_done" or "完成" in asr_text:
            if idx == 0 and asr_text:
                m = re.search(r'第([一二三四五六七八九十0-9]+)[个项条]|([0-9]+).*完成', asr_text)
                if m:
                    cn = m.group(1) or m.group(2)
                    cn_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
                              "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
                    idx = cn_map.get(cn, int(cn) if cn.isdigit() else 0)
            if idx > 0:
                return self._mark_done(idx)

        return self._list_bugs(asr_text=asr_text)