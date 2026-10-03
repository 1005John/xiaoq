"""
skills/name_corrector.py — ASR 人名纠错

将 ASR 识别错误的同音人名纠正为正确写法。
例如: "曹保单发的邮件" → "曹宝丹发的邮件"
"""

import json
import logging
from pathlib import Path

log = logging.getLogger("name_corrector")

_DATA_PATH = Path(__file__).parent / "name_corrector_data.json"
_CHAR_PY = {}
_NAMES = []
_ASR_FIX = {}  # 拼音变体 → 正确人名


def _load():
    global _CHAR_PY, _NAMES, _ASR_FIX
    if _ASR_FIX:
        return
    try:
        with open(_DATA_PATH, encoding="utf-8") as f:
            data = json.load(f)
        _CHAR_PY = data.get("char_pinyin", {})
        _NAMES = data.get("names", [])
        _ASR_FIX = data.get("asr_fix", {})
        log.info(f"人名纠错加载: {len(_NAMES)} 个人名, {len(_ASR_FIX)} 条纠错")
    except Exception as e:
        log.warning(f"人名纠错加载失败: {e}")


def _window_pinyin(text: str, start: int, length: int) -> str:
    """取文本中一段窗口的拼音"""
    parts = []
    for i in range(start, min(start + length, len(text))):
        ch = text[i]
        parts.append(_CHAR_PY.get(ch, ch))
    return " ".join(parts)


def correct(text: str) -> str:
    """纠正 ASR 文本中的人名
    
    对文本中每个 2~3 字窗口做拼音匹配，命中已知人名则替换。
    """
    _load()
    if not _ASR_FIX:
        return text

    result = text
    length = len(text)

    # 从长到短匹配（3字名优先）
    for name_len in [3, 2]:
        i = 0
        while i <= length - name_len:
            window = text[i:i + name_len]
            window_py = _window_pinyin(text, i, name_len)
            
            # 直接查纠错映射
            correct_name = _ASR_FIX.get(window_py)
            if correct_name and window != correct_name:
                result = result[:i] + correct_name + result[i + name_len:]
                log.info(f"人名纠错: '{window}' → '{correct_name}'")
                i += name_len
            else:
                i += 1

    return result
