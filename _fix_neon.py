#!/usr/bin/env python3
"""Fix NeonFace.init() to create its own objects"""
with open('/home/johnf/xiaoq/face_neon.py') as f:
    code = f.read()

old_init = '''    def init(self, screen):
        self.screen = screen
        self.style = StyleConfig()
        self.renderer = Renderer(screen)
        self.sm = sm  # Will be set by caller
        self.card_mgr = CardManager()
        self.vfx_mgr = None
        self.ambient_mgr = None
        self.squash = squash_stretch
        self.anim_director = anim_director
        self.perf = perf
        self.sm.auto_mode = True
        self.show_hud = False'''

new_init = '''    def init(self, screen):
        from face_base import SquashStretch, AnimationDirector, PerfMonitor, StateMachine
        self.screen = screen
        self.style = StyleConfig()
        self.sm = StateMachine(EXPRESSIONS, idle_p=IDLE_P, blink=BLINK)
        self.squash = SquashStretch()
        self.anim_director = AnimationDirector(self.squash)
        self.perf = PerfMonitor()
        self.renderer = Renderer(screen)
        self.anim_director.set_renderer(self.renderer)
        self.card_mgr = CardManager()
        self.vfx_mgr = None
        self.ambient_mgr = AmbientManager(WIDTH // 2, HEIGHT // 2)
        self.sm._on_expr_change = self._on_expr_change
        self.sm._breath_params_cb = self.anim_director.get_breath_params
        self.sm.auto_mode = True
        self.show_hud = False'''

code = code.replace(old_init, new_init)

# Also add _on_expr_change method
old_class_end = '''    def handle_mousebuttonup(self, pos):
        self.sm.interact_cooldown = random.uniform(2, 3)'''

new_class_end = '''    def _on_expr_change(self, expr_name):
        self.anim_director.on_expression_change(expr_name)
        mood_map = {
            'idle': 'idle', 'happy': 'happy', 'laugh': 'happy', 'excited': 'excited',
            'smile': 'happy', 'relaxed': 'idle', 'sad': 'sad', 'angry': 'angry',
            'surprised': 'surprised', 'scared': 'scared', 'sleepy': 'sleepy',
            'bored': 'idle', 'curious': 'curious', 'thinking': 'focus',
            'confused': 'curious', 'heart_eyes': 'love', 'star_eyes': 'excited',
            'speaking': 'happy',
        }
        mood = mood_map.get(expr_name)
        if mood and self.ambient_mgr:
            self.ambient_mgr.set_mood(mood)

    def handle_mousebuttonup(self, pos):
        self.sm.interact_cooldown = random.uniform(2, 3)'''

code = code.replace(old_class_end, new_class_end)

with open('/home/johnf/xiaoq/face_neon.py', 'w') as f:
    f.write(code)

print('NeonFace fixed')
