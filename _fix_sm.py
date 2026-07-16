#!/usr/bin/env python3
"""Fix: add parametrized StateMachine to face_base.py and update face_cute.py"""

# 1. Read current face_base.py
with open('/home/johnf/xiaoq/face_base.py') as f:
    base_lines = f.readlines()

# Find where to insert StateMachine (after PerfMonitor class)
insert_at = None
for i, line in enumerate(base_lines):
    if 'class PerfMonitor' in line:
        insert_at = i  # insert after this line's block ends
    if insert_at is not None and i > insert_at and not line.strip():
        # Found blank line after PerfMonitor class
        pass

# Find the end of PerfMonitor by looking for the next class or end of file
end_perf = None
for i in range(len(base_lines) - 1, -1, -1):
    if 'class PerfMonitor' in base_lines[i]:
        # Find the next class definition after PerfMonitor
        for j in range(i + 1, len(base_lines)):
            if base_lines[j].startswith('class '):
                end_perf = j
                break
        if end_perf is None:
            end_perf = len(base_lines)
        break

# StateMachine code that uses expressions as instance variable
sm_code = '''

# ═══════════════════════════════════════════════════════
# StateMachine — 表情状态机 (参数化，支持各自 EXPRESSIONS)
# ═══════════════════════════════════════════════════════
class StateMachine:
    def __init__(self, expressions, idle_p=None, blink=None, gimbal_map=None):
        self._exprs = expressions
        self._idle_p = idle_p or Params()
        self._blink = blink or Params(0, 0, 1, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0)
        self._gimbal_map = gimbal_map or {}

        self.current = self._idle_p.copy()
        self.phase = 'loop'
        self.active_expr = 'idle'
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
        self.gimbal = None
        self.last_gimbal_expr = None
        self._on_expr_change = None; self._breath_params_cb = None
        self._param_trans = False; self._param_trans_time = 0.0
        self._param_trans_dur = 0.3; self._param_trans_from = None
        self._param_easing = 'ease_out_quad'; self._prev_expr = 'idle'

    def trigger_gimbal(self, expr_name):
        if self.gimbal is None: return
        mapping = self._gimbal_map.get(expr_name)
        if mapping is None or expr_name == self.last_gimbal_expr: return
        pan_a, tilt_a = mapping
        self.gimbal.move_to(pan_a, tilt_a, 500, blocking=False)
        self.last_gimbal_expr = expr_name

    def trigger(self, expr_name):
        if expr_name not in self._exprs: return
        if expr_name == 'idle': self._goto_expr('idle'); return
        if self.active_expr in ('blink', 'wink'): self._goto_expr(expr_name); return
        if self.active_expr == expr_name and self.phase == 'loop': self.phase_time = 0; return
        if self.phase in ('loop', 'intro'): self._goto_expr(expr_name)
        elif self.phase == 'tail': self.next_expr = expr_name

    def _goto_expr(self, expr_name):
        self._prev_expr = self.active_expr
        self._param_trans = True; self._param_trans_time = 0.0
        self._param_trans_from = self.current.copy()
        rule = AnimationDirector.TRANSITION_RULES
        key = (self._prev_expr, expr_name)
        r = rule.get(key) or rule.get(('any', expr_name)) or rule.get((self._prev_expr, 'any'))
        if r: self._param_trans_dur = r['duration']; self._param_easing = r['easing']
        else: self._param_trans_dur = 0.35; self._param_easing = 'ease_out_quad'
        self.phase = 'intro' if 'intro_target' in self._exprs.get(expr_name, {}) else 'loop'
        self.active_expr = expr_name; self.next_expr = None; self.phase_time = 0
        self.speak_t = 0; self.sleepy_breathe = 0; self.blink_timer = 0
        self.trigger_gimbal(expr_name)
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
                if self.phase in ('intro', 'loop'): self.phase = 'loop'; self.phase_time = 0
                self.blink_timer = 0; self.next_blink = random.uniform(2.5, 5)
        elif (self.active_expr not in ('sleepy', 'blink') and
              self.blink_timer > self.next_blink and self.interact_cooldown <= 0):
            self.blink_phase = 1; self.blink_frame_time = 0
            self.is_blinking = True; self.phase_time = 0; self.blink_timer = 0
        # 随机视线
        if self.interact_cooldown <= 0: self.gaze_timer += dt
        if (self.gaze_timer > self.next_gaze and
            self.active_expr in ('idle', 'curious', 'bored', 'relaxed', 'smile')
            and self.blink_phase == 0):
            self.gaze_timer = 0; self.next_gaze = random.uniform(8, 20)
            self.trigger(random.choice(['look_left', 'look_right', 'look_up']))
        # 随机停顿
        if self.pause_active:
            self.pause_timer += dt
            if self.pause_timer > self.pause_duration:
                self.pause_active = False; self.pause_timer = 0
                self.current.l_open = 1.0; self.current.r_open = 1.0; self.pause_cooldown = 0
        else:
            self.pause_cooldown += dt
            if (self.pause_cooldown > self.next_pause and self.active_expr == 'idle' and
                self.blink_phase == 0 and self.interact_cooldown <= 0):
                self.pause_active = True; self.pause_timer = 0
                self.pause_duration = random.uniform(0.5, 1.5)
                self.next_pause = random.uniform(20, 60); self.pause_cooldown = 0
        # 随机wink
        if self.active_expr not in ('blink', 'wink', 'sleepy'):
            self.wink_timer += dt
            if self.wink_timer > self.next_wink:
                self._goto_expr('wink'); self.wink_timer = 0
                self.next_wink = random.uniform(15, 35)

        if self.phase == 'intro': self._update_intro(dt)
        elif self.phase == 'loop': self._update_loop(dt)
        elif self.phase == 'tail': self._update_tail(dt)

        if self.is_blinking:
            self.current.lerp(self._blink, 0.30 if self.blink_phase in (1, 3) else 0.25)
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
                defn = self._exprs[self.active_expr]
                if self.phase == 'intro': spd = defn.get('intro_speed', 0.10)
                elif self.phase == 'tail': spd = defn.get('tail_speed', 0.08)
                else: spd = 0.05
                self.current.lerp(target, spd)

    def _update_intro(self, dt):
        defn = self._exprs[self.active_expr]
        target = defn['intro_target']; spd = defn.get('intro_speed', 0.10)
        self.current.lerp(target, spd)
        if self.current.is_close(target): self.phase = 'loop'; self.phase_time = 0

    def _update_loop(self, dt):
        defn = self._exprs[self.active_expr]
        if defn.get('loop_dynamic'):
            if self.active_expr == 'sleepy':
                self.sleepy_breathe += dt
                base = 0.12 + 0.08 * math.sin(self.sleepy_breathe * 0.6)
                self.current.l_open = base; self.current.r_open = base * 0.9
            elif self.active_expr == 'excited':
                j = 0.08 * math.sin(self.phase_time * 8)
                self.current.l_open = 1.3 + j; self.current.r_open = 1.3 - j
            elif self.active_expr == 'thinking':
                cycle = math.sin(self.phase_time * 1.2)
                self.current.l_open = 0.7 + cycle * 0.15
                self.current.r_open = 0.6 - cycle * 0.1
            elif self.active_expr == 'speaking':
                self.speak_t += dt
                b = math.sin(self.speak_t * math.pi * 5)
                self.current.l_open = 0.85 + 0.15 * b
                self.current.r_open = 0.85 - 0.10 * b
            elif self.active_expr == 'idle':
                if self._breath_params_cb:
                    period, amp = self._breath_params_cb()
                    freq = 2 * math.pi / max(0.5, period)
                else: freq, amp = 0.8, 0.02
                breath = math.sin(self.idle_bounce * freq) * amp
                micro = math.sin(self.idle_bounce * 3.1) * 0.005
                self.current.l_open = 1.0 + breath + micro
                self.current.r_open = 1.0 + breath - micro
        loop_dur = defn.get('loop_duration', 999)
        if self.phase_time > loop_dur:
            tail_target = defn.get('tail_target')
            if tail_target is not None:
                self.phase = 'tail'; self.phase_time = 0
                if self.active_expr == 'sleepy': self.active_expr = 'surprised'
            else: self._goto_expr('idle'); self.phase = 'loop'; self.next_state_time = random.uniform(2, 4)

    def _update_tail(self, dt):
        defn = self._exprs[self.active_expr]
        tail_target = defn.get('tail_target', self._idle_p)
        spd = defn.get('tail_speed', 0.08)
        self.current.lerp(tail_target, spd)
        if self.current.is_close(tail_target):
            if self.active_expr == 'sleepy':
                self.active_expr = 'surprised'; self.phase = 'intro'; self.phase_time = 0
            elif self.next_expr: self._goto_expr(self.next_expr)
            else: self._goto_expr('idle'); self.phase = 'loop'; self.next_state_time = random.uniform(2, 4)

    def update_auto(self, dt):
        if not self.auto_mode or self.active_expr not in ('idle',): return
        if self.phase != 'loop': return
        self.next_state_time += dt
        if self.next_state_time > self.idle_next_time:
            self.next_state_time = 0; self.idle_next_time = random.uniform(2, 5)
            self._pick_next_idle()

    def _pick_next_idle(self):
        r = random.random()
        if r < 0.18: self._goto_expr('look_left')
        elif r < 0.36: self._goto_expr('look_right')
        elif r < 0.48: self._goto_expr('look_up')
        elif r < 0.58: self._goto_expr('happy')
        elif r < 0.65: self._goto_expr('smile')
        elif r < 0.72: self._goto_expr('curious')
        elif r < 0.78: self._goto_expr('thinking')
        elif r < 0.83: self._goto_expr('confused')
        elif r < 0.87: self._goto_expr('speaking'); self.speak_t = 0
        elif r < 0.92: self._goto_expr('sleepy'); self.sleepy_breathe = 0
        else: self._goto_expr('bored')

    def _get_current_target(self):
        defn = self._exprs.get(self.active_expr, {})
        if self.phase == 'intro': return defn.get('intro_target', self._idle_p)
        elif self.phase == 'loop': return defn.get('loop_target', self._idle_p)
        elif self.phase == 'tail': return defn.get('tail_target', self._idle_p)
        return self._idle_p

'''

# Insert StateMachine code before the last few blank lines
with open('/home/johnf/xiaoq/face_base.py', 'w') as f:
    f.writelines(base_lines[:end_perf])
    f.write(sm_code)

print('StateMachine added to face_base.py')

# 2. Update face_cute.py - replace CuteFace.init to use parametrized StateMachine
with open('/home/johnf/xiaoq/face_cute.py') as f:
    cute = f.read()

# The CuteFace class already imports StateMachine from face_base via:
# from face_base import FaceModule, Params, Easing, SquashStretch,
#     AnimationDirector, PerfMonitor
# We need to add StateMachine to this import

# Update the import line
cute = cute.replace(
    'from face_base import FaceModule, Params, Easing, SquashStretch, AnimationDirector, PerfMonitor',
    'from face_base import FaceModule, Params, Easing, SquashStretch, AnimationDirector, PerfMonitor, StateMachine'
)

# Also update CuteFace.init to pass idle_p and blink
old_init = '''    def init(self, screen):
        self.screen = screen
        self.style = CuteStyle()
        self.sm = StateMachine(EXPRESSIONS)
        self.squash = SquashStretch()'''

new_init = '''    def init(self, screen):
        self.screen = screen
        self.style = CuteStyle()
        self.sm = StateMachine(EXPRESSIONS, idle_p=IDLE_P, blink=BLINK)
        self.squash = SquashStretch()'''

cute = cute.replace(old_init, new_init)

with open('/home/johnf/xiaoq/face_cute.py', 'w') as f:
    f.write(cute)

print('face_cute.py updated')

# 3. Fix face_neon.py - make it import StateMachine from face_base too
# Since face_neon has its own StateMachine already, it should still work
# But remove the duplicate if any

print('Fix complete!')
