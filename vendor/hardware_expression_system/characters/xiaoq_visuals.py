"""Pinned XiaoQ cute/neon styles and visual renderers.

Source: the active product main program at the integration baseline.
The product owns hardware, voice, and business state.
"""

import math
import os
import random
import pygame
import pygame.freetype

WIDTH, HEIGHT = 1280, 720

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
    def dim_color(cls, color, factor=30):
        """调暗霓虹色(用于发光外圈)"""
        return tuple(max(0, min(255, int(c * factor))) for c in color[:3])


BG_COLOR = StyleConfig.BG_COLOR


EYE_COLOR = StyleConfig.NEON_DEFAULT


CARD_BG = StyleConfig.CARD_BG


CARD_BORDER = StyleConfig.CARD_BORDER


CARD_TEXT = StyleConfig.CARD_TEXT


CARD_TITLE = StyleConfig.CARD_TITLE


CARD_HINT = StyleConfig.CARD_HINT


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


class CuteStyle:
    """可爱自信风全局配色"""
    BG_COLOR = (240, 208, 192)
    BG_WARM = (245, 218, 202)
    FACE_SKIN = (245, 204, 183)
    FACE_SHADOW = (225, 184, 163)
    EYE_WHITE = (255, 255, 255, 230)
    EYE_OUTLINE = (80, 70, 65)
    PUPIL_COLOR = (78, 36, 22)
    PUPIL_HIGHLIGHT = (255, 255, 255)
    BROW_COLOR = (55, 48, 42)
    MOUTH_COLOR = (195, 105, 100)
    MOUTH_INNER = (220, 130, 125)
    BLUSH_COLOR = (193, 77, 51)
    MOOD_GLOW = {
        "idle": (255, 240, 220), "happy": (255, 220, 180),
        "love": (255, 190, 200), "sad": (200, 210, 240),
        "angry": (255, 200, 190), "surprised": (255, 235, 170),
        "excited": (255, 210, 140), "curious": (240, 225, 200),
        "sleepy": (220, 215, 230), "focus": (230, 225, 215),
    }
    PARTICLE_COLORS = {
        "heart": [(255, 120, 150), (255, 160, 180), (255, 100, 140)],
        "star": [(255, 210, 80), (255, 230, 130), (255, 190, 60)],
        "sparkle": [(255, 240, 180), (255, 220, 200), (255, 200, 220)],
    }


HAPPY      = P(1.0, 1.0, 1.1, 1.1, -5, -5, 0.55, 0.55,  1.2, 0.9, -3, -3, 0.5)    # 瞳孔放大+高光强+眉上扬+腮红


LAUGH      = P(1.0, 1.0, 1.2, 1.2, -8, -8, 0.65, 0.65,  1.3, 1.0, -5, -5, 0.7)    # 大瞳孔+强光+眉高扬+强腮红


EXCITED    = P(1.3, 1.3, 1.0, 1.0, -5, -5, 0, 0,          1.4, 1.0, -4, -4, 30)   # 最大瞳孔+强光


ANGRY      = P(0.7, 0.7, 1.2, 1.2, 8, 8, 0, 0,            0.6, 30, 8, 8, 0)       # 小瞳孔+弱光+眉下压


SURPRISE   = P(1.5, 1.5, 1.1, 1.1, -10, -10, 0, 0,        0.5, 0.95, -8, -8, 0)    # 小瞳孔+强光分裂+眉高耸


SCARED     = P(1.3, 1.0, 0.9, 1.3, -8, -5, 0, 0,          0.7, 0.4, -5, 5, 0)      # 中瞳孔+弱光+不对称眉


SMILE      = P(0.85, 0.85, 1.0, 1.0, 0, 0, 0.25, 0.25,    1.1, 0.8, -1, -1, 30)   # 轻度瞳孔+腮红


RELAXED    = P(0.8, 0.8, 1.0, 1.0, 0, 0, 0, 0,            0.9, 0.5, 0, 0, 0)       # 中瞳孔+柔光


SAD        = P(0.5, 0.5, 1.0, 1.0, 5, 5, 0, 0,            0.7, 30, 5, 5, 0)       # 小瞳孔+弱光+眉下垂


SLEEPY     = P(0.0, 0.0, 0.8, 0.8, 0, 0, 0, 0,            1.0, 0.1, 0, 0, 0)


DEEP_SLEEP  = P(0.0, 0.0, 0.8, 0.8, 0, 0, 0, 0,           1.0, 0.0, 0, 0, 0)      # 极小瞳孔+极弱光+眉松


BORED      = P(0.4, 0.6, 1.0, 0.8, 3, 0, 0, 0,            0.8, 30, 3, -1, 0)      # 中瞳孔+弱光+不对称


IDLE_P     = P(1.0, 1.0, 1.0, 1.0, 0, 0, 0, 0,            1.0, 0.7, 0, 0, 0)       # 标准瞳孔+标准光


CURIOUS    = P(1.2, 0.8, 1.1, 0.9, -5, 2, 0, 0,           1.3, 0.8, -3, 2, 0)      # 大瞳孔+中光+好奇眉


THINK      = P(0.8, 0.5, 0.9, 0.7, -2, 3, 0, 0,           0.8, 0.4, 2, 6, 0)       # 中瞳孔+弱光+思考眉


CONFUSED   = P(1.0, 0.6, 1.0, 0.8, 0, 3, 0, 0,            0.9, 0.5, -2, 5, 0)      # 中瞳孔+不对称眉


BLINK      = P(0.0, 0.0, 1.0, 1.0, 0, 0, 0, 0,            1.0, 0, 0, 0, 0)         # 闭眼无瞳孔/高光


WINK       = P(1.0, 0.0, 1.1, 1.0, -2, 0, 0, 0,           1.1, 0.8, -2, 0, 0.2)    # 左眼瞳孔大+腮红


LOOK_L     = P(1.0, 1.0, 1.15, 0.85, -2, -2, 0, 0,        1.0, 0.7, 0, 0, 0)


LOOK_R     = P(1.0, 1.0, 0.85, 1.15, -2, -2, 0, 0,        1.0, 0.7, 0, 0, 0)


LOOK_U     = P(1.1, 1.1, 0.9, 0.9, -10, -10, 0, 0,        1.0, 0.7, -2, -2, 0)


HEART_EYES = P(1.2, 1.2, 1.1, 1.1, -5, -5, 0.4, 0.4,     1.0, 0.9, -3, -3, 0.8)   # 爱心瞳孔


STAR_EYES  = P(1.3, 1.3, 1.0, 1.0, -5, -5, 0, 0,          1.0, 1.0, -4, -4, 30)   # 星星瞳孔


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
        "intro_target": SLEEPY, "intro_speed": 30,
        "loop_target": SLEEPY, "loop_duration": 999999.0,
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


CUTE_IDLE_P     = P(0.90, 0.90, 1.00, 1.00,  0,  0, 0.00, 0.00, 1.00, 0.80, -2, -2, 0.55)


CUTE_HAPPY      = P(0.05, 0.05, 1.12, 1.12, -3, -3, 0.20, 0.20, 1.20, 1.00, -8, -8, 0.75)


CUTE_LAUGH      = P(0.40, 0.40, 1.15, 1.15,  0,  0, 0.75, 0.75, 1.10, 0.90, -9, -9, 0.55)


CUTE_EXCITED    = P(1.20, 1.20, 1.20, 1.20, -5, -5, 0.00, 0.00, 1.40, 1.00, -10, -10, 0.55)


CUTE_SMILE      = P(0.70, 0.70, 1.08, 1.08,  0,  0, 0.50, 0.50, 1.15, 0.85, -5, -5, 0.55)


CUTE_RELAXED    = P(0.65, 0.65, 1.00, 1.00,  0,  0, 0.00, 0.00, 0.90, 0.50,  0,  0, 0.55)


CUTE_ANGRY      = P(0.60, 0.60, 0.90, 0.90,  4,  4, 0.00, 0.00, 0.60, 0.30,  6,  6, 0.55)


CUTE_SAD        = P(0.45, 0.45, 0.95, 0.95,  5,  5, 0.00, 0.00, 0.70, 0.30, 10, 10, 0.00)


CUTE_SCARED     = P(1.30, 0.90, 0.95, 1.20, -7, -3, 0.00, 0.00, 0.60, 0.40, -5,  7, 0.55)


CUTE_SLEEPY     = P(0.05, 0.05, 0.85, 0.85,  0,  0, 0.00, 0.00, 1.00, 0.05,  2,  2, 0.00)


CUTE_DEEP_SLEEP = P(0.00, 0.00, 0.85, 0.85,  0,  0, 0.00, 0.00, 1.00, 0.00,  2,  2, 0.00)


CUTE_BORED      = P(0.40, 0.60, 0.95, 0.85,  3,  0, 0.00, 0.00, 0.80, 0.30,  3, -1, 0.55)


CUTE_SURPRISE   = P(1.40, 1.40, 1.05, 1.05, -6, -6, 0.00, 0.00, 0.50, 0.90, -12, -12, 0.55)


CUTE_CURIOUS    = P(1.15, 0.85, 1.10, 1.00, -3,  2, 0.00, 0.00, 1.25, 0.80, -6,  3, 0.55)


CUTE_THINK      = P(0.75, 0.40, 0.90, 0.80, -2,  3, 0.00, 0.30, 0.80, 0.35,  3,  7, 0.55)


CUTE_CONFUSED   = P(1.00, 0.60, 1.00, 0.85,  0,  3, 0.00, 0.00, 0.85, 0.40, -3,  6, 0.55)


CUTE_SPEAK      = P(0.90, 0.90, 1.00, 1.00,  0,  0, 0.00, 0.00, 1.00, 0.60, -2, -2, 0.55)


CUTE_BLINK      = P(0.00, 0.00, 1.00, 1.00,  0,  0, 0.00, 0.00, 1.00, 0.00, -1, -1, 0.55)


CUTE_WINK       = P(0.90, 0.00, 1.05, 1.00, -1,  0, 0.00, 0.00, 1.10, 0.80, -4,  2, 0.55)


CUTE_LOOK_L     = P(0.90, 0.90, 0.85, 1.08, -1, -1, 0.00, 0.00, 0.95, 0.70,  0,  0, 0.55)


CUTE_LOOK_R     = P(0.90, 0.90, 1.08, 0.85, -1, -1, 0.00, 0.00, 0.95, 0.70,  0,  0, 0.55)


CUTE_LOOK_U     = P(1.05, 1.05, 0.90, 0.90, -8, -8, 0.00, 0.00, 0.95, 0.70, -2, -2, 0.55)


CUTE_HEART_EYES = P(1.10, 1.10, 1.10, 1.10, -3, -3, 0.30, 0.30, 1.00, 0.90, -7, -7, 0.55)


CUTE_STAR_EYES  = P(1.20, 1.20, 1.05, 1.05, -4, -4, 0.00, 0.00, 1.00, 1.00, -9, -9, 0.55)


CUTE_EXPRESSIONS = {
    "happy": {"intro_target": CUTE_HAPPY, "intro_speed": 0.15, "loop_target": CUTE_HAPPY, "loop_duration": 3.0, "tail_target": CUTE_IDLE_P, "tail_speed": 0.10},
    "laugh": {"intro_target": CUTE_LAUGH, "intro_speed": 0.12, "loop_target": CUTE_LAUGH, "loop_duration": 2.5, "tail_target": CUTE_IDLE_P, "tail_speed": 0.08},
    "excited": {"intro_target": CUTE_EXCITED, "intro_speed": 0.18, "loop_target": CUTE_EXCITED, "loop_duration": 2.0, "loop_dynamic": True, "tail_target": CUTE_IDLE_P, "tail_speed": 0.10},
    "angry": {"intro_target": CUTE_ANGRY, "intro_speed": 0.20, "loop_target": CUTE_ANGRY, "loop_duration": 2.0, "tail_target": CUTE_IDLE_P, "tail_speed": 0.08},
    "surprised": {"intro_target": CUTE_SURPRISE, "intro_speed": 0.20, "loop_target": CUTE_SURPRISE, "loop_duration": 1.5, "tail_target": CUTE_IDLE_P, "tail_speed": 0.08},
    "scared": {"intro_target": CUTE_SCARED, "intro_speed": 0.20, "loop_target": CUTE_SCARED, "loop_duration": 1.5, "tail_target": CUTE_IDLE_P, "tail_speed": 0.08},
    "smile": {"intro_target": CUTE_SMILE, "intro_speed": 0.10, "loop_target": CUTE_SMILE, "loop_duration": 5.0, "tail_target": CUTE_IDLE_P, "tail_speed": 0.08},
    "relaxed": {"intro_target": CUTE_RELAXED, "intro_speed": 0.06, "loop_target": CUTE_RELAXED, "loop_duration": 5.0, "tail_target": CUTE_IDLE_P, "tail_speed": 0.06},
    "sad": {"intro_target": CUTE_SAD, "intro_speed": 0.08, "loop_target": CUTE_SAD, "loop_duration": 4.0, "tail_target": CUTE_IDLE_P, "tail_speed": 0.06},
    "sleepy": {"intro_target": CUTE_SLEEPY, "intro_speed": 0.03, "loop_target": CUTE_SLEEPY, "loop_duration": 999999.0},
    "bored": {"intro_target": CUTE_BORED, "intro_speed": 0.08, "loop_target": CUTE_BORED, "loop_duration": 4.0, "tail_target": CUTE_IDLE_P, "tail_speed": 0.06},
    "idle": {"loop_target": CUTE_IDLE_P, "loop_dynamic": True},
    "curious": {"intro_target": CUTE_CURIOUS, "intro_speed": 0.12, "loop_target": CUTE_CURIOUS, "loop_duration": 3.0, "tail_target": CUTE_IDLE_P, "tail_speed": 0.08},
    "thinking": {"intro_target": CUTE_THINK, "intro_speed": 0.12, "loop_target": CUTE_THINK, "loop_duration": 4.0, "loop_dynamic": True, "tail_target": CUTE_IDLE_P, "tail_speed": 0.08},
    "confused": {"intro_target": CUTE_CONFUSED, "intro_speed": 0.12, "loop_target": CUTE_CONFUSED, "loop_duration": 3.0, "tail_target": CUTE_IDLE_P, "tail_speed": 0.08},
    "speaking": {"intro_target": CUTE_SPEAK, "intro_speed": 0.15, "loop_target": CUTE_SPEAK, "loop_duration": 4.0, "loop_dynamic": True, "tail_target": CUTE_IDLE_P, "tail_speed": 0.10},
    "look_left": {"intro_target": CUTE_LOOK_L, "intro_speed": 0.15, "loop_target": CUTE_LOOK_L, "loop_duration": 1.5, "tail_target": CUTE_IDLE_P, "tail_speed": 0.10},
    "look_right": {"intro_target": CUTE_LOOK_R, "intro_speed": 0.15, "loop_target": CUTE_LOOK_R, "loop_duration": 1.5, "tail_target": CUTE_IDLE_P, "tail_speed": 0.10},
    "look_up": {"intro_target": CUTE_LOOK_U, "intro_speed": 0.12, "loop_target": CUTE_LOOK_U, "loop_duration": 2.0, "tail_target": CUTE_IDLE_P, "tail_speed": 0.10},
    "wink": {"intro_target": CUTE_WINK, "intro_speed": 0.20, "loop_target": CUTE_WINK, "loop_duration": 0.3, "tail_target": CUTE_IDLE_P, "tail_speed": 0.15},
    "blink": {"intro_target": CUTE_BLINK, "intro_speed": 0.30, "loop_target": CUTE_BLINK, "loop_duration": 0.15, "tail_target": CUTE_IDLE_P, "tail_speed": 0.25},
    "heart_eyes": {"intro_target": CUTE_HEART_EYES, "intro_speed": 0.12, "loop_target": CUTE_HEART_EYES, "loop_duration": 3.0, "tail_target": CUTE_IDLE_P, "tail_speed": 0.08},
    "star_eyes": {"intro_target": CUTE_STAR_EYES, "intro_speed": 0.15, "loop_target": CUTE_STAR_EYES, "loop_duration": 2.0, "tail_target": CUTE_IDLE_P, "tail_speed": 0.10},
}


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


class CuteAmbientManager:
    """可爱氛围：暖色面部柔光 + 飘浮爱心/星星/闪光粒子"""
    PARTICLE_TYPES = ["heart", "star", "sparkle"]

    def __init__(self, face_cx, face_cy):
        self.face_cx = face_cx; self.face_cy = face_cy
        self.width = WIDTH; self.height = HEIGHT
        self._glow_alpha = 0.0; self._glow_target = 0.12
        self._glow_color = list(CuteStyle.MOOD_GLOW["idle"])
        self._glow_target_color = list(CuteStyle.MOOD_GLOW["idle"])
        self._breath_phase = 0.0
        self._particles = []
        self._spawn_timer = 0.0; self._spawn_interval = 0.8
        self._max_particles = 15; self._mood = "idle"

    def set_mood(self, mood_name):
        if mood_name == self._mood: return
        self._mood = mood_name
        color = list(CuteStyle.MOOD_GLOW.get(mood_name, CuteStyle.MOOD_GLOW["idle"]))
        self._glow_target_color = color
        self._glow_target = 0.18 if mood_name not in ("idle", "sleepy") else 0.10

    def update(self, dt):
        for i in range(3):
            self._glow_color[i] += (self._glow_target_color[i] - self._glow_color[i]) * min(1.0, 2.0 * dt)
        self._glow_alpha += (self._glow_target - self._glow_alpha) * min(1.0, 2.0 * dt)
        self._breath_phase += dt * 0.8
        self._spawn_timer += dt
        if self._spawn_timer >= self._spawn_interval and len(self._particles) < self._max_particles:
            self._spawn_timer = 0; self._spawn_particle()
        alive = []
        for p in self._particles:
            p["life"] -= dt
            if p["life"] <= 0: continue
            p["x"] += p["vx"] * dt; p["y"] += p["vy"] * dt
            if p["type"] in ("heart", "star"):
                p["x"] += math.sin(p["life"] * 2.0 + p.get("phase", 0)) * 0.4
            ml = p["max_life"]
            if p["life"] > ml - 0.4: p["alpha"] = min(1.0, (ml - p["life"]) / 0.4) * p["peak_alpha"]
            elif p["life"] < 0.8: p["alpha"] = (p["life"] / 0.8) * p["peak_alpha"]
            else: p["alpha"] = p["peak_alpha"]
            if p["type"] == "star": p["rotation"] += dt * 30
            if p["alpha"] > 0.02: alive.append(p)
        self._particles = alive

    def _spawn_particle(self):
        ptype = random.choice(self.PARTICLE_TYPES)
        color = random.choice(CuteStyle.PARTICLE_COLORS[ptype])
        max_life = random.uniform(3.0, 7.0)
        x = random.uniform(self.width * 0.05, self.width * 0.95)
        y = self.height + 15
        vx = random.uniform(-10, 10); vy = random.uniform(-35, -15)
        size = random.uniform(6, 14) if ptype == "heart" else random.uniform(5, 10)
        self._particles.append({"type": ptype, "x": x, "y": y, "vx": vx, "vy": vy,
            "size": size, "color": color, "life": max_life, "max_life": max_life,
            "alpha": 0.0, "peak_alpha": random.uniform(0.3, 0.6),
            "phase": random.uniform(0, 6.28), "rotation": random.uniform(0, 360)})

    def get_glow_color(self):
        return tuple(int(self._glow_color[i]) for i in range(3))

    def draw_glow(self, screen, cx=None, cy=None):
        if self._glow_alpha < 0.01: return
        cx = cx or self.face_cx; cy = cy or self.face_cy
        breath = 1.0 + 0.06 * math.sin(self._breath_phase * math.pi * 2)
        base_r = int(240 * breath); glow_size = base_r * 2 + 40
        gc = self.get_glow_color()
        surf = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
        center = glow_size // 2
        for i in range(6):
            t = i / 5; frac = 1.0 - t * 0.85; r = max(3, int(base_r * frac))
            alpha = int(self._glow_alpha * (0.03 + t * 0.28) * 255)
            alpha = min(255, max(0, alpha))
            pygame.draw.circle(surf, (*gc, alpha), (center, center), r)
        screen.blit(surf, (cx - center, cy - center))

    def draw_particles(self, screen, half=False):
        for i, p in enumerate(self._particles):
            if half and i % 2 == 1: continue
            if p["alpha"] < 0.02: continue
            alpha = int(min(255, p["alpha"] * 255)); color = (*p["color"], alpha); s = int(p["size"])
            if p["type"] == "heart":
                surf = pygame.Surface((s * 2 + 4, s * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(surf, color, (s // 2 + 2, s // 2 + 2), s // 2)
                pygame.draw.circle(surf, color, (s + s // 2 + 2, s // 2 + 2), s // 2)
                pts = [(2, s // 2 + s // 3), (s * 2 + 2, s // 2 + s // 3), (s + 2, s * 2)]
                pygame.draw.polygon(surf, color, pts)
                screen.blit(surf, (int(p["x"]) - s - 2, int(p["y"]) - s - 2))
            elif p["type"] == "star":
                pts = []
                for j in range(10):
                    ang = math.radians(j * 36 + p.get("rotation", 0))
                    r = s if j % 2 == 0 else s * 0.4
                    pts.append((int(p["x"]) + r * math.cos(ang - math.pi / 2), int(p["y"]) + r * math.sin(ang - math.pi / 2)))
                pygame.draw.polygon(screen, color, pts)
            else:
                surf = pygame.Surface((s * 3, s * 3), pygame.SRCALPHA); cs = s * 3 // 2
                pygame.draw.circle(surf, color, (cs, cs), s)
                pygame.draw.circle(surf, (*p["color"], alpha // 3), (cs, cs), s * 2)
                screen.blit(surf, (int(p["x"]) - cs, int(p["y"]) - cs))


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

    def draw_todo_card(self, title, lines, alpha, card_mgr):
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


class CuteRenderer:
    """可爱自信风渲染器"""

    def __init__(self, screen):
        self.screen = screen
        self.face_center_x = WIDTH // 2
        self._current_expr = "idle"
        self.face_center_y = HEIGHT // 2 + 20
        self.eye_rx = 135; self.eye_ry = 168
        self.eye_spacing = 320; self.eye_y_offset = -72
        self.brow_y_offset = -240
        self.pupil_mode = "normal"; self._pupil_mode_timer = 0.0
        pygame.freetype.init()
        self.font_small = None
        for fp in ["/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Light.ttc"]:
            if os.path.exists(fp):
                try: self.font_small = pygame.freetype.Font(fp, 13); break
                except: pass
        if self.font_small is None: self.font_small = pygame.freetype.Font(None, 13)

    def set_expression(self, expr_name): self._current_expr = expr_name
    def set_pupil_mode(self, mode, duration=3.0): self.pupil_mode = mode; self._pupil_mode_timer = duration
    def update(self, dt):
        if self._pupil_mode_timer > 0:
            self._pupil_mode_timer -= dt
            if self._pupil_mode_timer <= 0: self.pupil_mode = "normal"; self._pupil_mode_timer = 0
    def on_expression_change(self, expr_name): self._current_expr = expr_name

    def draw(self, state, face_scale=1.0, offset_x=0, offset_y=0,
             body_scale_x=1.0, body_scale_y=1.0, body_offset_x=0, body_offset_y=0,
             spacing_scale=1.0, vfx_mgr=None, ambient_mgr=None, perf=None):
        cx = self.face_center_x + offset_x + body_offset_x
        cy = self.face_center_y + offset_y + body_offset_y
        self.screen.fill(CuteStyle.BG_COLOR)
        if ambient_mgr and (perf is None or perf.enable_glow):
            ambient_mgr.draw_glow(self.screen, cx, cy)
        # 先画眉毛（图层在眼睛下方）
        if self._current_expr != "sleepy":
            for side in [-1, 1]:
                bry = state.brow_l if side < 0 else state.brow_r
                bx = cx + side * self.eye_spacing * face_scale * body_scale_x
                by = cy - (30 if self._current_expr == "surprised" else 0)
                self._draw_eyebrow(bx, by, bry, face_scale, side, 1.0)
        # 再画眼睛（图层在眉毛上方）
        for side in [-1, 1]:
            l_open = state.l_open if side < 0 else state.r_open
            l_w = state.l_w if side < 0 else state.r_w
            l_y = state.l_y if side < 0 else state.r_y
            l_cut = state.l_cut if side < 0 else state.r_cut
            pupil_sc = state.pupil_scale; hl = state.highlight
            ex = cx + side * self.eye_spacing * face_scale * body_scale_x
            ey = cy + self.eye_y_offset * face_scale + l_y * face_scale
            px_shift = -6 * face_scale if self._current_expr == "look_left" else (6 * face_scale if self._current_expr == "look_right" else 0)
            self._draw_eye(ex, ey, l_open, l_w, l_cut, pupil_sc, hl, px_shift, face_scale, side)
        if state.blush > 0.01: self._draw_blush(cx, cy, state.blush, face_scale)
        if ambient_mgr and (perf is None or perf.enable_dots):
            ambient_mgr.draw_particles(self.screen, half=(perf.dots_half if perf else False))

    def _draw_blush(self, cx, cy, blush_val, scale):
        alpha = int(min(140, blush_val * 180))
        if alpha < 5: return
        for side in [-1, 1]:
            bx = cx + side * (self.eye_spacing + 203) * scale
            by = cy + (self.eye_y_offset + 196) * scale
            brx = int(111 * scale); bry = int(52 * scale)  # 横轴+20
            angle = 10 if side < 0 else 170  # 左30° 右150°
            surf_size = max(brx, bry) * 2 + 16
            surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
            cx_s, cy_s = surf_size // 2, surf_size // 2
            pygame.draw.ellipse(surf, (*CuteStyle.BLUSH_COLOR, alpha),
                              (cx_s - brx, cy_s - bry, brx * 2, bry * 2))
            rotated = pygame.transform.rotate(surf, angle)
            rr = rotated.get_rect(center=(bx, by))
            self.screen.blit(rotated, rr)

    def _draw_eye(self, cx, cy, open_r, w_scale, cut, pupil_sc, hl, px_shift, face_scale, side=0):
        bw = int(self.eye_rx * w_scale * face_scale)
        bh = int(self.eye_ry * max(0.01, open_r) * face_scale)
        px = cx + px_shift; py = cy
        if bh < 10:
            lw = max(6, int(14 * face_scale))
            if True:
                # wink/blink：原始单线
                pts = [(cx - bw + int(bw * 2 * (i / 11.0)), cy + int(math.sin((i / 11.0) * math.pi) * 2)) for i in range(12)]
                pygame.draw.lines(self.screen, CuteStyle.PUPIL_COLOR, False, pts, lw)
            return
        cut_pixels = int(bh * cut * 2.0) if cut > 0.1 else 0
        if self.pupil_mode == "heart": self._draw_heart_eye(px, py, bw, bh, cut_pixels, hl, face_scale); return
        elif self.pupil_mode == "star": self._draw_star_eye(px, py, bw, bh, cut_pixels, hl, face_scale); return
        ww = int(bw * 1.52); wh = int(bh * 1.04)  # 宽椭圆(80%)
        pygame.draw.ellipse(self.screen, (250, 250, 250), (px - ww, py - wh, ww * 2, wh * 2))
        pw = int(ww * 0.7); ph = int(wh * 0.7)  # 白圈70%比例
        pygame.draw.ellipse(self.screen, CuteStyle.PUPIL_COLOR, (px - pw, py - ph, pw * 2, ph * 2))
        if cut_pixels > 0:
            clip_y = py + bh - cut_pixels; clip_h = wh + cut_pixels + 8
            pygame.draw.rect(self.screen, CuteStyle.BG_COLOR, (px - ww - 4, clip_y, ww * 2 + 8, clip_h))
            arc_pts = [(px - bw + int(bw * 2 * (i / 20.0)), clip_y + int(math.sin((i / 20.0) * math.pi) * 4)) for i in range(21)]
            pygame.draw.lines(self.screen, CuteStyle.PUPIL_COLOR, False, arc_pts, 3)
        if open_r > 0.05 and hl > 0.05:
            # 高光大小跟随眼睛比例
            eye_ref = min(bw, bh)
            # 主高光(左上，原4倍)
            hr = max(3, int(eye_ref * 0.6 * hl))
            hx = px - int(bw * 0.38); hy = py - int(bh * 0.40)
            pygame.draw.circle(self.screen, CuteStyle.PUPIL_HIGHLIGHT, (hx, hy), hr)
            # 次高光(右下，原2倍)
            hr2 = max(2, int(eye_ref * 0.3 * hl))
            hx2 = px + int(bw * 0.25); hy2 = py + int(bh * 0.25)
            pygame.draw.circle(self.screen, CuteStyle.PUPIL_HIGHLIGHT, (hx2, hy2), hr2)

    def _draw_heart_eye(self, cx, cy, bw, bh, cut_pixels, hl, face_scale):
        s = max(bw, bh); size = int(s * 0.85); surf_size = size * 3
        surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        cs_x, cs_y = surf_size // 2, surf_size // 2 - size // 3; c = CuteStyle.PUPIL_COLOR
        pygame.draw.circle(surf, c, (cs_x - size // 2, cs_y), size // 2)
        pygame.draw.circle(surf, c, (cs_x + size // 2, cs_y), size // 2)
        pts = [(cs_x - size, cs_y + size // 4), (cs_x + size, cs_y + size // 4), (cs_x, cs_y + size + size // 2)]
        pygame.draw.polygon(surf, c, pts)
        if hl > 0.05:
            hr = max(7, int(21 * hl * face_scale))
            pygame.draw.circle(surf, CuteStyle.PUPIL_HIGHLIGHT, (cs_x - int(size * 0.30), cs_y - int(size * 0.28)), hr)
        self.screen.blit(surf, (cx - cs_x, cy - cs_y))

    def _draw_star_eye(self, cx, cy, bw, bh, cut_pixels, hl, face_scale):
        size = max(bw, bh)
        pts = [(cx + (size if i % 2 == 0 else size * 0.45) * math.cos(math.radians(i * 36 - 90)),
                cy + (size if i % 2 == 0 else size * 0.45) * math.sin(math.radians(i * 36 - 90))) for i in range(10)]
        pygame.draw.polygon(self.screen, CuteStyle.PUPIL_COLOR, pts)
        if hl > 0.05:
            pygame.draw.circle(self.screen, CuteStyle.PUPIL_HIGHLIGHT, (cx - int(size * 0.30), cy - int(size * 0.28)), max(6, int(17 * hl * face_scale)))

    def _draw_eyebrow(self, cx, cy, brow_offset, face_scale, side, open_r=1.0):
        # 眉毛：旋转椭圆，横轴跟白圈相切(45°/135°)
        tilt = brow_offset * face_scale * 1.5
        bw = int(self.eye_rx * face_scale)
        bh = int(self.eye_ry * max(0.01, open_r) * face_scale)
        ww = int(bw * 1.9)
        wh = int(bh * 1.3)
        gap = max(1, int(4 * face_scale))
        # 椭圆尺寸：横轴=白圈弧长的一段，纵轴=横轴/4
        major = int(ww * 0.55) + 20  # 横轴半长+50像素
        minor = max(2, int(major // 3 * 0.96))  # 纵轴加粗20%
        # 切点角度：左眼45°，右眼135°
        if side < 0:
            tangent_angle = 75.0
        else:
            tangent_angle = 105.0
        # 切点在白圈边缘
        t_rad = math.radians(tangent_angle)
        tx = cx + int((ww + gap) * math.cos(t_rad))
        ty = cy - int((wh + gap) * math.sin(t_rad)) + int(tilt)
        # 椭圆中心：从切点沿法线方向(45°方向)偏移
        center_offset = minor + gap
        nx = tx + int(center_offset * math.cos(t_rad))
        ny = ty - int(center_offset * math.sin(t_rad))
        # 创建旋转椭圆
        rot_deg = tangent_angle - 90  # 横轴沿45°/135°方向
        surf_size = (major + minor) * 2 + 4
        surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        pygame.draw.ellipse(surf, (38, 26, 22),
                          (surf_size//2 - major, surf_size//2 - minor,
                           major * 2, minor * 2))
        rotated = pygame.transform.rotate(surf, rot_deg)
        rr = rotated.get_rect(center=(nx + side * 50, ny))
        self.screen.blit(rotated, rr)
    def draw_hud(self, info):
        try:
            for i, l in enumerate([
                f"FPS:{info.get('fps', 0):.0f} | {info.get('expr', '?')} | {info.get('phase', '?')}",
                f"MOOD:{info.get('mood', '?')} | PERF:{info.get('perf', '?')} | DOTS:{info.get('dots', 0)}",
            ]):
                s, _ = self.font_small.render(l, (120, 100, 90))
                self.screen.blit(s, (WIDTH - 350, 12 + i * 18))
        except: pass
