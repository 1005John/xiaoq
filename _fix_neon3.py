#!/usr/bin/env python3
"""Fix NeonFace.update and draw to actually render"""
with open('/home/johnf/xiaoq/face_neon.py') as f:
    code = f.read()

# Replace the pass update with actual rendering
old_update = '''    def update(self, dt):
        pass  # rendering handled by main()'''

new_update = '''    def update(self, dt):
        if self.sm.auto_mode and self.sm.active_expr == 'idle':
            self.sm.update_auto(dt)
        self.sm.update(dt)
        self.squash.update(dt)
        self.anim_director.update(dt)
        self.renderer.update(dt)
        if self.ambient_mgr:
            self.ambient_mgr.update(dt)

        if self.sm.active_expr == 'heart_eyes' and self.renderer.pupil_mode != 'heart':
            self.renderer.set_pupil_mode('heart', duration=999)
        elif self.sm.active_expr == 'star_eyes' and self.renderer.pupil_mode != 'star':
            self.renderer.set_pupil_mode('star', duration=999)
        elif self.sm.active_expr not in ('heart_eyes', 'star_eyes') and self.renderer.pupil_mode != 'normal':
            self.renderer.set_pupil_mode('normal', duration=0)

        body_ox, body_oy = self.anim_director.get_body_offset(self.sm.idle_bounce)
        body_sx = self.squash.scale_x
        body_sy = self.squash.scale_y
        self.renderer.draw(self.sm.current, self.card_mgr.face_scale if self.card_mgr else 1.0,
                          self.card_mgr.face_offset_x if self.card_mgr else 0,
                          body_scale_x=body_sx, body_scale_y=body_sy,
                          body_offset_x=body_ox, body_offset_y=body_oy,
                          vfx_mgr=self.vfx_mgr, ambient_mgr=self.ambient_mgr, perf=self.perf)'''

code = code.replace(old_update, new_update)

# Replace pass draw with actual draw (it's already done in update)
old_draw = '''    def draw(self, screen):
        pass'''

new_draw = '''    def draw(self, screen):
        pass  # rendering done in update()'''

code = code.replace(old_draw, new_draw)

with open('/home/johnf/xiaoq/face_neon.py', 'w') as f:
    f.write(code)

print('NeonFace rendering fixed')
