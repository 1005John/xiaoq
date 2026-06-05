#!/usr/bin/env python3
"""
舵机云台控制驱动 v4
ID=0: 水平舵机 (左右)
ID=1: 垂直舵机 (上下)
通信协议: #<ID>P<位置>T<时间>!
位置范围: 500~2500 (对应 0~180度)
"""

import serial
import time
import sys


class GimbalController:
    MIN_POS = 500
    MAX_POS = 2500
    MIN_ANGLE = 0
    MAX_ANGLE = 180
    
    def __init__(self, port='/dev/ttyAMA4', baudrate=115200, pan_id=0, tilt_id=1):
        self.port = port
        self.baudrate = baudrate
        self.pan_id = pan_id
        self.tilt_id = tilt_id
        self.ser = None
    
    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            print(f'[OK] 串口已连接: {self.port}')
            return True
        except Exception as e:
            print(f'[ERROR] 连接失败: {e}')
            return False
    
    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print('[OK] 串口已关闭')
    
    def angle_to_pos(self, angle):
        angle = max(self.MIN_ANGLE, min(self.MAX_ANGLE, angle))
        return int(self.MIN_POS + (angle - self.MIN_ANGLE) * (self.MAX_POS - self.MIN_POS) / (self.MAX_ANGLE - self.MIN_ANGLE))
    
    def _send(self, cmd):
        if not self.ser or not self.ser.is_open:
            return
        self.ser.write((cmd + '\r\n').encode('ascii'))
        self.ser.flush()
        print(f'[TX] {cmd}')
    
    def pan(self, angle, time_ms=1000):
        pos = self.angle_to_pos(angle)
        self._send(f'#{self.pan_id:03d}P{pos}T{time_ms}!')
        time.sleep(time_ms / 1000.0 + 0.1)
    
    def tilt(self, angle, time_ms=1000):
        pos = self.angle_to_pos(angle)
        self._send(f'#{self.tilt_id:03d}P{pos}T{time_ms}!')
        time.sleep(time_ms / 1000.0 + 0.1)
    
    def move_to(self, pan_angle, tilt_angle, time_ms=1000, blocking=True):
        """移动舵机，blocking=False 时只发送指令不阻塞（适合动画循环中使用）"""
        p1 = self.angle_to_pos(pan_angle)
        p2 = self.angle_to_pos(tilt_angle)
        self._send(f'#{self.pan_id:03d}P{p1}T{time_ms}!#{self.tilt_id:03d}P{p2}T{time_ms}!')
        if blocking:
            time.sleep(time_ms / 1000.0 + 0.1)
    
    def center(self, time_ms=1000):
        self.move_to(90, 150, time_ms)


def interactive():
    print('='*40)
    print('  舵机云台交互控制')
    print('='*40)
    print('p <角度>   - 水平旋转 (ID=0)')
    print('t <角度>   - 垂直旋转 (ID=1)')
    print('pt <p> <t> - 同时控制')
    print('center     - 回中位')
    print('q          - 退出')
    
    ctrl = GimbalController()
    if not ctrl.connect():
        return
    
    while True:
        try:
            cmd = input('gimbal> ').strip()
            if not cmd:
                continue
            if cmd in ('q', 'quit', 'exit'):
                break
            
            parts = cmd.split()
            if parts[0] == 'p' and len(parts) >= 2:
                ctrl.pan(int(parts[1]), int(parts[2]) if len(parts) >= 3 else 1000)
            elif parts[0] == 't' and len(parts) >= 2:
                ctrl.tilt(int(parts[1]), int(parts[2]) if len(parts) >= 3 else 1000)
            elif parts[0] == 'pt' and len(parts) >= 3:
                ctrl.move_to(int(parts[1]), int(parts[2]), int(parts[3]) if len(parts) >= 4 else 1000)
            elif parts[0] == 'center':
                ctrl.center()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f'错误: {e}')
    
    ctrl.disconnect()


if __name__ == '__main__':
    interactive()
