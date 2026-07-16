#!/usr/bin/env python3
"""Fix: add on_expression_change to CuteRenderer"""
with open('/home/johnf/xiaoq/face_cute.py') as f:
    code = f.read()

# Add on_expression_change method before the draw method
old = '''    def draw(self, state, face_scale=1.0, offset_x=0, offset_y=0,
             body_sx=1.0, body_sy=1.0, body_ox=0, body_oy=0,
             ambient_mgr=None, perf=None):'''

new = '''    def on_expression_change(self, expr_name):
        """Called when expression changes - store expression name for renderer"""
        self._current_expr = expr_name

    def draw(self, state, face_scale=1.0, offset_x=0, offset_y=0,
             body_sx=1.0, body_sy=1.0, body_ox=0, body_oy=0,
             ambient_mgr=None, perf=None):'''

code = code.replace(old, new)

# Also ensure _current_expr is initialized
old_init = '''    def __init__(self, screen):
        self.screen = screen
        self.face_center_x = WIDTH // 2'''

new_init = '''    def __init__(self, screen):
        self.screen = screen
        self.face_center_x = WIDTH // 2
        self._current_expr = 'idle' '''

code = code.replace(old_init, new_init)

with open('/home/johnf/xiaoq/face_cute.py', 'w') as f:
    f.write(code)

print('fix applied')
