#!/usr/bin/env python3
"""
小Q Mac 端独立表情查看器 — Neon Cyber Style
从 robot_face_v11.py 提取渲染核心，无需树莓派硬件。
键盘 1-9,0 触发表情 | M 切换情绪 | B 弹性动画 | F1 调试 | ESC 退出
"""

import pygame
import pygame.freetype
import math
import random
import sys
import time
import enum
from collections import namedtuple

# ── 配置 ──
WIDTH, HEIGHT = 1280, 720
FPS = 30

# ═══════════════════════════════════════════════════════
# StyleConfig — 霓虹赛博配色
# ═══════════════════════════════════════════════════════
class StyleConfig:
    BG_COLOR     = (10, 10, 15)
    BG_COLOR_RGB = (10, 10, 15)
    NEON_CYAN    = (0, 255, 255)
    NEON_PINK    = (255, 50, 150)
    NEON_AMBER   = (255, 191, 0)
    NEON_RED     = (255, 30, 30)
    NEON_PURPLE  = (160, 50, 255)
    NEON_BLUE    = (50, 120, 255)
    NEON_DEFAULT = (80, 180, 255)

    EXPR_NEON_MAP = {
        "idle": (80, 180, 255), "happy": (0, 255, 255), "laugh": (0, 255, 200),
        "excited": (255, 220, 0), "smile": (100, 230, 255), "relaxed": (80, 180, 255),
        "sad": (50, 120, 255), "angry": (255, 30, 30), "surprised": (255, 191, 0),
        "scared": (160, 50, 255), "sleepy": (60, 60, 140), "bored": (80, 130, 180),
        "curious": (100, 200, 255), "thinking": (80, 160, 255), "confused": (200, 100, 255),
        "speaking": (80, 220, 255), "blink": (80, 180, 255), "wink": (80, 180, 255),
        "look_left": (80, 180, 255), "look_right": (80, 180, 255), "look_up": (80, 180, 255),
        "heart_eyes": (255, 50, 150), "star_eyes": (255, 220, 0),
    }

    SCANLINE_COLOR = (0, 255, 255, 8)
    SCANLINE_GAP = 3
    SCANLINE_SPEED = 80
    GLITCH_INTERVAL_MIN = 8.0
    GLITCH_INTERVAL_MAX = 25.0
    GLITCH_DURATION = 0.15
    GLITCH_INTENSITY = 12
    BLOOM_LAYERS = 0
    BLOOM_SPREAD = 1.8
    BLOOM_MAX_ALPHA = 25
    MOUTH_WIDTH = 0.65

    @classmethod
    def get_neon_color(cls, expr_name):
        return cls.EXPR_NEON_MAP.get(expr_name, cls.NEON_DEFAULT)

    @classmethod
    def dim_color(cls, color, factor=30):
        return tuple(max(0, min(255, int(c * factor))) for c in color[:3])


# ═══════════════════════════════════════════════════════
# Params — 表情参数
# ═══════════════════════════════════════════════════════
class Params:
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

# ═══════════════════════════════════════════════════════
# 表情预设
# ═══════════════════════════════════════════════════════
# P(l_open, r_open, l_w, r_w, l_y, r_y, l_cut, r_cut, pupil_scale, highlight, brow_l, brow_r, blush)
HAPPY      = P(1.0, 1.0, 1.1, 1.1, -5, -5, 0.55, 0.55,  1.2, 0.9, -3, -3, 0.5)
LAUGH      = P(1.0, 1.0, 1.2, 1.2, -8, -8, 0.65, 0.65,  1.3, 1.0, -5, -5, 0.7)
EXCITED    = P(1.3, 1.3, 1.0, 1.0, -5, -5, 0, 0,          1.4, 1.0, -4, -4, 30)
ANGRY      = P(0.7, 0.7, 1.2, 1.2, 8, 8, 0, 0,            0.6, 30, 8, 8, 0)
SURPRISE   = P(1.5, 1.5, 1.1, 1.1, -10, -10, 0, 0,        0.5, 0.95, -8, -8, 0)
SCARED     = P(1.3, 1.0, 0.9, 1.3, -8, -5, 0, 0,          0.7, 0.4, -5, 5, 0)
SMILE      = P(0.85, 0.85, 1.0, 1.0, 0, 0, 0.25, 0.25,    1.1, 0.8, -1, -1, 30)
RELAXED    = P(0.8, 0.8, 1.0, 1.0, 0, 0, 0, 0,            0.9, 0.5, 0, 0, 0)
SAD        = P(0.5, 0.5, 1.0, 1.0, 5, 5, 0, 0,            0.7, 30, 5, 5, 0)
SLEEPY     = P(0.0, 0.0, 0.8, 0.8, 0, 0, 0, 0,            1.0, 0.1, 0, 0, 0)
DEEP_SLEEP = P(0.0, 0.0, 0.8, 0.8, 0, 0, 0, 0,           1.0, 0.0, 0, 0, 0)
BORED      = P(0.4, 0.6, 1.0, 0.8, 3, 0, 0, 0,            0.8, 30, 3, -1, 0)
IDLE_P     = P(1.0, 1.0, 1.0, 1.0, 0, 0, 0, 0,            1.0, 0.7, 0, 0, 0)
CURIOUS    = P(1.2, 0.8, 1.1, 0.9, -5, 2, 0, 0,           1.3, 0.8, -3, 2, 0)
THINK      = P(0.8, 0.5, 0.9, 0.7, -2, 3, 0, 0,           0.8, 0.4, 2, 6, 0)
CONFUSED   = P(1.0, 0.6, 1.0, 0.8, 0, 3, 0, 0,            0.9, 0.5, -2, 5, 0)
BLINK      = P(0.0, 0.0, 1.0, 1.0, 0, 0, 0, 0,            1.0, 0, 0, 0, 0)
WINK       = P(1.0, 0.0, 1.1, 1.0, -2, 0, 0, 0,           1.1, 0.8, -2, 0, 0.2)
LOOK_L     = P(1.0, 1.0, 1.15, 0.85, -2, -2, 0, 0,        1.0, 0.7, 0, 0, 0)
LOOK_R     = P(1.0, 1.0, 0.85, 1.15, -2, -2, 0, 0,        1.0, 0.7, 0, 0, 0)
LOOK_U     = P(1.1, 1.1, 0.9, 0.9, -10, -10, 0, 0,        1.0, 0.7, -2, -2, 0)
HEART_EYES = P(1.2, 1.2, 1.1, 1.1, -5, -5, 0.4, 0.4,     1.0, 0.9, -3, -3, 0.8)
STAR_EYES  = P(1.3, 1.3, 1.0, 1.0, -5, -5, 0, 0,          1.0, 1.0, -4, -4, 30)

# ═══════════════════════════════════════════════════════
# 表情动画定义
# ═══════════════════════════════════════════════════════
EXPRESSIONS = {
    "happy":     {"intro_target": HAPPY, "intro_speed": 0.15, "loop_target": HAPPY, "loop_duration": 3.0, "tail_target": IDLE_P, "tail_speed": 0.10},
    "laugh":     {"intro_target": LAUGH, "intro_speed": 0.12, "loop_target": LAUGH, "loop_duration": 2.5, "tail_target": IDLE_P, "tail_speed": 0.08},
    "excited":   {"intro_target": EXCITED, "intro_speed": 0.18, "loop_target": EXCITED, "loop_duration": 2.0, "loop_dynamic": True, "tail_target": IDLE_P, "tail_speed": 0.10},
    "angry":     {"intro_target": ANGRY, "intro_speed": 0.20, "loop_target": ANGRY, "loop_duration": 2.0, "tail_target": IDLE_P, "tail_speed": 0.08},
    "surprised": {"intro_target": SURPRISE, "intro_speed": 0.20, "loop_target": SURPRISE, "loop_duration": 1.5, "tail_target": IDLE_P, "tail_speed": 0.08},
    "scared":    {"intro_target": SCARED, "intro_speed": 0.20, "loop_target": SCARED, "loop_duration": 1.5, "tail_target": IDLE_P, "tail_speed": 0.08},
    "smile":     {"intro_target": SMILE, "intro_speed": 0.10, "loop_target": SMILE, "loop_duration": 5.0, "tail_target": IDLE_P, "tail_speed": 0.08},
    "relaxed":   {"intro_target": RELAXED, "intro_speed": 0.06, "loop_target": RELAXED, "loop_duration": 5.0, "tail_target": IDLE_P, "tail_speed": 0.06},
    "sad":       {"intro_target": SAD, "intro_speed": 0.08, "loop_target": SAD, "loop_duration": 4.0, "tail_target": IDLE_P, "tail_speed": 0.06},
    "sleepy":    {"intro_target": SLEEPY, "intro_speed": 30, "loop_target": SLEEPY, "loop_duration": 999999.0},
    "bored":     {"intro_target": BORED, "intro_speed": 0.08, "loop_target": BORED, "loop_duration": 4.0, "tail_target": IDLE_P, "tail_speed": 0.06},
    "idle":      {"loop_target": IDLE_P, "loop_dynamic": True},
    "curious":   {"intro_target": CURIOUS, "intro_speed": 0.12, "loop_target": CURIOUS, "loop_duration": 3.0, "tail_target": IDLE_P, "tail_speed": 0.08},
    "thinking":  {"intro_target": THINK, "intro_speed": 0.12, "loop_target": THINK, "loop_duration": 4.0, "loop_dynamic": True, "tail_target": IDLE_P, "tail_speed": 0.08},
    "confused":  {"intro_target": CONFUSED, "intro_speed": 0.12, "loop_target": CONFUSED, "loop_duration": 3.0, "tail_target": IDLE_P, "tail_speed": 0.08},
    "speaking":  {"intro_target": Params(0.95, 0.95, 1.0, 1.0, 0, 0, 0, 0, 1.0, 0.6, 0, 0, 0), "intro_speed": 0.15,
                  "loop_target": Params(0.9, 0.9, 1.0, 1.0, 0, 0, 0, 0, 1.0, 0.5, 0, 0, 0), "loop_duration": 4.0, "loop_dynamic": True,
                  "tail_target": IDLE_P, "tail_speed": 0.10},
    "look_left":  {"intro_target": LOOK_L, "intro_speed": 0.15, "loop_target": LOOK_L, "loop_duration": 1.5, "tail_target": IDLE_P, "tail_speed": 0.10},
    "look_right": {"intro_target": LOOK_R, "intro_speed": 0.15, "loop_target": LOOK_R, "loop_duration": 1.5, "tail_target": IDLE_P, "tail_speed": 0.10},
    "look_up":    {"intro_target": LOOK_U, "intro_speed": 0.12, "loop_target": LOOK_U, "loop_duration": 2.0, "tail_target": IDLE_P, "tail_speed": 0.10},
    "wink":       {"intro_target": WINK, "intro_speed": 0.20, "loop_target": WINK, "loop_duration": 0.3, "tail_target": IDLE_P, "tail_speed": 0.15},
    "blink":      {"intro_target": BLINK, "intro_speed": 0.30, "loop_target": BLINK, "loop_duration": 0.15, "tail_target": IDLE_P, "tail_speed": 0.25},
    "heart_eyes": {"intro_target": HEART_EYES, "intro_speed": 0.12, "loop_target": HEART_EYES, "loop_duration": 3.0, "tail_target": IDLE_P, "tail_speed": 0.08},
    "star_eyes":  {"intro_target": STAR_EYES, "intro_speed": 0.15, "loop_target": STAR_EYES, "loop_duration": 2.0, "tail_target": IDLE_P, "tail_speed": 0.10},
}


# ═══════════════════════════════════════════════════════
# StateMachine — 表情状态机（简化版，无硬件依赖）
# ═══════════════════════════════════════════════════════
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
        self.gaze_timer = 0
        self.next_gaze = random.uniform(8, 20)
        self.pause_active = False
        self.pause_timer = 0
        self.pause_duration = 0
        self.next_pause = random.uniform(20, 60)
        self.pause_cooldown = 0
        self.blink_phase = 0
        self.blink_frame_time = 0
        self.interact_cooldown = 0
        self._on_expr_change = None
        self._breath_params_cb = None
        self._param_trans = False
        self._param_trans_time = 0.0
        self._param_trans_dur = 0.3
        self._param_trans_from = None
        self._param_easing = "ease_out_quad"
        self._prev_expr = "idle"

    def trigger(self, expr_name):
        if expr_name not in EXPRESSIONS:
            return
        if expr_name == "idle":
            self._goto_expr("idle")
            return
        if self.active_expr in ("blink", "wink"):
            self._goto_expr(expr_name)
            return
        if self.active_expr == expr_name and self.phase == "loop":
            self.phase_time = 0
            return
        if self.phase in ("loop", "intro"):
            self._goto_expr(expr_name)
        elif self.phase == "tail":
            self.next_expr = expr_name

    def _goto_expr(self, expr_name):
        self._prev_expr = self.active_expr
        self._param_trans = True
        self._param_trans_time = 0.0
        self._param_trans_from = self.current.copy()
        rule = AnimationDirector.TRANSITION_RULES
        key = (self._prev_expr, expr_name)
        r = rule.get(key) or rule.get(("any", expr_name)) or rule.get((self._prev_expr, "any"))
        if r:
            self._param_trans_dur = r["duration"]
            self._param_easing = r["easing"]
        else:
            self._param_trans_dur = 0.35
            self._param_easing = "ease_out_quad"

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
        if self._on_expr_change:
            self._on_expr_change(expr_name)

    def update(self, dt):
        self.idle_bounce += dt
        self.phase_time += dt
        if self.interact_cooldown > 0:
            self.interact_cooldown -= dt

        # 眨眼帧序列
        if self.blink_phase > 0:
            self.blink_frame_time += dt
            if self.blink_phase == 1:  # closing
                if self.blink_frame_time > 0.06:
                    self.blink_phase = 2; self.blink_frame_time = 0
                    self.current.l_open = 0.0; self.current.r_open = 0.0
            elif self.blink_phase == 2:  # closed
                if self.blink_frame_time > 0.08:
                    self.blink_phase = 3; self.blink_frame_time = 0
            elif self.blink_phase == 3:  # opening
                if self.blink_frame_time > 0.06:
                    self.blink_phase = 0; self.blink_frame_time = 0
                    self.blink_timer = 0
                    self.next_blink = random.uniform(2.5, 6.0)
                    if random.random() < 0.10:
                        self.next_blink = random.uniform(0.3, 1.0)
        elif self.is_blinking:
            if self.phase_time > 0.15:
                self.is_blinking = False
                if self.phase in ("intro", "loop"):
                    self.phase = "loop"; self.phase_time = 0
                self.blink_timer = 0
                self.next_blink = random.uniform(2.5, 5)
        elif (self.active_expr not in ("sleepy", "blink") and
              self.blink_timer > self.next_blink and self.interact_cooldown <= 0):
            self.blink_phase = 1; self.blink_frame_time = 0
            self.is_blinking = True; self.phase_time = 0; self.blink_timer = 0

        # 随机视线
        if self.interact_cooldown <= 0:
            self.gaze_timer += dt
        if (self.gaze_timer > self.next_gaze and
            self.active_expr in ("idle", "curious", "bored", "relaxed", "smile") and
            self.blink_phase == 0):
            self.gaze_timer = 0; self.next_gaze = random.uniform(8, 20)
            self.trigger(random.choice(["look_left", "look_right", "look_up"]))

        # 随机停顿
        if self.pause_active:
            self.pause_timer += dt
            if self.pause_timer > self.pause_duration:
                self.pause_active = False; self.pause_timer = 0
                self.current.l_open = 1.0; self.current.r_open = 1.0
                self.pause_cooldown = 0
        else:
            self.pause_cooldown += dt
            if (self.pause_cooldown > self.next_pause and self.active_expr == "idle" and
                self.blink_phase == 0 and self.interact_cooldown <= 0):
                self.pause_active = True; self.pause_timer = 0
                self.pause_duration = random.uniform(0.5, 1.5)
                self.next_pause = random.uniform(20, 60); self.pause_cooldown = 0

        if self.active_expr not in ("blink", "wink", "sleepy"):
            self.wink_timer += dt
            if self.wink_timer > self.next_wink:
                self._goto_expr("wink")
                self.wink_timer = 0; self.next_wink = random.uniform(15, 35)

        if self.phase == "intro": self._update_intro(dt)
        elif self.phase == "loop": self._update_loop(dt)
        elif self.phase == "tail": self._update_tail(dt)

        if self.is_blinking:
            target = BLINK
            spd = 0.30 if self.blink_phase == 1 else (0.30 if self.blink_phase == 3 else 0.25)
            self.current.lerp(target, spd)
            return

        if self.pause_active:
            self.current.l_open += (0.6 - self.current.l_open) * 0.1
            self.current.r_open += (0.6 - self.current.r_open) * 0.1

        target = self._get_current_target()
        if target is not None:
            if self._param_trans and self._param_trans_from is not None:
                self._param_trans_time += dt
                t = min(1.0, self._param_trans_time / max(0.01, self._param_trans_dur))
                easing_fn = getattr(Easing, self._param_easing, Easing.ease_out_quad)
                t_eased = easing_fn(t)
                snap = self._param_trans_from.copy()
                snap.ease_lerp(target, t_eased)
                self.current = snap
                if t >= 1.0:
                    self._param_trans = False
            else:
                defn = EXPRESSIONS[self.active_expr]
                spd = defn.get("intro_speed" if self.phase == "intro" else "tail_speed", 0.10) if self.phase != "loop" else 0.05
                self.current.lerp(target, spd)

    def _update_intro(self, dt):
        defn = EXPRESSIONS[self.active_expr]
        target = defn["intro_target"]
        spd = defn.get("intro_speed", 0.10)
        self.current.lerp(target, spd)
        if self.current.is_close(target):
            self.phase = "loop"; self.phase_time = 0

    def _update_loop(self, dt):
        defn = EXPRESSIONS[self.active_expr]
        if defn.get("loop_dynamic"):
            if self.active_expr == "sleepy":
                self.sleepy_breathe += dt
                base = 0.12 + 0.08 * math.sin(self.sleepy_breathe * 0.6)
                self.current.l_open = base; self.current.r_open = base * 0.9
            elif self.active_expr == "excited":
                j = 0.08 * math.sin(self.phase_time * 8)
                self.current.l_open = 1.3 + j; self.current.r_open = 1.3 - j
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
                self.phase = "tail"; self.phase_time = 0
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
        self.current.lerp(tail_target, spd)
        if self.current.is_close(tail_target):
            if self.active_expr == "sleepy":
                self.active_expr = "surprised"; self.phase = "intro"; self.phase_time = 0
            elif self.next_expr:
                self._goto_expr(self.next_expr)
            else:
                self._goto_expr("idle")
                self.phase = "loop"
                self.next_state_time = random.uniform(2, 4)

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
        if r < 0.18: self._goto_expr("look_left")
        elif r < 0.36: self._goto_expr("look_right")
        elif r < 0.48: self._goto_expr("look_up")
        elif r < 0.58: self._goto_expr("happy")
        elif r < 0.65: self._goto_expr("smile")
        elif r < 0.72: self._goto_expr("curious")
        elif r < 0.78: self._goto_expr("thinking")
        elif r < 0.83: self._goto_expr("confused")
        elif r < 0.87:
            self._goto_expr("speaking"); self.speak_t = 0
        elif r < 0.92:
            self._goto_expr("sleepy"); self.sleepy_breathe = 0
        else: self._goto_expr("bored")

    def _get_current_target(self):
        defn = EXPRESSIONS[self.active_expr]
        if self.phase == "intro": return defn["intro_target"]
        elif self.phase == "loop": return defn["loop_target"]
        elif self.phase == "tail": return defn.get("tail_target", IDLE_P)
        return IDLE_P


# ═══════════════════════════════════════════════════════
# Easing 函数
# ═══════════════════════════════════════════════════════
class Easing:
    @staticmethod
    def linear(t): return t
    @staticmethod
    def ease_in_quad(t): return t * t
    @staticmethod
    def ease_out_quad(t): return t * (2 - t)
    @staticmethod
    def ease_in_out_quad(t): return 2 * t * t if t < 0.5 else -1 + (4 - 2 * t) * t
    @staticmethod
    def ease_out_back(t):
        c = 1.70158
        return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2
    @staticmethod
    def ease_in_out_sine(t): return -(math.cos(math.pi * t) - 1) / 2
    @staticmethod
    def ease_out_elastic(t):
        if t == 0 or t == 1: return t
        return 2 ** (-10 * t) * math.sin((t - 0.075) * (2 * math.pi) / 0.3) + 1
    @staticmethod
    def spring(t, damping=0.4):
        return 1 - math.exp(-6 * t) * math.cos(damping * 2 * math.pi * t)


# ═══════════════════════════════════════════════════════
# SquashStretch — 弹性形变系统
# ═══════════════════════════════════════════════════════
class SquashStretch:
    def __init__(self):
        self.scale_x = 1.0; self.scale_y = 1.0
        self.offset_y = 0.0; self.offset_x = 0.0
        self._animating = False; self._anim_time = 0.0
        self._anim_duration = 0.45
        self._keyframes = []
        self._easing = Easing.ease_out_quad
        self._damping_active = False; self._damp_time = 0.0
        self._damp_sx = 1.0; self._damp_sy = 1.0
        self._damp_ox = 0.0; self._damp_oy = 0.0

    @property
    def active(self):
        return self._animating or self._damping_active

    def trigger_squash(self, intensity=1.0, style="tap"):
        I = intensity
        if style == "tap":
            self._keyframes = [
                (0.00, 1.0, 1.0, 0, 0), (0.08, 1.15*I, 0.85*I, 0, 2),
                (0.22, 0.95, 1.10, 0, -3), (0.38, 1.02, 0.98, 0, 0.5), (0.45, 1.0, 1.0, 0, 0)]
            self._anim_duration = 0.45; self._easing = Easing.ease_out_quad
        elif style == "bounce":
            self._keyframes = [
                (0.00, 1.0, 1.0, 0, 0), (0.10, 0.92, 1.12, 0, -12*I),
                (0.25, 1.08, 0.92, 0, -20*I), (0.50, 1.0, 1.0, 0, 0),
                (0.65, 1.18*I, 0.82*I, 0, 4), (0.80, 0.96, 1.08, 0, -2), (1.00, 1.0, 1.0, 0, 0)]
            self._anim_duration = 0.6; self._easing = Easing.ease_out_quad
        elif style == "shake":
            self._keyframes = [
                (0.00, 1.0, 1.0, 0, 0), (0.10, 1.0, 1.0, -6*I, 0),
                (0.25, 1.0, 1.0, 5*I, 0), (0.40, 1.0, 1.0, -4*I, 0),
                (0.55, 1.0, 1.0, 3*I, 0), (0.70, 1.0, 1.0, -1.5, 0), (1.00, 1.0, 1.0, 0, 0)]
            self._anim_duration = 0.4; self._easing = Easing.ease_out_quad
        elif style == "surprise":
            self._keyframes = [
                (0.00, 1.0, 1.0, 0, 0), (0.05, 0.90, 1.10, 0, 3),
                (0.15, 1.05, 0.95, 0, -18*I), (0.35, 1.0, 1.0, 0, -12*I),
                (0.55, 1.12, 0.88, 0, 2), (0.75, 0.98, 1.03, 0, -1), (1.00, 1.0, 1.0, 0, 0)]
            self._anim_duration = 0.5; self._easing = Easing.ease_out_back
        else: return
        self._animating = True; self._anim_time = 0.0

    def update(self, dt):
        if self._animating:
            self._anim_time += dt
            t_norm = min(1.0, self._anim_time / self._anim_duration)
            t_eased = self._easing(t_norm)
            sx, sy, ox, oy = self._interpolate_keyframes(t_eased)
            self.scale_x = sx; self.scale_y = sy
            self.offset_x = ox; self.offset_y = oy
            if t_norm >= 1.0:
                self._animating = False
                self.scale_x = 1.0; self.scale_y = 1.0
                self.offset_x = 0.0; self.offset_y = 0.0
        if self._damping_active:
            self._damp_time += dt
            decay = math.exp(-8 * self._damp_time)
            self.scale_x = 1.0 + self._damp_sx * decay * math.cos(self._damp_time * 12)
            self.scale_y = 1.0 + self._damp_sy * decay * math.cos(self._damp_time * 12 + math.pi)
            self.offset_y = self._damp_oy * decay * math.cos(self._damp_time * 10)
            if decay < 0.01:
                self._damping_active = False
                self.scale_x = 1.0; self.scale_y = 1.0; self.offset_y = 0.0

    def _interpolate_keyframes(self, t):
        kf = self._keyframes
        if not kf: return 1.0, 1.0, 0.0, 0.0
        for i in range(len(kf) - 1):
            t0, sx0, sy0, ox0, oy0 = kf[i]
            t1, sx1, sy1, ox1, oy1 = kf[i + 1]
            if t0 <= t <= t1:
                span = t1 - t0
                if span < 0.001: return sx1, sy1, ox1, oy1
                local_t = (t - t0) / span
                return (sx0 + (sx1 - sx0) * local_t, sy0 + (sy1 - sy0) * local_t,
                        ox0 + (ox1 - ox0) * local_t, oy0 + (oy1 - oy0) * local_t)
        last = kf[-1]
        return last[1], last[2], last[3], last[4]

    def start_damping(self, sx=0.04, sy=0.04, oy=3.0):
        self._damping_active = True; self._damp_time = 0.0
        self._damp_sx = sx; self._damp_sy = sy; self._damp_oy = oy


# ═══════════════════════════════════════════════════════
# AnimationDirector
# ═══════════════════════════════════════════════════════
class AnimationDirector:
    TRANSITION_RULES = {
        ("idle", "happy"):      {"duration": 0.30, "easing": "ease_out_back"},
        ("idle", "excited"):    {"duration": 0.25, "easing": "ease_out_back"},
        ("any", "surprised"):   {"duration": 0.10, "easing": "linear"},
        ("surprised", "any"):   {"duration": 0.60, "easing": "ease_in_out_sine"},
        ("any", "angry"):       {"duration": 0.15, "easing": "ease_in_quad"},
        ("happy", "sad"):       {"duration": 0.80, "easing": "ease_in_out_sine"},
        ("excited", "sad"):     {"duration": 0.80, "easing": "ease_in_out_sine"},
        ("any", "sleepy"):      {"duration": 1.00, "easing": "ease_in_out_sine"},
        ("sleepy", "surprised"): {"duration": 0.08, "easing": "linear"},
    }

    EMOTION_BODY = {
        "idle": {"y": 0, "breath_period": 3.5, "breath_amp": 0.02, "shake_x": 0, "shake_y": 0},
        "happy": {"y": -3, "breath_period": 2.5, "breath_amp": 0.04, "shake_x": 0, "shake_y": 0},
        "laugh": {"y": -4, "breath_period": 2.2, "breath_amp": 0.06, "shake_x": 0, "shake_y": 1.5},
        "excited": {"y": -5, "breath_period": 2.0, "breath_amp": 0.06, "shake_x": 1.0, "shake_y": 0},
        "angry": {"y": 2, "breath_period": 2.8, "breath_amp": 0.05, "shake_x": 1.5, "shake_y": 0},
        "surprised": {"y": -15, "breath_period": 3.0, "breath_amp": 0.03, "shake_x": 0, "shake_y": 0},
        "scared": {"y": -5, "breath_period": 2.0, "breath_amp": 0.04, "shake_x": 2.0, "shake_y": 0.5},
        "sad": {"y": 2, "breath_period": 4.5, "breath_amp": 0.01, "shake_x": 0, "shake_y": 0},
        "sleepy": {"y": 3, "breath_period": 5.0, "breath_amp": 0.01, "shake_x": 0, "shake_y": 0},
        "bored": {"y": 1, "breath_period": 4.0, "breath_amp": 0.015, "shake_x": 0, "shake_y": 0},
        "curious": {"y": -2, "breath_period": 3.0, "breath_amp": 0.03, "shake_x": 0, "shake_y": 0},
        "thinking": {"y": 0, "breath_period": 3.5, "breath_amp": 0.02, "shake_x": 0, "shake_y": 0},
        "confused": {"y": 0, "breath_period": 3.2, "breath_amp": 0.03, "shake_x": 0.5, "shake_y": 0},
        "smile": {"y": -1, "breath_period": 3.2, "breath_amp": 0.03, "shake_x": 0, "shake_y": 0},
        "relaxed": {"y": 1, "breath_period": 4.0, "breath_amp": 0.015, "shake_x": 0, "shake_y": 0},
        "speaking": {"y": 0, "breath_period": 3.0, "breath_amp": 0.03, "shake_x": 0, "shake_y": 0},
        "look_left": {"y": 0, "breath_period": 3.5, "breath_amp": 0.02, "shake_x": 0, "shake_y": 0},
        "look_right": {"y": 0, "breath_period": 3.5, "breath_amp": 0.02, "shake_x": 0, "shake_y": 0},
        "look_up": {"y": -1, "breath_period": 3.5, "breath_amp": 0.02, "shake_x": 0, "shake_y": 0},
        "blink": {"y": 0, "breath_period": 3.5, "breath_amp": 0.02, "shake_x": 0, "shake_y": 0},
        "wink": {"y": 0, "breath_period": 3.5, "breath_amp": 0.02, "shake_x": 0, "shake_y": 0},
    }

    _DEFAULT_BODY = {"y": 0, "breath_period": 3.5, "breath_amp": 0.02, "shake_x": 0, "shake_y": 0}

    EMOTION_SQUASH = {
        "surprised": ("surprise", 1.0), "excited": ("bounce", 0.6),
        "happy": ("tap", 0.4), "laugh": ("tap", 0.5),
        "angry": ("shake", 0.7), "scared": ("shake", 0.5),
    }

    def __init__(self, squash_stretch):
        self.squash = squash_stretch
        self.current_expr = "idle"; self.prev_expr = "idle"
        self._renderer = None
        self.body_y = 0.0; self.body_shake_x = 0.0; self.body_shake_y = 0.0
        self.breath_period = 3.5; self.breath_amp = 0.02
        self._transitioning = False; self._trans_time = 0.0
        self._trans_duration = 0.3
        self._trans_from_body = None; self._trans_to_body = None

    def on_expression_change(self, expr_name):
        self.prev_expr = self.current_expr
        self.current_expr = expr_name
        if hasattr(self, '_renderer') and self._renderer:
            self._renderer.set_neon_color(expr_name)
        from_body = self.EMOTION_BODY.get(self.prev_expr, self._DEFAULT_BODY)
        to_body = self.EMOTION_BODY.get(expr_name, self._DEFAULT_BODY)
        rule = self._get_transition_rule(self.prev_expr, expr_name)
        self._transitioning = True; self._trans_time = 0.0
        self._trans_duration = rule["duration"]
        self._trans_from_body = from_body; self._trans_to_body = to_body
        squash_info = self.EMOTION_SQUASH.get(expr_name)
        if squash_info and not self.squash.active:
            style, intensity = squash_info
            self.squash.trigger_squash(intensity, style)

    def _get_transition_rule(self, from_expr, to_expr):
        rule = self.TRANSITION_RULES.get((from_expr, to_expr))
        if rule: return rule
        rule = self.TRANSITION_RULES.get(("any", to_expr))
        if rule: return rule
        rule = self.TRANSITION_RULES.get((from_expr, "any"))
        if rule: return rule
        return {"duration": 0.35, "easing": "ease_out_quad"}

    def update(self, dt):
        if self._transitioning:
            self._trans_time += dt
            t = min(1.0, self._trans_time / max(0.01, self._trans_duration))
            easing_name = self._get_transition_rule(self.prev_expr, self.current_expr).get("easing", "ease_out_quad")
            easing_fn = getattr(Easing, easing_name, Easing.ease_out_quad)
            t_eased = easing_fn(t)
            fb = self._trans_from_body; tb = self._trans_to_body
            self.body_y = fb["y"] + (tb["y"] - fb["y"]) * t_eased
            self.breath_period = fb["breath_period"] + (tb["breath_period"] - fb["breath_period"]) * t_eased
            self.breath_amp = fb["breath_amp"] + (tb["breath_amp"] - fb["breath_amp"]) * t_eased
            self.body_shake_x = fb["shake_x"] + (tb["shake_x"] - fb["shake_x"]) * t_eased
            self.body_shake_y = fb["shake_y"] + (tb["shake_y"] - fb["shake_y"]) * t_eased
            if t >= 1.0: self._transitioning = False
        else:
            if self.body_shake_x > 0:
                self.body_y += random.gauss(0, self.body_shake_x * 0.3) * dt * 10

    def get_body_offset(self, idle_bounce_t):
        ox = 0.0; oy = self.body_y
        if self.body_shake_x > 0.1: ox += random.gauss(0, self.body_shake_x)
        breath_y = math.sin(idle_bounce_t * 2 * math.pi / max(0.5, self.breath_period)) * self.breath_amp * 8
        oy += breath_y
        oy += self.squash.offset_y; ox += self.squash.offset_x
        return ox, oy

    def get_breath_params(self):
        return self.breath_period, self.breath_amp


# ═══════════════════════════════════════════════════════
# PerfMonitor — FPS自适应
# ═══════════════════════════════════════════════════════
class PerfMonitor:
    LEVEL_FULL = 0; LEVEL_HALF_DOTS = 1; LEVEL_NO_DOTS = 2
    LEVEL_NO_VFX = 3; LEVEL_MINIMAL = 4

    def __init__(self):
        self.level = self.LEVEL_FULL
        self.fps_history = []; self.check_interval = 3.0
        self.timer = 0.0; self.current_fps = 60.0

    def update(self, dt, actual_fps):
        self.current_fps = actual_fps
        self.timer += dt
        if self.timer < self.check_interval: return
        self.timer = 0.0
        self.fps_history.append(actual_fps)
        if len(self.fps_history) > 5: self.fps_history.pop(0)
        avg_fps = sum(self.fps_history) / len(self.fps_history)
        if avg_fps < 25: new_level = self.LEVEL_MINIMAL
        elif avg_fps < 30: new_level = self.LEVEL_NO_VFX
        elif avg_fps < 35: new_level = self.LEVEL_NO_DOTS
        elif avg_fps < 45: new_level = self.LEVEL_HALF_DOTS
        else: new_level = self.LEVEL_FULL
        if new_level != self.level:
            self.level = new_level
            print(f"[PERF] 降级: L{self.level} (avg FPS={avg_fps:.1f})")

    @property
    def enable_dots(self): return self.level <= self.LEVEL_HALF_DOTS
    @property
    def dots_half(self): return self.level == self.LEVEL_HALF_DOTS
    @property
    def enable_vfx(self): return self.level <= self.LEVEL_NO_DOTS
    @property
    def enable_glow(self): return self.level <= self.LEVEL_HALF_DOTS
    @property
    def level_name(self): return ["FULL", "HALF_DOTS", "NO_DOTS", "NO_VFX", "MINIMAL"][self.level]


# ═══════════════════════════════════════════════════════
# AmbientManager — 环境氛围层
# ═══════════════════════════════════════════════════════
class AmbientManager:
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
        self.face_cx = face_cx; self.face_cy = face_cy
        self.width = WIDTH; self.height = HEIGHT
        self._bg_current = [8.0, 8.0, 18.0]; self._bg_target = [8.0, 8.0, 18.0]; self._bg_speed = 1.5
        self._glow_current = [30.0, 40.0, 80.0]; self._glow_target = [30.0, 40.0, 80.0]
        self._glow_speed = 1.5; self._glow_alpha = 0.0; self._glow_target_alpha = 0.25
        self._glow_alpha_speed = 2.0; self._breath_phase = 0.0
        self._dots = []; self._dot_colors = [(60, 80, 140)]
        self._dot_target_colors = [(60, 80, 140)]
        self._dot_spawn_timer = 0.0; self._dot_spawn_interval = 0.5
        self._max_dots = 12; self._dot_behavior = "float"
        self._mood = "idle"
        self._glow_surf = None; self._glow_size = 0

    def set_mood(self, mood_name, transition=1.5):
        preset = self.MOOD_PRESETS.get(mood_name, self.MOOD_PRESETS["idle"])
        if mood_name == self._mood: return
        self._mood = mood_name
        self._bg_target = list(preset["bg"]); self._bg_speed = 1.0 / max(0.1, transition)
        self._glow_target = list(preset["glow"]); self._glow_speed = 1.0 / max(0.1, transition)
        self._dot_target_colors = preset["dots"]
        behavior_map = {"idle": "float", "happy": "float", "sad": "fall", "angry": "float",
                        "surprised": "orbit", "excited": "float", "curious": "orbit",
                        "sleepy": "fall", "love": "float", "focus": "orbit"}
        self._dot_behavior = behavior_map.get(mood_name, "float")
        self._glow_target_alpha = 0.25 if mood_name != "idle" else 0.15

    def update(self, dt):
        for i in range(3):
            self._bg_current[i] += (self._bg_target[i] - self._bg_current[i]) * min(1.0, self._bg_speed * dt)
            self._glow_current[i] += (self._glow_target[i] - self._glow_current[i]) * min(1.0, self._glow_speed * dt)
        self._glow_alpha += (self._glow_target_alpha - self._glow_alpha) * min(1.0, self._glow_alpha_speed * dt)
        self._breath_phase += dt * 1.2
        for i, tc in enumerate(self._dot_target_colors):
            if i >= len(self._dot_colors): self._dot_colors.append(tc)
            else:
                cc = self._dot_colors[i]
                self._dot_colors[i] = (int(cc[0] + (tc[0] - cc[0]) * min(1.0, dt * 2)),
                                       int(cc[1] + (tc[1] - cc[1]) * min(1.0, dt * 2)),
                                       int(cc[2] + (tc[2] - cc[2]) * min(1.0, dt * 2)))
        self._dot_spawn_timer += dt
        if self._dot_spawn_timer >= self._dot_spawn_interval and len(self._dots) < self._max_dots:
            self._dot_spawn_timer = 0; self._spawn_dot()
        alive = []
        for d in self._dots:
            d["life"] -= dt
            if d["life"] <= 0: continue
            if d["behavior"] == "float":
                d["x"] += d["vx"] * dt; d["y"] += d["vy"] * dt
                d["x"] += math.sin(d["life"] * 1.5) * 0.3
            elif d["behavior"] == "orbit":
                d["angle"] += d["angular_v"] * dt
                d["x"] = self.face_cx + d["orbit_r"] * math.cos(d["angle"])
                d["y"] = self.face_cy + d["orbit_r"] * math.sin(d["angle"]) * 0.6
            elif d["behavior"] == "fall":
                d["x"] += d["vx"] * dt; d["vy"] += 15 * dt; d["y"] += d["vy"] * dt
            ml = d["max_life"]
            if d["life"] > ml - 0.5: d["alpha"] = min(1.0, (ml - d["life"]) / 0.5) * d["peak_alpha"]
            elif d["life"] < 1.0: d["alpha"] = (d["life"] / 1.0) * d["peak_alpha"]
            else: d["alpha"] = d["peak_alpha"]
            if d["alpha"] > 0.01: alive.append(d)
        self._dots = alive

    def _spawn_dot(self):
        color = random.choice(self._dot_colors)
        behavior = self._dot_behavior
        max_life = random.uniform(3.0, 6.0)
        if behavior == "float":
            side = random.choice(["bottom", "left", "right"])
            x = random.uniform(self.width * 0.1, self.width * 0.9) if side == "bottom" else (-10 if side == "left" else self.width + 10)
            y = self.height + 10 if side == "bottom" else random.uniform(self.height * 0.3, self.height * 0.9)
            self._dots.append({"x": x, "y": y, "vx": random.uniform(-5, 5), "vy": random.uniform(-20, -8),
                "r": random.uniform(3, 8), "color": color, "life": max_life, "max_life": max_life,
                "alpha": 0.0, "peak_alpha": random.uniform(0.3, 0.6), "behavior": "float"})
        elif behavior == "orbit":
            angle = random.uniform(0, math.pi * 2); orbit_r = random.uniform(250, 400)
            self._dots.append({"x": self.face_cx + orbit_r * math.cos(angle),
                "y": self.face_cy + orbit_r * math.sin(angle) * 0.6,
                "vx": 0, "vy": 0, "r": random.uniform(2, 5), "color": color,
                "life": max_life, "max_life": max_life, "alpha": 0.0,
                "peak_alpha": random.uniform(0.2, 0.4), "behavior": "orbit",
                "angle": angle, "orbit_r": orbit_r,
                "angular_v": random.uniform(0.3, 0.8) * random.choice([-1, 1])})
        elif behavior == "fall":
            self._dots.append({"x": random.uniform(self.width * 0.15, self.width * 0.85), "y": -10,
                "vx": random.uniform(-8, 8), "vy": random.uniform(5, 15),
                "r": random.uniform(2, 6), "color": color, "life": max_life, "max_life": max_life,
                "alpha": 0.0, "peak_alpha": random.uniform(0.2, 0.5), "behavior": "fall"})

    def get_bg_color(self):
        return (int(self._bg_current[0]), int(self._bg_current[1]), int(self._bg_current[2]))

    def draw_bg(self, screen):
        screen.fill(self.get_bg_color())

    def draw_dots(self, screen, half=False):
        for i, d in enumerate(self._dots):
            if half and i % 2 == 1: continue
            if d["alpha"] < 0.01: continue
            r = max(1, int(d["r"]))
            size = r * 2 + 4
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            alpha = int(min(255, d["alpha"] * 255))
            pygame.draw.circle(surf, (*d["color"], alpha), (size // 2, size // 2), r)
            if r >= 3:
                glow_alpha = int(min(255, d["alpha"] * 80))
                pygame.draw.circle(surf, (*d["color"], glow_alpha), (size // 2, size // 2), int(r * 2.0))
            screen.blit(surf, (int(d["x"]) - size // 2, int(d["y"]) - size // 2))

    def draw_glow(self, screen, face_cx=None, face_cy=None):
        if self._glow_alpha < 0.01: return
        cx = face_cx or self.face_cx; cy = face_cy or self.face_cy
        breath_scale = 1.0 + 0.1 * math.sin(self._breath_phase * math.pi * 2)
        base_r = int(280 * breath_scale)
        glow_size = base_r * 2 + 20
        gc = self._glow_current
        glow_rgb = (int(gc[0]), int(gc[1]), int(gc[2]))
        glow_surf = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
        center = glow_size // 2
        layers = 5
        for i in range(layers):
            t = i / (layers - 1)
            frac = 1.0 - t * 0.8
            layer_r = max(2, int(base_r * frac))
            layer_alpha = int(self._glow_alpha * (0.08 + t * 0.35) * 255)
            layer_alpha = min(255, max(0, layer_alpha))
            pygame.draw.circle(glow_surf, (*glow_rgb, layer_alpha), (center, center), layer_r)
        screen.blit(glow_surf, (cx - center, cy - center))


# ═══════════════════════════════════════════════════════
# Renderer — 霓虹赛博渲染引擎
# ═══════════════════════════════════════════════════════
class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.face_center_x = WIDTH // 2
        self.face_center_y = HEIGHT // 2 - 50
        self.eye_r_x = 160; self.eye_r_y = 170; self.spacing = 580
        self.pupil_mode = "normal"; self._pupil_mode_timer = 0.0
        self._current_bg = StyleConfig.BG_COLOR_RGB
        self._neon_current = list(StyleConfig.NEON_DEFAULT)
        self._neon_target = list(StyleConfig.NEON_DEFAULT)
        self._neon_speed = 4.0; self._current_expr = "idle"
        self._bloom_phase = 0.0
        self._scanline_offset = 0.0
        self._glitch_timer = random.uniform(StyleConfig.GLITCH_INTERVAL_MIN, StyleConfig.GLITCH_INTERVAL_MAX)
        self._glitch_active = False; self._glitch_time = 0.0; self._glitch_lines = []
        self._scanline_surf = None
        self._build_scanline_surface()
        # 字体 (macOS 系统中文字体)
        pygame.freetype.init()
        for font_path in [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
        ]:
            if __import__('os').path.exists(font_path):
                try:
                    self.font_cn = pygame.freetype.Font(font_path, 22)
                    self.font_cn_body = pygame.freetype.Font(font_path, 16)
                    self.font_cn_small = pygame.freetype.Font(font_path, 13)
                    print(f"[Font] 使用系统字体: {font_path}")
                    break
                except: continue
        else:
            self.font_cn = pygame.freetype.Font(None, 22)
            self.font_cn_body = pygame.freetype.Font(None, 16)
            self.font_cn_small = pygame.freetype.Font(None, 13)

    def _build_scanline_surface(self):
        self._scanline_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self._scanline_surf.fill((0, 0, 0, 0))
        gap = StyleConfig.SCANLINE_GAP
        for y in range(0, HEIGHT, gap):
            pygame.draw.line(self._scanline_surf, StyleConfig.SCANLINE_COLOR, (0, y), (WIDTH, y), 1)

    def set_neon_color(self, expr_name):
        self._current_expr = expr_name
        self._neon_target = list(StyleConfig.get_neon_color(expr_name))

    def get_neon_color(self):
        return (int(self._neon_current[0]), int(self._neon_current[1]), int(self._neon_current[2]))

    def set_pupil_mode(self, mode, duration=3.0):
        self.pupil_mode = mode; self._pupil_mode_timer = duration

    def update(self, dt):
        if self._pupil_mode_timer > 0:
            self._pupil_mode_timer -= dt
            if self._pupil_mode_timer <= 0:
                self.pupil_mode = "normal"; self._pupil_mode_timer = 0
        for i in range(3):
            self._neon_current[i] += (self._neon_target[i] - self._neon_current[i]) * min(1.0, self._neon_speed * dt)
        self._bloom_phase += dt * 1.2
        self._scanline_offset += StyleConfig.SCANLINE_SPEED * dt
        if self._scanline_offset >= HEIGHT: self._scanline_offset -= HEIGHT
        if not self._glitch_active:
            self._glitch_timer -= dt
            if self._glitch_timer <= 0:
                self._glitch_active = True; self._glitch_time = 0; self._glitch_lines = []
                for _ in range(random.randint(3, 8)):
                    self._glitch_lines.append((random.randint(0, HEIGHT),
                        random.randint(-StyleConfig.GLITCH_INTENSITY, StyleConfig.GLITCH_INTENSITY),
                        random.randint(50, WIDTH // 2)))
                self._glitch_timer = random.uniform(StyleConfig.GLITCH_INTERVAL_MIN, StyleConfig.GLITCH_INTERVAL_MAX)
        else:
            self._glitch_time += dt
            if self._glitch_time >= StyleConfig.GLITCH_DURATION:
                self._glitch_active = False; self._glitch_time = 0; self._glitch_lines = []

    def draw(self, state, face_scale=1.0, face_offset_x=0,
             body_scale_x=1.0, body_scale_y=1.0, body_offset_x=0, body_offset_y=0,
             ambient_mgr=None, perf=None, spacing_scale=1.0):
        if ambient_mgr:
            ambient_mgr.draw_bg(self.screen)
            self._current_bg = ambient_mgr.get_bg_color()
        else:
            self.screen.fill(StyleConfig.BG_COLOR_RGB)
            self._current_bg = StyleConfig.BG_COLOR_RGB
        if ambient_mgr and (perf is None or perf.enable_glow):
            ambient_mgr.draw_glow(self.screen)
        self._draw_body(state, face_scale, face_offset_x, body_scale_x, body_scale_y, body_offset_x, body_offset_y, spacing_scale)
        if ambient_mgr and (perf is None or perf.enable_dots):
            ambient_mgr.draw_dots(self.screen, half=perf.dots_half if perf else False)
        if perf is None or perf.enable_vfx:
            self._draw_scanlines()
        if self._glitch_active and (perf is None or perf.enable_vfx):
            self._draw_glitch()

    def _draw_body(self, s, face_scale, offset_x, bsx, bsy, box, boy, spacing_scale=1.0):
        cx = self.face_center_x + offset_x + box
        cy = self.face_center_y + boy
        rx = int(self.eye_r_x * face_scale * bsx)
        ry = int(self.eye_r_y * face_scale * bsy)
        sp = int(self.spacing * face_scale * bsx * spacing_scale)
        neon = self.get_neon_color()
        if s.blush > 0.01:
            self._draw_blush(cx, cy, sp, rx, ry, s.blush, face_scale)
        for side in [-1, 1]:
            l_open = s.l_open if side < 0 else s.r_open
            l_w = s.l_w if side < 0 else s.r_w
            l_y = s.l_y if side < 0 else s.r_y
            ex = cx + side * sp // 2
            ey = cy + l_y * face_scale
            rw = int(rx * l_w)
            rh = int(ry * max(0.01, l_open))
            if rh < 3:
                lw = max(3, int(5 * face_scale))
                pts = [(ex - rw + int(rw * 2 * (i / 11.0)), ey + int(math.sin((i / 11.0) * math.pi) * 4)) for i in range(12)]
                pygame.draw.lines(self.screen, StyleConfig.dim_color(neon, 0.3), False, pts, lw + 5)
                pygame.draw.lines(self.screen, neon, False, pts, lw)
            else:
                self._draw_neon_eye(ex, ey, rw, rh, neon)
        # 嘴巴
        self._draw_mouth(cx, cy, sp, rx, ry, s, face_scale, neon)

    def _draw_neon_eye(self, ex, ey, rw, rh, neon):
        bloom_pulse = 0.7 + 0.3 * math.sin(self._bloom_phase)
        margin = 40
        max_spread = 1.0 + StyleConfig.BLOOM_LAYERS * 0.25 * StyleConfig.BLOOM_SPREAD
        surf_hw = int(rw * max_spread) + margin
        surf_hh = int(rh * max_spread) + margin
        bloom_surf = pygame.Surface((surf_hw * 2, surf_hh * 2), pygame.SRCALPHA)
        bloom_surf.fill((0, 0, 0, 0))
        bcx, bcy = surf_hw, surf_hh
        for i in range(StyleConfig.BLOOM_LAYERS, 0, -1):
            spread = 1.0 + i * 0.25 * StyleConfig.BLOOM_SPREAD
            brw = int(rw * spread); brh = int(rh * spread)
            alpha = int(StyleConfig.BLOOM_MAX_ALPHA * (i / StyleConfig.BLOOM_LAYERS) * bloom_pulse)
            alpha = max(0, min(255, alpha))
            pygame.draw.ellipse(bloom_surf, (*neon, alpha), (bcx - brw, bcy - brh, brw * 2, brh * 2))
        self.screen.blit(bloom_surf, (ex - surf_hw, ey - surf_hh))
        # 眼底渐变
        eye_surf = pygame.Surface((rw * 2 + 10, rh * 2 + 10), pygame.SRCALPHA)
        eye_surf.fill((0, 0, 0, 0))
        base_col = (25, 40, 70)
        blends = [(0.05, 120), (0.18, 190), (0.35, 245)]
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
            lrw = max(3, int(rw * frac)); lrh = max(3, int(rh * frac))
            pad_x = (rw * 2 + 10 - lrw * 2) // 2; pad_y = (rh * 2 + 10 - lrh * 2) // 2
            pygame.draw.ellipse(eye_surf, (cr, cg, cb, ca), (pad_x, pad_y, lrw * 2, lrh * 2))
        self.screen.blit(eye_surf, (ex - rw - 5, ey - rh - 5))
        # 内部霓虹辉光
        glow_surf = pygame.Surface((rw * 2 + 4, rh * 2 + 4), pygame.SRCALPHA)
        glow_surf.fill((0, 0, 0, 0))
        pygame.draw.ellipse(glow_surf, (*neon, int(55 * bloom_pulse)), (0, 0, rw * 2 + 4, rh * 2 + 4))
        cw, ch = rw // 2, rh // 2
        pygame.draw.ellipse(glow_surf, (*neon, int(30 * bloom_pulse)), (rw - cw + 2, rh - ch + 2, cw * 2, ch * 2))
        self.screen.blit(glow_surf, (ex - rw - 2, ey - rh - 2))
        # 瞳孔
        pupil_r = max(8, int(min(rw, rh) * 0.52))
        bright_neon = tuple(min(255, int(c * 1.5)) for c in neon)
        pygame.draw.circle(self.screen, bright_neon, (ex, ey - int(rh * 0.05)), pupil_r)
        hl_r = max(1, pupil_r // 3)
        pygame.draw.circle(self.screen, (255, 255, 255), (ex - int(pupil_r * 0.4), ey - int(rh * 0.05) - int(pupil_r * 0.4)), hl_r)

    def _draw_mouth(self, cx, cy, sp, rx, ry, s, face_scale, neon):
        expr = self._current_expr
        mouth_y = cy + int(ry * 0.65 * face_scale)
        mouth_w = int(sp * StyleConfig.MOUTH_WIDTH * 0.5)
        mx = cx; my = mouth_y
        lip_w = max(6, int(12 * face_scale))

        def draw_lip_arc(pts, width):
            pygame.draw.lines(self.screen, StyleConfig.dim_color(neon, 0.3), False, pts, width + 6)
            pygame.draw.lines(self.screen, neon, False, pts, width)
            bright = tuple(min(255, int(c * 1.25)) for c in neon)
            inner_w = max(2, width - 4)
            pygame.draw.lines(self.screen, bright, False, pts, inner_w)

        if expr in ("happy", "laugh", "excited", "smile", "heart_eyes", "star_eyes"):
            pts = [(mx - mouth_w + int(mouth_w * 2 * (i / 29.0)), my + int(math.sin((i / 29.0) * math.pi) * 16)) for i in range(30)]
            draw_lip_arc(pts, lip_w)
        elif expr in ("sad", "scared"):
            pts = [(mx - mouth_w + int(mouth_w * 2 * (i / 29.0)), my - int(math.sin((i / 29.0) * math.pi) * 14)) for i in range(30)]
            draw_lip_arc(pts, lip_w)
        elif expr == "surprised":
            ow = int(mouth_w * 0.5); oh = int(14 * face_scale)
            pygame.draw.ellipse(self.screen, StyleConfig.dim_color(neon, 0.3), (mx - ow - 6, my - oh - 6, ow * 2 + 12, oh * 2 + 12))
            pygame.draw.ellipse(self.screen, neon, (mx - ow, my - oh, ow * 2, oh * 2))
            bright = tuple(min(255, int(c * 1.25)) for c in neon)
            iow, ioh = max(2, ow - 4), max(2, oh - 4)
            pygame.draw.ellipse(self.screen, bright, (mx - iow, my - ioh, iow * 2, ioh * 2))
        elif expr == "angry":
            pts = [(mx - mouth_w + int(mouth_w * 2 * (i / 23.0)), my - int(math.sin((i / 23.0) * math.pi) * 8)) for i in range(24)]
            draw_lip_arc(pts, lip_w + 1)
        elif expr in ("thinking", "confused"):
            pts = [(mx - mouth_w + int(mouth_w * 2 * (i / 21.0)), my - int(math.sin((i / 21.0) * math.pi * 0.5) * 6)) for i in range(22)]
            draw_lip_arc(pts, lip_w - 1)
        elif expr in ("speaking",):
            pts = [(mx - mouth_w + int(mouth_w * 2 * (i / 23.0)), my + int(math.sin((i / 23.0) * math.pi * 0.4) * 8)) for i in range(24)]
            draw_lip_arc(pts, lip_w)

    def _draw_blush(self, cx, cy, sp, rx, ry, blush_val, face_scale):
        alpha = min(120, int(blush_val * 200))
        if alpha < 5: return
        color = (*StyleConfig.NEON_PINK, alpha)
        for side in [-1, 1]:
            bx = cx + side * (sp // 2 + int(rx * 0.7))
            by = cy + int(ry * 0.25)
            br = int(rx * 0.5)
            surf = pygame.Surface((br * 2 + 8, br * 2 + 8), pygame.SRCALPHA)
            surf.fill((0, 0, 0, 0))
            pygame.draw.ellipse(surf, color, (0, 0, br * 2 + 8, br * 2 + 8))
            self.screen.blit(surf, (bx - br - 4, by - br - 4))

    def _draw_scanlines(self):
        if self._scanline_surf is None: return
        y = int(self._scanline_offset)
        self.screen.blit(self._scanline_surf, (0, y - HEIGHT))
        self.screen.blit(self._scanline_surf, (0, y))

    def _draw_glitch(self):
        for y, offset, w in self._glitch_lines:
            x = random.randint(0, WIDTH - w)
            try:
                strip = self.screen.subsurface((x, y, w, 2)).copy()
                self.screen.blit(strip, (x + offset, y))
            except: pass

    def draw_hud(self, info):
        lines = [
            f"FPS:{info.get('fps', 0):.0f} | EXPR:{info.get('expr','?')} | PHASE:{info.get('phase','?')}",
            f"MOOD:{info.get('mood','?')} | DOTS:{info.get('dots',0)} | PERF:{info.get('perf','?')}",
            f"TRANS:{info.get('param_trans',False)} | T:{info.get('param_t',0):.2f}",
        ]
        for i, line in enumerate(lines):
            try:
                surf, _ = self.font_cn_small.render(line, (100, 255, 100))
                self.screen.blit(surf, (WIDTH - 350, 12 + i * 20))
            except: pass


# ═══════════════════════════════════════════════════════
# MAIN — Mac 查看器主循环
# ═══════════════════════════════════════════════════════
def main():
    pygame.init()
    pygame.freetype.init()
    # Mac 上用窗口模式 (非全屏)，可调整大小
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("小Q 表情查看器 — Neon Cyber Style | 1-9表情 M情绪 B弹性 F1调试 ESC退出")
    clock = pygame.time.Clock()

    sm = StateMachine()
    renderer = Renderer(screen)
    squash_stretch = SquashStretch()
    anim_director = AnimationDirector(squash_stretch)
    anim_director._renderer = renderer
    ambient_mgr = AmbientManager(renderer.face_center_x, renderer.face_center_y)
    perf = PerfMonitor()

    def _on_expr_change(expr_name):
        anim_director.on_expression_change(expr_name)
        expr_to_mood = {
            "idle": "idle", "happy": "happy", "laugh": "happy", "excited": "excited",
            "smile": "happy", "relaxed": "idle", "sad": "sad", "angry": "angry",
            "surprised": "surprised", "scared": "scared", "sleepy": "sleepy",
            "bored": "idle", "curious": "curious", "thinking": "focus",
            "confused": "curious", "blink": None, "wink": None,
            "look_left": None, "look_right": None, "look_up": None,
            "heart_eyes": "love", "star_eyes": "excited", "speaking": "happy",
        }
        mood = expr_to_mood.get(expr_name)
        if mood: ambient_mgr.set_mood(mood)

    sm._on_expr_change = _on_expr_change
    sm._breath_params_cb = anim_director.get_breath_params
    sm.auto_mode = True

    # 鼠标追踪用于交互
    pygame.mouse.set_visible(True)

    running = True
    show_hud = False
    fps_timer = 0; fps_count = 0; _actual_fps = 60.0
    touch_down_pos = None; touch_down_time = 0; last_click_time = 0

    print("=" * 60)
    print("小Q Mac 表情查看器 — Neon Cyber Style")
    print("=" * 60)
    print("键盘控制:")
    print("  1=Happy  2=Surprised  3=Thinking  4=Speaking  5=Sleepy")
    print("  6=Curious  7=Wink  8=Laugh  9=Excited  0=Sad")
    print("  H=HeartEyes  S=StarEyes")
    print("  M=循环情绪氛围  B=弹性动画  V=自动/手动模式")
    print("  F1=调试HUD  F12=截图  ESC=退出")
    print("  SPACE=回到idle  N=NPC自主模式")
    print("鼠标: 点击=交互  上滑=惊讶  下滑=伤心  长按=生气  双击=兴奋")
    print("=" * 60)

    while running:
        dt = clock.tick(FPS) / 1000.0
        fps_count += 1; fps_timer += dt
        if fps_timer >= 5.0:
            _actual_fps = fps_count / fps_timer
            fps_count = 0; fps_timer = 0

        perf.update(dt, _actual_fps)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                    running = False
                elif event.key == pygame.K_SPACE:
                    sm.trigger("idle")
                elif event.key == pygame.K_1: sm.trigger("happy")
                elif event.key == pygame.K_2: sm.trigger("surprised")
                elif event.key == pygame.K_3: sm.trigger("thinking")
                elif event.key == pygame.K_4: sm.trigger("speaking")
                elif event.key == pygame.K_5: sm.trigger("sleepy")
                elif event.key == pygame.K_6: sm.trigger("curious")
                elif event.key == pygame.K_7: sm.trigger("wink")
                elif event.key == pygame.K_8: sm.trigger("laugh")
                elif event.key == pygame.K_9: sm.trigger("excited")
                elif event.key == pygame.K_0: sm.trigger("sad")
                elif event.key == pygame.K_h: sm.trigger("heart_eyes")
                elif event.key == pygame.K_s: sm.trigger("star_eyes")
                elif event.key == pygame.K_m:
                    _moods = ["idle", "happy", "sad", "angry", "surprised", "excited", "curious", "sleepy", "love", "focus"]
                    if not hasattr(pygame, '_mood_idx'): pygame._mood_idx = -1
                    pygame._mood_idx = (pygame._mood_idx + 1) % len(_moods)
                    ambient_mgr.set_mood(_moods[pygame._mood_idx])
                    print(f"[情绪] {_moods[pygame._mood_idx]}")
                elif event.key == pygame.K_b:
                    _styles = ["tap", "bounce", "shake", "surprise"]
                    if not hasattr(pygame, '_sq_idx'): pygame._sq_idx = -1
                    pygame._sq_idx = (pygame._sq_idx + 1) % len(_styles)
                    squash_stretch.trigger_squash(1.0, _styles[pygame._sq_idx])
                    print(f"[弹性] {_styles[pygame._sq_idx]}")
                elif event.key == pygame.K_v:
                    sm.auto_mode = not sm.auto_mode
                    print(f"[模式] {'手动触发' if not sm.auto_mode else '自动循环'}")
                elif event.key == pygame.K_n:
                    sm.auto_mode = True
                    sm._goto_expr("idle"); sm.phase = "loop"
                    print("[NPC] 自主模式")
                elif event.key == pygame.K_F1:
                    show_hud = not show_hud
                elif event.key == pygame.K_F12:
                    ts = time.strftime('%H%M%S')
                    fname = f'/tmp/xiaoq_mac_{ts}.png'
                    pygame.image.save(screen, fname)
                    print(f'[截图] {fname}')
                sm.interact_cooldown = random.uniform(1.5, 2.5)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                touch_down_pos = event.pos; touch_down_time = time.time()
            elif event.type == pygame.MOUSEBUTTONUP:
                up_pos = event.pos
                elapsed = time.time() - (touch_down_time or 0)
                dx = up_pos[0] - (touch_down_pos[0] or up_pos[0])
                dy = up_pos[1] - (touch_down_pos[1] or up_pos[1])
                if elapsed > 1.0:
                    sm.trigger("angry")
                    squash_stretch.trigger_squash(0.7, "shake")
                elif abs(dy) > 80 and abs(dy) > abs(dx):
                    if dy < 0:
                        sm.trigger("surprised")
                        squash_stretch.trigger_squash(0.8, "surprise")
                    else:
                        sm.trigger("sad")
                        squash_stretch.trigger_squash(0.3, "tap")
                elif time.time() - last_click_time < 0.3:
                    sm.trigger("excited")
                    squash_stretch.trigger_squash(0.6, "bounce")
                    last_click_time = 0
                else:
                    last_click_time = time.time()
                    mid_x = WIDTH // 2
                    if up_pos[0] < mid_x * 0.4: sm.trigger("look_left")
                    elif up_pos[0] > mid_x * 1.6: sm.trigger("look_right")
                    else:
                        sm.trigger("happy")
                        squash_stretch.trigger_squash(0.5, "tap")
                sm.interact_cooldown = random.uniform(2, 3)

        if sm.auto_mode:
            sm.update_auto(dt)
        sm.update(dt)
        squash_stretch.update(dt)
        anim_director.update(dt)
        renderer.update(dt)
        ambient_mgr.update(dt)

        # 瞳孔模式同步
        if sm.active_expr == "heart_eyes" and renderer.pupil_mode != "heart":
            renderer.set_pupil_mode("heart", duration=999)
        elif sm.active_expr == "star_eyes" and renderer.pupil_mode != "star":
            renderer.set_pupil_mode("star", duration=999)
        elif sm.active_expr not in ("heart_eyes", "star_eyes") and renderer.pupil_mode != "normal":
            renderer.set_pupil_mode("normal", duration=0)

        body_ox, body_oy = anim_director.get_body_offset(sm.idle_bounce)
        body_sx = squash_stretch.scale_x; body_sy = squash_stretch.scale_y

        renderer.draw(sm.current, 1.0, 0,
                      body_scale_x=body_sx, body_scale_y=body_sy,
                      body_offset_x=body_ox, body_offset_y=body_oy,
                      ambient_mgr=ambient_mgr, perf=perf)

        # 状态栏
        status = f"表情:{sm.active_expr} | 霓虹:{renderer.get_neon_color()} | 氛围:{ambient_mgr._mood} | FPS:{_actual_fps:.0f}"
        try:
            surf, _ = renderer.font_cn_small.render(status, (150, 150, 150))
            screen.blit(surf, (12, HEIGHT - 24))
        except: pass

        if show_hud:
            renderer.draw_hud({
                "expr": sm.active_expr, "phase": sm.phase, "fps": _actual_fps,
                "mood": ambient_mgr._mood, "dots": len(ambient_mgr._dots),
                "perf": perf.level_name, "param_trans": sm._param_trans,
                "param_t": sm._param_trans_time / sm._param_trans_dur if sm._param_trans and sm._param_trans_dur > 0 else 0,
            })

        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == '__main__':
    main()
