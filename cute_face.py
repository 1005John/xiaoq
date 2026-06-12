#!/usr/bin/env python3
"""
桌面机器人 — "可爱自信风" 脸部表情系统 (Cute Confident Style)
基于13维参数驱动 + Pygame 2D矢量渲染
支持全部 23 种表情 + 状态机动画 + 弹性形变 + 可爱氛围

与 robot_face_v11.py (霓虹赛博风) 架构同源，渲染层完全不同
"""

import pygame
import pygame.freetype
import math
import random
import sys
import time
import os

# ── 画布配置 ──
WIDTH, HEIGHT = 1280, 720
FPS = 30

# ═══════════════════════════════════════════════════════
# CuteStyle — 可爱风配色系统
# ═══════════════════════════════════════════════════════
class CuteStyle:
    """可爱自信风全局配色"""

    # ── 背景 ──
    BG_COLOR = (240, 208, 192)       # 肉肤色 #F0D0C0
    BG_WARM   = (245, 218, 202)      # 略浅

    # ── 面部 ──
    FACE_SKIN     = (255, 228, 196)  # 肤色
    FACE_SHADOW   = (245, 210, 180)  # 肤色暗部(立体感)

    # ── 眼睛 ──
    EYE_WHITE     = (255, 255, 255, 230)  # 眼白(微透)
    EYE_OUTLINE   = (80, 70, 65)     # 眼框线(深棕)
    PUPIL_COLOR   = (25, 22, 20)     # 瞳孔(近黑)
    PUPIL_HIGHLIGHT = (255, 255, 255)  # 瞳孔高光白

    # ── 眉毛 ──
    BROW_COLOR    = (55, 48, 42)     # 深棕灰

    # ── 嘴巴 ──
    MOUTH_COLOR   = (195, 105, 100)  # 柔和粉色唇
    MOUTH_INNER   = (220, 130, 125)  # 嘴唇内侧(开口时)

    # ── 腮红 ──
    BLUSH_COLOR   = (240, 130, 125)  # 红润腮红

    # ── 情绪色调(用于氛围) ──
    MOOD_GLOW = {
        "idle":      (255, 240, 220),
        "happy":     (255, 220, 180),
        "love":      (255, 190, 200),
        "sad":       (200, 210, 240),
        "angry":     (255, 200, 190),
        "surprised": (255, 235, 170),
        "excited":   (255, 210, 140),
        "curious":   (240, 225, 200),
        "sleepy":    (220, 215, 230),
        "focus":     (230, 225, 215),
    }

    # ── 可爱粒子色 ──
    PARTICLE_COLORS = {
        "heart":  [(255, 120, 150), (255, 160, 180), (255, 100, 140)],
        "star":   [(255, 210, 80), (255, 230, 130), (255, 190, 60)],
        "sparkle": [(255, 240, 180), (255, 220, 200), (255, 200, 220)],
    }


# ═══════════════════════════════════════════════════════
# Params — 13维参数向量
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
# 23 组表情参数预设 (为可爱风重新调参)
# ═══════════════════════════════════════════════════════
# P(l_open, r_open, l_w, r_w, l_y, r_y, l_cut, r_cut, pupil_scale, highlight, brow_l, brow_r, blush)

# ── 基础 ──
IDLE_P     = P(0.90, 0.90, 1.00, 1.00,  0,  0, 0.00, 0.00, 1.00, 0.80, -2, -2, 0.15)

# ── 正向情绪 ──
HAPPY      = P(1.05, 1.05, 1.12, 1.12, -3, -3, 0.20, 0.20, 1.20, 1.00, -8, -8, 0.55)
LAUGH      = P(0.40, 0.40, 1.15, 1.15,  0,  0, 0.75, 0.75, 1.10, 0.90, -9, -9, 0.70)
EXCITED    = P(1.20, 1.20, 1.20, 1.20, -5, -5, 0.00, 0.00, 1.40, 1.00, -10, -10, 0.60)
SMILE      = P(0.70, 0.70, 1.08, 1.08,  0,  0, 0.50, 0.50, 1.15, 0.85, -5, -5, 0.50)
RELAXED    = P(0.65, 0.65, 1.00, 1.00,  0,  0, 0.00, 0.00, 0.90, 0.50,  0,  0, 0.10)

# ── 负向情绪 ──
ANGRY      = P(0.60, 0.60, 0.90, 0.90,  4,  4, 0.00, 0.00, 0.60, 0.30,  6,  6, 0.00)
SAD        = P(0.45, 0.45, 0.95, 0.95,  5,  5, 0.00, 0.00, 0.70, 0.30, 10, 10, 0.00)
SCARED     = P(1.30, 0.90, 0.95, 1.20, -7, -3, 0.00, 0.00, 0.60, 0.40, -5,  7, 0.00)
SLEEPY     = P(0.08, 0.08, 0.85, 0.85,  0,  0, 0.00, 0.00, 1.00, 0.05,  2,  2, 0.00)
DEEP_SLEEP = P(0.00, 0.00, 0.85, 0.85,  0,  0, 0.00, 0.00, 1.00, 0.00,  2,  2, 0.00)
BORED      = P(0.40, 0.60, 0.95, 0.85,  3,  0, 0.00, 0.00, 0.80, 0.30,  3, -1, 0.00)

# ── 惊讶 ──
SURPRISE   = P(1.40, 1.40, 1.05, 1.05, -6, -6, 0.00, 0.00, 0.50, 0.90, -12, -12, 0.00)

# ── 认知类 ──
CURIOUS    = P(1.15, 0.85, 1.10, 1.00, -3,  2, 0.00, 0.00, 1.25, 0.80, -6,  3, 0.20)
THINK      = P(0.75, 0.40, 0.90, 0.80, -2,  3, 0.00, 0.30, 0.80, 0.35,  3,  7, 0.00)
CONFUSED   = P(1.00, 0.60, 1.00, 0.85,  0,  3, 0.00, 0.00, 0.85, 0.40, -3,  6, 0.00)
SPEAK      = P(0.90, 0.90, 1.00, 1.00,  0,  0, 0.00, 0.00, 1.00, 0.60, -2, -2, 0.10)

# ── 瞬态 ──
BLINK      = P(0.00, 0.00, 1.00, 1.00,  0,  0, 0.00, 0.00, 1.00, 0.00, -1, -1, 0.00)
WINK       = P(0.90, 0.00, 1.05, 1.00, -1,  0, 0.00, 0.00, 1.10, 0.80, -4,  2, 0.15)

# ── 视线 ──
LOOK_L     = P(0.90, 0.90, 0.85, 1.08, -1, -1, 0.00, 0.00, 0.95, 0.70,  0,  0, 0.00)
LOOK_R     = P(0.90, 0.90, 1.08, 0.85, -1, -1, 0.00, 0.00, 0.95, 0.70,  0,  0, 0.00)
LOOK_U     = P(1.05, 1.05, 0.90, 0.90, -8, -8, 0.00, 0.00, 0.95, 0.70, -2, -2, 0.00)

# ── 特殊瞳孔 ──
HEART_EYES = P(1.10, 1.10, 1.10, 1.10, -3, -3, 0.30, 0.30, 1.00, 0.90, -7, -7, 0.70)
STAR_EYES  = P(1.20, 1.20, 1.05, 1.05, -4, -4, 0.00, 0.00, 1.00, 1.00, -9, -9, 0.50)


# ═══════════════════════════════════════════════════════
# 表情动画定义 (intro→loop→tail 三段式)
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
    "sleepy":    {"intro_target": SLEEPY, "intro_speed": 0.03, "loop_target": SLEEPY, "loop_duration": 999999.0},
    "bored":     {"intro_target": BORED, "intro_speed": 0.08, "loop_target": BORED, "loop_duration": 4.0, "tail_target": IDLE_P, "tail_speed": 0.06},
    "idle":      {"loop_target": IDLE_P, "loop_dynamic": True},
    "curious":   {"intro_target": CURIOUS, "intro_speed": 0.12, "loop_target": CURIOUS, "loop_duration": 3.0, "tail_target": IDLE_P, "tail_speed": 0.08},
    "thinking":  {"intro_target": THINK, "intro_speed": 0.12, "loop_target": THINK, "loop_duration": 4.0, "loop_dynamic": True, "tail_target": IDLE_P, "tail_speed": 0.08},
    "confused":  {"intro_target": CONFUSED, "intro_speed": 0.12, "loop_target": CONFUSED, "loop_duration": 3.0, "tail_target": IDLE_P, "tail_speed": 0.08},
    "speaking":  {"intro_target": SPEAK, "intro_speed": 0.15, "loop_target": SPEAK, "loop_duration": 4.0, "loop_dynamic": True, "tail_target": IDLE_P, "tail_speed": 0.10},
    "look_left":  {"intro_target": LOOK_L, "intro_speed": 0.15, "loop_target": LOOK_L, "loop_duration": 1.5, "tail_target": IDLE_P, "tail_speed": 0.10},
    "look_right": {"intro_target": LOOK_R, "intro_speed": 0.15, "loop_target": LOOK_R, "loop_duration": 1.5, "tail_target": IDLE_P, "tail_speed": 0.10},
    "look_up":    {"intro_target": LOOK_U, "intro_speed": 0.12, "loop_target": LOOK_U, "loop_duration": 2.0, "tail_target": IDLE_P, "tail_speed": 0.10},
    "wink":       {"intro_target": WINK, "intro_speed": 0.20, "loop_target": WINK, "loop_duration": 0.3, "tail_target": IDLE_P, "tail_speed": 0.15},
    "blink":      {"intro_target": BLINK, "intro_speed": 0.30, "loop_target": BLINK, "loop_duration": 0.15, "tail_target": IDLE_P, "tail_speed": 0.25},
    "heart_eyes": {"intro_target": HEART_EYES, "intro_speed": 0.12, "loop_target": HEART_EYES, "loop_duration": 3.0, "tail_target": IDLE_P, "tail_speed": 0.08},
    "star_eyes":  {"intro_target": STAR_EYES, "intro_speed": 0.15, "loop_target": STAR_EYES, "loop_duration": 2.0, "tail_target": IDLE_P, "tail_speed": 0.10},
}


# ═══════════════════════════════════════════════════════
# StateMachine — 表情状态机
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
        self.pause_active = False; self.pause_timer = 0; self.pause_duration = 0
        self.next_pause = random.uniform(20, 60); self.pause_cooldown = 0
        self.blink_phase = 0; self.blink_frame_time = 0
        self.interact_cooldown = 0
        self._on_expr_change = None; self._breath_params_cb = None
        self._param_trans = False; self._param_trans_time = 0.0
        self._param_trans_dur = 0.3; self._param_trans_from = None
        self._param_easing = "ease_out_quad"; self._prev_expr = "idle"

    def trigger(self, expr_name):
        if expr_name not in EXPRESSIONS: return
        if expr_name == "idle": self._goto_expr("idle"); return
        if self.active_expr in ("blink", "wink"): self._goto_expr(expr_name); return
        if self.active_expr == expr_name and self.phase == "loop": self.phase_time = 0; return
        if self.phase in ("loop", "intro"): self._goto_expr(expr_name)
        elif self.phase == "tail": self.next_expr = expr_name

    def _goto_expr(self, expr_name):
        self._prev_expr = self.active_expr
        self._param_trans = True; self._param_trans_time = 0.0
        self._param_trans_from = self.current.copy()
        rule = AnimationDirector.TRANSITION_RULES
        key = (self._prev_expr, expr_name)
        r = rule.get(key) or rule.get(("any", expr_name)) or rule.get((self._prev_expr, "any"))
        if r: self._param_trans_dur = r["duration"]; self._param_easing = r["easing"]
        else: self._param_trans_dur = 0.35; self._param_easing = "ease_out_quad"
        self.phase = "intro" if "intro_target" in EXPRESSIONS.get(expr_name, {}) else "loop"
        self.active_expr = expr_name; self.next_expr = None; self.phase_time = 0
        self.speak_t = 0; self.sleepy_breathe = 0; self.blink_timer = 0
        if self._on_expr_change: self._on_expr_change(expr_name)

    def update(self, dt):
        self.idle_bounce += dt; self.phase_time += dt
        if self.interact_cooldown > 0: self.interact_cooldown -= dt
        # 眨眼帧序列
        if self.blink_phase > 0:
            self.blink_frame_time += dt
            if self.blink_phase == 1:
                if self.blink_frame_time > 0.06:
                    self.blink_phase = 2; self.blink_frame_time = 0
                    self.current.l_open = 0.0; self.current.r_open = 0.0
            elif self.blink_phase == 2:
                if self.blink_frame_time > 0.08:
                    self.blink_phase = 3; self.blink_frame_time = 0
            elif self.blink_phase == 3:
                if self.blink_frame_time > 0.06:
                    self.blink_phase = 0; self.blink_frame_time = 0
                    self.blink_timer = 0; self.next_blink = random.uniform(2.5, 6.0)
                    if random.random() < 0.10: self.next_blink = random.uniform(0.3, 1.0)
        elif self.is_blinking:
            if self.phase_time > 0.15:
                self.is_blinking = False
                if self.phase in ("intro", "loop"): self.phase = "loop"; self.phase_time = 0
                self.blink_timer = 0; self.next_blink = random.uniform(2.5, 5)
        elif (self.active_expr not in ("sleepy", "blink") and
              self.blink_timer > self.next_blink and self.interact_cooldown <= 0):
            self.blink_phase = 1; self.blink_frame_time = 0
            self.is_blinking = True; self.phase_time = 0; self.blink_timer = 0
        # 随机视线
        if self.interact_cooldown <= 0: self.gaze_timer += dt
        if (self.gaze_timer > self.next_gaze and
            self.active_expr in ("idle", "curious", "bored", "relaxed", "smile") and self.blink_phase == 0):
            self.gaze_timer = 0; self.next_gaze = random.uniform(8, 20)
            self.trigger(random.choice(["look_left", "look_right", "look_up"]))
        # 随机停顿
        if self.pause_active:
            self.pause_timer += dt
            if self.pause_timer > self.pause_duration:
                self.pause_active = False; self.pause_timer = 0
                self.current.l_open = 1.0; self.current.r_open = 1.0; self.pause_cooldown = 0
        else:
            self.pause_cooldown += dt
            if (self.pause_cooldown > self.next_pause and self.active_expr == "idle" and
                self.blink_phase == 0 and self.interact_cooldown <= 0):
                self.pause_active = True; self.pause_timer = 0
                self.pause_duration = random.uniform(0.5, 1.5)
                self.next_pause = random.uniform(20, 60); self.pause_cooldown = 0
        # 随机wink
        if self.active_expr not in ("blink", "wink", "sleepy"):
            self.wink_timer += dt
            if self.wink_timer > self.next_wink:
                self._goto_expr("wink"); self.wink_timer = 0
                self.next_wink = random.uniform(15, 35)

        if self.phase == "intro": self._update_intro(dt)
        elif self.phase == "loop": self._update_loop(dt)
        elif self.phase == "tail": self._update_tail(dt)

        if self.is_blinking:
            self.current.lerp(BLINK, 0.30 if self.blink_phase in (1, 3) else 0.25)
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
                if t >= 1.0: self._param_trans = False
            else:
                defn = EXPRESSIONS[self.active_expr]
                if self.phase == "intro": spd = defn.get("intro_speed", 0.10)
                elif self.phase == "tail": spd = defn.get("tail_speed", 0.08)
                else: spd = 0.05
                self.current.lerp(target, spd)

    def _update_intro(self, dt):
        defn = EXPRESSIONS[self.active_expr]
        target = defn["intro_target"]; spd = defn.get("intro_speed", 0.10)
        self.current.lerp(target, spd)
        if self.current.is_close(target): self.phase = "loop"; self.phase_time = 0

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
                else: freq, amp = 0.8, 0.02
                breath = math.sin(self.idle_bounce * freq) * amp
                micro = math.sin(self.idle_bounce * 3.1) * 0.005
                self.current.l_open = 1.0 + breath + micro
                self.current.r_open = 1.0 + breath - micro
        loop_dur = defn.get("loop_duration", 999)
        if self.phase_time > loop_dur:
            tail_target = defn.get("tail_target")
            if tail_target is not None:
                self.phase = "tail"; self.phase_time = 0
                if self.active_expr == "sleepy": self.active_expr = "surprised"
            else: self._goto_expr("idle"); self.phase = "loop"; self.next_state_time = random.uniform(2, 4)

    def _update_tail(self, dt):
        defn = EXPRESSIONS[self.active_expr]
        tail_target = defn.get("tail_target", IDLE_P)
        spd = defn.get("tail_speed", 0.08)
        self.current.lerp(tail_target, spd)
        if self.current.is_close(tail_target):
            if self.active_expr == "sleepy":
                self.active_expr = "surprised"; self.phase = "intro"; self.phase_time = 0
            elif self.next_expr: self._goto_expr(self.next_expr)
            else: self._goto_expr("idle"); self.phase = "loop"; self.next_state_time = random.uniform(2, 4)

    def update_auto(self, dt):
        if not self.auto_mode or self.active_expr not in ("idle",): return
        if self.phase != "loop": return
        self.next_state_time += dt
        if self.next_state_time > self.idle_next_time:
            self.next_state_time = 0; self.idle_next_time = random.uniform(2, 5)
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
        elif r < 0.87: self._goto_expr("speaking"); self.speak_t = 0
        elif r < 0.92: self._goto_expr("sleepy"); self.sleepy_breathe = 0
        else: self._goto_expr("bored")

    def _get_current_target(self):
        defn = EXPRESSIONS[self.active_expr]
        if self.phase == "intro": return defn["intro_target"]
        elif self.phase == "loop": return defn["loop_target"]
        elif self.phase == "tail": return defn.get("tail_target", IDLE_P)
        return IDLE_P


# ═══════════════════════════════════════════════════════
# Easing / SquashStretch / AnimationDirector / PerfMonitor
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
        c = 1.70158; return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2
    @staticmethod
    def ease_in_out_sine(t): return -(math.cos(math.pi * t) - 1) / 2
    @staticmethod
    def ease_out_elastic(t):
        if t == 0 or t == 1: return t
        return 2 ** (-10 * t) * math.sin((t - 0.075) * (2 * math.pi) / 0.3) + 1


class SquashStretch:
    def __init__(self):
        self.scale_x = 1.0; self.scale_y = 1.0; self.offset_y = 0.0; self.offset_x = 0.0
        self._animating = False; self._anim_time = 0.0; self._anim_duration = 0.45
        self._keyframes = []; self._easing = Easing.ease_out_quad
        self._damping_active = False; self._damp_time = 0.0
        self._damp_sx = 1.0; self._damp_sy = 1.0; self._damp_ox = 0.0; self._damp_oy = 0.0

    @property
    def active(self): return self._animating or self._damping_active

    def trigger_squash(self, intensity=1.0, style="tap"):
        I = intensity
        if style == "tap":
            self._keyframes = [(0.00, 1.0, 1.0, 0, 0), (0.08, 1.15*I, 0.85*I, 0, 2),
                (0.22, 0.95, 1.10, 0, -3), (0.38, 1.02, 0.98, 0, 0.5), (0.45, 1.0, 1.0, 0, 0)]
            self._anim_duration = 0.45; self._easing = Easing.ease_out_quad
        elif style == "bounce":
            self._keyframes = [(0.00, 1.0, 1.0, 0, 0), (0.10, 0.92, 1.12, 0, -12*I),
                (0.25, 1.08, 0.92, 0, -20*I), (0.50, 1.0, 1.0, 0, 0),
                (0.65, 1.18*I, 0.82*I, 0, 4), (0.80, 0.96, 1.08, 0, -2), (1.00, 1.0, 1.0, 0, 0)]
            self._anim_duration = 0.6; self._easing = Easing.ease_out_quad
        elif style == "shake":
            self._keyframes = [(0.00, 1.0, 1.0, 0, 0), (0.10, 1.0, 1.0, -6*I, 0),
                (0.25, 1.0, 1.0, 5*I, 0), (0.40, 1.0, 1.0, -4*I, 0),
                (0.55, 1.0, 1.0, 3*I, 0), (0.70, 1.0, 1.0, -1.5, 0), (1.00, 1.0, 1.0, 0, 0)]
            self._anim_duration = 0.4; self._easing = Easing.ease_out_quad
        elif style == "surprise":
            self._keyframes = [(0.00, 1.0, 1.0, 0, 0), (0.05, 0.90, 1.10, 0, 3),
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
            self.scale_x = sx; self.scale_y = sy; self.offset_x = ox; self.offset_y = oy
            if t_norm >= 1.0:
                self._animating = False; self.scale_x = 1.0; self.scale_y = 1.0
                self.offset_x = 0.0; self.offset_y = 0.0
        if self._damping_active:
            self._damp_time += dt; decay = math.exp(-8 * self._damp_time)
            self.scale_x = 1.0 + self._damp_sx * decay * math.cos(self._damp_time * 12)
            self.scale_y = 1.0 + self._damp_sy * decay * math.cos(self._damp_time * 12 + math.pi)
            self.offset_y = self._damp_oy * decay * math.cos(self._damp_time * 10)
            if decay < 0.01:
                self._damping_active = False; self.scale_x = 1.0; self.scale_y = 1.0; self.offset_y = 0.0

    def _interpolate_keyframes(self, t):
        kf = self._keyframes
        if not kf: return 1.0, 1.0, 0.0, 0.0
        for i in range(len(kf) - 1):
            t0, sx0, sy0, ox0, oy0 = kf[i]; t1, sx1, sy1, ox1, oy1 = kf[i + 1]
            if t0 <= t <= t1:
                span = t1 - t0
                if span < 0.001: return sx1, sy1, ox1, oy1
                local_t = (t - t0) / span
                return (sx0 + (sx1 - sx0) * local_t, sy0 + (sy1 - sy0) * local_t,
                        ox0 + (ox1 - ox0) * local_t, oy0 + (oy1 - oy0) * local_t)
        last = kf[-1]; return last[1], last[2], last[3], last[4]

    def start_damping(self, sx=0.04, sy=0.04, oy=3.0):
        self._damping_active = True; self._damp_time = 0.0
        self._damp_sx = sx; self._damp_sy = sy; self._damp_oy = oy


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
        self._trans_duration = 0.3; self._trans_from_body = None; self._trans_to_body = None

    def on_expression_change(self, expr_name):
        self.prev_expr = self.current_expr; self.current_expr = expr_name
        if hasattr(self, '_renderer') and self._renderer:
            self._renderer.set_expression(expr_name)
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


class PerfMonitor:
    LEVEL_FULL = 0; LEVEL_HALF_DOTS = 1; LEVEL_NO_DOTS = 2
    LEVEL_NO_VFX = 3; LEVEL_MINIMAL = 4

    def __init__(self):
        self.level = self.LEVEL_FULL; self.fps_history = []
        self.check_interval = 3.0; self.timer = 0.0; self.current_fps = 60.0

    def update(self, dt, actual_fps):
        self.current_fps = actual_fps; self.timer += dt
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
            print(f"[PERF] {['FULL','HALF','NO_DOTS','NO_VFX','MINIMAL'][self.level]} (FPS={avg_fps:.0f})")

    @property
    def enable_dots(self): return self.level <= self.LEVEL_HALF_DOTS
    @property
    def enable_glow(self): return self.level <= self.LEVEL_HALF_DOTS
    @property
    def dots_half(self): return self.level == self.LEVEL_HALF_DOTS
    @property
    def enable_vfx(self): return self.level <= self.LEVEL_NO_DOTS
    @property
    def level_name(self): return ["FULL", "HALF", "NO_DOTS", "NO_VFX", "MINIMAL"][self.level]


# ═══════════════════════════════════════════════════════
# CuteAmbientManager — 可爱氛围层
# ═══════════════════════════════════════════════════════
class CuteAmbientManager:
    """可爱氛围：暖色面部柔光 + 飘浮爱心/星星/闪光粒子"""

    PARTICLE_TYPES = ["heart", "star", "sparkle"]

    def __init__(self, face_cx, face_cy):
        self.face_cx = face_cx; self.face_cy = face_cy
        self.width = WIDTH; self.height = HEIGHT

        # 光晕
        self._glow_alpha = 0.0; self._glow_target = 0.12
        self._glow_color = list(CuteStyle.MOOD_GLOW["idle"])
        self._glow_target_color = list(CuteStyle.MOOD_GLOW["idle"])
        self._breath_phase = 0.0

        # 粒子
        self._particles = []
        self._spawn_timer = 0.0; self._spawn_interval = 0.8
        self._max_particles = 15
        self._mood = "idle"

    def set_mood(self, mood_name):
        if mood_name == self._mood: return
        self._mood = mood_name
        color = list(CuteStyle.MOOD_GLOW.get(mood_name, CuteStyle.MOOD_GLOW["idle"]))
        self._glow_target_color = color
        self._glow_target = 0.18 if mood_name not in ("idle", "sleepy") else 0.10

    def update(self, dt):
        # 光晕过渡
        for i in range(3):
            self._glow_color[i] += (self._glow_target_color[i] - self._glow_color[i]) * min(1.0, 2.0 * dt)
        self._glow_alpha += (self._glow_target - self._glow_alpha) * min(1.0, 2.0 * dt)
        self._breath_phase += dt * 0.8  # 缓慢呼吸

        # 粒子生成
        self._spawn_timer += dt
        if self._spawn_timer >= self._spawn_interval and len(self._particles) < self._max_particles:
            self._spawn_timer = 0; self._spawn_particle()

        # 粒子更新
        alive = []
        for p in self._particles:
            p["life"] -= dt
            if p["life"] <= 0: continue
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            # 正弦摇摆
            if p["type"] in ("heart", "star"):
                p["x"] += math.sin(p["life"] * 2.0 + p.get("phase", 0)) * 0.4
            # 淡入淡出
            ml = p["max_life"]
            if p["life"] > ml - 0.4: p["alpha"] = min(1.0, (ml - p["life"]) / 0.4) * p["peak_alpha"]
            elif p["life"] < 0.8: p["alpha"] = (p["life"] / 0.8) * p["peak_alpha"]
            else: p["alpha"] = p["peak_alpha"]
            # 旋转(星星用)
            if p["type"] == "star": p["rotation"] += dt * 30
            if p["alpha"] > 0.02: alive.append(p)
        self._particles = alive

    def _spawn_particle(self):
        ptype = random.choice(self.PARTICLE_TYPES)
        color = random.choice(CuteStyle.PARTICLE_COLORS[ptype])
        max_life = random.uniform(3.0, 7.0)
        x = random.uniform(self.width * 0.05, self.width * 0.95)
        y = self.height + 15
        vx = random.uniform(-10, 10)
        vy = random.uniform(-35, -15)
        size = random.uniform(6, 14) if ptype == "heart" else random.uniform(5, 10)
        self._particles.append({
            "type": ptype, "x": x, "y": y, "vx": vx, "vy": vy,
            "size": size, "color": color, "life": max_life, "max_life": max_life,
            "alpha": 0.0, "peak_alpha": random.uniform(0.3, 0.6),
            "phase": random.uniform(0, 6.28), "rotation": random.uniform(0, 360),
        })

    def get_glow_color(self):
        return tuple(int(self._glow_color[i]) for i in range(3))

    def draw_glow(self, screen, cx=None, cy=None):
        if self._glow_alpha < 0.01: return
        cx = cx or self.face_cx; cy = cy or self.face_cy
        breath = 1.0 + 0.06 * math.sin(self._breath_phase * math.pi * 2)
        base_r = int(240 * breath)
        glow_size = base_r * 2 + 40
        gc = self.get_glow_color()
        surf = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
        center = glow_size // 2
        for i in range(6):
            t = i / 5; frac = 1.0 - t * 0.85
            r = max(3, int(base_r * frac))
            alpha = int(self._glow_alpha * (0.03 + t * 0.28) * 255)
            alpha = min(255, max(0, alpha))
            pygame.draw.circle(surf, (*gc, alpha), (center, center), r)
        screen.blit(surf, (cx - center, cy - center))

    def draw_particles(self, screen, half=False):
        for i, p in enumerate(self._particles):
            if half and i % 2 == 1: continue
            if p["alpha"] < 0.02: continue
            alpha = int(min(255, p["alpha"] * 255))
            color = (*p["color"], alpha)
            s = int(p["size"])
            if p["type"] == "heart":
                self._draw_heart_shape(screen, int(p["x"]), int(p["y"]), s, color)
            elif p["type"] == "star":
                self._draw_star_shape(screen, int(p["x"]), int(p["y"]), s, color, p.get("rotation", 0))
            else:  # sparkle
                surf = pygame.Surface((s * 3, s * 3), pygame.SRCALPHA)
                cx_s = s * 3 // 2; cy_s = s * 3 // 2
                pygame.draw.circle(surf, color, (cx_s, cy_s), s)
                pygame.draw.circle(surf, (*p["color"], alpha // 3), (cx_s, cy_s), s * 2)
                screen.blit(surf, (int(p["x"]) - cx_s, int(p["y"]) - cy_s))

    def _draw_heart_shape(self, screen, cx, cy, size, color):
        """用两个圆 + 三角画爱心"""
        s = size
        surf = pygame.Surface((s * 2 + 4, s * 2 + 4), pygame.SRCALPHA)
        # 左圆
        pygame.draw.circle(surf, color, (s // 2 + 2, s // 2 + 2), s // 2)
        # 右圆
        pygame.draw.circle(surf, color, (s + s // 2 + 2, s // 2 + 2), s // 2)
        # 底部三角
        pts = [(2, s // 2 + s // 3), (s * 2 + 2, s // 2 + s // 3), (s + 2, s * 2)]
        pygame.draw.polygon(surf, color, pts)
        screen.blit(surf, (cx - s - 2, cy - s - 2))

    def _draw_star_shape(self, screen, cx, cy, size, color, rotation=0):
        """画 5 角星"""
        points = []
        for i in range(10):
            angle = math.radians(i * 36 + rotation)
            r = size if i % 2 == 0 else size * 0.4
            points.append((cx + r * math.cos(angle - math.pi / 2),
                          cy + r * math.sin(angle - math.pi / 2)))
        if len(points) >= 3:
            surf = pygame.Surface((size * 2 + 4, size * 2 + 4), pygame.SRCALPHA)
            pts_shifted = [(x - cx + size + 2, y - cy + size + 2) for x, y in points]
            pygame.draw.polygon(surf, color, pts_shifted)
            screen.blit(surf, (cx - size - 2, cy - size - 2))


# ═══════════════════════════════════════════════════════
# CuteRenderer — 可爱风渲染引擎
# ═══════════════════════════════════════════════════════
class CuteRenderer:
    """可爱自信风渲染器 — 肤色椭圆脸 + 眼白/黑瞳孔/高光 + 粗眉 + 粉色嘴 + 腮红"""

    def __init__(self, screen):
        self.screen = screen
        self.face_center_x = WIDTH // 2
        self.face_center_y = HEIGHT // 2 + 20
        # 眼睛尺寸 (大眼，与霓虹版本比例一致)
        self.eye_rx = 160           # 眼 X 半径
        self.eye_ry = 200           # 眼 Y 半径
        self.eye_spacing = 320      # 眼间距(中心到中心 X 偏移)
        self.eye_y_offset = -60     # 眼睛 Y 偏移(相对 face_center)
        # 眉毛
        self.brow_y_offset = -280   # 眉基 Y 偏移(远离眼球)

        self.pupil_mode = "normal"
        self._pupil_mode_timer = 0.0
        self._current_expr = "idle"

        # 字体(用于 HUD)
        pygame.freetype.init()
        self.font_small = None
        for fp in ["/System/Library/Fonts/PingFang.ttc",
                    "/System/Library/Fonts/STHeiti Light.ttc"]:
            if os.path.exists(fp):
                try: self.font_small = pygame.freetype.Font(fp, 13); break
                except: pass
        if self.font_small is None:
            self.font_small = pygame.freetype.Font(None, 13)

    def set_expression(self, expr_name):
        self._current_expr = expr_name

    def set_pupil_mode(self, mode, duration=3.0):
        self.pupil_mode = mode; self._pupil_mode_timer = duration

    def update(self, dt):
        if self._pupil_mode_timer > 0:
            self._pupil_mode_timer -= dt
            if self._pupil_mode_timer <= 0:
                self.pupil_mode = "normal"; self._pupil_mode_timer = 0

    def draw(self, state, face_scale=1.0, offset_x=0, offset_y=0,
             body_sx=1.0, body_sy=1.0, body_ox=0, body_oy=0,
             ambient_mgr=None, perf=None):
        """主绘制入口"""
        cx = self.face_center_x + offset_x + body_ox
        cy = self.face_center_y + offset_y + body_oy

        # Layer 1: 背景
        self.screen.fill(CuteStyle.BG_COLOR)

        # Layer 2: 面部柔光
        if ambient_mgr and (perf is None or perf.enable_glow):
            ambient_mgr.draw_glow(self.screen, cx, cy)

        # Layer 3: 眼睛 (先画，月牙眼裁剪不会盖住腮红)
        for side in [-1, 1]:
            l_open = state.l_open if side < 0 else state.r_open
            l_w = state.l_w if side < 0 else state.r_w
            l_y = state.l_y if side < 0 else state.r_y
            l_cut = state.l_cut if side < 0 else state.r_cut
            pupil_sc = state.pupil_scale
            hl = state.highlight

            ex = cx + side * self.eye_spacing * face_scale * body_sx
            ey = cy + self.eye_y_offset * face_scale + l_y * face_scale

            px_shift = 0
            if self._current_expr == "look_left":
                px_shift = -6 * face_scale
            elif self._current_expr == "look_right":
                px_shift = 6 * face_scale

            self._draw_eye(ex, ey, l_open, l_w, l_cut, pupil_sc, hl, px_shift, face_scale)

        # Layer 4: 腮红 (在眼睛之后画，不被遮盖)
        if state.blush > 0.01:
            self._draw_blush(cx, cy, state.blush, face_scale)

        # Layer 5: 眉毛 (sleepy 不画眉)
        if self._current_expr != "sleepy":
            for side in [-1, 1]:
                bry = state.brow_l if side < 0 else state.brow_r
                bx = cx + side * self.eye_spacing * face_scale * body_sx
                by = cy + self.brow_y_offset * face_scale
                self._draw_eyebrow(bx, by, bry, face_scale, side)

        # Layer 7: 可爱粒子
        if ambient_mgr and (perf is None or perf.enable_dots):
            ambient_mgr.draw_particles(self.screen, half=(perf.dots_half if perf else False))

    # ── 面部底色(已取消) ──
    def _draw_face_base(self, cx, cy, scale, sx, sy):
        pass

    # ── 腮红 ──
    def _draw_blush(self, cx, cy, blush_val, scale):
        alpha = int(min(140, blush_val * 180))
        if alpha < 5: return
        for side in [-1, 1]:
            bx = cx + side * (self.eye_spacing + 290) * scale
            by = cy + (self.eye_y_offset + 280) * scale
            brx = int(130 * scale); bry = int(75 * scale)
            surf = pygame.Surface((brx * 2 + 8, bry * 2 + 8), pygame.SRCALPHA)
            pygame.draw.ellipse(surf, (*CuteStyle.BLUSH_COLOR, alpha),
                              (4, 4, brx * 2, bry * 2))
            self.screen.blit(surf, (bx - brx - 4, by - bry - 4))

    # ── 眼睛 (黑色竖椭圆，无眼白) ──
    def _draw_eye(self, cx, cy, open_r, w_scale, cut, pupil_sc, hl, px_shift, face_scale):
        # 基础尺寸 — 正椭圆
        bw = int(self.eye_rx * w_scale * face_scale)
        bh = int(self.eye_ry * max(0.01, open_r) * face_scale)

        # 瞳孔 X 偏移 (look_left/right)
        px = cx + px_shift
        py = cy

        if bh < 5:
            # 闭眼/困倦 — 细弧线，无高光
            lw = max(8, int(20 * face_scale))
            pts = [(cx - bw + int(bw * 2 * (i / 11.0)),
                    cy + int(math.sin((i / 11.0) * math.pi) * 2))
                   for i in range(12)]
            pygame.draw.lines(self.screen, CuteStyle.PUPIL_COLOR, False, pts, lw)
            return

        # 月牙眼裁剪量
        cut_pixels = int(bh * cut * 2.0) if cut > 0.1 else 0

        # 眼球色
        eye_color = CuteStyle.PUPIL_COLOR

        if self.pupil_mode == "heart":
            # 爱心形眼睛 — 用爱心形状替代椭圆
            self._draw_heart_eye(px, py, bw, bh, cut_pixels, hl, face_scale)
            return
        elif self.pupil_mode == "star":
            # 星形眼睛 — 用星形替代椭圆
            self._draw_star_eye(px, py, bw, bh, cut_pixels, hl, face_scale)
            return

        # 正椭圆眼球
        pygame.draw.ellipse(self.screen, eye_color, (px - bw, py - bh, bw * 2, bh * 2))

        # 月牙眼裁剪
        if cut_pixels > 0:
            bg = CuteStyle.BG_COLOR
            clip_rect = (px - bw - 2, py + bh - cut_pixels, bw * 2 + 4, cut_pixels + 4)
            pygame.draw.rect(self.screen, bg, clip_rect)
            arc_pts = [(px - bw + int(bw * 2 * (i / 20.0)),
                       py + bh - cut_pixels + int(math.sin((i / 20.0) * math.pi) * 3))
                      for i in range(21)]
            pygame.draw.lines(self.screen, eye_color, False, arc_pts, 2)

        # 高光点(左上角)
        if open_r > 0.05 and hl > 0.05:
            hr = max(14, int(45 * hl * face_scale))
            hx = px - int(bw * 0.38)
            hy = py - int(bh * 0.40)
            pygame.draw.circle(self.screen, CuteStyle.PUPIL_HIGHLIGHT, (hx, hy), hr)

    # ── 爱心形眼睛 ──
    def _draw_heart_eye(self, cx, cy, bw, bh, cut_pixels, hl, face_scale):
        """爱心形状替代椭圆眼睛"""
        s = max(bw, bh)  # 爱心尺寸
        size = int(s * 0.85)
        surf_size = size * 3
        surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        cs_x, cs_y = surf_size // 2, surf_size // 2 - size // 3
        color = CuteStyle.PUPIL_COLOR
        # 两个圆 + 三角 = 爱心
        pygame.draw.circle(surf, color, (cs_x - size // 2, cs_y), size // 2)
        pygame.draw.circle(surf, color, (cs_x + size // 2, cs_y), size // 2)
        pts = [(cs_x - size, cs_y + size // 4),
               (cs_x + size, cs_y + size // 4),
               (cs_x, cs_y + size + size // 2)]
        pygame.draw.polygon(surf, color, pts)
        # 高光(左上角)
        if hl > 0.05:
            hr = max(10, int(30 * hl * face_scale))
            hx = cs_x - int(size * 0.30)
            hy = cs_y - int(size * 0.28)
            pygame.draw.circle(surf, CuteStyle.PUPIL_HIGHLIGHT, (hx, hy), hr)
        self.screen.blit(surf, (cx - cs_x, cy - cs_y))

    # ── 星星形眼睛 ──
    def _draw_star_eye(self, cx, cy, bw, bh, cut_pixels, hl, face_scale):
        """星形替代椭圆眼睛"""
        size = max(bw, bh)
        points = []
        for i in range(10):
            angle = math.radians(i * 36 - 90)
            r = size if i % 2 == 0 else size * 0.45
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        if len(points) >= 3:
            pygame.draw.polygon(self.screen, CuteStyle.PUPIL_COLOR, points)
            if hl > 0.05:
                hr = max(8, int(25 * hl * face_scale))
                hx = cx - int(size * 0.30)
                hy = cy - int(size * 0.28)
                pygame.draw.circle(self.screen, CuteStyle.PUPIL_HIGHLIGHT, (hx, hy), hr)

    # ── 眉毛 (外端粗→内端细的渐细斜线) ──
    def _draw_eyebrow(self, cx, cy, brow_offset, face_scale, side):
        """渐细圆润眉毛：重叠圆点串，外粗→内细。
        左边: 左上↘右下  右边: 右上↙左下"""
        blen = int(260 * face_scale)
        thick_outer = max(14, int(24 * face_scale))
        thick_inner = max(4, int(9 * face_scale))

        tilt = brow_offset * face_scale * 1.5
        half = blen // 2

        if side < 0:
            x1, y1 = cx - half, cy - int(40 * face_scale) + tilt
            x2, y2 = cx + half, cy + int(10 * face_scale) - tilt * 0.5
        else:
            x1, y1 = cx + half, cy - int(40 * face_scale) + tilt
            x2, y2 = cx - half, cy + int(10 * face_scale) - tilt * 0.5

        # 圆点串画眉毛 — 天然圆润，4层渐透柔化
        margin = int(thick_outer + 5)
        sw = int(abs(x2 - x1) + margin * 2 + 4)
        sh = int(abs(y2 - y1) + margin * 2 + 4)
        cx_surf = sw // 2; cy_surf = sh // 2

        for r_add, alpha in [(3.0, 15), (1.8, 45), (0.6, 150), (0, 255)]:
            layer = pygame.Surface((sw, sh), pygame.SRCALPHA)
            for i in range(30):
                t = i / 29
                sx = int((x1 + (x2 - x1) * t) - x1 + cx_surf)
                sy = int((y1 + (y2 - y1) * t) - y1 + cy_surf)
                sr = max(1, int(thick_outer + (thick_inner - thick_outer) * t + r_add))
                pygame.draw.circle(layer, (*CuteStyle.BROW_COLOR, alpha), (sx, sy), sr)
            self.screen.blit(layer, (x1 - cx_surf, y1 - cy_surf))

    # ── 嘴巴(已取消) ──
    def _draw_mouth(self, cx, cy, face_scale):
        pass

    # ── HUD ──
    def draw_hud(self, info):
        lines = [
            f"FPS:{info.get('fps', 0):.0f} | {info.get('expr','?')} | {info.get('phase','?')}",
            f"MOOD:{info.get('mood','?')} | PERF:{info.get('perf','?')} | DOTS:{info.get('dots',0)}",
        ]
        for i, line in enumerate(lines):
            try:
                surf, _ = self.font_small.render(line, (120, 100, 90))
                self.screen.blit(surf, (WIDTH - 350, 12 + i * 18))
            except: pass


# ═══════════════════════════════════════════════════════
# MAIN — 可爱风查看器主循环
# ═══════════════════════════════════════════════════════
def main():
    pygame.init()
    pygame.freetype.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("小Q — 可爱自信风 | 1-9表情 M氛围 B弹性 F1调试 ESC退出")
    clock = pygame.time.Clock()

    sm = StateMachine()
    renderer = CuteRenderer(screen)
    squash_stretch = SquashStretch()
    anim_director = AnimationDirector(squash_stretch)
    anim_director._renderer = renderer
    ambient_mgr = CuteAmbientManager(renderer.face_center_x, renderer.face_center_y)
    perf = PerfMonitor()

    def _on_expr_change(expr_name):
        anim_director.on_expression_change(expr_name)
        expr_to_mood = {
            "idle": "idle", "happy": "happy", "laugh": "happy", "excited": "excited",
            "smile": "happy", "relaxed": "idle", "sad": "sad", "angry": "angry",
            "surprised": "surprised", "scared": "sad", "sleepy": "sleepy",
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

    pygame.mouse.set_visible(True)

    running = True; show_hud = False
    fps_timer = 0; fps_count = 0; _actual_fps = 60.0
    touch_down_pos = None; touch_down_time = 0; last_click_time = 0

    print("=" * 60)
    print("小Q 可爱自信风 表情查看器 — 23种表情完整支持")
    print("=" * 60)
    print("  1=Happy  2=Surprised  3=Thinking  4=Speaking  5=Sleepy")
    print("  6=Curious  7=Wink  8=Laugh  9=Excited  0=Sad")
    print("  H=HeartEyes  S=StarEyes  V=切换自动/手动  N=自主模式")
    print("  M=循环情绪氛围  B=弹性动画  F1=HUD  F12=截图")
    print("  SPACE=Idle  ESC=退出")
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
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_SPACE: sm.trigger("idle")
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
                    print(f"[氛围] {_moods[pygame._mood_idx]}")
                elif event.key == pygame.K_b:
                    _styles = ["tap", "bounce", "shake", "surprise"]
                    if not hasattr(pygame, '_sq_idx'): pygame._sq_idx = -1
                    pygame._sq_idx = (pygame._sq_idx + 1) % len(_styles)
                    squash_stretch.trigger_squash(1.0, _styles[pygame._sq_idx])
                    print(f"[弹性] {_styles[pygame._sq_idx]}")
                elif event.key == pygame.K_v:
                    sm.auto_mode = not sm.auto_mode
                    print(f"[模式] {'手动' if not sm.auto_mode else '自动'}")
                elif event.key == pygame.K_n:
                    sm.auto_mode = True; sm._goto_expr("idle"); sm.phase = "loop"
                    print("[NPC] 自主模式")
                elif event.key == pygame.K_F1:
                    show_hud = not show_hud
                elif event.key == pygame.K_F12:
                    ts = time.strftime('%H%M%S')
                    fname = f'/tmp/cute_face_{ts}.png'
                    pygame.image.save(screen, fname)
                    print(f'[截图] {fname}')
                sm.interact_cooldown = random.uniform(1.5, 2.5)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                touch_down_pos = event.pos; touch_down_time = time.time()
            elif event.type == pygame.MOUSEBUTTONUP:
                if touch_down_pos is None: continue
                up_pos = event.pos
                elapsed = time.time() - touch_down_time
                dx = up_pos[0] - touch_down_pos[0]
                dy = up_pos[1] - touch_down_pos[1]
                if elapsed > 1.0:
                    sm.trigger("angry"); squash_stretch.trigger_squash(0.7, "shake")
                elif abs(dy) > 80 and abs(dy) > abs(dx):
                    if dy < 0:
                        sm.trigger("surprised"); squash_stretch.trigger_squash(0.8, "surprise")
                    else:
                        sm.trigger("sad"); squash_stretch.trigger_squash(0.3, "tap")
                elif time.time() - last_click_time < 0.3:
                    sm.trigger("excited"); squash_stretch.trigger_squash(0.6, "bounce")
                    last_click_time = 0
                else:
                    last_click_time = time.time()
                    mid_x = WIDTH // 2
                    if up_pos[0] < mid_x * 0.4: sm.trigger("look_left")
                    elif up_pos[0] > mid_x * 1.6: sm.trigger("look_right")
                    else:
                        sm.trigger("happy"); squash_stretch.trigger_squash(0.5, "tap")
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

        renderer.draw(sm.current, 1.0, 0, 0,
                     body_sx=body_sx, body_sy=body_sy,
                     body_ox=body_ox, body_oy=body_oy,
                     ambient_mgr=ambient_mgr, perf=perf)

        # 底部状态栏
        status = f"表情:{sm.active_expr} | 氛围:{ambient_mgr._mood} | FPS:{_actual_fps:.0f}"
        try:
            surf, _ = renderer.font_small.render(status, (140, 120, 110))
            screen.blit(surf, (12, HEIGHT - 24))
        except: pass

        if show_hud:
            renderer.draw_hud({
                "expr": sm.active_expr, "phase": sm.phase, "fps": _actual_fps,
                "mood": ambient_mgr._mood, "dots": len(ambient_mgr._particles),
                "perf": perf.level_name,
            })

        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == '__main__':
    main()
