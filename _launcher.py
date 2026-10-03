#!/usr/bin/env python3
"""Launch main.py with proper display env"""
import os, subprocess, sys
env = os.environ.copy()
env['DISPLAY'] = ':0'
env['XAUTHORITY'] = '/home/johnf/.Xauthority'
os.chdir('/home/johnf/xiaoq')
subprocess.run([sys.executable, 'main.py'], env=env)
