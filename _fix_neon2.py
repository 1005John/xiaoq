#!/usr/bin/env python3
"""Add on_expression_change to neon Renderer"""
with open('/home/johnf/xiaoq/face_neon.py') as f:
    code = f.read()

# Find the Renderer class's draw method and add on_expression_change before it
old = '''    def draw_hud(self, info):'''

new = '''    def on_expression_change(self, expr_name):
        """Called from AnimationDirector on expression change"""
        self.set_neon_color(expr_name)

    def draw_hud(self, info):'''

code = code.replace(old, new)

with open('/home/johnf/xiaoq/face_neon.py', 'w') as f:
    f.write(code)

print('fixed')
