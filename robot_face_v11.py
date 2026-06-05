import faulthandler; faulthandler.enable()
#!/usr/bin/env python3
"""
桌面机器人面部表情系统 v10 - 霓虹赛博风格 (Neon Cyber)
基于v9新增: StyleConfig风格配置 + 霓虹几何眼 + 线条嘴 + 6色情绪映射 + 扫描线/Glitch
向下兼容: 无素材目录时自动回退纯矢量模式
"""

import pygame
import pygame.freetype
import math
import random
import sys
import asyncio
import threading
import json
import time
import enum
import datetime
import os
import websockets
import wave, struct, subprocess as _subprocess
import socket
from gimbal_driver import GimbalController
from skills.data_collector import DataCollector
from skills.name_corrector import correct
import dashscope
from dashscope.audio.asr import Recognition
from dashscope.audio.tts import SpeechSynthesizer, ResultCallback as _TTSResultCallback
import logging
import os as _log_os
_log_dir = _log_os.path.join(_log_os.path.dirname(_log_os.path.abspath(__file__)), "logs")
_log_os.makedirs(_log_dir, exist_ok=True)
_log_fh = logging.FileHandler(_log_os.path.join(_log_dir, "v10_{}.log".format(__import__("datetime").datetime.now().strftime("%Y%m%d"))))
_log_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"))
logging.basicConfig(level=logging.INFO, handlers=[_log_fh], format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("v10")


# ── 配置 ──
WIDTH, HEIGHT = 1280, 720
FPS = 60
CARD_WIDTH = WIDTH // 2  # 640

# ═══════════════════════════════════════════════════════
# v10: 风格配置系统 — 霓虹赛博配色
# ═══════════════════════════════════════════════════════
class StyleConfig:
    """v10: 霓虹赛博风格配置 — 所有颜色/尺寸/效果统一管理
    6色情绪映射：电光青(happy) / 霓虹粉(love) / 琥珀金(surprise) /
                赛博红(angry) / 紫外紫(fear) / 数字蓝(sad)
    """
    # ── 基础色 ──
    BG_COLOR     = (10, 10, 15)           # 深空黑 #0A0A0F
    BG_COLOR_RGB = (10, 10, 15)

    # ── 6色情绪霓虹 ──
    NEON_CYAN    = (0, 255, 255)          # 电光青 — happy
    NEON_PINK    = (255, 50, 150)         # 霓虹粉 — love
    NEON_AMBER   = (255, 191, 0)          # 琥珀金 — surprise
    NEON_RED     = (255, 30, 30)          # 赛博红 — angry
    NEON_PURPLE  = (160, 50, 255)         # 紫外紫 — fear
    NEON_BLUE    = (50, 120, 255)         # 数字蓝 — sad

    # 默认/idle色
    NEON_DEFAULT = (80, 180, 255)         # 默认霓虹蓝

    # ── 表情→霓虹色映射 ──
    EXPR_NEON_MAP = {
        "idle": (80, 180, 255),
        "happy": (0, 255, 255),
        "laugh": (0, 255, 200),
        "excited": (255, 220, 0),
        "smile": (100, 230, 255),
        "relaxed": (80, 180, 255),
        "sad": (50, 120, 255),
        "angry": (255, 30, 30),
        "surprised": (255, 191, 0),
        "scared": (160, 50, 255),
        "sleepy": (60, 60, 140),
        "bored": (80, 130, 180),
        "curious": (100, 200, 255),
        "thinking": (80, 160, 255),
        "confused": (200, 100, 255),
        "speaking": (80, 220, 255),
        "blink": (80, 180, 255),
        "wink": (80, 180, 255),
        "look_left": (80, 180, 255),
        "look_right": (80, 180, 255),
        "look_up": (80, 180, 255),
        "heart_eyes": (255, 50, 150),
        "star_eyes": (255, 220, 0),
    }

    # ── 渲染常量 ──
    EYE_OUTLINE_COLOR = (0, 200, 200, 120)   # 霓虹描边(半透明青)
    PUPIL_COLOR       = (0, 0, 0)             # 纯黑瞳孔
    HIGHLIGHT_COL     = (255, 255, 255)       # 高光白
    BROW_COLOR        = None                  # 眉毛色=None表示跟随霓虹色
    BLUSH_COLOR       = (255, 50, 150, 120)   # 霓虹粉腮红

    # ── 扫描线 ──
    SCANLINE_COLOR    = (0, 255, 255, 8)      # 极淡扫描线
    SCANLINE_GAP      = 3                      # 每3px一条线
    SCANLINE_SPEED    = 80                      # 扫描线滚动速度(px/s)

    # ── Glitch ──
    GLITCH_INTERVAL_MIN = 8.0                  # 最小Glitch间隔(秒)
    GLITCH_INTERVAL_MAX = 25.0                 # 最大Glitch间隔
    GLITCH_DURATION     = 0.15                 # 单次Glitch持续(秒)
    GLITCH_INTENSITY    = 12                    # Glitch偏移像素

    # ── 霓虹外发光 ──
    BLOOM_LAYERS    = 0                         # 发光层数(关闭)
    BLOOM_SPREAD    = 1.8                       # 发光扩散系数

    # ── 卡片(保留暗色调) ──
    CARD_BG     = (12, 15, 30, 230)
    CARD_BORDER = (0, 200, 200, 100)
    CARD_TEXT   = (180, 210, 240)
    CARD_TITLE  = (0, 255, 255)
    CARD_HINT   = (80, 100, 120)

    # ── 嘴型 ──
    MOUTH_COLOR     = None                      # None=跟随霓虹色
    MOUTH_THICKNESS = 4                          # 线条粗细(加厚)
    MOUTH_WIDTH     = 0.65                       # 嘴宽占spacing比例(加宽)

    @classmethod
    def get_neon_color(cls, expr_name):
        """根据表情名获取霓虹色"""
        return cls.EXPR_NEON_MAP.get(expr_name, cls.NEON_DEFAULT)

    @classmethod
    def dim_color(cls, color, factor=0.3):
        """调暗霓虹色(用于发光外圈)"""
        return tuple(max(0, min(255, int(c * factor))) for c in color[:3])

# 兼容旧引用
BG_COLOR = StyleConfig.BG_COLOR
EYE_COLOR = StyleConfig.NEON_DEFAULT
CARD_BG = StyleConfig.CARD_BG
CARD_BORDER = StyleConfig.CARD_BORDER
CARD_TEXT = StyleConfig.CARD_TEXT
CARD_TITLE = StyleConfig.CARD_TITLE
CARD_HINT = StyleConfig.CARD_HINT

# ── 表情参数 ──
class Params:
    """v8: 扩展13参数 — 新增pupil_scale/highlight/brow_l/brow_r/blush"""
    __slots__ = ('l_open', 'r_open', 'l_w', 'r_w', 'l_y', 'r_y', 'l_cut', 'r_cut',
                 'pupil_scale', 'highlight', 'brow_l', 'brow_r', 'blush')
    def __init__(self, l_open=1, r_open=1, l_w=1, r_w=1, l_y=0, r_y=0,
                 l_cut=0, r_cut=0, pupil_scale=1.0, highlight=0.7,
                 brow_l=0, brow_r=0, blush=0):
        self.l_open = l_open; self.r_open = r_open
        self.l_w = l_w; self.r_w = r_w
        self.l_y = l_y; self.r_y = r_y
        self.l_cut = l_cut; self.r_cut = r_cut
        self.pupil_scale = pupil_scale; self.highlight = highlight
        self.brow_l = brow_l; self.brow_r = brow_r; self.blush = blush

    def lerp(self, target, speed):
        """指数衰减插值(向后兼容)"""
        s = speed
        self.l_open += (target.l_open - self.l_open) * s
        self.r_open += (target.r_open - self.r_open) * s
        self.l_w += (target.l_w - self.l_w) * s
        self.r_w += (target.r_w - self.r_w) * s
        self.l_y += (target.l_y - self.l_y) * s
        self.r_y += (target.r_y - self.r_y) * s
        self.l_cut += (target.l_cut - self.l_cut) * s
        self.r_cut += (target.r_cut - self.r_cut) * s
        self.pupil_scale += (target.pupil_scale - self.pupil_scale) * s
        self.highlight += (target.highlight - self.highlight) * s
        self.brow_l += (target.brow_l - self.brow_l) * s
        self.brow_r += (target.brow_r - self.brow_r) * s
        self.blush += (target.blush - self.blush) * s

    def ease_lerp(self, target, t_eased):
        """基于easing进度t(0~1)的线性插值 — 配合过渡规则使用
        注意: 此方法从self当前值向target插值，t_eased=0时不变，t_eased=1时=target
        适合从快照起点调用: start.ease_lerp(target, t_eased)
        """
        self.l_open = self.l_open + (target.l_open - self.l_open) * t_eased
        self.r_open = self.r_open + (target.r_open - self.r_open) * t_eased
        self.l_w = self.l_w + (target.l_w - self.l_w) * t_eased
        self.r_w = self.r_w + (target.r_w - self.r_w) * t_eased
        self.l_y = self.l_y + (target.l_y - self.l_y) * t_eased
        self.r_y = self.r_y + (target.r_y - self.r_y) * t_eased
        self.l_cut = self.l_cut + (target.l_cut - self.l_cut) * t_eased
        self.r_cut = self.r_cut + (target.r_cut - self.r_cut) * t_eased
        self.pupil_scale = self.pupil_scale + (target.pupil_scale - self.pupil_scale) * t_eased
        self.highlight = self.highlight + (target.highlight - self.highlight) * t_eased
        self.brow_l = self.brow_l + (target.brow_l - self.brow_l) * t_eased
        self.brow_r = self.brow_r + (target.brow_r - self.brow_r) * t_eased
        self.blush = self.blush + (target.blush - self.blush) * t_eased

    def copy(self):
        return Params(self.l_open, self.r_open, self.l_w, self.r_w,
                       self.l_y, self.r_y, self.l_cut, self.r_cut,
                       self.pupil_scale, self.highlight,
                       self.brow_l, self.brow_r, self.blush)

    def is_close(self, target, eps=0.005):
        return (abs(self.l_open - target.l_open) < eps and
                abs(self.r_open - target.r_open) < eps and
                abs(self.l_w - target.l_w) < eps and
                abs(self.r_w - target.r_w) < eps and
                abs(self.l_y - target.l_y) < eps and
                abs(self.r_y - target.r_y) < eps and
                abs(self.l_cut - target.l_cut) < eps and
                abs(self.r_cut - target.r_cut) < eps and
                abs(self.pupil_scale - target.pupil_scale) < eps and
                abs(self.highlight - target.highlight) < eps and
                abs(self.brow_l - target.brow_l) < eps and
                abs(self.brow_r - target.brow_r) < eps and
                abs(self.blush - target.blush) < eps)

P = Params


# ═══ 人格参数系统 ═══
class Personality:
    """6维人格参数 - 影响NPC行为概率和幅度"""
    __slots__ = ('activity_level', 'initiative_level', 'empathy_level',
                 'expressiveness', 'patience_level', 'talkativeness')

    def __init__(self, activity_level=0.5, initiative_level=0.5, empathy_level=0.5,
                 expressiveness=0.5, patience_level=1.0, talkativeness=0.5):
        self.activity_level = activity_level
        self.initiative_level = initiative_level
        self.empathy_level = empathy_level
        self.expressiveness = expressiveness
        self.patience_level = patience_level
        self.talkativeness = talkativeness

    @classmethod
    def gentle(cls):
        """温柔陪伴型"""
        return cls(activity_level=0.4, initiative_level=0.3, empathy_level=0.8,
                   expressiveness=0.5, patience_level=1.2, talkativeness=0.4)

    @classmethod
    def energetic(cls):
        """元气活跃型"""
        return cls(activity_level=0.8, initiative_level=0.7, empathy_level=0.5,
                   expressiveness=0.9, patience_level=0.6, talkativeness=0.8)

    def __repr__(self):
        return (f"Personality(act={self.activity_level:.1f} ini={self.initiative_level:.1f} "
                f"emp={self.empathy_level:.1f} exp={self.expressiveness:.1f} "
                f"pat={self.patience_level:.1f} tal={self.talkativeness:.1f})")


# ═══ NPC状态枚举 ═══
class NPCState(enum.Enum):
    IDLE = "idle"
    OBSERVE = "observe"
    ENGAGED = "engaged"
    WARN = "warn"
    SLEEP = "sleep"

# ═══ ESP Emotion Matrix 表情预设 (v8: +pupil/highlight/brow/blush) ═══
# P(l_open, r_open, l_w, r_w, l_y, r_y, l_cut, r_cut, pupil_scale, highlight, brow_l, brow_r, blush)
HAPPY      = P(1.0, 1.0, 1.1, 1.1, -5, -5, 0.55, 0.55,  1.2, 0.9, -3, -3, 0.5)    # 瞳孔放大+高光强+眉上扬+腮红
LAUGH      = P(1.0, 1.0, 1.2, 1.2, -8, -8, 0.65, 0.65,  1.3, 1.0, -5, -5, 0.7)    # 大瞳孔+强光+眉高扬+强腮红
EXCITED    = P(1.3, 1.3, 1.0, 1.0, -5, -5, 0, 0,          1.4, 1.0, -4, -4, 0.3)   # 最大瞳孔+强光
ANGRY      = P(0.7, 0.7, 1.2, 1.2, 8, 8, 0, 0,            0.6, 0.3, 8, 8, 0)       # 小瞳孔+弱光+眉下压
SURPRISE   = P(1.5, 1.5, 1.1, 1.1, -10, -10, 0, 0,        0.5, 0.95, -8, -8, 0)    # 小瞳孔+强光分裂+眉高耸
SCARED     = P(1.3, 1.0, 0.9, 1.3, -8, -5, 0, 0,          0.7, 0.4, -5, 5, 0)      # 中瞳孔+弱光+不对称眉
SMILE      = P(0.85, 0.85, 1.0, 1.0, 0, 0, 0.25, 0.25,    1.1, 0.8, -1, -1, 0.3)   # 轻度瞳孔+腮红
RELAXED    = P(0.8, 0.8, 1.0, 1.0, 0, 0, 0, 0,            0.9, 0.5, 0, 0, 0)       # 中瞳孔+柔光
SAD        = P(0.5, 0.5, 1.0, 1.0, 5, 5, 0, 0,            0.7, 0.3, 5, 5, 0)       # 小瞳孔+弱光+眉下垂
SLEEPY     = P(0.15, 0.15, 1.0, 1.0, 0, 0, 0, 0,          0.5, 0.15, 2, 2, 0)      # 极小瞳孔+极弱光+眉松
BORED      = P(0.4, 0.6, 1.0, 0.8, 3, 0, 0, 0,            0.8, 0.3, 3, -1, 0)      # 中瞳孔+弱光+不对称
IDLE_P     = P(1.0, 1.0, 1.0, 1.0, 0, 0, 0, 0,            1.0, 0.7, 0, 0, 0)       # 标准瞳孔+标准光
CURIOUS    = P(1.2, 0.8, 1.1, 0.9, -5, 2, 0, 0,           1.3, 0.8, -3, 2, 0)      # 大瞳孔+中光+好奇眉
THINK      = P(0.8, 0.5, 0.9, 0.7, -2, 3, 0, 0,           0.8, 0.4, 2, 6, 0)       # 中瞳孔+弱光+思考眉
CONFUSED   = P(1.0, 0.6, 1.0, 0.8, 0, 3, 0, 0,            0.9, 0.5, -2, 5, 0)      # 中瞳孔+不对称眉
BLINK      = P(0.0, 0.0, 1.0, 1.0, 0, 0, 0, 0,            1.0, 0, 0, 0, 0)         # 闭眼无瞳孔/高光
WINK       = P(1.0, 0.0, 1.1, 1.0, -2, 0, 0, 0,           1.1, 0.8, -2, 0, 0.2)    # 左眼瞳孔大+腮红
LOOK_L     = P(1.0, 1.0, 1.15, 0.85, -2, -2, 0, 0,        1.0, 0.7, 0, 0, 0)
LOOK_R     = P(1.0, 1.0, 0.85, 1.15, -2, -2, 0, 0,        1.0, 0.7, 0, 0, 0)
LOOK_U     = P(1.1, 1.1, 0.9, 0.9, -10, -10, 0, 0,        1.0, 0.7, -2, -2, 0)

# 瞳孔特殊形态预设
HEART_EYES = P(1.2, 1.2, 1.1, 1.1, -5, -5, 0.4, 0.4,     1.0, 0.9, -3, -3, 0.8)   # 爱心瞳孔
STAR_EYES  = P(1.3, 1.3, 1.0, 1.0, -5, -5, 0, 0,          1.0, 1.0, -4, -4, 0.3)   # 星星瞳孔

# ── 分段动画定义 ──
EXPRESSIONS = {
    "happy": {
        "intro_target": HAPPY, "intro_speed": 0.15,
        "loop_target": HAPPY, "loop_duration": 3.0,
        "tail_target": IDLE_P, "tail_speed": 0.10,
    },
    "laugh": {
        "intro_target": LAUGH, "intro_speed": 0.12,
        "loop_target": LAUGH, "loop_duration": 2.5,
        "tail_target": IDLE_P, "tail_speed": 0.08,
    },
    "excited": {
        "intro_target": EXCITED, "intro_speed": 0.18,
        "loop_target": EXCITED, "loop_duration": 2.0,
        "loop_dynamic": True,
        "tail_target": IDLE_P, "tail_speed": 0.10,
    },
    "angry": {
        "intro_target": ANGRY, "intro_speed": 0.20,
        "loop_target": ANGRY, "loop_duration": 2.0,
        "tail_target": IDLE_P, "tail_speed": 0.08,
    },
    "surprised": {
        "intro_target": SURPRISE, "intro_speed": 0.20,
        "loop_target": SURPRISE, "loop_duration": 1.5,
        "tail_target": IDLE_P, "tail_speed": 0.08,
    },
    "scared": {
        "intro_target": SCARED, "intro_speed": 0.20,
        "loop_target": SCARED, "loop_duration": 1.5,
        "tail_target": IDLE_P, "tail_speed": 0.08,
    },
    "smile": {
        "intro_target": SMILE, "intro_speed": 0.10,
        "loop_target": SMILE, "loop_duration": 5.0,
        "tail_target": IDLE_P, "tail_speed": 0.08,
    },
    "relaxed": {
        "intro_target": RELAXED, "intro_speed": 0.06,
        "loop_target": RELAXED, "loop_duration": 5.0,
        "tail_target": IDLE_P, "tail_speed": 0.06,
    },
    "sad": {
        "intro_target": SAD, "intro_speed": 0.08,
        "loop_target": SAD, "loop_duration": 4.0,
        "tail_target": IDLE_P, "tail_speed": 0.06,
    },
    "sleepy": {
        "intro_target": SLEEPY, "intro_speed": 0.04,
        "loop_target": SLEEPY, "loop_duration": 8.0,
        "loop_dynamic": True,
        "tail_target": SURPRISE, "tail_speed": 0.25,
    },
    "bored": {
        "intro_target": BORED, "intro_speed": 0.08,
        "loop_target": BORED, "loop_duration": 4.0,
        "tail_target": IDLE_P, "tail_speed": 0.06,
    },
    "idle": {
        "loop_target": IDLE_P,
        "loop_dynamic": True,
    },
    "curious": {
        "intro_target": CURIOUS, "intro_speed": 0.12,
        "loop_target": CURIOUS, "loop_duration": 3.0,
        "tail_target": IDLE_P, "tail_speed": 0.08,
    },
    "thinking": {
        "intro_target": THINK, "intro_speed": 0.12,
        "loop_target": THINK, "loop_duration": 4.0,
        "loop_dynamic": True,
        "tail_target": IDLE_P, "tail_speed": 0.08,
    },
    "confused": {
        "intro_target": CONFUSED, "intro_speed": 0.12,
        "loop_target": CONFUSED, "loop_duration": 3.0,
        "tail_target": IDLE_P, "tail_speed": 0.08,
    },
    "speaking": {
        "intro_target": Params(0.95, 0.95, 1.0, 1.0, 0, 0, 0, 0, 1.0, 0.6, 0, 0, 0), "intro_speed": 0.15,
        "loop_target": Params(0.9, 0.9, 1.0, 1.0, 0, 0, 0, 0, 1.0, 0.5, 0, 0, 0), "loop_duration": 4.0,
        "loop_dynamic": True,
        "tail_target": IDLE_P, "tail_speed": 0.10,
    },
    "look_left": {
        "intro_target": LOOK_L, "intro_speed": 0.15,
        "loop_target": LOOK_L, "loop_duration": 1.5,
        "tail_target": IDLE_P, "tail_speed": 0.10,
    },
    "look_right": {
        "intro_target": LOOK_R, "intro_speed": 0.15,
        "loop_target": LOOK_R, "loop_duration": 1.5,
        "tail_target": IDLE_P, "tail_speed": 0.10,
    },
    "look_up": {
        "intro_target": LOOK_U, "intro_speed": 0.12,
        "loop_target": LOOK_U, "loop_duration": 2.0,
        "tail_target": IDLE_P, "tail_speed": 0.10,
    },
    "wink": {
        "intro_target": WINK, "intro_speed": 0.20,
        "loop_target": WINK, "loop_duration": 0.3,
        "tail_target": IDLE_P, "tail_speed": 0.15,
    },
    "blink": {
        "intro_target": BLINK, "intro_speed": 0.30,
        "loop_target": BLINK, "loop_duration": 0.15,
        "tail_target": IDLE_P, "tail_speed": 0.25,
    },
    "heart_eyes": {
        "intro_target": HEART_EYES, "intro_speed": 0.12,
        "loop_target": HEART_EYES, "loop_duration": 3.0,
        "tail_target": IDLE_P, "tail_speed": 0.08,
    },
    "star_eyes": {
        "intro_target": STAR_EYES, "intro_speed": 0.15,
        "loop_target": STAR_EYES, "loop_duration": 2.0,
        "tail_target": IDLE_P, "tail_speed": 0.10,
    },
}


# ═══ 表情 ↔ 舵机角度映射 ═══
EXPRESSION_GIMBAL = {
    "idle":       (90, 150),
    "happy":      (90, 150),
    "laugh":      (90, 146),
    "excited":    (90, 148),
    "smile":      (90, 150),
    "relaxed":    (90, 155),
    "sad":        (90, 160),
    "angry":      (90, 144),
    "surprised":  (90, 138),
    "scared":     (85, 140),
    "sleepy":     (90, 162),
    "bored":      (80, 152),
    "curious":    (105, 146),
    "thinking":   (75, 150),
    "confused":   (100, 144),
    "speaking":   (90, 150),
    "look_left":  (100, 150),
    "look_right": (80, 150),
    "look_up":    (90, 138),
    "blink":      None,
    "wink":       None,
    "heart_eyes": (90, 148),
    "star_eyes":  (90, 145),
}


class StateMachine:
    def __init__(self):
        self.current = IDLE_P.copy()
        self.phase = "loop"
        self.active_expr = "idle"
        self.next_expr = None
        self.phase_time = 0
        self.blink_timer = 0
        self.next_blink = random.uniform(2.5, 5)
        self.is_blinking = False
        self.wink_timer = 0
        self.next_wink = random.uniform(15, 30)
        self.speak_t = 0
        self.sleepy_breathe = 0
        self.idle_bounce = 0
        self.auto_mode = True
        self.next_state_time = 0
        self.idle_next_time = random.uniform(2, 4)
        # 微行为增强
        self.gaze_timer = 0
        self.next_gaze = random.uniform(8, 20)
        self.pause_active = False
        self.pause_timer = 0
        self.pause_duration = 0
        self.next_pause = random.uniform(20, 60)
        self.pause_cooldown = 0
        # 眨眼帧序列
        self.blink_phase = 0  # 0=none, 1=closing, 2=closed, 3=opening
        self.blink_frame_time = 0
        # 触控后暂停随机眼动
        self.interact_cooldown = 0
        # 舵机控制
        self.gimbal = None
        self.last_gimbal_expr = None
        # VFX回调
        self._on_expr_change = None  # callable(expr_name)
        # v7: 呼吸参数回调(anim_director.get_breath_params)
        self._breath_params_cb = None
        # v9: 参数过渡系统(easing驱动)
        self._param_trans = False      # 是否正在做参数过渡
        self._param_trans_time = 0.0   # 过渡已用时间
        self._param_trans_dur = 0.3    # 过渡总时长
        self._param_trans_from = None  # 过渡起点Params快照
        self._param_easing = "ease_out_quad"  # 过渡easing函数名
        self._prev_expr = "idle"       # 上一个表情名(用于查过渡规则)

    def trigger_gimbal(self, expr_name):
        if self.gimbal is None:
            return
        mapping = EXPRESSION_GIMBAL.get(expr_name)
        if mapping is None or expr_name == self.last_gimbal_expr:
            return
        pan_a, tilt_a = mapping
        self.gimbal.move_to(pan_a, tilt_a, 800, blocking=False)
        self.last_gimbal_expr = expr_name
        print(f'[GIMBAL] {expr_name} -> P{pan_a} T{tilt_a}')

    def trigger(self, expr_name):
        if expr_name not in EXPRESSIONS:
            return
        old_expr = self.active_expr
        if expr_name == "idle":
            self._goto_expr("idle")
            return
        if self.active_expr in ("blink", "wink"):
            self._goto_expr(expr_name)
            return
        if self.active_expr == expr_name and self.phase == "loop":
            self.phase_time = 0
            return
        if self.phase == "loop" or self.phase == "intro":
            self._goto_expr(expr_name)
        elif self.phase == "tail":
            self.next_expr = expr_name

    def _goto_expr(self, expr_name):
        # v9: 启动参数easing过渡
        self._prev_expr = self.active_expr
        self._param_trans = True
        self._param_trans_time = 0.0
        self._param_trans_from = self.current.copy()
        # 查过渡规则
        rule = AnimationDirector.TRANSITION_RULES  # 类变量
        key = (self._prev_expr, expr_name)
        r = rule.get(key)
        if not r:
            r = rule.get(("any", expr_name))
        if not r:
            r = rule.get((self._prev_expr, "any"))
        if r:
            self._param_trans_dur = r["duration"]
            self._param_easing = r["easing"]
        else:
            self._param_trans_dur = 0.35
            self._param_easing = "ease_out_quad"

        self.phase = "intro"
        if "intro_target" not in EXPRESSIONS.get(expr_name, {}):
            self.phase = "loop"
        else:
            self.phase = "intro"
        self.active_expr = expr_name
        self.next_expr = None
        self.phase_time = 0
        self.speak_t = 0
        self.sleepy_breathe = 0
        self.blink_timer = 0
        self.trigger_gimbal(expr_name)
        # VFX回调
        if self._on_expr_change:
            self._on_expr_change(expr_name)

    def update(self, dt):
        self.idle_bounce += dt
        self.phase_time += dt

        # 交互冷却
        if self.interact_cooldown > 0:
            self.interact_cooldown -= dt

        # 增强眨眼：帧序列
        if self.blink_phase > 0:
            self.blink_frame_time += dt
            if self.blink_phase == 1:  # closing
                if self.blink_frame_time > 0.06:
                    self.blink_phase = 2
                    self.blink_frame_time = 0
                    self.current.l_open = 0.0
                    self.current.r_open = 0.0
            elif self.blink_phase == 2:  # closed
                if self.blink_frame_time > 0.08:
                    self.blink_phase = 3
                    self.blink_frame_time = 0
            elif self.blink_phase == 3:  # opening
                if self.blink_frame_time > 0.06:
                    self.blink_phase = 0
                    self.blink_frame_time = 0
                    self.blink_timer = 0
                    self.next_blink = random.uniform(2.5, 6.0)
                    if random.random() < 0.10:
                        self.next_blink = random.uniform(0.3, 1.0)
        elif self.is_blinking:
            if self.phase_time > 0.15:
                self.is_blinking = False
                if self.phase == "intro" or self.phase == "loop":
                    self.phase = "loop"
                    self.phase_time = 0
                self.blink_timer = 0
                self.next_blink = random.uniform(2.5, 5)
        elif (self.active_expr not in ("sleepy", "blink") and
              self.blink_timer > self.next_blink and
              self.interact_cooldown <= 0):
            self.blink_phase = 1
            self.blink_frame_time = 0
            self.is_blinking = True
            self.phase_time = 0
            self.blink_timer = 0

        # 随机视线
        if self.interact_cooldown <= 0:
            self.gaze_timer += dt
        if (self.gaze_timer > self.next_gaze and
            self.active_expr in ("idle", "curious", "bored", "relaxed", "smile") and
            self.blink_phase == 0):
            self.gaze_timer = 0
            self.next_gaze = random.uniform(8, 20)
            gaze = random.choice(["look_left", "look_right", "look_up"])
            self.trigger(gaze)

        # 随机停顿
        if self.pause_active:
            self.pause_timer += dt
            if self.pause_timer > self.pause_duration:
                self.pause_active = False
                self.pause_timer = 0
                self.current.l_open = 1.0
                self.current.r_open = 1.0
                self.pause_cooldown = 0
        else:
            self.pause_cooldown += dt
            if (self.pause_cooldown > self.next_pause and
                self.active_expr == "idle" and
                self.blink_phase == 0 and
                self.interact_cooldown <= 0):
                self.pause_active = True
                self.pause_timer = 0
                self.pause_duration = random.uniform(0.5, 1.5)
                self.next_pause = random.uniform(20, 60)
                self.pause_cooldown = 0

        if self.active_expr not in ("blink", "wink", "sleepy"):
            self.wink_timer += dt
            if self.wink_timer > self.next_wink:
                self._goto_expr("wink")
                self.wink_timer = 0
                self.next_wink = random.uniform(15, 35)

        if self.phase == "intro":
            self._update_intro(dt)
        elif self.phase == "loop":
            self._update_loop(dt)
        elif self.phase == "tail":
            self._update_tail(dt)

        if self.is_blinking:
            if self.blink_phase == 1:
                spd = 0.40
            elif self.blink_phase == 3:
                target = self._get_current_target() or IDLE_P
                spd = 0.30
            else:
                target = BLINK
                spd = 0.30 if self.current.l_open > 0.5 else 0.25
            self.current.lerp(target, spd)
            return

        # 随机停顿覆盖
        if self.pause_active:
            base_open = 0.6
            self.current.l_open += (base_open - self.current.l_open) * 0.1
            self.current.r_open += (base_open - self.current.r_open) * 0.1

        target = self._get_current_target()
        if target is not None:
            # v9: 参数过渡期间使用easing驱动插值
            if self._param_trans and self._param_trans_from is not None:
                self._param_trans_time += dt
                t = min(1.0, self._param_trans_time / max(0.01, self._param_trans_dur))
                easing_fn = getattr(Easing, self._param_easing, Easing.ease_out_quad)
                t_eased = easing_fn(t)
                # 从快照起点向当前target做easing插值
                snap = self._param_trans_from.copy()
                snap.ease_lerp(target, t_eased)
                self.current = snap
                if t >= 1.0:
                    self._param_trans = False
            else:
                defn = EXPRESSIONS[self.active_expr]
                if self.phase == "intro":
                    spd = defn.get("intro_speed", 0.10)
                elif self.phase == "tail":
                    spd = defn.get("tail_speed", 0.08)
                else:
                    spd = 0.05
                self.current.lerp(target, spd)

    def _update_intro(self, dt):
        defn = EXPRESSIONS[self.active_expr]
        target = defn["intro_target"]
        spd = defn.get("intro_speed", 0.10)
        self.current.lerp(target, spd)
        if self.current.is_close(target):
            self.phase = "loop"
            self.phase_time = 0

    def _update_loop(self, dt):
        defn = EXPRESSIONS[self.active_expr]
        if defn.get("loop_dynamic"):
            if self.active_expr == "sleepy":
                self.sleepy_breathe += dt
                base = 0.12 + 0.08 * math.sin(self.sleepy_breathe * 0.6)
                self.current.l_open = base
                self.current.r_open = base * 0.9
            elif self.active_expr == "excited":
                j = 0.08 * math.sin(self.phase_time * 8)
                self.current.l_open = 1.3 + j
                self.current.r_open = 1.3 - j
            elif self.active_expr == "thinking":
                cycle = math.sin(self.phase_time * 1.2)
                self.current.l_open = 0.7 + cycle * 0.15
                self.current.r_open = 0.6 - cycle * 0.1
            elif self.active_expr == "speaking":
                self.speak_t += dt
                b = math.sin(self.speak_t * math.pi * 5)
                self.current.l_open = 0.85 + 0.15 * b
                self.current.r_open = 0.85 - 0.10 * b
            elif self.active_expr == "idle":
                # v7: 呼吸参数受情绪影响(通过anim_director回调)
                if self._breath_params_cb:
                    period, amp = self._breath_params_cb()
                    freq = 2 * math.pi / max(0.5, period)
                else:
                    freq, amp = 0.8, 0.02
                breath = math.sin(self.idle_bounce * freq) * amp
                micro = math.sin(self.idle_bounce * 3.1) * 0.005
                self.current.l_open = 1.0 + breath + micro
                self.current.r_open = 1.0 + breath - micro

        loop_dur = defn.get("loop_duration", 999)
        if self.phase_time > loop_dur:
            tail_target = defn.get("tail_target")
            if tail_target is not None:
                self.phase = "tail"
                self.phase_time = 0
                if self.active_expr == "sleepy":
                    self.active_expr = "surprised"
            else:
                self._goto_expr("idle")
                self.phase = "loop"
                self.next_state_time = random.uniform(2, 4)

    def _update_tail(self, dt):
        defn = EXPRESSIONS[self.active_expr]
        tail_target = defn.get("tail_target", IDLE_P)
        spd = defn.get("tail_speed", 0.08)
        if isinstance(tail_target, str):
            tail_target = EXPRESSIONS.get(tail_target, {}).get("intro_target", IDLE_P)
        self.current.lerp(tail_target, spd)
        if self.current.is_close(tail_target):
            if self.active_expr == "sleepy":
                self.active_expr = "surprised"
                self.phase = "intro"
                self.phase_time = 0
            elif self.next_expr:
                self._goto_expr(self.next_expr)
            else:
                self._goto_expr("idle")
                self.phase = "loop"
                self.next_state_time = random.uniform(2, 4)

    next_state_time = 0
    def update_auto(self, dt):
        if not self.auto_mode or self.active_expr not in ("idle",):
            return
        if self.phase != "loop":
            return
        self.next_state_time += dt
        if self.next_state_time > self.idle_next_time:
            self.next_state_time = 0
            self.idle_next_time = random.uniform(2, 5)
            self._pick_next_idle()

    def _pick_next_idle(self):
        r = random.random()
        if r < 0.18:
            self._goto_expr("look_left")
        elif r < 0.36:
            self._goto_expr("look_right")
        elif r < 0.48:
            self._goto_expr("look_up")
        elif r < 0.58:
            self._goto_expr("happy")
        elif r < 0.65:
            self._goto_expr("smile")
        elif r < 0.72:
            self._goto_expr("curious")
        elif r < 0.78:
            self._goto_expr("thinking")
        elif r < 0.83:
            self._goto_expr("confused")
        elif r < 0.87:
            self._goto_expr("speaking")
            self.speak_t = 0
        elif r < 0.92:
            self._goto_expr("sleepy")
            self.sleepy_breathe = 0
        else:
            self._goto_expr("bored")

    def _get_current_target(self):
        defn = EXPRESSIONS[self.active_expr]
        if self.phase == "intro":
            return defn["intro_target"]
        elif self.phase == "loop":
            return defn["loop_target"]
        elif self.phase == "tail":
            return defn.get("tail_target", IDLE_P)
        return IDLE_P


# ═══ NPC状态机 ═══
class NPCStateMachine:
    """NPC行为状态机"""

    STATE_DEFAULT_EXPR = {
        NPCState.IDLE: "idle",
        NPCState.OBSERVE: "curious",
        NPCState.ENGAGED: "happy",
        NPCState.WARN: "bored",
        NPCState.SLEEP: "sleepy",
    }

    STATE_BEHAVIORS = {
        NPCState.IDLE: [
            ("look_left", 0.18), ("look_right", 0.18), ("look_up", 0.12),
            ("happy", 0.10), ("smile", 0.07), ("curious", 0.07),
            ("thinking", 0.06), ("confused", 0.05), ("bored", 0.05),
        ],
        NPCState.OBSERVE: [
            ("look_left", 0.25), ("look_right", 0.25), ("look_up", 0.10),
            ("curious", 0.20), ("thinking", 0.15), ("confused", 0.05),
        ],
        NPCState.ENGAGED: [
            ("happy", 0.25), ("smile", 0.20), ("excited", 0.15),
            ("laugh", 0.15), ("wink", 0.10), ("look_left", 0.08), ("look_right", 0.07),
        ],
        NPCState.WARN: [
            ("bored", 0.30), ("angry", 0.10), ("confused", 0.20),
            ("look_left", 0.15), ("look_right", 0.15), ("sad", 0.10),
        ],
        NPCState.SLEEP: [],
    }

    def __init__(self, sm, personality=None):
        self.sm = sm
        self.personality = personality or Personality()
        self.state = NPCState.IDLE
        self.idle_time = 0
        self.behavior_timer = 0
        self._schedule_next_behavior()

    def _schedule_next_behavior(self):
        base = 3.0 / (0.5 + self.personality.activity_level)
        self.next_behavior_time = random.uniform(base * 0.6, base * 1.8)

    def update(self, dt):
        hour = datetime.datetime.now().hour

        if hour >= 23 or hour < 7:
            if self.state != NPCState.SLEEP:
                self._set_state(NPCState.SLEEP)
            return
        elif self.state == NPCState.SLEEP:
            self._set_state(NPCState.IDLE)
            self.sm.trigger("surprised")
            return

        self.idle_time += dt

        if self.state == NPCState.IDLE:
            if self.idle_time > 10:
                self._set_state(NPCState.OBSERVE)
        elif self.state == NPCState.OBSERVE:
            if self.idle_time > 30 * self.personality.patience_level:
                self._set_state(NPCState.WARN)
        elif self.state == NPCState.ENGAGED:
            if self.idle_time > 15:
                self._set_state(NPCState.IDLE)

        self.behavior_timer += dt
        if self.behavior_timer >= self.next_behavior_time:
            self.behavior_timer = 0
            self._schedule_next_behavior()
            self._pick_behavior()

    def interact(self, interaction_type="touch"):
        self.idle_time = 0
        if self.state == NPCState.SLEEP:
            self._set_state(NPCState.IDLE)
            self.sm.trigger("surprised")
            return
        self._set_state(NPCState.ENGAGED)
        expr_map = {
            "touch": "happy",
            "voice": "curious",
            "long_press": "angry",
            "double_tap": "excited",
        }
        self.sm.trigger(expr_map.get(interaction_type, "happy"))

    def set_npc_state(self, state_name):
        try:
            new_state = NPCState(state_name)
            self.idle_time = 0
            self._set_state(new_state)
        except ValueError:
            pass

    def _set_state(self, new_state):
        if self.state == new_state:
            return
        old_state = self.state
        self.state = new_state
        expr = self.STATE_DEFAULT_EXPR.get(new_state, "idle")
        self.sm.trigger(expr)
        print(f'[NPC] {old_state.value} -> {new_state.value}, expr -> {expr}')

    def _pick_behavior(self):
        behaviors = self.STATE_BEHAVIORS.get(self.state, [])
        if not behaviors:
            return
        if self.sm.active_expr in ("blink", "wink"):
            return
        r = random.random()
        cumulative = 0
        for expr_name, weight in behaviors:
            cumulative += weight
            if r < cumulative:
                self.sm.trigger(expr_name)
                return
        if behaviors:
            self.sm.trigger(behaviors[-1][0])


# ═══════════════════════════════════════════════════════
# v9 新增：AmbientManager — 环境氛围层
# ═══════════════════════════════════════════════════════

# ============================================================
# v9: 性能监控 — FPS自适应降级
# ============================================================
class PerfMonitor:
    """FPS监控与自适应降级策略
    FPS<45: 粒子减半 | FPS<35: 关环境粒子 | FPS<30: 关VFX | FPS<25: 降动画复杂度
    """
    LEVEL_FULL = 0      # 全特效
    LEVEL_HALF_DOTS = 1 # 粒子减半
    LEVEL_NO_DOTS = 2   # 关闭环境粒子
    LEVEL_NO_VFX = 3    # 关闭VFX层
    LEVEL_MINIMAL = 4   # 最低复杂度

    def __init__(self):
        self.level = self.LEVEL_FULL
        self.fps_history = []
        self.check_interval = 3.0  # 每3秒检查一次
        self.timer = 0.0
        self.current_fps = 60.0

    def update(self, dt, actual_fps):
        """每帧调用, actual_fps为最近测量的FPS"""
        self.current_fps = actual_fps
        self.timer += dt
        if self.timer < self.check_interval:
            return
        self.timer = 0.0
        self.fps_history.append(actual_fps)
        if len(self.fps_history) > 5:
            self.fps_history.pop(0)
        avg_fps = sum(self.fps_history) / len(self.fps_history)

        new_level = self.LEVEL_FULL
        if avg_fps < 25:
            new_level = self.LEVEL_MINIMAL
        elif avg_fps < 30:
            new_level = self.LEVEL_NO_VFX
        elif avg_fps < 35:
            new_level = self.LEVEL_NO_DOTS
        elif avg_fps < 45:
            new_level = self.LEVEL_HALF_DOTS

        if new_level != self.level:
            old = self.level
            self.level = new_level
            print(f"[PERF] 降级: L{old}→L{new_level} (avg FPS={avg_fps:.1f})")

    @property
    def enable_dots(self):
        return self.level <= self.LEVEL_HALF_DOTS

    @property
    def dots_half(self):
        return self.level == self.LEVEL_HALF_DOTS

    @property
    def enable_vfx(self):
        return self.level <= self.LEVEL_NO_DOTS

    @property
    def enable_glow(self):
        return self.level <= self.LEVEL_HALF_DOTS

    @property
    def enable_squash(self):
        return self.level <= self.LEVEL_NO_VFX

    @property
    def level_name(self):
        return ["FULL", "HALF_DOTS", "NO_DOTS", "NO_VFX", "MINIMAL"][self.level]


class AmbientManager:
    """环境氛围管理器 — 情绪色调 + 氛围光斑 + 面部光晕
    
    三层环境效果：
    1. 情绪色调：背景色随NPC状态/情绪微妙偏移(HSL插值过渡)
    2. 氛围光斑：情绪驱动的浮动光点(向上飘浮/环绕/下落)
    3. 面部光晕：脸部周围径向渐变柔光(呼吸节奏脉冲)
    """

    # v10: 霓虹赛博情绪→环境色调映射(深空黑基底+霓虹色氛围)
    MOOD_PRESETS = {
        "idle":     {"bg": (10, 10, 15),     "glow": (20, 60, 100),   "dots": [(0, 180, 255)]},
        "happy":    {"bg": (5, 15, 15),      "glow": (0, 200, 200),   "dots": [(0, 255, 255), (100, 255, 200)]},
        "sad":      {"bg": (5, 8, 18),       "glow": (30, 60, 180),   "dots": [(50, 120, 255), (80, 140, 255)]},
        "angry":    {"bg": (18, 5, 5),       "glow": (200, 20, 20),   "dots": [(255, 30, 30), (255, 80, 30)]},
        "surprised":{"bg": (15, 12, 5),      "glow": (200, 150, 0),   "dots": [(255, 191, 0), (255, 220, 100)]},
        "scared":   {"bg": (12, 5, 18),      "glow": (120, 30, 200),  "dots": [(160, 50, 255), (200, 100, 255)]},
        "excited":  {"bg": (12, 10, 5),      "glow": (200, 170, 0),   "dots": [(255, 220, 0), (255, 150, 0), (0, 255, 200)]},
        "curious":  {"bg": (5, 12, 18),      "glow": (40, 120, 200),  "dots": [(80, 180, 255), (100, 200, 255)]},
        "sleepy":   {"bg": (5, 5, 10),       "glow": (20, 20, 50),    "dots": [(30, 30, 80)]},
        "love":     {"bg": (15, 5, 10),      "glow": (200, 30, 100),  "dots": [(255, 50, 150), (255, 100, 180)]},
        "focus":    {"bg": (5, 10, 18),      "glow": (30, 80, 160),   "dots": [(50, 120, 255)]},
    }

    def __init__(self, face_cx, face_cy):
        self.face_cx = face_cx
        self.face_cy = face_cy
        self.width = WIDTH
        self.height = HEIGHT
        
        # 情绪色调 — 当前/目标/过渡
        self._bg_current = [8.0, 8.0, 18.0]     # 当前背景色(浮点)
        self._bg_target  = [8.0, 8.0, 18.0]      # 目标背景色
        self._bg_speed   = 1.5                     # 过渡速度(1.5s完成)

        # 光晕 — 当前/目标/过渡
        self._glow_current = [30.0, 40.0, 80.0]
        self._glow_target  = [30.0, 40.0, 80.0]
        self._glow_speed   = 1.5
        self._glow_alpha   = 0.0    # 当前光晕alpha(0-1)
        self._glow_target_alpha = 0.25  # 目标光晕alpha
        self._glow_alpha_speed = 2.0
        self._breath_phase  = 0.0   # 呼吸相位(用于光晕脉冲)

        # 光斑(ambient dots) — 独立于VFXManager的氛围粒子
        self._dots = []             # [{x,y,vx,vy,r,color,life,max_life,alpha,behavior}]
        self._dot_colors = [(60, 80, 140)]  # 当前光斑颜色列表
        self._dot_target_colors = [(60, 80, 140)]
        self._dot_spawn_timer = 0.0
        self._dot_spawn_interval = 0.5  # 每0.5s生成一个
        self._max_dots = 12        # 最多12个(性能安全)
        self._dot_behavior = "float"  # float/orbit/fall

        # 当前情绪
        self._mood = "idle"
        
        # 光晕预渲染Surface(缓存)
        self._glow_surf = None
        self._glow_size = 0

    def set_mood(self, mood_name, transition=1.5):
        """设置情绪氛围 — mood_name: idle/happy/sad/angry/surprised/excited/curious/sleepy/love/focus"""
        preset = self.MOOD_PRESETS.get(mood_name, self.MOOD_PRESETS["idle"])
        if mood_name == self._mood:
            return
        
        self._mood = mood_name
        self._bg_target = list(preset["bg"])
        self._bg_speed = 1.0 / max(0.1, transition)
        self._glow_target = list(preset["glow"])
        self._glow_speed = 1.0 / max(0.1, transition)
        self._dot_target_colors = preset["dots"]

        # 情绪→光斑行为映射
        behavior_map = {
            "idle": "float", "happy": "float", "sad": "fall",
            "angry": "float", "surprised": "orbit", "excited": "float",
            "curious": "orbit", "sleepy": "fall", "love": "float", "focus": "orbit",
        }
        self._dot_behavior = behavior_map.get(mood_name, "float")
        self._glow_target_alpha = 0.25 if mood_name != "idle" else 0.15

    def update(self, dt):
        """更新所有环境效果"""
        # ── 背景色过渡 ──
        for i in range(3):
            diff = self._bg_target[i] - self._bg_current[i]
            self._bg_current[i] += diff * min(1.0, self._bg_speed * dt)
        
        # ── 光晕色过渡 ──
        for i in range(3):
            diff = self._glow_target[i] - self._glow_current[i]
            self._glow_current[i] += diff * min(1.0, self._glow_speed * dt)
        
        # ── 光晕alpha过渡 ──
        diff = self._glow_target_alpha - self._glow_alpha
        self._glow_alpha += diff * min(1.0, self._glow_alpha_speed * dt)

        # ── 光晕呼吸脉冲 ──
        self._breath_phase += dt * 1.2  # ~1.2Hz呼吸频率

        # ── 光斑颜色过渡(逐帧趋近目标) ──
        for i, tc in enumerate(self._dot_target_colors):
            if i >= len(self._dot_colors):
                self._dot_colors.append(tc)
            else:
                cc = self._dot_colors[i]
                self._dot_colors[i] = (
                    int(cc[0] + (tc[0] - cc[0]) * min(1.0, dt * 2)),
                    int(cc[1] + (tc[1] - cc[1]) * min(1.0, dt * 2)),
                    int(cc[2] + (tc[2] - cc[2]) * min(1.0, dt * 2)),
                )

        # ── 生成光斑 ──
        self._dot_spawn_timer += dt
        if self._dot_spawn_timer >= self._dot_spawn_interval and len(self._dots) < self._max_dots:
            self._dot_spawn_timer = 0
            self._spawn_dot()

        # ── 更新光斑 ──
        alive = []
        for d in self._dots:
            d["life"] -= dt
            if d["life"] <= 0:
                continue

            # 运动
            if d["behavior"] == "float":
                d["x"] += d["vx"] * dt
                d["y"] += d["vy"] * dt
                # 正弦摇摆
                d["x"] += math.sin(d["life"] * 1.5) * 0.3
            elif d["behavior"] == "orbit":
                d["angle"] += d["angular_v"] * dt
                d["x"] = self.face_cx + d["orbit_r"] * math.cos(d["angle"])
                d["y"] = self.face_cy + d["orbit_r"] * math.sin(d["angle"]) * 0.6  # 椭圆轨道
            elif d["behavior"] == "fall":
                d["x"] += d["vx"] * dt
                d["vy"] += 15 * dt  # 轻微重力
                d["y"] += d["vy"] * dt

            # 淡入淡出
            max_l = d["max_life"]
            if d["life"] > max_l - 0.5:
                d["alpha"] = min(1.0, (max_l - d["life"]) / 0.5) * d["peak_alpha"]
            elif d["life"] < 1.0:
                d["alpha"] = (d["life"] / 1.0) * d["peak_alpha"]
            else:
                d["alpha"] = d["peak_alpha"]

            if d["alpha"] > 0.01:
                alive.append(d)

        self._dots = alive

    def _spawn_dot(self):
        """生成一个氛围光斑"""
        color = random.choice(self._dot_colors)
        behavior = self._dot_behavior
        max_life = random.uniform(3.0, 6.0)

        if behavior == "float":
            # 从底部或两侧飘入
            side = random.choice(["bottom", "left", "right"])
            if side == "bottom":
                x = random.uniform(self.width * 0.1, self.width * 0.9)
                y = self.height + 10
            elif side == "left":
                x = -10
                y = random.uniform(self.height * 0.3, self.height * 0.9)
            else:
                x = self.width + 10
                y = random.uniform(self.height * 0.3, self.height * 0.9)
            vx = random.uniform(-5, 5)
            vy = random.uniform(-20, -8)  # 向上飘浮

            self._dots.append({
                "x": x, "y": y, "vx": vx, "vy": vy,
                "r": random.uniform(3, 8),
                "color": color, "life": max_life, "max_life": max_life,
                "alpha": 0.0, "peak_alpha": random.uniform(0.3, 0.6),
                "behavior": "float",
            })
        elif behavior == "orbit":
            # 环绕面部
            angle = random.uniform(0, math.pi * 2)
            orbit_r = random.uniform(250, 400)
            self._dots.append({
                "x": self.face_cx + orbit_r * math.cos(angle),
                "y": self.face_cy + orbit_r * math.sin(angle) * 0.6,
                "vx": 0, "vy": 0,
                "r": random.uniform(2, 5),
                "color": color, "life": max_life, "max_life": max_life,
                "alpha": 0.0, "peak_alpha": random.uniform(0.2, 0.4),
                "behavior": "orbit",
                "angle": angle, "orbit_r": orbit_r,
                "angular_v": random.uniform(0.3, 0.8) * random.choice([-1, 1]),
            })
        elif behavior == "fall":
            # 从上方飘落
            x = random.uniform(self.width * 0.15, self.width * 0.85)
            y = -10
            vx = random.uniform(-8, 8)
            vy = random.uniform(5, 15)
            self._dots.append({
                "x": x, "y": y, "vx": vx, "vy": vy,
                "r": random.uniform(2, 6),
                "color": color, "life": max_life, "max_life": max_life,
                "alpha": 0.0, "peak_alpha": random.uniform(0.2, 0.5),
                "behavior": "fall",
            })

    def get_bg_color(self):
        """获取当前插值后的背景色"""
        return (int(self._bg_current[0]), int(self._bg_current[1]), int(self._bg_current[2]))

    def draw_bg(self, screen):
        """绘制背景(情绪色调)"""
        screen.fill(self.get_bg_color())

    def draw_dots(self, screen, half=False):
        """绘制氛围光斑 — half=True时只绘制偶数索引(粒子减半)"""
        for i, d in enumerate(self._dots):
            if half and i % 2 == 1:
                continue  # 跳过奇数索引，减半粒子
            if d["alpha"] < 0.01:
                continue
            r = max(1, int(d["r"]))
            # SRCALPHA Surface绘制半透明圆
            size = r * 2 + 4
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            alpha = int(min(255, d["alpha"] * 255))
            color = (*d["color"], alpha)
            pygame.draw.circle(surf, color, (size // 2, size // 2), r)
            # 外发光(更大更淡的圆)
            if r >= 3:
                glow_r = int(r * 2.0)
                glow_alpha = int(min(255, d["alpha"] * 80))
                glow_color = (*d["color"], glow_alpha)
                pygame.draw.circle(surf, glow_color, (size // 2, size // 2), glow_r)
            screen.blit(surf, (int(d["x"]) - size // 2, int(d["y"]) - size // 2))

    def draw_glow(self, screen, face_cx=None, face_cy=None):
        """绘制面部光晕 — 径向渐变 + 呼吸脉冲"""
        if self._glow_alpha < 0.01:
            return
        
        cx = face_cx or self.face_cx
        cy = face_cy or self.face_cy

        # 呼吸脉冲 → 光晕scale 0.9~1.1
        breath_scale = 1.0 + 0.1 * math.sin(self._breath_phase * math.pi * 2)
        base_r = int(280 * breath_scale)  # 基准半径
        
        # 预算Surface尺寸
        glow_size = base_r * 2 + 20
        
        # 颜色
        gc = self._glow_current
        glow_rgb = (int(gc[0]), int(gc[1]), int(gc[2]))
        
        # 5层同心圆实现径向渐变：外层几乎透明→内层较亮
        glow_surf = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
        center = glow_size // 2

        layers = 5
        for i in range(layers):
            t = i / (layers - 1)  # 0=最外, 1=最内
            frac = 1.0 - t * 0.8   # 半径: 100%→20%
            layer_r = max(2, int(base_r * frac))
            # alpha: 外层极淡→内层适中
            layer_alpha = int(self._glow_alpha * (0.08 + t * 0.35) * 255)
            layer_alpha = min(255, max(0, layer_alpha))
            color = (*glow_rgb, layer_alpha)
            pygame.draw.circle(glow_surf, color, (center, center), layer_r)

        screen.blit(glow_surf, (cx - center, cy - center))


# ═══════════════════════════════════════════════════════
# v6 新增：AssetLoader + VFXManager
# ═══════════════════════════════════════════════════════

class AssetLoader:
    """位图素材加载器 - 预加载+缓存, 无素材时安全回退"""

    def __init__(self, base_dir=None):
        if base_dir is None:
            base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
        self.base_dir = base_dir
        self.cache = {}      # key (filename without .png) -> pygame.Surface
        self.available = os.path.isdir(self.base_dir)
        self._loaded = False

    def load_all(self):
        """在pygame.init()之后调用, 扫描并预加载所有PNG"""
        if not self.available or self._loaded:
            return
        self._loaded = True
        count = 0
        for root, dirs, files in os.walk(self.base_dir):
            for f in files:
                if f.lower().endswith('.png'):
                    path = os.path.join(root, f)
                    key = f[:-4]  # strip .png
                    try:
                        surf = pygame.image.load(path).convert_alpha()
                        self.cache[key] = surf
                        count += 1
                    except Exception as e:
                        print(f'[AssetLoader] WARN: 加载失败 {f}: {e}')
        if count > 0:
            print(f'[AssetLoader] 已加载 {count} 张素材 from {self.base_dir}')
        else:
            print(f'[AssetLoader] 未找到素材, 将使用纯矢量回退模式')
            self.available = False

    def get(self, key):
        return self.cache.get(key)

    def has(self, key):
        return key in self.cache

    def get_matching(self, prefix):
        return {k: v for k, v in self.cache.items() if k.startswith(prefix)}


class VFXElement:
    """单个特效元素 - 弹出/叠加通用"""
    __slots__ = ('key', 'x', 'y', 'vx', 'vy', 'scale', 'target_scale',
                 'alpha', 'lifetime', 'age', 'alive', 'gravity',
                 'fade_in', 'fade_out', 'rotation', 'rot_speed',
                 'base_w', 'base_h')

    def __init__(self, key, x, y, lifetime=1.5, vx=0, vy=0,
                 target_scale=1.0, gravity=0,
                 fade_in=0.15, fade_out=0.3, rot_speed=0):
        self.key = key
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.scale = 0.1          # 从小弹出
        self.target_scale = target_scale
        self.alpha = 0.0
        self.lifetime = lifetime
        self.age = 0.0
        self.alive = True
        self.gravity = gravity
        self.fade_in = fade_in
        self.fade_out = fade_out
        self.rotation = 0.0
        self.rot_speed = rot_speed
        self.base_w = 0
        self.base_h = 0

    def update(self, dt):
        self.age += dt
        if self.age >= self.lifetime:
            self.alive = False
            return
        # 物理运动
        self.vy += self.gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        # 旋转
        self.rotation += self.rot_speed * dt
        # 弹性缩放 (overshoot)
        diff = self.target_scale - self.scale
        self.scale += diff * 0.18
        if abs(diff) < 0.02:
            self.scale = self.target_scale
        # Alpha 淡入淡出
        if self.age < self.fade_in:
            self.alpha = min(1.0, self.age / self.fade_in)
        elif self.age > self.lifetime - self.fade_out:
            self.alpha = max(0.0, (self.lifetime - self.age) / self.fade_out)
        else:
            self.alpha = 1.0


class VFXManager:
    """特效管理器 - 弹出元素 + 叠加层 + 环境粒子"""

    # 表情 → 弹出特效映射 (asset_key, spawn_type)
    EXPR_VFX_MAP = {
        "surprised":  [("icon_exclamation_surprise_64x64_01", "above")],
        "confused":   [("icon_question_confused_64x64_01", "above")],
        "happy":      [("icon_heart_happy_64x64_01", "float"),
                       ("icon_note_happy_48x48_01", "side")],
        "laugh":      [("icon_star_celebrate_64x64_01", "above"),
                       ("icon_star_celebrate_64x64_02", "side")],
        "excited":    [("icon_star_celebrate_64x64_01", "above"),
                       ("icon_star_celebrate_64x64_02", "above_offset"),
                       ("icon_note_happy_48x48_01", "side")],
        "angry":      [("icon_lightning_angry_48x48_01", "above")],
        "sad":        [("icon_sweat_nervous_32x48_01", "side")],
        "sleepy":     [("icon_zzz_sleepy_64x48_01", "float")],
        "smile":      [("icon_heart_happy_32x32_01", "float")],
    }

    # 表情 → 叠加层映射 (持续显示, 随表情淡入淡出)
    EXPR_OVERLAY_MAP = {
        "happy":    ["blush_shy_48x48_01"],
        "laugh":    ["blush_shy_48x48_01"],
        "smile":    ["blush_shy_48x48_01"],
        "thinking": ["bubble_thought_96x64_01"],
    }

    def __init__(self, asset_loader, face_cx, face_cy):
        self.assets = asset_loader
        self.face_cx = face_cx
        self.face_cy = face_cy
        self.elements = []         # VFXElement list (弹出/一次性)
        self.overlays = {}         # key -> current_alpha
        self.overlay_targets = {}   # key -> target_alpha
        # 环境粒子
        self.ambient_type = "none"  # "none" / "dots" / "confetti" / "woodfish"
        self.ambient_particles = []
        self.ambient_timer = 0.0

    def on_expression_change(self, expr_name):
        """StateMachine回调 - 表情切换时触发"""
        if not self.assets.available:
            return

        # 弹出元素
        vfx_list = self.EXPR_VFX_MAP.get(expr_name, [])
        for asset_key, spawn_type in vfx_list:
            if self.assets.has(asset_key):
                self._spawn_popup(asset_key, spawn_type)

        # 叠加层管理
        new_keys = set(self.EXPR_OVERLAY_MAP.get(expr_name, []))
        # 淡入新的
        for key in new_keys:
            if self.assets.has(key) and key not in self.overlays:
                self.overlays[key] = 0.0
            self.overlay_targets[key] = 0.7
        # 淡出旧的
        for key in list(self.overlay_targets.keys()):
            if key not in new_keys:
                self.overlay_targets[key] = 0.0

    def trigger_vfx(self, asset_key, x=None, y=None):
        """手动触发特效 (WS指令)"""
        if not self.assets.available or not self.assets.has(asset_key):
            return
        sx = x if x is not None else self.face_cx
        sy = y if y is not None else self.face_cy - 200
        self._spawn_popup(asset_key, "custom", sx, sy)

    def set_ambient(self, ambient_type):
        """设置环境氛围: none / dots / confetti / woodfish"""
        if ambient_type not in ("none", "dots", "confetti", "woodfish"):
            ambient_type = "none"
        self.ambient_type = ambient_type
        if ambient_type == "none":
            self.ambient_particles.clear()

    def _spawn_popup(self, asset_key, spawn_type, custom_x=None, custom_y=None):
        cx, cy = self.face_cx, self.face_cy
        if spawn_type == "above":
            x = cx + random.randint(-30, 30)
            y = cy - 220
            vx, vy = random.uniform(-15, 15), random.uniform(-40, -20)
            lt, grav = random.uniform(1.2, 2.0), 60
        elif spawn_type == "above_offset":
            x = cx + random.randint(60, 100)
            y = cy - 180
            vx, vy = random.uniform(-20, 0), random.uniform(-50, -30)
            lt, grav = random.uniform(1.0, 1.8), 80
        elif spawn_type == "float":
            x = cx + random.randint(-50, 50)
            y = cy - 160
            vx, vy = random.uniform(-10, 10), random.uniform(-20, -5)
            lt, grav = random.uniform(1.5, 2.5), 15
        elif spawn_type == "side":
            side = random.choice([-1, 1])
            x = cx + side * random.randint(250, 320)
            y = cy - 100
            vx, vy = side * random.uniform(5, 15), random.uniform(-10, 10)
            lt, grav = random.uniform(1.0, 1.8), 20
        elif spawn_type == "custom":
            x, y = custom_x, custom_y
            vx, vy = random.uniform(-10, 10), random.uniform(-30, -10)
            lt, grav = 1.5, 40
        else:
            return

        elem = VFXElement(key=asset_key, x=x, y=y, lifetime=lt,
                          vx=vx, vy=vy, target_scale=1.0, gravity=grav,
                          rot_speed=random.uniform(-30, 30))
        surf = self.assets.get(asset_key)
        if surf:
            elem.base_w = surf.get_width()
            elem.base_h = surf.get_height()
        self.elements.append(elem)

    def update(self, dt):
        # 弹出元素
        for e in self.elements:
            e.update(dt)
        self.elements = [e for e in self.elements if e.alive]

        # 叠加层 alpha 插值
        for key in list(self.overlays.keys()):
            target = self.overlay_targets.get(key, 0.0)
            cur = self.overlays[key]
            speed = 0.08 if target > cur else 0.05
            self.overlays[key] += (target - cur) * speed
            if self.overlays[key] < 0.01 and target <= 0.0:
                del self.overlays[key]
                self.overlay_targets.pop(key, None)

        # 环境粒子
        if self.ambient_type != "none" and self.assets.available:
            self.ambient_timer += dt
            spawn_interval = 0.3 if self.ambient_type == "dots" else (0.5 if self.ambient_type == "woodfish" else 0.12)
            if self.ambient_timer > spawn_interval and len(self.ambient_particles) < 30:
                self.ambient_timer = 0
                self._spawn_ambient()
            for p in self.ambient_particles:
                p['x'] += p['vx'] * dt
                p['vy'] += p.get('grav', 0) * dt
                p['y'] += p['vy'] * dt
                # woodfish摇摆效果
                if p.get('wobble_amp'):
                    p['wobble_phase'] = p.get('wobble_phase', 0) + p.get('wobble_speed', 2.0) * dt
                    p['x'] += math.sin(p['wobble_phase']) * p['wobble_amp'] * dt
                p['age'] += dt
                if p['age'] < 0.3:
                    p['alpha'] = p['age'] / 0.3
                elif p['age'] > p['lt'] - 0.5:
                    p['alpha'] = max(0, (p['lt'] - p['age']) / 0.5)
                else:
                    p['alpha'] = 1.0
                if p['age'] >= p['lt']:
                    p['alive'] = False
            self.ambient_particles = [p for p in self.ambient_particles if p.get('alive', True)]

    def _spawn_ambient(self):
        if self.ambient_type == "dots":
            key = "particle_ambient_dot_16x16_01"
            if not self.assets.has(key):
                return
            self.ambient_particles.append({
                'key': key,
                'x': random.uniform(0, WIDTH),
                'y': random.uniform(0, HEIGHT),
                'vx': random.uniform(-5, 5),
                'vy': random.uniform(-8, -2),
                'grav': 0,
                'alpha': 0.0, 'age': 0,
                'lt': random.uniform(2, 5),
                'alive': True,
                'scale': random.uniform(0.3, 1.0),
            })
        elif self.ambient_type == "confetti":
            keys = [k for k in self.assets.cache if k.startswith("particle_confetti_")]
            if not keys:
                return
            key = random.choice(keys)
            self.ambient_particles.append({
                'key': key,
                'x': random.uniform(0, WIDTH),
                'y': -20,
                'vx': random.uniform(-20, 20),
                'vy': random.uniform(40, 80),
                'grav': 30,
                'alpha': 0.0, 'age': 0,
                'lt': random.uniform(3, 6),
                'alive': True,
                'scale': random.uniform(0.5, 1.5),
            })
        elif self.ambient_type == "woodfish":
            key = "particle_woodfish_64x64_01"
            if not self.assets.has(key):
                return
            self.ambient_particles.append({
                'key': key,
                'x': random.uniform(50, WIDTH - 50),
                'y': -40,
                'vx': random.uniform(-8, 8),
                'vy': random.uniform(25, 50),
                'grav': 5,
                'alpha': 0.0, 'age': 0,
                'lt': random.uniform(4, 7),
                'alive': True,
                'scale': random.uniform(0.4, 0.9),
                'wobble_phase': random.uniform(0, 6.28),
                'wobble_speed': random.uniform(1.5, 3.0),
                'wobble_amp': random.uniform(10, 25),
            })

    def draw(self, screen):
        """绘制所有特效层"""
        if not self.assets.available:
            return

        # 1. 环境粒子 (最底层)
        for p in self.ambient_particles:
            surf = self.assets.get(p['key'])
            if not surf:
                continue
            s = p.get('scale', 1.0)
            w = max(1, int(surf.get_width() * s))
            h = max(1, int(surf.get_height() * s))
            try:
                scaled = pygame.transform.scale(surf, (w, h))
            except:
                continue
            scaled.set_alpha(int(255 * max(0, min(1, p.get('alpha', 1.0)))))
            screen.blit(scaled, (int(p['x'] - w // 2), int(p['y'] - h // 2)))

        # 2. 叠加层 (眼睛上方)
        for key, alpha in self.overlays.items():
            surf = self.assets.get(key)
            if not surf or alpha < 0.01:
                continue
            overlay = surf.copy()
            overlay.set_alpha(int(255 * max(0, min(1, alpha))))
            # 定位策略
            if "blush" in key:
                bx = self.face_cx
                by = self.face_cy + 30
                screen.blit(overlay, (bx - 320 - surf.get_width() // 2, by - surf.get_height() // 2))
                screen.blit(overlay.copy(), (bx + 320 - surf.get_width() // 2, by - surf.get_height() // 2))
            elif "bubble" in key:
                screen.blit(overlay, (self.face_cx + 250, self.face_cy - 160))
            elif "glow" in key:
                screen.blit(overlay, (self.face_cx - surf.get_width() // 2,
                                       self.face_cy - surf.get_height() // 2))
            else:
                screen.blit(overlay, (self.face_cx - surf.get_width() // 2,
                                       self.face_cy - 200 - surf.get_height() // 2))

        # 3. 弹出元素 (最顶层)
        for elem in self.elements:
            surf = self.assets.get(elem.key)
            if not surf:
                continue
            s = max(0.01, elem.scale)
            w = max(1, int(elem.base_w * s))
            h = max(1, int(elem.base_h * s))
            try:
                scaled = pygame.transform.scale(surf, (w, h))
            except:
                continue
            if abs(elem.rotation) > 0.5:
                try:
                    scaled = pygame.transform.rotate(scaled, elem.rotation)
                except:
                    pass
            a = int(255 * max(0, min(1, elem.alpha)))
            scaled.set_alpha(a)
            bx = int(elem.x - scaled.get_width() // 2)
            by = int(elem.y - scaled.get_height() // 2)
            screen.blit(scaled, (bx, by))


# ═══════════════════════════════════════════════════════
# v7 新增：Easing函数 + AnimationDirector + SquashStretch
# ═══════════════════════════════════════════════════════

class Easing:
    """标准easing函数库 - t∈[0,1] → [0,1]"""

    @staticmethod
    def linear(t):
        return t

    @staticmethod
    def ease_in_quad(t):
        return t * t

    @staticmethod
    def ease_out_quad(t):
        return t * (2 - t)

    @staticmethod
    def ease_in_out_quad(t):
        return 2 * t * t if t < 0.5 else -1 + (4 - 2 * t) * t

    @staticmethod
    def ease_out_back(t):
        c = 1.70158
        return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2

    @staticmethod
    def ease_in_out_sine(t):
        return -(math.cos(math.pi * t) - 1) / 2

    @staticmethod
    def ease_out_elastic(t):
        if t == 0 or t == 1:
            return t
        return 2 ** (-10 * t) * math.sin((t - 0.075) * (2 * math.pi) / 0.3) + 1

    @staticmethod
    def spring(t, damping=0.4):
        """弹簧阻尼: 快速到达目标后轻微回弹"""
        return 1 - math.exp(-6 * t) * math.cos(damping * 2 * math.pi * t)


class SquashStretch:
    """Squash & Stretch 弹性形变系统 - 物理感反馈"""

    def __init__(self):
        self.scale_x = 1.0   # 当前X缩放
        self.scale_y = 1.0   # 当前Y缩放
        self.offset_y = 0.0  # Y轴偏移(像素)
        self.offset_x = 0.0  # X轴偏移(像素) - 用于紧张抖动

        # 动画状态
        self._animating = False
        self._anim_time = 0.0
        self._anim_duration = 0.45
        self._keyframes = []  # [(t_norm, sx, sy, ox, oy), ...]
        self._easing = Easing.ease_out_quad

        # 阻尼振荡(用于表情切换后的settle)
        self._damping_active = False
        self._damp_time = 0.0
        self._damp_sx = 1.0
        self._damp_sy = 1.0
        self._damp_ox = 0.0
        self._damp_oy = 0.0

    @property
    def active(self):
        return self._animating or self._damping_active

    def trigger_squash(self, intensity=1.0, style="tap"):
        """触发Squash & Stretch动画

        style:
          "tap"    - 短按: 压扁→拉伸→回弹 (0.45s)
          "bounce" - 跳起: 伸展→落地→压扁→回弹 (0.6s)
          "shake"  - 抖动: 左右晃动 (0.4s)
          "surprise" - 惊讶: 跳起+缩放 (0.5s)
        """
        I = intensity  # 强度系数 0.0-1.5

        if style == "tap":
            self._keyframes = [
                (0.00, 1.0,    1.0,    0,    0),     # 起始
                (0.08, 1.15*I, 0.85*I, 0,    2),     # 压扁
                (0.22, 0.95,   1.10,   0,   -3),     # 反向拉伸
                (0.38, 1.02,   0.98,   0,    0.5),   # 阻尼回弹
                (0.45, 1.0,    1.0,    0,    0),     # 归位
            ]
            self._anim_duration = 0.45
            self._easing = Easing.ease_out_quad

        elif style == "bounce":
            self._keyframes = [
                (0.00, 1.0,    1.0,    0,    0),
                (0.10, 0.92,   1.12,   0,   -12*I), # 预备下蹲
                (0.25, 1.08,   0.92,   0,   -20*I), # 跳起
                (0.50, 1.0,    1.0,    0,    0),     # 最高点
                (0.65, 1.18*I, 0.82*I, 0,    4),     # 落地压扁
                (0.80, 0.96,   1.08,   0,   -2),     # 回弹
                (1.00, 1.0,    1.0,    0,    0),     # 归位
            ]
            self._anim_duration = 0.6
            self._easing = Easing.ease_out_quad

        elif style == "shake":
            self._keyframes = [
                (0.00, 1.0,  1.0,  0,     0),
                (0.10, 1.0,  1.0,  -6*I,  0),
                (0.25, 1.0,  1.0,   5*I,  0),
                (0.40, 1.0,  1.0,  -4*I,  0),
                (0.55, 1.0,  1.0,   3*I,  0),
                (0.70, 1.0,  1.0,  -1.5,  0),
                (1.00, 1.0,  1.0,   0,    0),
            ]
            self._anim_duration = 0.4
            self._easing = Easing.ease_out_quad

        elif style == "surprise":
            self._keyframes = [
                (0.00, 1.0,    1.0,    0,     0),
                (0.05, 0.90,   1.10,   0,     3),    # 预备
                (0.15, 1.05,   0.95,   0,   -18*I),  # 跳起
                (0.35, 1.0,    1.0,    0,   -12*I),  # 悬浮
                (0.55, 1.12,   0.88,   0,     2),    # 落地
                (0.75, 0.98,   1.03,   0,    -1),    # 回弹
                (1.00, 1.0,    1.0,    0,     0),    # 归位
            ]
            self._anim_duration = 0.5
            self._easing = Easing.ease_out_back

        else:
            return

        self._animating = True
        self._anim_time = 0.0

    def update(self, dt):
        """每帧更新形变参数"""
        if self._animating:
            self._anim_time += dt
            t_norm = min(1.0, self._anim_time / self._anim_duration)
            t_eased = self._easing(t_norm)

            # 在关键帧之间插值
            sx, sy, ox, oy = self._interpolate_keyframes(t_eased)
            self.scale_x = sx
            self.scale_y = sy
            self.offset_x = ox
            self.offset_y = oy

            if t_norm >= 1.0:
                self._animating = False
                self.scale_x = 1.0
                self.scale_y = 1.0
                self.offset_x = 0.0
                self.offset_y = 0.0

        # 阻尼振荡(表情切换后的软回弹)
        if self._damping_active:
            self._damp_time += dt
            decay = math.exp(-8 * self._damp_time)
            self.scale_x = 1.0 + self._damp_sx * decay * math.cos(self._damp_time * 12)
            self.scale_y = 1.0 + self._damp_sy * decay * math.cos(self._damp_time * 12 + math.pi)
            self.offset_y = self._damp_oy * decay * math.cos(self._damp_time * 10)
            if decay < 0.01:
                self._damping_active = False
                self.scale_x = 1.0
                self.scale_y = 1.0
                self.offset_y = 0.0

    def _interpolate_keyframes(self, t):
        """在关键帧序列中插值"""
        kf = self._keyframes
        if not kf:
            return 1.0, 1.0, 0.0, 0.0

        # 找到t所在的两个关键帧
        for i in range(len(kf) - 1):
            t0, sx0, sy0, ox0, oy0 = kf[i]
            t1, sx1, sy1, ox1, oy1 = kf[i + 1]
            if t0 <= t <= t1:
                span = t1 - t0
                if span < 0.001:
                    return sx1, sy1, ox1, oy1
                local_t = (t - t0) / span
                return (
                    sx0 + (sx1 - sx0) * local_t,
                    sy0 + (sy1 - sy0) * local_t,
                    ox0 + (ox1 - ox0) * local_t,
                    oy0 + (oy1 - oy0) * local_t,
                )
        # 超出范围，返回最后一帧
        last = kf[-1]
        return last[1], last[2], last[3], last[4]

    def start_damping(self, sx=0.04, sy=0.04, oy=3.0):
        """启动阻尼振荡 - 表情切换后的软着陆"""
        self._damping_active = True
        self._damp_time = 0.0
        self._damp_sx = sx
        self._damp_sy = sy
        self._damp_oy = oy


class AnimationDirector:
    """动画编排器 - 管理过渡规则、情绪节奏、身体姿态

    职责:
    1. 表情切换时的过渡规则(duration + easing)
    2. 情绪驱动的身体姿态(偏移、呼吸参数)
    3. 动画原则: anticipation→action→settle→pause
    """

    # 表情过渡规则: (from_expr, to_expr) → {duration, easing}
    TRANSITION_RULES = {
        # 默认 → 开心: 快速、弹性
        ("idle", "happy"):      {"duration": 0.30, "easing": "ease_out_back"},
        ("idle", "excited"):    {"duration": 0.25, "easing": "ease_out_back"},
        # 任何 → 惊讶: 极快、线性(反射动作)
        ("any", "surprised"):   {"duration": 0.10, "easing": "linear"},
        # 惊讶 → 任何: 慢、缓动(平复)
        ("surprised", "any"):   {"duration": 0.60, "easing": "ease_in_out_sine"},
        # 任何 → 生气: 快、硬(突变)
        ("any", "angry"):       {"duration": 0.15, "easing": "ease_in_quad"},
        # 开心 → 失落: 慢、软(情绪下坠)
        ("happy", "sad"):       {"duration": 0.80, "easing": "ease_in_out_sine"},
        ("excited", "sad"):     {"duration": 0.80, "easing": "ease_in_out_sine"},
        # 任何 → 困倦: 很慢(渐入)
        ("any", "sleepy"):      {"duration": 1.00, "easing": "ease_in_out_sine"},
        # 困倦 → 惊讶(醒): 瞬间
        ("sleepy", "surprised"):{"duration": 0.08, "easing": "linear"},
    }

    # 情绪身体姿态: 表情名 → (y偏移, 呼吸周期s, 呼吸幅度, 微抖x, 微抖y)
    EMOTION_BODY = {
        "idle":      {"y":  0,   "breath_period": 3.5, "breath_amp": 0.02,
                      "shake_x": 0,   "shake_y": 0},
        "happy":     {"y": -3,   "breath_period": 2.5, "breath_amp": 0.04,
                      "shake_x": 0,   "shake_y": 0},
        "laugh":     {"y": -4,   "breath_period": 2.2, "breath_amp": 0.06,
                      "shake_x": 0,   "shake_y": 1.5},
        "excited":   {"y": -5,   "breath_period": 2.0, "breath_amp": 0.06,
                      "shake_x": 1.0, "shake_y": 0},
        "angry":     {"y":  2,   "breath_period": 2.8, "breath_amp": 0.05,
                      "shake_x": 1.5, "shake_y": 0},
        "surprised": {"y": -15,  "breath_period": 3.0, "breath_amp": 0.03,
                      "shake_x": 0,   "shake_y": 0},
        "scared":    {"y": -5,   "breath_period": 2.0, "breath_amp": 0.04,
                      "shake_x": 2.0, "shake_y": 0.5},
        "sad":       {"y":  2,   "breath_period": 4.5, "breath_amp": 0.01,
                      "shake_x": 0,   "shake_y": 0},
        "sleepy":    {"y":  3,   "breath_period": 5.0, "breath_amp": 0.01,
                      "shake_x": 0,   "shake_y": 0},
        "bored":     {"y":  1,   "breath_period": 4.0, "breath_amp": 0.015,
                      "shake_x": 0,   "shake_y": 0},
        "curious":   {"y": -2,   "breath_period": 3.0, "breath_amp": 0.03,
                      "shake_x": 0,   "shake_y": 0},
        "thinking":  {"y":  0,   "breath_period": 3.5, "breath_amp": 0.02,
                      "shake_x": 0,   "shake_y": 0},
        "confused":  {"y":  0,   "breath_period": 3.2, "breath_amp": 0.03,
                      "shake_x": 0.5, "shake_y": 0},
        "smile":     {"y": -1,   "breath_period": 3.2, "breath_amp": 0.03,
                      "shake_x": 0,   "shake_y": 0},
        "relaxed":   {"y":  1,   "breath_period": 4.0, "breath_amp": 0.015,
                      "shake_x": 0,   "shake_y": 0},
        "speaking":  {"y":  0,   "breath_period": 3.0, "breath_amp": 0.03,
                      "shake_x": 0,   "shake_y": 0},
        # look/wink/blink用idle默认
        "look_left":  {"y": 0, "breath_period": 3.5, "breath_amp": 0.02,
                       "shake_x": 0, "shake_y": 0},
        "look_right": {"y": 0, "breath_period": 3.5, "breath_amp": 0.02,
                       "shake_x": 0, "shake_y": 0},
        "look_up":    {"y": -1, "breath_period": 3.5, "breath_amp": 0.02,
                       "shake_x": 0, "shake_y": 0},
        "blink":      {"y": 0, "breath_period": 3.5, "breath_amp": 0.02,
                       "shake_x": 0, "shake_y": 0},
        "wink":       {"y": 0, "breath_period": 3.5, "breath_amp": 0.02,
                       "shake_x": 0, "shake_y": 0},
    }

    # 默认身体姿态(用于无映射的表情)
    _DEFAULT_BODY = {"y": 0, "breath_period": 3.5, "breath_amp": 0.02,
                     "shake_x": 0, "shake_y": 0}

    def __init__(self, squash_stretch):
        self.squash = squash_stretch
        self.current_expr = "idle"
        self.prev_expr = "idle"
        self._renderer = None  # v10: renderer引用(由main设置)

        # 当前身体姿态参数(平滑过渡中)
        self.body_y = 0.0
        self.body_shake_x = 0.0
        self.body_shake_y = 0.0
        self.breath_period = 3.5
        self.breath_amp = 0.02

        # 过渡动画
        self._transitioning = False
        self._trans_time = 0.0
        self._trans_duration = 0.3
        self._trans_from_body = None
        self._trans_to_body = None

        # 情绪驱动的Squash映射
        self.EMOTION_SQUASH = {
            "surprised": ("surprise", 1.0),
            "excited":   ("bounce",   0.6),
            "happy":     ("tap",      0.4),
            "laugh":     ("tap",      0.5),
            "angry":     ("shake",    0.7),
            "scared":    ("shake",    0.5),
        }

    def on_expression_change(self, expr_name):
        """表情变化回调 - 编排过渡动画和身体姿态 + v10霓虹色同步"""
        self.prev_expr = self.current_expr
        self.current_expr = expr_name

        # v10: 通知Renderer切换霓虹色
        if hasattr(self, '_renderer') and self._renderer:
            self._renderer.set_neon_color(expr_name)

        # 1. 启动身体姿态过渡
        from_body = self.EMOTION_BODY.get(self.prev_expr, self._DEFAULT_BODY)
        to_body = self.EMOTION_BODY.get(expr_name, self._DEFAULT_BODY)
        rule = self._get_transition_rule(self.prev_expr, expr_name)
        self._transitioning = True
        self._trans_time = 0.0
        self._trans_duration = rule["duration"]
        self._trans_from_body = from_body
        self._trans_to_body = to_body

        # 2. 触发Squash & Stretch
        squash_info = self.EMOTION_SQUASH.get(expr_name)
        if squash_info and not self.squash.active:
            style, intensity = squash_info
            self.squash.trigger_squash(intensity, style)

    def _get_transition_rule(self, from_expr, to_expr):
        """查找过渡规则，支持通配符"any" """
        # 精确匹配优先
        rule = self.TRANSITION_RULES.get((from_expr, to_expr))
        if rule:
            return rule
        # from=any
        rule = self.TRANSITION_RULES.get(("any", to_expr))
        if rule:
            return rule
        # to=any
        rule = self.TRANSITION_RULES.get((from_expr, "any"))
        if rule:
            return rule
        # 默认
        return {"duration": 0.35, "easing": "ease_out_quad"}

    def update(self, dt):
        """每帧更新身体姿态插值"""
        if self._transitioning:
            self._trans_time += dt
            t = min(1.0, self._trans_time / max(0.01, self._trans_duration))

            # 使用对应的easing函数
            easing_name = self._get_transition_rule(
                self.prev_expr, self.current_expr).get("easing", "ease_out_quad")
            easing_fn = getattr(Easing, easing_name, Easing.ease_out_quad)
            t_eased = easing_fn(t)

            # 插值身体参数
            fb = self._trans_from_body
            tb = self._trans_to_body
            self.body_y = fb["y"] + (tb["y"] - fb["y"]) * t_eased
            self.breath_period = fb["breath_period"] + (tb["breath_period"] - fb["breath_period"]) * t_eased
            self.breath_amp = fb["breath_amp"] + (tb["breath_amp"] - fb["breath_amp"]) * t_eased
            self.body_shake_x = fb["shake_x"] + (tb["shake_x"] - fb["shake_x"]) * t_eased
            self.body_shake_y = fb["shake_y"] + (tb["shake_y"] - fb["shake_y"]) * t_eased

            if t >= 1.0:
                self._transitioning = False
        else:
            # 微抖动(随机高斯噪声)
            if self.body_shake_x > 0:
                self.body_y += random.gauss(0, self.body_shake_x * 0.3) * dt * 10
            if self.body_shake_y > 0:
                pass  # shake_y通过Squash的offset_y实现

    def get_body_offset(self, idle_bounce_t):
        """获取当前帧的身体偏移量 (offset_x, offset_y)"""
        ox = 0.0
        oy = self.body_y  # 情绪偏移

        # 微抖动
        if self.body_shake_x > 0.1:
            ox += random.gauss(0, self.body_shake_x)

        # 呼吸Y偏移
        breath_y = math.sin(idle_bounce_t * 2 * math.pi / max(0.5, self.breath_period)) * self.breath_amp * 8
        oy += breath_y

        # Squash & Stretch叠加
        oy += self.squash.offset_y
        ox += self.squash.offset_x

        return ox, oy

    def get_breath_params(self):
        """获取当前情绪下的呼吸参数 (period, amplitude)"""
        return self.breath_period, self.breath_amp


# ── 渲染引擎 ──
class Renderer:
    """v10霓虹赛博渲染引擎 — 分层绘制：环境→光晕→身体(霓虹眼+嘴)→VFX→扫描线→Glitch"""

    # 颜色常量 — 全部从StyleConfig引用
    OUTLINE_COLOR = None           # None=跟随霓虹色
    PUPIL_COLOR   = (0, 0, 0)     # 纯黑瞳孔
    HIGHLIGHT_COL = (255, 255, 255)
    BLUSH_COLOR   = (255, 50, 150, 120)  # 霓虹粉腮红
    BROW_COLOR    = None           # 跟随霓虹色

    def __init__(self, screen):
        self.screen = screen
        self.face_center_x = WIDTH // 2
        self.face_center_y = HEIGHT // 2 - 50
        self.eye_r_x = 160
        self.eye_r_y = 170
        self.spacing = 580
        self.pupil_mode = "normal"      # "normal"/"heart"/"star"
        self._pupil_mode_timer = 0.0
        self._current_bg = BG_COLOR     # 动态背景色

        # v10: 霓虹色状态 — 当前/目标/过渡
        self._neon_current = list(StyleConfig.NEON_DEFAULT)  # 当前霓虹色(浮点)
        self._neon_target = list(StyleConfig.NEON_DEFAULT)   # 目标霓虹色
        self._neon_speed = 4.0          # 霓虹色过渡速度
        self._current_expr = "idle"     # 当前表情(用于颜色映射)

        # v10: 呼吸发光
        self._bloom_phase = 0.0         # 发光脉冲相位

        # v10: 扫描线状态
        self._scanline_offset = 0.0     # 扫描线Y偏移

        # v10: Glitch状态
        self._glitch_timer = random.uniform(StyleConfig.GLITCH_INTERVAL_MIN,
                                            StyleConfig.GLITCH_INTERVAL_MAX)
        self._glitch_active = False
        self._glitch_time = 0.0
        self._glitch_lines = []         # [(y, offset, width), ...]

        # v10: 预渲染扫描线surface(缓存)
        self._scanline_surf = None
        self._build_scanline_surface()

        # 字体(中文字体优先: 文泉驿正黑)
        pygame.freetype.init()
        cn_font_path = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
        try:
            self.font_cn = pygame.freetype.Font(cn_font_path, 22)
            self.font_cn_body = pygame.freetype.Font(cn_font_path, 16)
            self.font_cn_small = pygame.freetype.Font(cn_font_path, 13)
            self.font_cn_t = pygame.freetype.Font(cn_font_path, 40)   # 大标题 +5
            self.font_cn_t.strong = True  # 加粗
            self.font_cn_b = pygame.freetype.Font(cn_font_path, 32)   # 大正文 +5
            self.font_cn_h = pygame.freetype.Font(cn_font_path, 24)   # 小提示 +5
        except:
            self.font_cn = pygame.freetype.Font(None, 22)
            self.font_cn_body = pygame.freetype.Font(None, 16)
            self.font_cn_small = pygame.freetype.Font(None, 13)
            self.font_cn_t = pygame.freetype.Font(None, 40)
            self.font_cn_b = pygame.freetype.Font(None, 32)
            self.font_cn_h = pygame.freetype.Font(None, 24)
        try:
            self.font_title = pygame.freetype.Font("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
            self.font_body = pygame.freetype.Font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
            self.font_hint = pygame.freetype.Font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
        except:
            self.font_title = pygame.freetype.Font(None, 22)
            self.font_body = pygame.freetype.Font(None, 16)
            self.font_hint = pygame.freetype.Font(None, 13)

    def _build_scanline_surface(self):
        """预渲染全屏扫描线(半透明条纹)"""
        self._scanline_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self._scanline_surf.fill((0, 0, 0, 0))
        gap = StyleConfig.SCANLINE_GAP
        for y in range(0, HEIGHT, gap):
            pygame.draw.line(self._scanline_surf, StyleConfig.SCANLINE_COLOR,
                           (0, y), (WIDTH, y), 1)

    def set_neon_color(self, expr_name):
        """v10: 根据表情设置霓虹色目标"""
        self._current_expr = expr_name
        target = StyleConfig.get_neon_color(expr_name)
        self._neon_target = list(target)

    def get_neon_color(self):
        """获取当前插值后的霓虹色(RGB)"""
        return (int(self._neon_current[0]),
                int(self._neon_current[1]),
                int(self._neon_current[2]))

    def set_pupil_mode(self, mode, duration=3.0):
        """设置瞳孔特殊形态: normal/heart/star"""
        self.pupil_mode = mode
        self._pupil_mode_timer = duration

    def update(self, dt):
        """v10: 更新渲染器状态 — 瞳孔计时 + 霓虹色过渡 + 扫描线 + Glitch"""
        # 瞳孔形态计时
        if self._pupil_mode_timer > 0:
            self._pupil_mode_timer -= dt
            if self._pupil_mode_timer <= 0:
                self.pupil_mode = "normal"
                self._pupil_mode_timer = 0

        # v10: 霓虹色过渡
        for i in range(3):
            diff = self._neon_target[i] - self._neon_current[i]
            self._neon_current[i] += diff * min(1.0, self._neon_speed * dt)

        # v10: 呼吸发光相位
        self._bloom_phase += dt * 1.2  # ~1.2Hz

        # v10: 扫描线滚动
        self._scanline_offset += StyleConfig.SCANLINE_SPEED * dt
        if self._scanline_offset >= HEIGHT:
            self._scanline_offset -= HEIGHT

        # v10: Glitch触发
        if not self._glitch_active:
            self._glitch_timer -= dt
            if self._glitch_timer <= 0:
                self._glitch_active = True
                self._glitch_time = 0
                # 生成随机Glitch行
                self._glitch_lines = []
                num_lines = random.randint(3, 8)
                for _ in range(num_lines):
                    y = random.randint(0, HEIGHT)
                    offset = random.randint(-StyleConfig.GLITCH_INTENSITY,
                                           StyleConfig.GLITCH_INTENSITY)
                    w = random.randint(50, WIDTH // 2)
                    self._glitch_lines.append((y, offset, w))
                self._glitch_timer = random.uniform(StyleConfig.GLITCH_INTERVAL_MIN,
                                                    StyleConfig.GLITCH_INTERVAL_MAX)
        else:
            self._glitch_time += dt
            if self._glitch_time >= StyleConfig.GLITCH_DURATION:
                self._glitch_active = False
                self._glitch_time = 0
                self._glitch_lines = []

    def draw(self, state, face_scale=1.0, face_offset_x=0,
             body_scale_x=1.0, body_scale_y=1.0, body_offset_x=0, body_offset_y=0,
             vfx_mgr=None, ambient_mgr=None, perf=None, spacing_scale=1.0):
        """v10霓虹赛博分层绘制 — 环境→光晕→身体(霓虹眼+嘴)→VFX→扫描线→Glitch"""
        # Layer 5a: 环境层 — 霓虹深空黑背景
        if ambient_mgr:
            ambient_mgr.draw_bg(self.screen)
            self._current_bg = ambient_mgr.get_bg_color()
        else:
            self.screen.fill(StyleConfig.BG_COLOR_RGB)
            self._current_bg = StyleConfig.BG_COLOR_RGB

        # Layer 5b: 环境层 — 面部光晕(在身体下方, perf>=HALF_DOTS才关闭)
        if ambient_mgr and (perf is None or perf.enable_glow):
            ambient_mgr.draw_glow(self.screen)

        # Layer 1+2+3: 身体+表情+眼部(霓虹几何眼+嘴)
        self._draw_body(state, face_scale, face_offset_x,
                        body_scale_x, body_scale_y, body_offset_x, body_offset_y,
                        spacing_scale)

        # Layer 4: 特效层 (perf>=NO_VFX才关闭)
        if vfx_mgr and (perf is None or perf.enable_vfx):
            self._draw_vfx(vfx_mgr)

        # Layer 5c: 环境层 — 氛围光斑(在特效上方, perf>=NO_DOTS才关闭)
        if ambient_mgr and (perf is None or perf.enable_dots):
            ambient_mgr.draw_dots(self.screen, half=perf.dots_half if perf else False)

        # v10 Layer 6: 扫描线叠加
        if perf is None or perf.enable_vfx:
            self._draw_scanlines()

        # v10 Layer 7: Glitch效果
        if self._glitch_active and (perf is None or perf.enable_vfx):
            self._draw_glitch()

    def _draw_body(self, s, face_scale, offset_x, bsx, bsy, box, boy,
                   spacing_scale=1.0):
        """v10: 身体层 — 霓虹几何眼 + 线条嘴 + 发光"""
        cx = self.face_center_x + offset_x + box
        cy = self.face_center_y + boy
        rx = int(self.eye_r_x * face_scale * bsx)
        ry = int(self.eye_r_y * face_scale * bsy)
        sp = int(self.spacing * face_scale * bsx * spacing_scale)
        neon = self.get_neon_color()

        # 先绘制腮红(霓虹粉)
        if s.blush > 0.01:
            self._draw_blush(cx, cy, sp, rx, ry, s.blush, face_scale)

        for side in [-1, 1]:
            l_open = s.l_open if side < 0 else s.r_open
            l_w    = s.l_w if side < 0 else s.r_w
            l_y    = s.l_y if side < 0 else s.r_y
            l_cut  = s.l_cut if side < 0 else s.r_cut
            brow   = s.brow_l if side < 0 else s.brow_r

            ex = cx + side * sp // 2
            ey = cy + l_y * face_scale
            rw = int(rx * l_w)
            rh = int(ry * max(0.01, l_open))

            if rh < 3:
                # v10: 闭眼 — 微弧曲线(模拟闭合眼睑，非生硬直线)
                lw = max(3, int(5 * face_scale))
                pts = [(ex - rw + int(rw * 2 * (i / 11.0)),
                        ey + int(math.sin((i / 11.0) * math.pi) * 4))
                       for i in range(12)]
                # 外发光(宽弧线)
                pygame.draw.lines(self.screen, StyleConfig.dim_color(neon, 0.3),
                                False, pts, lw + 5)
                # 核心弧线
                pygame.draw.lines(self.screen, neon, False, pts, lw)
            else:
                # v10: 霓虹几何眼 + 外发光(无需v9的裁切/瞳孔)
                self._draw_neon_eye(ex, ey, rw, rh, neon)

        # [v10: 眉毛暂时禁用]

        # [v10: 嘴巴暂时禁用]

    # ═══ v10: 霓虹赛博绘制方法 ═══

    def _draw_neon_eye(self, ex, ey, rw, rh, neon):
        """v10: 霓虹几何眼 — 无硬边外框，bloom渐变过渡到眼底"""
        bloom_pulse = 0.7 + 0.3 * math.sin(self._bloom_phase)

        # 1) 外发光(bloom) — 从眼底边缘到外层渐变，替代硬描边
        margin = 40
        max_spread = 1.0 + StyleConfig.BLOOM_LAYERS * 0.25 * StyleConfig.BLOOM_SPREAD
        surf_hw = int(rw * max_spread) + margin
        surf_hh = int(rh * max_spread) + margin
        bloom_surf = pygame.Surface((surf_hw * 2, surf_hh * 2), pygame.SRCALPHA)
        bloom_surf.fill((0, 0, 0, 0))
        bcx, bcy = surf_hw, surf_hh
        for i in range(StyleConfig.BLOOM_LAYERS, 0, -1):
            spread = 1.0 + i * 0.25 * StyleConfig.BLOOM_SPREAD
            brw = int(rw * spread)
            brh = int(rh * spread)
            alpha = int(StyleConfig.BLOOM_MAX_ALPHA * (i / StyleConfig.BLOOM_LAYERS) * bloom_pulse)
            alpha = max(0, min(255, alpha))
            pygame.draw.ellipse(bloom_surf, (*neon, alpha),
                              (bcx - brw, bcy - brh, brw * 2, brh * 2))
        self.screen.blit(bloom_surf, (ex - surf_hw, ey - surf_hh))

        # 2) 眼底渐变 — 覆盖更大(几乎满眼) + 颜色更亮
        eye_surf = pygame.Surface((rw * 2 + 10, rh * 2 + 10), pygame.SRCALPHA)
        eye_surf.fill((0, 0, 0, 0))
        # 眼底颜色跟随表情霓虹色变化: 基础蓝灰 + 霓虹色混合
        base_col = (25, 40, 70)  # 基础蓝灰
        blends = [(0.05, 120), (0.18, 190), (0.35, 245)]  # (霓虹占比, alpha)
        eye_layers = []
        for bf, al in blends:
            r = int(base_col[0] * (1 - bf) + neon[0] * bf)
            g = int(base_col[1] * (1 - bf) + neon[1] * bf)
            b = int(base_col[2] * (1 - bf) + neon[2] * bf)
            eye_layers.append((min(255, r), min(255, g), min(255, b), al))
        n_layers = len(eye_layers)
        for i, (cr, cg, cb, ca) in enumerate(eye_layers):
            t = i / (n_layers - 1)
            frac = 1.0 - t * 0.15
            lrw = max(3, int(rw * frac))
            lrh = max(3, int(rh * frac))
            pad_x = (rw * 2 + 10 - lrw * 2) // 2
            pad_y = (rh * 2 + 10 - lrh * 2) // 2
            pygame.draw.ellipse(eye_surf, (cr, cg, cb, ca),
                              (pad_x, pad_y, lrw * 2, lrh * 2))
        self.screen.blit(eye_surf, (ex - rw - 5, ey - rh - 5))

        # 3) 内部霓虹辉光
        glow_surf = pygame.Surface((rw * 2 + 4, rh * 2 + 4), pygame.SRCALPHA)
        glow_surf.fill((0, 0, 0, 0))
        pygame.draw.ellipse(glow_surf, (*neon, int(55 * bloom_pulse)),
                          (0, 0, rw * 2 + 4, rh * 2 + 4))
        cw, ch = rw // 2, rh // 2
        pygame.draw.ellipse(glow_surf, (*neon, int(30 * bloom_pulse)),
                          (rw - cw + 2, rh - ch + 2, cw * 2, ch * 2))
        self.screen.blit(glow_surf, (ex - rw - 2, ey - rh - 2))

        # 4) 霓虹瞳孔(再大) + 白色高光
        pupil_r = max(8, int(min(rw, rh) * 0.52))
        bright_neon = tuple(min(255, int(c * 1.5)) for c in neon)
        pygame.draw.circle(self.screen, bright_neon, (ex, ey - int(rh * 0.05)), pupil_r)
        hl_r = max(1, pupil_r // 3)
        pygame.draw.circle(self.screen, (255, 255, 255),
                         (ex - int(pupil_r * 0.4), ey - int(rh * 0.05) - int(pupil_r * 0.4)), hl_r)

    def _draw_mouth(self, cx, cy, sp, rx, ry, s, face_scale, neon):
        """v10: 拟人嘴型 — 厚线条绘制弧线(glow+核心+高亮)"""
        expr = self._current_expr
        mouth_y = cy + int(ry * 0.65 * face_scale)
        mouth_w = int(sp * StyleConfig.MOUTH_WIDTH * 0.5)
        mx = cx
        my = mouth_y
        lip_w = max(6, int(12 * face_scale))  # 嘴唇线条宽度

        def draw_lip_arc(pts, width):
            """用厚线条绘制自然嘴唇弧线: glow + 核心 + 高亮"""
            # 外发光(宽)
            pygame.draw.lines(self.screen, StyleConfig.dim_color(neon, 0.3),
                            False, pts, width + 6)
            # 核心
            pygame.draw.lines(self.screen, neon, False, pts, width)
            # 内部高亮(细)
            bright = tuple(min(255, int(c * 1.25)) for c in neon)
            inner_w = max(2, width - 4)
            pygame.draw.lines(self.screen, bright, False, pts, inner_w)

        if expr in ("happy", "laugh", "excited", "smile", "heart_eyes", "star_eyes"):
            # 微笑弧线
            pts = [(mx - mouth_w + int(mouth_w * 2 * (i / 29.0)),
                    my + int(math.sin((i / 29.0) * math.pi) * 16))
                   for i in range(30)]
            draw_lip_arc(pts, lip_w)

        elif expr in ("sad", "scared"):
            pts = [(mx - mouth_w + int(mouth_w * 2 * (i / 29.0)),
                    my - int(math.sin((i / 29.0) * math.pi) * 14))
                   for i in range(30)]
            draw_lip_arc(pts, lip_w)

        elif expr == "surprised":
            # O型嘴 — 实心椭圆(已有厚度)
            ow = int(mouth_w * 0.5)
            oh = int(14 * face_scale)
            pygame.draw.ellipse(self.screen, StyleConfig.dim_color(neon, 0.3),
                              (mx - ow - 6, my - oh - 6, ow * 2 + 12, oh * 2 + 12))
            pygame.draw.ellipse(self.screen, neon,
                              (mx - ow, my - oh, ow * 2, oh * 2))
            bright = tuple(min(255, int(c * 1.25)) for c in neon)
            iow, ioh = max(2, ow - 4), max(2, oh - 4)
            pygame.draw.ellipse(self.screen, bright,
                              (mx - iow, my - ioh, iow * 2, ioh * 2))

        elif expr == "angry":
            pts = [(mx - mouth_w + int(mouth_w * 2 * (i / 23.0)),
                    my - int(math.sin((i / 23.0) * math.pi) * 8))
                   for i in range(24)]
            draw_lip_arc(pts, lip_w + 1)

        elif expr == "speaking":
            phase = (pygame.time.get_ticks() % 300) / 300.0
            open_h = int(8 * math.sin(phase * math.pi) * face_scale)
            if open_h < 3:
                draw_lip_arc([(mx - mouth_w, my), (mx + mouth_w, my)], lip_w)
            else:
                ow = int(mouth_w * 0.6)
                pygame.draw.ellipse(self.screen, StyleConfig.dim_color(neon, 0.3),
                                  (mx - ow - 4, my - open_h - 4, ow * 2 + 8, open_h * 2 + 8))
                pygame.draw.ellipse(self.screen, neon,
                                  (mx - ow, my - open_h, ow * 2, open_h * 2))

        else:
            # idle: 微弧
            pts = [(mx - mouth_w + int(mouth_w * 2 * (i / 23.0)),
                    my - int(math.sin((i / 23.0) * math.pi) * 8))
                   for i in range(24)]
            draw_lip_arc(pts, lip_w)

    def _draw_scanlines(self):
        """v10: 扫描线叠加 — 预渲染surface + 简单偏移blit(无额外surface分配)"""
        offset = int(self._scanline_offset) % StyleConfig.SCANLINE_GAP
        if self._scanline_surf:
            # 直接在screen上blit，用offset偏移；screen会自动裁剪
            # 双blit处理wrap-around(顶部露出空白由第二张补上)
            self.screen.blit(self._scanline_surf, (0, offset))
            if offset > 0:
                self.screen.blit(self._scanline_surf, (0, offset - HEIGHT))

    def _draw_glitch(self):
        """v10: Glitch效果 — 随机行偏移+色差条纹"""
        glitch_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        neon = self.get_neon_color()

        for y, offset, w in self._glitch_lines:
            # 从屏幕抓取行并偏移
            if 0 <= y < HEIGHT:
                try:
                    strip = self.screen.subsurface(pygame.Rect(0, y, min(w, WIDTH), 2))
                    glitch_surf.blit(strip, (offset, y))
                except:
                    pass
            # 色差条纹
            strip_w = min(w, WIDTH)
            color = (neon[0], neon[1] // 2, neon[2] // 2, 30)
            pygame.draw.rect(glitch_surf, color, (offset, y, strip_w, 2))

        self.screen.blit(glitch_surf, (0, 0))

    # ═══ 保留旧方法(兼容回退) ═══

    def _draw_gradient_eye(self, ex, ey, rw, rh):
        """[兼容] 渐变眼白 + 2px描边 — 同心椭圆实现径向渐变(白→微灰)"""
        # 描边(外圈深色)
        outline_rect = pygame.Rect(ex - rw - 2, ey - rh - 2, (rw + 2) * 2, (rh + 2) * 2)
        pygame.draw.ellipse(self.screen, (45, 45, 45), outline_rect)

        # 渐变层: 5层同心椭圆从外到内，颜色从暗到亮
        layers = 5
        for i in range(layers):
            t = i / (layers - 1)  # 0→1 从外到内
            r = int(200 + 40 * t)
            g = int(210 + 35 * t)
            b = int(230 + 25 * t)
            frac = 1.0 - t * 0.7
            lrw = max(1, int(rw * frac))
            lrh = max(1, int(rh * frac))
            rect = pygame.Rect(ex - lrw, ey - lrh, lrw * 2, lrh * 2)
            pygame.draw.ellipse(self.screen, (r, g, b), rect)

    def _draw_pupil(self, ex, ey, rw, rh, pupil_scale, highlight, face_scale):
        """瞳孔系统：圆形瞳孔 + 高光点 + 特殊形态"""
        # 瞳孔基准半径：眼白的30% * pupil_scale
        base_r = min(rw, rh) * 0.30
        pr = max(3, int(base_r * pupil_scale))

        # 瞳孔Y偏移：略偏上，更自然
        py = ey - int(rh * 0.05)

        mode = self.pupil_mode

        if mode == "heart":
            self._draw_heart_pupil(ex, py, pr, highlight)
        elif mode == "star":
            self._draw_star_pupil(ex, py, pr, highlight)
        else:
            # 普通圆形瞳孔
            pygame.draw.circle(self.screen, self.PUPIL_COLOR, (ex, py), pr)

            # ── 高光 ──
            if highlight > 0.05:
                self._draw_highlights(ex, py, pr, highlight, pupil_scale)

    def _draw_highlights(self, ex, ey, pr, intensity, pupil_scale):
        """高光点系统：主高光(左上) + 次高光(右下)"""
        # 主高光：瞳孔左上方，大小随intensity
        hl_r = max(2, int(pr * 0.35 * intensity))
        hl_x = ex - int(pr * 0.3)
        hl_y = ey - int(pr * 0.3)

        # 半透明高光
        hl_surf = pygame.Surface((hl_r * 2 + 2, hl_r * 2 + 2), pygame.SRCALPHA)
        alpha = int(220 * intensity)
        pygame.draw.circle(hl_surf, (*self.HIGHLIGHT_COL, alpha),
                          (hl_r + 1, hl_r + 1), hl_r)
        self.screen.blit(hl_surf, (hl_x - hl_r - 1, hl_y - hl_r - 1))

        # 次高光(小点，右下方) — 仅intensity>0.5时显示
        if intensity > 0.5:
            hl2_r = max(1, int(pr * 0.15 * intensity))
            hl2_x = ex + int(pr * 0.25)
            hl2_y = ey + int(pr * 0.25)
            hl2_surf = pygame.Surface((hl2_r * 2 + 2, hl2_r * 2 + 2), pygame.SRCALPHA)
            alpha2 = int(140 * intensity)
            pygame.draw.circle(hl2_surf, (*self.HIGHLIGHT_COL, alpha2),
                              (hl2_r + 1, hl2_r + 1), hl2_r)
            self.screen.blit(hl2_surf, (hl2_x - hl2_r - 1, hl2_y - hl2_r - 1))

    def _draw_heart_pupil(self, cx, cy, size, highlight):
        """爱心瞳孔 — 两个圆弧+三角底部"""
        # 用两个重叠圆+三角构成心形
        r = max(3, int(size * 0.45))
        offset = int(r * 0.6)

        # 填充心形
        heart_surf = pygame.Surface((size * 3, size * 3), pygame.SRCALPHA)
        hcx, hcy = size * 3 // 2, size * 3 // 2

        # 左半圆
        pygame.draw.circle(heart_surf, self.PUPIL_COLOR, (hcx - offset, hcy - offset // 2), r)
        # 右半圆
        pygame.draw.circle(heart_surf, self.PUPIL_COLOR, (hcx + offset, hcy - offset // 2), r)
        # 底部三角
        points = [
            (hcx - size, hcy),
            (hcx + size, hcy),
            (hcx, hcy + int(size * 1.2))
        ]
        pygame.draw.polygon(heart_surf, self.PUPIL_COLOR, points)

        self.screen.blit(heart_surf, (cx - size * 3 // 2, cy - size * 3 // 2))

        # 爱心上的高光
        if highlight > 0.3:
            hl_r = max(1, int(r * 0.3))
            hl_surf = pygame.Surface((hl_r * 2 + 2, hl_r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(hl_surf, (*self.HIGHLIGHT_COL, int(180 * highlight)),
                              (hl_r + 1, hl_r + 1), hl_r)
            self.screen.blit(hl_surf, (cx - offset - hl_r - 1, cy - offset // 2 - hl_r - 1))

    def _draw_star_pupil(self, cx, cy, size, highlight):
        """星星瞳孔 — 五角星"""
        r_outer = max(4, int(size * 0.9))
        r_inner = max(2, int(r_outer * 0.4))
        points = []
        for i in range(10):
            angle = math.pi / 2 + i * math.pi / 5  # 从顶部开始
            r = r_outer if i % 2 == 0 else r_inner
            px = cx + int(r * math.cos(angle))
            py = cy - int(r * math.sin(angle))
            points.append((px, py))

        if len(points) >= 3:
            pygame.draw.polygon(self.screen, self.PUPIL_COLOR, points)
            # 中心亮点
            pygame.draw.circle(self.screen, (60, 60, 80), (cx, cy), max(2, r_inner // 2))

        # 星星高光
        if highlight > 0.3:
            hl_r = max(1, int(r_outer * 0.2))
            hl_surf = pygame.Surface((hl_r * 2 + 2, hl_r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(hl_surf, (*self.HIGHLIGHT_COL, int(200 * highlight)),
                              (hl_r + 1, hl_r + 1), hl_r)
            self.screen.blit(hl_surf, (cx - r_outer // 3 - hl_r, cy - r_outer // 3 - hl_r))

    def _draw_brow(self, ex, ey, rw, rh, brow_val, face_scale, side):
        """v10: Bézier弧形眉毛 — 归一化参数, 正确方向"""
        neon = self.get_neon_color()
        brow_y = ey - rh - int(25 * face_scale)

        # brow_val范围 -8~+8, 归一化到 -1~+1
        # 负值(开心/惊讶)=扬起, 正值(生气/悲伤)=压低
        bv = max(-1.0, min(1.0, brow_val / 8.0))

        # 长度: |brow_val|越大越长
        intensity = max(0.3, abs(bv))
        # 最小长度=眼直径(rw*2)*1.1, 动态增长
        min_len = int(rw * 2.2)
        length = max(min_len, min(int(rw * 4.0), int(rw * 3.0 * intensity)))

        # ── P0: 内侧(近鼻梁) — 轻微跟随表情 ──
        # 扬起(bv<0): 内端上提; 压低(bv>0): 内端下沉
        inner_off = int(bv * rw * 0.06)
        p0 = (ex - side * int(rw * 0.15), brow_y + inner_off)

        # ── P2: 外侧(近太阳穴) — 角度偏转 ──
        # 注意符号: -bv = 负值(扬起)→正角度(外端上翘)
        angle_deg = max(-20, min(20, -bv * 20))
        ang = math.radians(angle_deg)
        p2 = (ex + side * length, brow_y - int(length * math.sin(ang)))

        # ── P1: 控制点 → 拱高 ──
        # -bv: 扬起时正拱高(上拱), 压低时负拱高(下压)
        arch = int(-bv * rw * 0.25)
        p1 = ((p0[0] + p2[0]) // 2, (p0[1] + p2[1]) // 2 - arch)

        # ── 采样Bézier曲线(30点) ──
        n = 30
        curve = []
        for i in range(n):
            t = i / (n - 1)
            mt = 1 - t
            # 二次Bézier: B(t) = (1-t)²P0 + 2(1-t)tP1 + t²P2
            x = int(mt*mt * p0[0] + 2*mt*t * p1[0] + t*t * p2[0])
            y = int(mt*mt * p0[1] + 2*mt*t * p1[1] + t*t * p2[1])
            curve.append((x, y))

        # ── 厚度渐变: 减半(15→之前30) ══
        max_thick = max(4, int(15 * face_scale))
        top_edge = []
        bot_edge = []
        for i in range(n):
            # 切线方向(数值差分)
            if i == 0:
                dx = curve[1][0] - curve[0][0]
                dy = curve[1][1] - curve[0][1]
            elif i == n - 1:
                dx = curve[-1][0] - curve[-2][0]
                dy = curve[-1][1] - curve[-2][1]
            else:
                dx = curve[i+1][0] - curve[i-1][0]
                dy = curve[i+1][1] - curve[i-1][1]

            dl = math.sqrt(dx*dx + dy*dy)
            if dl > 0:
                nx, ny = -dy/dl, dx/dl  # 法线方向
            else:
                nx, ny = 0, -1

            # 厚度: sin曲线渐变, 中间厚两端细
            tr = i / (n - 1)
            taper = math.sin(tr * math.pi)  # 0→1→0
            thick = max(2, int(max_thick * (0.3 + 0.7 * taper)))

            top_edge.append((int(curve[i][0] + nx * thick), int(curve[i][1] + ny * thick)))
            bot_edge.append((int(curve[i][0] - nx * thick), int(curve[i][1] - ny * thick)))

        # ── 填充多边形(上边缘+下边缘反转) ──
        pygame.draw.polygon(self.screen, neon, top_edge + bot_edge[::-1])

    def _draw_blush(self, cx, cy, sp, rx, ry, intensity, face_scale):
        """v10: 霓虹粉腮红 — 眼下半透明粉色发光"""
        if intensity < 0.01:
            return
        blush_w = int(rx * 0.5 * face_scale)
        blush_h = int(ry * 0.25 * face_scale)
        neon = self.get_neon_color()

        for side in [-1, 1]:
            bx = cx + side * sp // 2
            by = cy + int(ry * 0.35 * face_scale)

            surf = pygame.Surface((blush_w * 2 + 4, blush_h * 2 + 4), pygame.SRCALPHA)
            alpha = int(min(1.0, intensity) * 120)
            # 霓虹粉发光
            pygame.draw.ellipse(surf, (255, 50, 150, alpha),
                               (2, 2, blush_w * 2, blush_h * 2))
            # 内核更亮
            inner_alpha = int(min(1.0, intensity) * 60)
            pygame.draw.ellipse(surf, (255, 100, 180, inner_alpha),
                               (blush_w // 2, blush_h // 2, blush_w, blush_h))
            self.screen.blit(surf, (bx - blush_w - 2, by - blush_h - 2))

    def _draw_vfx(self, vfx_mgr):
        """绘制VFX特效层(代理给VFXManager)"""
        vfx_mgr.draw(self.screen)

    def draw_hud(self, info):
        """绘制调试HUD — 半透明信息叠加层"""
        screen = self.screen
        font = self.font  # 复用已有字体
        lines = []
        # NPC状态
        npc_state = info.get("npc_state", "?")
        npc_personality = info.get("personality", "?")
        lines.append(f"NPC: {npc_state}  人格: {npc_personality}")
        # 表情
        expr = info.get("expr", "?")
        expr_phase = info.get("phase", "?")
        lines.append(f"表情: {expr}  阶段: {expr_phase}")
        # 参数过渡
        if info.get("param_trans"):
            lines.append(f"过渡: {info['param_easing']} {info['param_t']:.0%}")
        # FPS & 性能
        fps = info.get("fps", 0)
        perf = info.get("perf", "FULL")
        lines.append(f"FPS: {fps:.0f}  性能: {perf}")
        # 氛围
        mood = info.get("mood", "idle")
        dots = info.get("dots", 0)
        lines.append(f"氛围: {mood}  粒子: {dots}")
        # VFX
        vfx_count = info.get("vfx", 0)
        lines.append(f"VFX: {vfx_count}")

        # 绘制半透明背景条
        hud_h = len(lines) * 22 + 12
        hud_surf = pygame.Surface((280, hud_h), pygame.SRCALPHA)
        hud_surf.fill((0, 0, 0, 160))
        screen.blit(hud_surf, (8, 8))

        # 绘制文字
        for i, line in enumerate(lines):
            surf = font.render(line, True, (200, 255, 200))
            screen.blit(surf, (14, 14 + i * 22))

    # ═══ 新卡片系统 ═══

    def _card_bg(self, surf, w, h, neon, alpha):
        """统一眼底风格卡片: 深蓝灰半透明底 + 霓虹色边框"""
        # 半透明深蓝灰(眼底同色系)
        bg = (20, 28, 50, int(200 * alpha))
        pygame.draw.rect(surf, bg, (0, 0, w, h), border_radius=14)
        # 霓虹色边框(跟随表情)
        neon_a = (*neon, int(150 * alpha))
        pygame.draw.rect(surf, neon_a, (0, 0, w, h), width=2, border_radius=14)

    def draw_todo_card(self, title, lines, alpha=1.0):
        """待办事项卡片 — 支持垂直滚动 + 表面缓存"""
        if alpha <= 0:
            return
        cw, ch = 910, 500
        cx = (WIDTH - cw) // 2
        cy = (HEIGHT - ch) // 2

        neon = self.get_neon_color() if hasattr(self, 'get_neon_color') else (80, 180, 255)

        # 创建卡片和裁切面
        card = pygame.Surface((cw, ch), pygame.SRCALPHA)
        self._card_bg(card, cw, ch, neon, alpha)

        # 标题
        if title:
            t_s, _ = self.font_cn_t.render(title, (200, 225, 250))
            card.blit(t_s, (24, 14))
            pygame.draw.line(card, (*neon, int(80 * alpha)), (24, 50), (cw-24, 50), 1)

        # 创建内容裁切区域（排除标题区）
        content = pygame.Surface((cw - 20, ch - 70), pygame.SRCALPHA)
        vh = ch - 70  # 可见区域高度

        # 计算内容总高
        total_h = int(len(lines) * 64 * 1.4) + 25  # 起始偏移+行高（×1.4 预估算换行）
        # 使用card_mgr的滚动位置
        scroll_y = card_mgr.scroll_y if hasattr(card_mgr, 'scroll_y') else 0.0

        # 预换行（只做一次）
        font = self.font_cn_b
        avail_w = cw - 90
        if card_mgr._wrapped_lines is None:
            card_mgr._wrapped_lines = []
            font = self.font_cn_b
            avail_w = cw - 90
            for line in lines:
                if line.strip() == "":
                    wls = [""]
                else:
                    wls = []
                    cur = ""
                    text = line.strip()
                    for c in text:
                        t = cur + c
                        if font.get_rect(t).width > avail_w and cur:
                            wls.append(cur)
                            cur = c
                        else:
                            cur = t
                    if cur: wls.append(cur)
                    if not wls: wls = [text]
                card_mgr._wrapped_lines.append(wls)
        wrapped_data = card_mgr._wrapped_lines

        y_pos = 0
        for i, line in enumerate(lines):
            if line.strip() == "":
                y_pos += 10; continue
            wls = wrapped_data[i]
            n = len(wls)
            item_top = y_pos
            item_bot = y_pos + 64 + (n - 1) * 38
            if item_bot < scroll_y or item_top > scroll_y + vh:
                y_pos += 64 + (n - 1) * 38; continue
            draw_y = y_pos - scroll_y
            bx, by = 10, draw_y + 4
            # 勾选框
            pygame.draw.rect(content, (*neon, int(160 * alpha)),
                           (bx, by, 18, 18), width=2, border_radius=3)
            pygame.draw.line(content, (*neon, int(200 * alpha)),
                           (bx+4, by+9), (bx+8, by+13), 2)
            pygame.draw.line(content, (*neon, int(200 * alpha)),
                           (bx+8, by+13), (bx+15, by+5), 2)
            for wi, wl in enumerate(wls):
                if wl:
                    try:
                        ws, _ = font.render(wl, (255, 255, 255))
                        content.blit(ws, (54, draw_y + 2 + wi * 38))
                    except Exception as e:
                        print(f"[CARD_TEXT] render error: {e}")
            y_pos += 64 + (n - 1) * 38

        # 创建裁切区域并blit
        clip = pygame.Surface((cw - 20, vh), pygame.SRCALPHA)
        clip.blit(content, (0, 0), (0, 0, cw - 20, vh))
        card.blit(clip, (10, 65))

        # 如果内容超出范围,显示滚动指示条
        if total_h > vh:
            bar_h = max(12, int(vh * vh / total_h))
            bar_y = int(scroll_y / total_h * vh)
            bar_x = cw - 8
            pygame.draw.rect(card, (*neon, int(80 * alpha)),
                           (bar_x, 65 + bar_y, 4, bar_h), border_radius=2)

        hs, _ = self.font_cn_h.render("点击关闭", (100, 130, 160))
        card.blit(hs, (cw - hs.get_width() - 15, ch - 24))
        self.screen.blit(card, (cx, cy))

    def draw_dialog_card(self, title, lines, alpha=1.0):
        """对话回复卡片 — 眼底配色 + 再大20%"""
    def draw_dialog_card(self, title, lines, alpha=1.0):
        """半圆卡片 — 真椭圆半圆(无锯齿) + 高斯模糊 + 70%透明 + 文字居中"""
        if alpha <= 0:
            return
        neon = self.get_neon_color() if hasattr(self, 'get_neon_color') else (80, 180, 255)
        base_col = (25, 40, 70)  # 眼底基础蓝灰
        neon = self.get_neon_color() if hasattr(self, 'get_neon_color') else (80, 180, 255)
        # 最内层: 65%基础蓝灰 + 35%霓虹色, alpha=245(眼底中心透明度)
        bg_r = int(base_col[0] * 0.65 + neon[0] * 0.35)
        bg_g = int(base_col[1] * 0.65 + neon[1] * 0.35)
        bg_b = int(base_col[2] * 0.65 + neon[2] * 0.35)
        bg_a = int(245 * alpha)

        cw, ch = WIDTH - 80, 340
        cx, cy = 40, HEIGHT - ch

        # 真半圆 + 高斯模糊
        card = pygame.Surface((cw, ch), pygame.SRCALPHA)
        pygame.draw.ellipse(card, (bg_r, bg_g, bg_b, bg_a), (0, -ch, cw, ch*2))

        try:
            card = pygame.transform.gaussian_blur(card, 3)
        except AttributeError:
            pass

        # 装饰: 白色小圆点(透明度低, 隐约可见)
        pygame.draw.circle(card, (255, 255, 255, int(60*alpha)), (30, 10), 4)
        pygame.draw.circle(card, (255, 255, 255, int(60*alpha)), (cw-30, 10), 4)
        # 底部小圆点
        for edx in [cw//3, cw*2//3]:
            pygame.draw.circle(card, (200, 210, 230, int(35*alpha)), (edx, ch-6), 2)

        # 文字居中
        y_pos = 30
        tc = (235, 240, 250, min(240, int(220*alpha)))
        for line in lines:
            if y_pos > ch - 35:
                break
            if line.strip() == "":
                y_pos += 10; continue
            if any(ord(c) > 127 for c in line):
                cur = ""
                for ch_c in line.strip():
                    test = cur + ch_c
                    ts, _ = self.font_cn_b.render(test, tc)
                    if ts.get_width() > cw - 80:
                        if cur:
                            ls, _ = self.font_cn_b.render(cur, tc)
                            cx_t = (cw - ls.get_width()) // 2
                            card.blit(ls, (cx_t, y_pos)); y_pos += 60
                        cur = ch_c
                    else:
                        cur = test
                if cur:
                    ls, _ = self.font_cn_b.render(cur, tc)
                    cx_t = (cw - ls.get_width()) // 2
                    card.blit(ls, (cx_t, y_pos)); y_pos += 60
            else:
                cur = ""
                for w in line.split(" "):
                    test = cur + w + " "
                    ts, _ = self.font_cn_b.render(test, tc)
                    if ts.get_width() > cw - 80:
                        if cur:
                            ls, _ = self.font_cn_b.render(cur.strip(), tc)
                            cx_t = (cw - ls.get_width()) // 2
                            card.blit(ls, (cx_t, y_pos)); y_pos += 60
                        cur = w + " "
                    else:
                        cur = test
                if cur:
                    ls, _ = self.font_cn_b.render(cur.strip(), tc)
                    cx_t = (cw - ls.get_width()) // 2
                    card.blit(ls, (cx_t, y_pos)); y_pos += 60

        hs, _ = self.font_cn_h.render("点击关闭", (*neon, int(200*alpha)))
        ch_x = (cw - hs.get_width()) // 2
        card.blit(hs, (ch_x, ch - 32))
        self.screen.blit(card, (cx, cy))


# ── 卡片管理 ──
class CardManager:
    def __init__(self):
        self.visible = False
        self.hiding = False
        self.target_alpha = 0.0
        self.current_alpha = 0.0
        self.title = ""
        self.lines = []
        self.card_type = "dialog"  # "dialog" 或 "todo"
        self.face_scale = 1.0
        self.target_scale = 1.0
        self.face_offset_x = 0
        self.target_offset_x = 0
        self.face_offset_y = 0
        self.target_offset_y = 0
        self.spacing_scale = 1.0
        self.target_spacing = 1.0
        # 垂直滚动状态
        self.scroll_y = 0.0          # 当前滚动位置(像素)
        self.max_scroll = 0.0        # 最大可滚动距离
        self.scroll_timer = 0.0      # 滚动前等待计时(秒)
        self.scroll_delay = 3.0      # 等待3秒开始滚动
        self._row_h = 64             # 行高(与draw_todo_card对齐)
        self._wrapped_lines = None   # 预换行缓存
    def show(self, title, lines, card_type="dialog"):
        self.visible = True
        self.title = title
        self.lines = lines
        self.card_type = card_type
        self.target_alpha = 1.0
        # 重置滚动状态
        self.scroll_y = 0.0
        self.scroll_timer = 0.0
        self._cached_card = None  # 清除卡片缓存
        self._wrapped_lines = None   # 重置换行缓存
        if card_type == "todo":
            # todo: 脸缩小并随机偏移 + 眼距缩小
            self.target_scale = 0.35
            rx = random.randint(-WIDTH//3, WIDTH//3)
            ry = random.randint(-HEIGHT//3, HEIGHT//3)
            self.target_offset_x = rx
            self.target_offset_y = ry
            self.target_spacing = 420 / 580.0
        else:
            # dialog: 眼睛上移给卡片留空间, 眼距不变
            self.target_scale = 1.0
            self.target_offset_x = 0
            self.target_offset_y = -160  # 眼睛上移
            self.target_spacing = 1.0

    def hide(self):
        self.target_alpha = 0.0
        self.current_alpha = 0.0  # 瞬间变为全透明
        self.target_scale = 1.0
        self.target_offset_x = 0
        self.target_offset_y = 0
        self.target_spacing = 1.0
        self.visible = False  # 立刻标记不可见
        self.hiding = False   # 不需要定时器了
        pass

    def _mark_hidden(self):
        self.visible = False
        self.hiding = False

    def update(self, dt):
        speed = 0.08
        self.current_alpha += (self.target_alpha - self.current_alpha) * speed
        self.face_scale += (self.target_scale - self.face_scale) * speed
        self.face_offset_x += (self.target_offset_x - self.face_offset_x) * speed
        self.face_offset_y += (self.target_offset_y - self.face_offset_y) * speed
        self.spacing_scale += (self.target_spacing - self.spacing_scale) * speed
        # ── 垂直滚动 (todo卡片) ──
        if self.card_type == "todo" and self.visible and self.lines:
            cw, ch = 910, 500
            total_h = int(len(self.lines) * self._row_h * 1.4) + 120
            vh = ch - 70
            self.max_scroll = max(0, total_h - vh)
            if self.max_scroll > 0:
                # 先等3秒再开始滚动
                if self.scroll_timer < self.scroll_delay:
                    self.scroll_timer += dt
                else:
                    self.scroll_y += 20 * dt  # 20 px/s 缓慢上滚
                    if self.scroll_y >= self.max_scroll:
                        self.scroll_y = self.max_scroll  # 到底停止



# ── L3 窄意图 (迭代3: VoiceManager 关键词匹配, 非 LLM tool_use) ──
INTENT_SKILL_MAP_SEMANTIC = {
    "todo_list": {
        "skill": "todo",
        "params": {"action": "list"},
        "tts_template": "",
    },
    "bug_list": {
        "skill": "bug",
        "params": {"action": "list"},
        "tts_template": "",
    },
    "weather": {
        "skill": "weather",
        "params": {},
        "tts_template": "",
    },
    "news": {
        "skill": "news",
        "params": {"count": 10},
        "tts_template": "",
    },
    "relax": {
        "skill": "relax",
        "params": {"action": "wooden_fish"},
        "tts_template": "",
    },
    "lingji": {
        "skill": "lingji",
        "params": {},
        "tts_template": "",
    },
    "email_knowledge": {
        "skill": "email_knowledge",
        "params": {},
        "tts_template": "",
    },
    "wechat_knowledge": {
        "skill": "wechat_knowledge",
        "params": {},
        "tts_template": "",
    },
    "moa": {
        "skill": "moa",
        "params": {},
        "tts_template": "",
    },
    "ingest": {
        "skill": "ingest",
        "params": {},
        "tts_template": "",
    },
}

# ── 语义匹配器 ──
_SEMANTIC_MATCHER = None

def _get_semantic_matcher():
    global _SEMANTIC_MATCHER
    if _SEMANTIC_MATCHER is not None:
        return _SEMANTIC_MATCHER
    try:
        from skills.semantic_matcher import SemanticMatcher
        # 从配置加载 API Key
        import json
        config_path = os.path.expanduser("~/.hermes/hermes-desktop-assistant/config.json")
        api_key = ""
        if os.path.exists(config_path):
            with open(config_path) as f:
                api_key = json.load(f).get("aliyun_api_key", "")
        if not api_key:
            print("[SEMANTIC] No API key found")
            return None
        _SEMANTIC_MATCHER = SemanticMatcher(api_key=api_key)
        ok = _SEMANTIC_MATCHER.init()
        if ok:
            print(f"[SEMANTIC] 初始化完成: {len(_SEMANTIC_MATCHER._skill_names)} 个技能")
        else:
            print("[SEMANTIC] 初始化失败, 回退到关键词匹配")
            _SEMANTIC_MATCHER = None
        return _SEMANTIC_MATCHER
    except Exception as e:
        print(f"[SEMANTIC] 初始化异常: {e}")
        return None

# ── 上下文追踪：记住上次执行的技能 ──
_CONTEXT = {"last_intent": None, "last_skill": None}

def match_intent(text):
    """L3 意图匹配 — 语义匹配 + 微信关键词拦截"""
    if not text:
        return None
    text_lower = text.lower()

    # 1. 微信关键词拦截（不走语义）
    if "微信" in text_lower:
        return ("wechat_knowledge", "wechat_knowledge", {})

    # MOA关键词拦截（不走语义，避免与缺陷技能冲突）
    if any(kw in text_lower for kw in ["moa", "聊天记录", "群聊"]):
        return ("moa", "moa", {})

    # 2. 语义匹配
    matcher = _get_semantic_matcher()
    if matcher and matcher._init_ok:
        skill_name = matcher.match(text)
        if skill_name:
            for intent_id, cfg in INTENT_SKILL_MAP_SEMANTIC.items():
                if cfg["skill"] == skill_name:
                    return (intent_id, skill_name, cfg["params"])

    # 3. 语义匹配不可用时的关键词降级
    best_match = None
    max_len = 0
    for intent_id, cfg in INTENT_SKILL_MAP_SEMANTIC.items():
        # 仅用少数关键区分词做降级
        kw_fallback = {
            "todo_list": ["待办", "代办", "清单", "添加"],
            "bug_list": ["缺陷", "bug", "测试"],
            "weather": ["天气", "温度", "下雨"],
            "news": ["新闻", "消息", "资讯"],
            "relax": ["放松", "木鱼", "休息"],
            "bgm": ["音乐", "听歌", "bgm"],
            "lingji": ["灵畿", "任务"],
            "email_knowledge": ["邮件", "项目"],
            "wechat_knowledge": ["微信"],
            "ingest": ["刷新", "拉取", "更新"],
            "moa": ["MOA", "聊天记录", "聊天", "群聊"],
        }
        fkws = kw_fallback.get(intent_id, [])
        for kw in fkws:
            if kw in text_lower:
                kl = len(kw)
                if kl > max_len:
                    max_len = kl
                    best_match = (intent_id, cfg["skill"], cfg["params"])

    return best_match



class VoiceManager:
    """语音识别+合成+处理"""
    def __init__(self):
        self.proc = None  # arecord进程
        self.rec_file = '/tmp/voice_rec.wav'
        self.mono_file = '/tmp/voice_in.wav'
        self.state = "idle"  # idle/listening/thinking/speaking
        self.result_text = ""
        self.reply_text = ""
        self._lock = threading.Lock()
        self._pending = False  # 有待处理的语音
        self.asr_text = ""     # 最近一次ASR识别文字
        self._history = []     # 对话历史 [{role, content}, ...] 最多6条

    def start_record(self):
        if self.proc:
            return
        self.state = "listening"
        self.proc = _subprocess.Popen(
            ['arecord', '-D', 'plughw:2,0', '-f', 'S16_LE', '-r', '16000', '-c', '2', self.rec_file],
            stdout=_subprocess.DEVNULL, stderr=_subprocess.DEVNULL)
        print("[Voice] Recording started (plughw:2,0)")

    def stop_record(self):
        if not self.proc:
            return None
        self.state = "thinking"
        try:
            self.proc.terminate()
            self.proc.wait(timeout=3)
        except:
            try: self.proc.kill()
            except: pass
        self.proc = None
        print("[Voice] Recording stopped, converting to mono...")
        if not os.path.exists(self.rec_file):
            self.state = "idle"
            return None
        try:
            with wave.open(self.rec_file, 'rb') as wf:
                raw = wf.readframes(wf.getnframes())
        except:
            self.state = "idle"
            return None
        if len(raw) < 2048:
            self.state = "idle"
            return None
        rs = struct.unpack(f'<{len(raw)//2}h', raw)
        mono = struct.pack(f'<{len(rs)//2}h', *(rs[::2]))
        samples = list(struct.unpack(f'<{len(mono)//2}h', mono))
        mx = max(abs(x) for x in samples) if samples else 0
        if 0 < mx < 15000:
            g = 15000 / mx
            samples = [min(32767, max(-32768, int(x*g))) for x in samples]
            mono = struct.pack(f'<{len(samples)}h', *samples)
        wf_out = wave.open(self.mono_file, 'wb')
        wf_out.setnchannels(1); wf_out.setsampwidth(2)
        wf_out.setframerate(16000); wf_out.writeframes(mono)
        wf_out.close()
        return self.mono_file

    def asr(self, wav_path):
        """语音识别"""
        if not wav_path:
            with open('/tmp/voice_debug.txt','a') as _f:
                _f.write("asr: no wav_path\n")
            return ""
        print("[ASR] Recognizing...")
        with open('/tmp/voice_debug.txt','a') as _f:
            _f.write(f"asr: calling API...\n")
        try:
            # ASR需要callback参数(用空回调)
            class _DummyCB:
                def on_event(self, r): pass
                def on_error(self, e): print(f"[ASR] cb error: {e}")
                def on_complete(self): pass
            rec = Recognition(model='paraformer-realtime-v2', format='wav',
                            sample_rate=16000, callback=_DummyCB())
            result = rec.call(file=wav_path)
            with open('/tmp/voice_debug.txt','a') as _f:
                _f.write(f"asr: result type={type(result).__name__}\n")
            if hasattr(result, 'output') and result.output:
                texts = [s.get('text','').strip() for s in result.output.get('sentence',[])
                        if s.get('text')]
                return ''.join(texts)
        except Exception as e:
            print(f"[ASR] Error: {e}")
            with open('/tmp/voice_debug.txt','a') as _f:
                _f.write(f"asr EXCEPTION: {e}\n")
        return ""

    def tts(self, text, voice="Mochi", on_start=None, on_end=None):
        """qwen3-tts-flash 流式TTS → PyAudio实时播放"""
        if not text:
            return
        print(f"[TTS] qwen3-tts-flash: {text[:40]}...")
        if on_start: on_start()
        # 停止录音释放设备
        if self.proc:
            self.proc.terminate()
            try: self.proc.wait(timeout=2)
            except: pass
            self.proc = None
            time.sleep(0.3)
        try:
            # 设置API地域
            dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'
            # 读取API key
            api_key = ""
            _cp = os.path.expanduser("~/.hermes/hermes-desktop-assistant/config.json")
            if os.path.exists(_cp):
                try:
                    api_key = json.load(open(_cp)).get("aliyun_api_key", "")
                    with open('/tmp/voice_debug.txt','a') as _f:
                        _f.write(f"tts api_key loaded: {api_key[:8] if api_key else 'EMPTY'}...\n")
                except Exception as _ke:
                    with open('/tmp/voice_debug.txt','a') as _f:
                        _f.write(f"tts key error: {_ke}\n")

            # PyAudio初始化
            import pyaudio as _pa
            import numpy as _np
            import base64 as _b64
            with open('/tmp/voice_debug.txt','a') as _f:
                _f.write("tts: init pyaudio...\n")
            _p = None; _stream = None
            try:
                _p = _pa.PyAudio()
                _stream = _p.open(format=_pa.paInt16, channels=1, rate=16000,
                                output=True, frames_per_buffer=1024)
                _audio_buf = b""
                with open('/tmp/voice_debug.txt','a') as _f:
                    _f.write(f"tts: calling qwen3-tts-flash voice={voice}\n")

                response = dashscope.MultiModalConversation.call(
                    api_key=api_key,
                    model="qwen3-tts-flash",
                    text=text,
                    voice=voice,
                    language_type="Chinese",
                    stream=True
                )
                _chunk_count = 0
                for chunk in response:
                    _chunk_count += 1
                    if chunk.output is not None:
                        audio = chunk.output.audio
                        if audio is not None and audio.data is not None:
                            wav24 = _b64.b64decode(audio.data)
                            _pcm24 = _np.frombuffer(wav24, dtype=_np.int16)
                            if len(_pcm24) == 0:
                                continue
                            _pcm16 = _np.interp(
                                _np.linspace(0, len(_pcm24)-1, int(len(_pcm24)*2/3)),
                                _np.arange(len(_pcm24)),
                                _pcm24.astype(_np.float32)
                            ).astype(_np.int16)
                            _stream.write(_pcm16.tobytes())
                            _audio_buf += _pcm16.tobytes()
                        if chunk.output.finish_reason == "stop":
                            with open('/tmp/voice_debug.txt','a') as _f:
                                _f.write(f"tts: complete, {_chunk_count} chunks, {len(_audio_buf)} bytes\n")
            finally:
                try:
                    if _stream: _stream.stop_stream(); _stream.close()
                except: pass
                try:
                    if _p: _p.terminate()
                except: pass

            if _audio_buf:
                import wave, struct
                with wave.open('/tmp/tts_out.wav', 'wb') as _wf:
                    _wf.setnchannels(1); _wf.setsampwidth(2)
                    _wf.setframerate(24000)
                    _wf.writeframes(_audio_buf)
                print(f"[TTS] Saved {len(_audio_buf)//1024}KB")

        except Exception as e:
            print(f"[TTS] Error: {e}")
            with open('/tmp/voice_debug.txt','a') as _f:
                _f.write(f"TTS EXCEPTION: {e}\n")
        if on_end:
            on_end()
        print("[TTS] Done")

    def _call_llm_direct(self, prompt, is_context_prompt=False):
        """调 DeepSeek v4-flash（直连，不经过本地代理）"""
        import time, requests, json as _llm_json, os as _llm_os
        
        t0 = time.time()
        try:
            _llm_cfg_paths = [
                _llm_os.path.expanduser("~/.hermes/skills/email/email-knowledge/config/llm.json"),
                _llm_os.path.expanduser("~/email-knowledge/config/llm.json"),
                _llm_os.path.join(_llm_os.path.dirname(__file__), "llm.json"),
            ]
            _llm_api_key = ""
            _llm_base_url = "https://api.deepseek.com/v1"
            for _p in _llm_cfg_paths:
                if _llm_os.path.exists(_p):
                    try:
                        with open(_p) as _f:
                            _llm_data = _llm_json.load(_f)
                        _llm_api_key = _llm_data.get("llm", {}).get("api_key", "")
                        _llm_base_url = _llm_data.get("llm", {}).get("base_url", "https://api.deepseek.com/v1")
                        break
                    except:
                        pass
            if not _llm_api_key:
                _llm_api_key = _llm_os.environ.get("DEEPSEEK_API_KEY", "")
            
            messages = []
            if is_context_prompt:
                for h in self._history[-4:]:
                    messages.append({"role": h["role"], "content": h["content"]})
                messages.append({"role": "user", "content": prompt})
            else:
                messages.append({"role": "system", "content": "你是语音助手小Q，用简洁口语回答，50字以内。"})
                for h in self._history[-4:]:
                    messages.append({"role": h["role"], "content": h["content"]})
                messages.append({"role": "user", "content": prompt})
            
            resp = requests.post(
                _llm_base_url.rstrip("/") + "/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + _llm_api_key,
                },
                json={"messages": messages, "model": "deepseek-v4-flash", "max_tokens": 500},
                timeout=60,
            )
            data = resp.json()
            reply = data["choices"][0]["message"]["content"].strip()
            self._history.append({"role": "user", "content": prompt})
            self._history.append({"role": "assistant", "content": reply})
            if len(self._history) > 10:
                self._history = self._history[-10:]
        except Exception as e:
            reply = f"出错: {e}"
        t1 = time.time()
        llm_ms = int((t1 - t0) * 1000)
        print(f"[Hermes] {llm_ms}ms, reply: {reply[:50]}")
        return reply, llm_ms

    def process_voice(self, wav_path):
        """[实验] 语音流水线: ASR -> 人名纠错 -> 直连LLM -> TTS (Bypass L3)"""
        if self._pending:
            print("[Voice] Already processing, skipping")
            return
        self._pending = True
        import time as _time
        self._proc_start = _time.time()
        try:
            # 调试: 写ASR开始标记
            with open('/tmp/voice_debug.txt','w') as _f:
                _f.write(f"wav={wav_path} size={os.path.getsize(wav_path) if os.path.exists(wav_path) else 0}\n")
            txt = self.asr(wav_path)
            self.asr_text = txt
            with open('/tmp/voice_debug.txt','a') as _f:
                _f.write(f"asr_result='{txt}'\n")
            print(f"[ASR] Result: '{txt}'")
            if not txt or len(txt) < 2:
                print("[Voice] No speech detected")
                with open('/tmp/voice_debug.txt','a') as _f:
                    _f.write("NO_SPEECH -> idle\n")
                self.state = "idle"
                return

            self.state = "thinking"
            with open('/tmp/voice_debug.txt','a') as _f:
                _f.write("state=thinking\n")

            # ── Hermes Skills: ASR → 纠错 → 交给Hermes自主决策路由 ──
            txt = correct(txt)
            txt = correct(txt)
            t_asr_end = time.time()

            # 直接调 Hermes Agent，由其内部自主判断意图、调用技能或纯聊天
            # _call_hermes 内部已包含 TTS，所以这里不需要再调 TTS
            self._pending = False
            self._call_hermes(txt)
            return
            # ── 原 L3 流程已跳过 ──
            intent = match_intent(txt)
            if not intent and ("完成第" in txt or "已完成" in txt):
                _last_sk = _CONTEXT.get("last_skill")
                if _last_sk:
                    for _iid, _icfg in INTENT_SKILL_MAP_SEMANTIC.items():
                        if _icfg["skill"] == _last_sk:
                            print(f"[L3] Mark-done fallback to last skill: {_last_sk}")
                            intent = (_iid, _last_sk, _icfg["params"])
                            break
            if intent:
                intent_id, skill_name, skill_params = intent
                print(f"[L3] Intent matched: {intent_id} → skill '{skill_name}'")
                with open('/tmp/voice_debug.txt','a') as _f:
                    _f.write(f"L3 intent={intent_id} skill={skill_name}\n")
                try:
                    # skills 包: 优先本地目录, 其次 cubicle_npc 仓库
                    _skills_dirs = [
                        os.path.dirname(os.path.abspath(__file__)),  # v10同目录
                    ]
                    for _d in _skills_dirs:
                        if _d not in sys.path:
                            sys.path.insert(0, _d)
                    print("[DBG] step1: importing")
                    with open("/tmp/v10_debug.txt","a") as _df: _df.write("step1: importing\n")
                    from skills import SkillManager
                    if not hasattr(self, '_l3_skill_mgr'):
                        print("[DBG] step2: creating SkillManager")
                        with open("/tmp/v10_debug.txt","a") as _df: _df.write("step2: create\n")
                        self._l3_skill_mgr = SkillManager().create_minimal()
                        print("[DBG] step2b: create_minimal done")
                        with open("/tmp/v10_debug.txt","a") as _df: _df.write("step2b: done\n")
                    skill_params["_asr_text"] = txt
                    print("[DBG] step3: before execute")
                    with open("/tmp/v10_debug.txt","a") as _df: _df.write("step3: before exec\n")
                    result = self._l3_skill_mgr.execute(skill_name, skill_params)
                    _CONTEXT["last_intent"] = intent_id
                    _CONTEXT["last_skill"] = skill_name
                    print(f"[DBG] step4: exec done, success={result.success}")
                    with open("/tmp/v10_debug.txt","a") as _df: _df.write("step4: exec done\n")
                    with open("/tmp/v10_debug.txt","a") as _df: _df.write("step5a: if success\n")
                    if result.success:
                        print("[DBG] step5: success block")
                        with open("/tmp/v10_debug.txt","a") as _df: _df.write("step5b: in block\n")
                        tts_text = "好的"
                        non_tts_effects = []
                        with open("/tmp/v10_debug.txt","a") as _df: _df.write("step5c: vars init\n")
                        for effect in result.side_effects:
                            if effect.type == "voice_tts":
                                tts_text = effect.params.get("text", "好的")
                            else:
                                non_tts_effects.append(effect)
                        # 执行非TTS side_effects (线程安全: 通过 WS command_queue)
                        for effect in non_tts_effects:
                            # SideEffect → dict (WSServer.process_commands 需要 dict)
                            cmd = {"type": effect.type}
                            cmd.update(effect.params)
                            with open("/tmp/v10_debug.txt","a") as _df: _df.write("step6a: non_tts loop\n")
                            if ws_server:
                                with open("/tmp/v10_debug.txt","a") as _df: _df.write("step6b: queue append\n")
                                ws_server.command_queue.append(cmd)
                                with open("/tmp/v10_debug.txt","a") as _df: _df.write("step6c: appended\n")
                                print(f"[L3] side_effect queued: {cmd}")
                        # TTS 播报 (v10 直接调用, 不走 WS)
                        with open("/tmp/v10_debug.txt","a") as _df: _df.write("step7a: before TTS\n")
                        print(f"[L3] TTS: {tts_text}")
                        with open("/tmp/v10_debug.txt","a") as _df: _df.write("step7b: calling TTS\n")
                        self.tts(tts_text,
                                on_start=lambda: setattr(self, 'state', 'speaking'),
                                on_end=lambda: setattr(self, 'state', 'idle'))
                        with open("/tmp/v10_debug.txt","a") as _df: _df.write("step7c: TTS returned\n")
                        with open("/tmp/v10_debug.txt","a") as _df: _df.write("step8: about to return\n")
                        # L3 命中后直接返回, 不走 Hermes
                        return
                        with open("/tmp/v10_debug.txt","a") as _df: _df.write("step9: after return (should never reach)\n")
                    else:
                        print(f"[L3] Skill failed: {result.error}, falling back to Hermes")
                except Exception as e:
                    print(f"[L3] Exception: {e}, falling back to Hermes")
                    with open('/tmp/voice_debug.txt','a') as _f:
                        _f.write(f"L3 EXCEPTION: {e}\n")
                # L3 失败 → 继续走 Hermes (不中断)

            print(f"[AI] Calling Hermes: {txt}")

            # Hermes子进程调用(保留记忆和工具)
            reply = ""
            HERMES_PY = os.path.expanduser("~/.hermes/hermes-agent/venv/bin/python")
            HERMES_WRAP = os.path.expanduser("~/gimbal_control/hermes_wrapper.py")
            if os.path.exists(HERMES_PY) and os.path.exists(HERMES_WRAP):
                try:
                    r = _subprocess.run([HERMES_PY, HERMES_WRAP, txt],
                                      capture_output=True, text=True, timeout=300)
                    reply = r.stdout.strip()
                    if reply.startswith("HERMES_ERROR:"):
                        reply = reply.replace("HERMES_ERROR:", "出错:")
                    elif not reply:
                        reply = "Hermes 没有返回内容"
                except _subprocess.TimeoutExpired:
                    reply = "思考时间过长"
                except Exception as e:
                    reply = f"Hermes 启动失败: {e}"
            else:
                # 回退: 直接调用DashScope
                try:
                    r = dashscope.Generation.call(model='qwen-turbo', prompt=txt)
                    reply = r.output.get('text', '收到') if r.status_code == 200 else '网络错误'
                except Exception as e:
                    reply = f"抱歉: {e}"

            print(f"[AI] Reply: {reply[:60]}...")
            with open('/tmp/voice_debug.txt','a') as _f:
                _f.write(f"hermes_reply='{reply[:80]}'\n")

            # 统一摘要：去掉代码/路径/技术细节，生成人话摘要
            import re as _re
            # 先清理原始回复中的代码块和行内代码
            _cleaned = _re.sub(r'```[\s\S]*?```', '', reply)
            _cleaned = _re.sub(r'`[^`]+`', '', _cleaned)
            _cleaned = _re.sub(r'https?://\S+', '', _cleaned)
            _cleaned = _re.sub(r'[/~\w]+\.\w{1,4}(:\d+)?', '', _cleaned)
            _cleaned = _re.sub(r'\$[^$]+\$', '', _cleaned)
            _cleaned = _re.sub(r'\n{2,}', '\n', _cleaned)
            _cleaned = _cleaned.strip()

            voice_text = reply
            display = _cleaned if _cleaned else reply

            # 用AI摘要，让回复变成口语化人话
            if len(display) > 40:
                try:
                    sr = dashscope.Generation.call(model='qwen-turbo',
                        prompt=f'用简洁口语总结以下内容，不要代码、不要路径、不要技术术语，只说结论(40字以内):\n{display}')
                    if sr.status_code == 200:
                        vt = sr.output.get('text', '').strip()
                        if vt:
                            display = vt
                            voice_text = vt
                except: pass
            else:
                voice_text = display

            self.reply_text = display

            # TTS播报 (speaking表情在首个chunk出声时触发，与声音同步)
            with open('/tmp/voice_debug.txt','a') as _f:
                _f.write(f"calling tts: text='{voice_text[:40]}'\n")
            self.tts(voice_text,
                    on_start=lambda: setattr(self, 'state', 'speaking'),
                    on_end=lambda: setattr(self, 'state', 'idle'))
            with open('/tmp/voice_debug.txt','a') as _f:
                _f.write("tts returned\n")
        finally:
            self._pending = False

    def process_text(self, txt):
        """直接处理文本 (跳过ASR, 用于voice_inject测试)"""
        if self._pending:
            print("[Voice] Already processing, skipping")
            return
        self._pending = True
        try:
            self.asr_text = txt
            print(f"[ASR-Inject] Result: '{txt}'")

            if not txt or len(txt) < 2:
                print("[Voice] Empty text")
                self.state = "idle"
                return

            self.state = "thinking"

            # ── L3 窄意图拦截 (迭代3) ──
            intent = match_intent(txt)
            if not intent and ("完成第" in txt or "已完成" in txt):
                _last_sk = _CONTEXT.get("last_skill")
                if _last_sk:
                    for _iid, _icfg in INTENT_SKILL_MAP_SEMANTIC.items():
                        if _icfg["skill"] == _last_sk:
                            print(f"[L3] Mark-done fallback to last skill: {_last_sk}")
                            intent = (_iid, _last_sk, _icfg["params"])
                            break
            if intent:
                intent_id, skill_name, skill_params = intent
                print(f"[L3] Intent matched: {intent_id} → skill '{skill_name}'")
                try:
                    skill_params["_asr_text"] = txt
                    print("[DBG] step1: importing")
                    with open("/tmp/v10_debug.txt","a") as _df: _df.write("step1: importing\n")
                    from skills import SkillManager
                    if not hasattr(self, '_l3_skill_mgr'):
                        print("[DBG] step2: creating SkillManager")
                        with open("/tmp/v10_debug.txt","a") as _df: _df.write("step2: create\n")
                        self._l3_skill_mgr = SkillManager().create_minimal()
                        print("[DBG] step2b: create_minimal done")
                        with open("/tmp/v10_debug.txt","a") as _df: _df.write("step2b: done\n")
                    result = self._l3_skill_mgr.execute(skill_name, skill_params)
                    _CONTEXT["last_intent"] = intent_id
                    _CONTEXT["last_skill"] = skill_name
                    if result.success:
                        tts_text = "好的"
                        non_tts_effects = []
                        for effect in result.side_effects:
                            if effect.type == "voice_tts":
                                tts_text = effect.params.get("text", "好的")
                            else:
                                non_tts_effects.append(effect)
                        for effect in non_tts_effects:
                            cmd = {"type": effect.type}
                            cmd.update(effect.params)
                            with open("/tmp/v10_debug.txt","a") as _df: _df.write("step6a: non_tts loop\n")
                            if ws_server:
                                with open("/tmp/v10_debug.txt","a") as _df: _df.write("step6b: queue append\n")
                                ws_server.command_queue.append(cmd)
                                with open("/tmp/v10_debug.txt","a") as _df: _df.write("step6c: appended\n")
                                print(f"[L3] side_effect queued: {cmd}")
                        with open("/tmp/v10_debug.txt","a") as _df: _df.write("step7a: before TTS\n")
                        print(f"[L3] TTS: {tts_text}")
                        with open("/tmp/v10_debug.txt","a") as _df: _df.write("step7b: calling TTS\n")
                        self.tts(tts_text,
                                on_start=lambda: setattr(self, 'state', 'speaking'),
                                on_end=lambda: setattr(self, 'state', 'idle'))
                        with open("/tmp/v10_debug.txt","a") as _df: _df.write("step7c: TTS returned\n")
                        return
                    else:
                        print(f"[L3] Skill failed: {result.error}, falling back to Hermes")
                except Exception as e:
                    print(f"[L3] Exception: {e}, falling back to Hermes")
            # 最终兜底 → Hermes
            print(f"[AI] Calling Hermes: {txt}")
            self._call_hermes(txt)
        finally:
            self._pending = False

    def _call_hermes(self, txt):
        """调用 Hermes API Server (v0.15.1, 常驻端口8086，无冷启动)"""
        import json as _json, urllib.request as _ur

        reply = None

        # ── 方式1: HTTP API Server (常驻，无冷启动) ──
        try:
            _body = _json.dumps({
                "model": "deepseek-v4-flash",
                "messages": [{"role": "user", "content": txt}],
                "max_tokens": 500,
            }, ensure_ascii=False).encode("utf-8")
            _req = _ur.Request(
                "http://127.0.0.1:8086/v1/chat/completions",
                data=_body,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Authorization": "Bearer local-secret-2026",
                },
            )
            with _ur.urlopen(_req, timeout=90) as _resp:
                _data = _json.loads(_resp.read().decode("utf-8"))
                reply = _data["choices"][0]["message"]["content"].strip()
                _tokens = _data.get("usage", {}).get("total_tokens", "?")
                print(f"[HERMES-API] {_tokens} tokens, reply: {reply[:50]}")
        except Exception as e:
            print(f"[HERMES-API] failed: {e}, falling back to subprocess")

        # ── 方式2: hermes chat -q 子进程 (回退) ──
        if reply is None:
            import subprocess
            HERMES_BIN = os.path.expanduser("~/.hermes/hermes-agent/venv/bin/hermes")
            try:
                result = subprocess.run(
                    [HERMES_BIN, "chat", "-q", txt, "-Q", "--provider", "deepseek", "--source", "tool"],
                    capture_output=True, text=True, timeout=120
                )
                out = result.stdout.strip()
                if out:
                    reply_lines = [l for l in out.split("\n") if l.strip() and not l.startswith("session_id:") and not l.startswith("⚠")]
                    reply = "\n".join(reply_lines) if reply_lines else out
                else:
                    err = result.stderr.strip()[-200:] if result.stderr else ""
                    print(f"[HERMES] empty stdout, stderr tail: {err[:100]}")
                    reply = "抱歉，我没听懂"
            except subprocess.TimeoutExpired:
                reply = "思考时间过长"
            except Exception as e:
                reply = f"Hermes 启动失败: {e}"
                print(f"[HERMES] Error: {e}")
        # 通过 ws_server 发送 todo 风格的大卡片
        self.reply_text = reply
        try:
            card_lines = [l.strip() for l in reply.split("\n") if l.strip()]
            cmd = {
                "type": "card_show",
                "title": "回复",
                "lines": card_lines if card_lines else [reply],
                "card_type": "todo",
            }
            if ws_server:
                ws_server.command_queue.append(cmd)
        except Exception as e:
            print(f"[HERMES] Card error: {e}")

        # TTS用简短摘要播报，卡片显示完整回复
        voice_text = reply
        if len(reply) > 40:
            try:
                sr = dashscope.Generation.call(model='qwen-turbo',
                    prompt=f'用简洁口语总结以下内容，只说结论，不要编号(20字以内):\n{reply[:200]}',
                    result_format='text')
                if sr.status_code == 200:
                    vt = sr.output.get('text', '').strip()
                    if vt and len(vt) < len(reply):
                        voice_text = vt
            except Exception as e:
                print(f"[HERMES] TTS summary failed: {e}")
        
        self.state = "speaking"
        self.tts(voice_text,
                on_start=lambda: setattr(self, 'state', 'speaking'),
                on_end=lambda: setattr(self, 'state', 'idle'))


    def quit(self):
        if self.proc:
            try: self.proc.terminate()
            except: pass


# ── WebSocket 服务端 ──
class WSServer:
    def __init__(self):
        self.command_queue = []
        self.loop = None

    def start(self):
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._run_loop, daemon=True).start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._serve())
        self.loop.run_forever()

    async def _serve(self):
        async def handler(websocket):
            print(f"[WS] 客户端连接: {websocket.remote_address}")
            try:
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        self.command_queue.append(data)
                        print(f"[WS] 收到指令: {data}")
                    except json.JSONDecodeError:
                        pass
            except websockets.exceptions.ConnectionClosed:
                print("[WS] 客户端断开")

        server = await websockets.serve(handler, "0.0.0.0", 8766)
        print("[WS] 表情服务器启动 ws://0.0.0.0:8766")
        await asyncio.Future()

    def process_commands(self):
        """在主循环中处理指令"""
        while self.command_queue:
            cmd = self.command_queue.pop(0)
            cmd_type = cmd.get("type")
            if cmd_type == "expression":
                sm.trigger(cmd.get("name", "idle"))
                if npc_sm: npc_sm.idle_time = 0
            elif cmd_type == "card_show":
                card_mgr.show(cmd.get("title", ""), cmd.get("lines", []),
                            cmd.get("card_type", "dialog"))
            elif cmd_type == "card_hide":
                card_mgr.hide()
            elif cmd_type == "auto":
                sm.auto_mode = cmd.get("enabled", True)
            elif cmd_type == "set_state":
                state = cmd.get("state", "idle")
                if npc_sm and npc_enabled:
                    npc_mapping = {
                        "idle": "idle", "observe": "observe",
                        "engaged": "engaged", "warn": "warn", "sleep": "sleep",
                    }
                    voice_mapping = {
                        "listening": "observe",
                        "thinking": "engaged",
                        "talking": "engaged",
                    }
                    if state in npc_mapping:
                        npc_sm.set_npc_state(npc_mapping[state])
                    elif state in voice_mapping:
                        npc_sm.set_npc_state(voice_mapping[state])
                        npc_sm.idle_time = 0
                    else:
                        sm.trigger(state)
                else:
                    voice_fallback = {
                        "idle": "idle",
                        "listening": "curious",
                        "thinking": "thinking",
                        "talking": "speaking",
                    }
                    sm.trigger(voice_fallback.get(state, "idle"))
            elif cmd_type == "npc_interact":
                if npc_sm and npc_enabled:
                    npc_sm.interact(cmd.get("interaction", "touch"))
            # ── v6新增指令 ──
            elif cmd_type == "trigger_vfx":
                vfx_name = cmd.get("name", "")
                vfx_x = cmd.get("x")      # 可选
                vfx_y = cmd.get("y")      # 可选
                if vfx_name and vfx_mgr:
                    vfx_mgr.trigger_vfx(vfx_name, vfx_x, vfx_y)
            elif cmd_type == "set_ambient":
                ambient = cmd.get("mode", "none")
                if vfx_mgr:
                    vfx_mgr.set_ambient(ambient)
            # ── v7新增指令 ──
            elif cmd_type == "trigger_squash":
                sq_style = cmd.get("style", "tap")
                sq_intensity = cmd.get("intensity", 1.0)
                squash_stretch.trigger_squash(sq_intensity, sq_style)

            elif cmd_type == "set_pupil_mode":
                pmode = cmd.get("mode", "normal")   # normal/heart/star
                pdur = cmd.get("duration", 3.0)
                renderer.set_pupil_mode(pmode, pdur)

            # ── v9新增指令 ──
            elif cmd_type == "set_mood":
                mood_name = cmd.get("mood", "idle")  # idle/happy/sad/angry/surprised/excited/curious/sleepy/love/focus
                transition = cmd.get("transition", 1.5)
                ambient_mgr.set_mood(mood_name, transition)

            # ── 语音指令 ──
            elif cmd_type == "voice_start":
                voice_mgr.start_record()
                sm.trigger("curious")
                print("[Voice] start by WS")
            elif cmd_type == "voice_stop":
                wf = voice_mgr.stop_record()
                if wf:
                    threading.Thread(target=voice_mgr.process_voice, args=(wf,), daemon=True).start()
                print("[Voice] stop by WS")
            elif cmd_type == "voice_tts":
                txt = cmd.get("text", "")
                if txt:
                    threading.Thread(target=voice_mgr.tts, args=(txt,), daemon=True).start()

            elif cmd_type == "voice_inject":
                # iter3 debug: 直接注入ASR文本, 跳过录音, 测试L3 intent
                txt = cmd.get("text", "")
                if txt and voice_mgr:
                    print(f"[Voice-Inject] text='{txt}'")
                    voice_mgr.asr_text = txt
                    threading.Thread(target=voice_mgr.process_text, args=(txt,), daemon=True).start()

            # ── v10新增指令 ──
            elif cmd_type == "screenshot":
                import time as _time
                ts = _time.strftime('%H%M%S')
                fname = f'/tmp/v10_screenshot_{ts}.png'
                pygame.image.save(screen, fname)
                print(f'[v10] Screenshot: {fname}')


# ── 初始化 ──
# 防止pygame占用音频设备(语音用aplay独立播放)
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['AUDIODEV'] = '/dev/null'
pygame.init()
pygame.freetype.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("Robot Face v9 + NPC + VFX + Body + Eyes + Ambient")
clock = pygame.time.Clock()

sm = StateMachine()
renderer = Renderer(screen)
card_mgr = CardManager()
# 配置DashScope API key(语音ASR/TTS/AI用)
_cfg_path = os.path.expanduser("~/.hermes/hermes-desktop-assistant/config.json")
if os.path.exists(_cfg_path):
    try:
        _cfg = json.load(open(_cfg_path))
        _api_key = _cfg.get("aliyun_api_key", "")
        if _api_key:
            dashscope.api_key = _api_key
            print(f"[DashScope] API key loaded ({_api_key[:8]}...)")
        else:
            print("[DashScope] WARNING: No aliyun_api_key in config")
    except Exception as _e:
        print(f"[DashScope] Config load error: {_e}")
else:
    print(f"[DashScope] Config not found: {_cfg_path}")

ws_server = WSServer()
ws_server.start()
voice_mgr = VoiceManager()

# 启动待办提醒监视器
try:
    from hermes_skills.todo import set_reminder_callback, start_reminder_watcher
    def _reminder_tts(text):
        if ws_server:
            ws_server.command_queue.append({"type": "voice_tts", "text": text})
    set_reminder_callback(_reminder_tts)
    start_reminder_watcher()
    print("[Reminder] Watcher started via hermes_skills")
except Exception as e:
    print(f"[Reminder] Init error: {e}")

# v6: 初始化素材加载器和特效管理器
asset_loader = AssetLoader()
asset_loader.load_all()
vfx_mgr = VFXManager(asset_loader, renderer.face_center_x, renderer.face_center_y)

# v7: 初始化SquashStretch + AnimationDirector
squash_stretch = SquashStretch()
anim_director = AnimationDirector(squash_stretch)
anim_director._renderer = renderer  # v10: 连接renderer引用(霓虹色同步)

# v9: 初始化AmbientManager — 环境氛围层
ambient_mgr = AmbientManager(renderer.face_center_x, renderer.face_center_y)

# v9: 性能监控
perf = PerfMonitor()

# VFX回调链: 表情变化时通知特效管理器 + 动画编排器 + 环境氛围
def _on_expr_change_chain(expr_name):
    vfx_mgr.on_expression_change(expr_name)
    anim_director.on_expression_change(expr_name)
    # v9: 表情→情绪氛围映射
    expr_to_mood = {
        "idle": "idle", "happy": "happy", "laugh": "happy", "excited": "excited",
        "smile": "happy", "relaxed": "idle", "sad": "sad", "angry": "angry",
        "surprised": "surprised", "scared": "scared", "sleepy": "sleepy",
        "bored": "idle", "curious": "curious", "thinking": "focus",
        "confused": "curious", "blink": None, "wink": None,
        "look_left": None, "look_right": None, "look_up": None,
        "heart_eyes": "love", "star_eyes": "excited",
        "speaking": "happy",
    }
    mood = expr_to_mood.get(expr_name)
    if mood:
        ambient_mgr.set_mood(mood)
sm._on_expr_change = _on_expr_change_chain
sm._breath_params_cb = anim_director.get_breath_params  # v7: 情绪呼吸

# 初始化舵机
gimbal_ctrl = GimbalController()
if gimbal_ctrl.connect():
    gimbal_ctrl.center()
    sm.gimbal = gimbal_ctrl  # 调试时禁用舵机，取消注释恢复
else:
    print('[WARN] 舵机未连接，表情将不带动舵机')

# 定时数据采集器 (30分钟后台采集天气/新闻/灵畿任务)
collector_cfg = {
    "interval_sec": 1800,  # 30分钟
    "latitude": 39.9042,
    "longitude": 116.4074,
    "timeout": 10,
    "rss_urls": [
        "https://36kr.com/feed",
        "https://sspai.com/feed",
        "https://www.ifanr.com/feed",
        "https://www.ithome.com/rss/",
        "https://www.oschina.net/news/rss",
    ],
    "lingji_workspace": "CMIOTonemoredcap",
}
data_collector = DataCollector(collector_cfg)
data_collector.start()

# ── 后台待办提醒监视器 ──
from skills.todo import TodoSkill, ReminderWatcher
_todo_for_reminder = TodoSkill()
def _remind_callback(text):
    try:
        ws_server.command_queue.append({"type": "voice_tts", "text": text})
    except:
        pass
_reminder_watcher = ReminderWatcher(_todo_for_reminder, _remind_callback, interval=30.0)
_reminder_watcher.start()

# NPC状态机 + 人格系统
PERSONALITY_PRESETS = [
    ("温柔陪伴型", Personality.gentle),
    ("元气活跃型", Personality.energetic),
    ("默认中性", Personality),
]
personality_idx = 0
personality = PERSONALITY_PRESETS[personality_idx][1]()
npc_sm = NPCStateMachine(sm, personality)
npc_enabled = True
sm.auto_mode = False

# 鼠标控制
pygame.mouse.set_visible(False)

# 触控交互状态
touch_down_pos = None
touch_down_time = 0
last_click_time = 0

running = True
show_hud = False  # v9: 调试HUD开关(F1切换)
print("Robot Face v9 started. WS:8766 | 1-9表情 | SPACE=NPC/auto | P=人格 | V=VFX | B=Squash | M=情绪 | F1=HUD | ESC=quit")
print(f"[NPC] 人格: {PERSONALITY_PRESETS[personality_idx][0]} {personality}")
print("WS指令: {\"type\":\"expression\",\"name\":\"happy\"}")
print("WS指令: {\"type\":\"set_state\",\"state\":\"idle|observe|engaged|warn|sleep|listening|thinking|talking\"}")
print("WS指令: {\"type\":\"npc_interact\",\"interaction\":\"touch|voice|long_press|double_tap\"}")
print("WS指令: {\"type\":\"card_show\",\"title\":\"回复\",\"lines\":[\"文本1\",\"文本2\"]}")
print("WS指令: {\"type\":\"card_hide\"}")
print("WS指令: {\"type\":\"trigger_vfx\",\"name\":\"icon_heart_happy_64x64_01\",\"x\":640,\"y\":200}")
print('WS指令: {"type":"set_ambient","mode":"none|dots|confetti|woodfish"}')
print('WS指令: {"type":"trigger_squash","style":"tap|bounce|shake|surprise","intensity":1.0}')
print('WS指令: {"type":"set_pupil_mode","mode":"normal|heart|star","duration":3.0}')
print('WS指令: {"type":"set_mood","mood":"idle|happy|sad|angry|surprised|excited|curious|sleepy|love|focus","transition":1.5}')
print('[键盘] M=循环切换情绪氛围')
if asset_loader.available:
    print(f"[VFX] 素材已加载, 特效系统已启用")
else:
    print(f"[VFX] 无素材, 纯矢量回退模式")

fps_timer = 0
fps_count = 0
_actual_fps = 60.0  # v9: perf monitor用
while running:
    dt = clock.tick(FPS) / 1000.0
    fps_count += 1
    fps_timer += dt
    if fps_timer >= 5.0:
        _actual_fps = fps_count / fps_timer
        print(f"[FPS] {_actual_fps:.1f} (target {FPS}) perf={perf.level_name}")
        fps_count = 0
        fps_timer = 0

    # v9: 性能监控更新
    perf.update(dt, _actual_fps)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_SPACE:
                # 松手: 停止录音并处理(即使proc可能为None也尝试)
                wf = voice_mgr.stop_record()
                if wf:
                    threading.Thread(target=voice_mgr.process_voice, args=(wf,), daemon=True).start()
                    print("[Voice] Push-to-talk: 处理中...")
                else:
                    print("[Voice] KEYUP but no audio file")
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_q:
                print("[System] 'Q' pressed, exiting...")
                running = False
            elif event.key == pygame.K_SPACE:
                # 空格: 按住说话(语音push-to-talk)
                voice_mgr.start_record()
                sm.trigger("curious")
                card_mgr.hide()
                print("[Voice] Push-to-talk: 开始录音")
            elif event.key == pygame.K_n:
                # N: 切换NPC模式(原SPACE功能)
                if npc_enabled:
                    npc_enabled = False
                    sm.auto_mode = True
                    sm._goto_expr("idle")
                    sm.phase = "loop"
                    sm.next_state_time = 0
                    print("[NPC] NPC模式关闭，切换到auto模式")
                else:
                    npc_enabled = True
                    sm.auto_mode = False
                    npc_sm.idle_time = 0
                    print("[NPC] NPC模式开启")
                card_mgr.hide()
            elif event.key == pygame.K_p:
                personality_idx = (personality_idx + 1) % len(PERSONALITY_PRESETS)
                name, factory = PERSONALITY_PRESETS[personality_idx]
                npc_sm.personality = factory()
                print(f"[NPC] 人格切换: {name} {npc_sm.personality}")
            elif event.key == pygame.K_v:
                # V: 循环切换环境氛围
                cycle = ["none", "dots", "confetti", "woodfish"]
                idx = (cycle.index(vfx_mgr.ambient_type) + 1) % len(cycle)
                vfx_mgr.set_ambient(cycle[idx])
                print(f"[VFX] 环境氛围: {cycle[idx]}")
            elif event.key == pygame.K_b:
                # B: 循环测试Squash&Stretch
                _sq_styles = ["tap", "bounce", "shake", "surprise"]
                if not hasattr(pygame, '_sq_idx'):
                    pygame._sq_idx = -1
                pygame._sq_idx = (pygame._sq_idx + 1) % len(_sq_styles)
                style = _sq_styles[pygame._sq_idx]
                squash_stretch.trigger_squash(1.0, style)
                print(f"[Body] Squash测试: {style}")
            elif event.key == pygame.K_m:
                # M: 循环切换情绪氛围
                _moods = ["idle", "happy", "sad", "angry", "surprised", "excited", "curious", "sleepy", "love", "focus"]
                if not hasattr(pygame, '_mood_idx'):
                    pygame._mood_idx = -1
                pygame._mood_idx = (pygame._mood_idx + 1) % len(_moods)
                mood = _moods[pygame._mood_idx]
                ambient_mgr.set_mood(mood)
                print(f"[Ambient] 情绪氛围: {mood}")
            elif event.key == pygame.K_1:
                sm.trigger("happy")
                if npc_sm: npc_sm.idle_time = 0
            elif event.key == pygame.K_2:
                sm.trigger("surprised")
                if npc_sm: npc_sm.idle_time = 0
            elif event.key == pygame.K_3:
                sm.trigger("thinking")
                if npc_sm: npc_sm.idle_time = 0
            elif event.key == pygame.K_4:
                sm.trigger("speaking")
                if npc_sm: npc_sm.idle_time = 0
            elif event.key == pygame.K_5:
                sm.trigger("sleepy")
                if npc_sm: npc_sm.idle_time = 0
            elif event.key == pygame.K_6:
                sm.trigger("curious")
                if npc_sm: npc_sm.idle_time = 0
            elif event.key == pygame.K_7:
                sm.trigger("wink")
                if npc_sm: npc_sm.idle_time = 0
            elif event.key == pygame.K_8:
                sm.trigger("laugh")
                if npc_sm: npc_sm.idle_time = 0
            elif event.key == pygame.K_9:
                sm.trigger("excited")
                if npc_sm: npc_sm.idle_time = 0
            elif event.key == pygame.K_0:
                sm.trigger("sad")
                if npc_sm: npc_sm.idle_time = 0
            elif event.key == pygame.K_h:
                sm.trigger("heart_eyes")
                if npc_sm: npc_sm.idle_time = 0
            elif event.key == pygame.K_s and not (event.mod & pygame.KMOD_CTRL):
                sm.trigger("star_eyes")
                if npc_sm: npc_sm.idle_time = 0
            elif event.key == pygame.K_F1:
                # F1: 切换调试HUD
                show_hud = not show_hud
            elif event.key == pygame.K_F12:
                # v10: F12截图
                ts = __import__('time').strftime('%H%M%S')
                fname = f'/tmp/v10_screenshot_{ts}.png'
                pygame.image.save(screen, fname)
                print(f'[v10] Screenshot saved: {fname}')
                print(f"[HUD] 调试信息: {'ON' if show_hud else 'OFF'}")
        elif event.type == pygame.MOUSEBUTTONDOWN:
            touch_down_pos = event.pos
            touch_down_time = time.time()
        elif event.type == pygame.MOUSEBUTTONUP:
            if card_mgr.visible:
                card_mgr.hide()
                voice_mgr.reply_text = ""
                voice_mgr.asr_text = ""
            elif npc_enabled and npc_sm:
                up_pos = event.pos
                elapsed = time.time() - (touch_down_time or 0)
                dx = up_pos[0] - (touch_down_pos[0] or up_pos[0])
                dy = up_pos[1] - (touch_down_pos[1] or up_pos[1])

                if elapsed > 1.0:
                    npc_sm.interact("long_press")
                    sm.trigger("angry")
                    squash_stretch.trigger_squash(0.7, "shake")  # v7: 长按→抖动
                elif abs(dy) > 80 and abs(dy) > abs(dx):
                    if dy < 0:
                        sm.trigger("surprised")
                        squash_stretch.trigger_squash(0.8, "surprise")  # v7: 上滑→惊讶跳
                    else:
                        sm.trigger("sad")
                        squash_stretch.trigger_squash(0.3, "tap")  # v7: 下滑→轻压
                    if npc_sm: npc_sm.idle_time = 0
                elif time.time() - last_click_time < 0.3:
                    npc_sm.interact("double_tap")
                    sm.trigger("excited")
                    squash_stretch.trigger_squash(0.6, "bounce")  # v7: 双击→弹跳
                    last_click_time = 0
                else:
                    last_click_time = time.time()
                    mid_x = WIDTH // 2
                    if up_pos[0] < mid_x * 0.4:
                        sm.trigger("look_left")
                        if npc_sm: npc_sm.idle_time = 0
                    elif up_pos[0] > mid_x * 1.6:
                        sm.trigger("look_right")
                        if npc_sm: npc_sm.idle_time = 0
                    else:
                        npc_sm.interact("touch")
                        squash_stretch.trigger_squash(0.5, "tap")  # v7: 短按→压扁回弹

                sm.interact_cooldown = random.uniform(2, 3)

    ws_server.process_commands()
    # 语音状态 → 表情+卡片联动
    vs = voice_mgr.state
    if vs == "listening":
        if sm.active_expr not in ("curious", "listening"):
            sm.trigger("curious")
    elif vs == "thinking":
        if sm.active_expr not in ("thinking",):
            sm.trigger("thinking")
    elif vs == "speaking":
        if sm.active_expr not in ("speaking",):
            sm.trigger("speaking")
        if voice_mgr.reply_text and not card_mgr.visible and not card_mgr.hiding:
            lines = (voice_mgr.reply_text.split("\n") 
                    if "\n" in voice_mgr.reply_text 
                    else [voice_mgr.reply_text])
            card_mgr.show("", lines, "dialog")
    elif vs == "idle":
        if voice_mgr.reply_text:
            voice_mgr.reply_text = ""
        if card_mgr.visible:
            if card_mgr.card_type == "dialog":
                card_mgr.hide()

    card_mgr.update(dt)
    if npc_enabled and npc_sm:
        npc_sm.update(dt)
    elif sm.auto_mode:
        sm.update_auto(dt)
    sm.update(dt)
    vfx_mgr.update(dt)  # v6: 更新特效
    squash_stretch.update(dt)  # v7: 更新Squash&Stretch
    anim_director.update(dt)   # v7: 更新身体姿态过渡
    renderer.update(dt)       # v8: 更新渲染器(瞳孔形态计时等)
    ambient_mgr.update(dt)    # v9: 更新环境氛围(色调/光晕/光斑)

    # v7: 获取身体层参数
    body_ox, body_oy = anim_director.get_body_offset(sm.idle_bounce)
    body_sx = squash_stretch.scale_x
    body_sy = squash_stretch.scale_y

    # v8: 瞳孔模式同步(heart_eyes/star_eyes)
    if sm.active_expr == "heart_eyes" and renderer.pupil_mode != "heart":
        renderer.set_pupil_mode("heart", duration=999)
    elif sm.active_expr == "star_eyes" and renderer.pupil_mode != "star":
        renderer.set_pupil_mode("star", duration=999)
    elif sm.active_expr not in ("heart_eyes", "star_eyes") and renderer.pupil_mode != "normal":
        renderer.set_pupil_mode("normal", duration=0)

    # v9: NPC状态→情绪氛围(每帧低频检查)
    if npc_enabled and npc_sm:
        npc_mood_map = {
            NPCState.IDLE: "idle", NPCState.OBSERVE: "curious",
            NPCState.ENGAGED: "happy", NPCState.WARN: "idle",
            NPCState.SLEEP: "sleepy",
        }
        npc_mood = npc_mood_map.get(npc_sm.state, "idle")
        if ambient_mgr._mood != npc_mood:
            ambient_mgr.set_mood(npc_mood)

    # 渲染(v9: 环境层内置于renderer.draw)
    # face_offset_x/y = 卡片弹出时的脸角落偏移(移动整个脸)
    # body_offset_x/y = 动画(squash)微偏移(叠加在脸上)
    renderer.draw(sm.current, card_mgr.face_scale, card_mgr.face_offset_x,
                  body_scale_x=body_sx, body_scale_y=body_sy,
                  body_offset_x=body_ox,
                  body_offset_y=body_oy + card_mgr.face_offset_y,
                  spacing_scale=card_mgr.spacing_scale,
                  vfx_mgr=vfx_mgr, ambient_mgr=ambient_mgr, perf=perf)
    if card_mgr.visible or card_mgr.current_alpha > 0.01:
        if card_mgr.card_type == "todo":
            renderer.draw_todo_card(card_mgr.title, card_mgr.lines, card_mgr.current_alpha)
        else:
            renderer.draw_dialog_card(card_mgr.title, card_mgr.lines, card_mgr.current_alpha)

    # 语音状态叠加层(永久显示)
    _vs = voice_mgr.state
    _vcolor = (150, 150, 150)
    _vlines = [f"🎤 {_vs.upper()} | 表情:{sm.active_expr}"]
    if _vs == "listening":
        _vcolor = (100, 200, 255)
    elif _vs == "thinking":
        _vcolor = (200, 200, 100)
        if voice_mgr.asr_text:
            _vlines.append("📝 \"" + voice_mgr.asr_text + "\"")
    elif _vs == "speaking":
        _vcolor = (100, 255, 150)
        if voice_mgr.asr_text:
            _vlines.append("📝 \"" + voice_mgr.asr_text + "\"")
    try:
        for _i, _t in enumerate(_vlines):
            _vs2, _ = renderer.font_cn_h.render(_t, _vcolor)
            renderer.screen.blit(_vs2, (12, 12 + _i * 24))
    except:
        pass

    # v9: 调试HUD (F1切换)
    if show_hud:
        hud_info = {
            "npc_state": npc_sm.state if npc_sm else "OFF",
            "personality": personality,
            "expr": sm.active_expr,
            "phase": sm.phase,
            "param_trans": sm._param_trans,
            "param_easing": sm._param_trans_easing if sm._param_trans else "",
            "param_t": sm._param_trans_time / sm._param_trans_dur if sm._param_trans and sm._param_trans_dur > 0 else 0,
            "fps": _actual_fps,
            "perf": perf.level if perf else "FULL",
            "mood": ambient_mgr._mood if ambient_mgr else "idle",
            "dots": len(ambient_mgr._dots) if ambient_mgr else 0,
            "vfx": len(vfx_mgr._effects) if vfx_mgr else 0,
        }
        renderer.draw_hud(hud_info)

    pygame.display.flip()

if gimbal_ctrl is not None:
    gimbal_ctrl.disconnect()
voice_mgr.quit()
pygame.quit()
sys.exit(0)
