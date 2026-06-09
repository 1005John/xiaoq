#!/usr/bin/env python3
"""快速测试 Hailo Face Pipeline v2 — 使用 hailo-apps 框架"""
import queue
import time
import sys
import os

# 加载 hailo-apps 环境
sys.path.insert(0, os.path.expanduser("~/hailo-apps"))
sys.path.insert(0, os.path.expanduser("~"))
sys.path.insert(0, '/home/johnf/gimbal_control')

from hailo_face_pipeline import HailoFacePipeline, FaceDetection

print("Starting Hailo Face Pipeline v2 test...")
q = queue.Queue(maxsize=5)

pipeline = HailoFacePipeline(q)
pipeline.start()

# 等待启动
print("Waiting for pipeline to start (5s)...")
time.sleep(5)

print("Scanning for faces (15 seconds)... Please look at camera!")
start = time.time()
detection_count = 0
last_print = 0

while time.time() - start < 15:
    try:
        detections = q.get(timeout=0.3)
        now = time.time()
        if detections and now - last_print > 0.5:
            print(f"\n=== Frame {detection_count+1} ===")
            for d in detections:
                print(f"  Track#{d.track_id} conf={d.confidence:.2f} "
                      f"bbox=({d.bbox[0]:.3f},{d.bbox[1]:.3f},{d.bbox[2]:.3f},{d.bbox[3]:.3f})")
            last_print = now
            detection_count += 1
    except queue.Empty:
        pass

print(f"\nTotal face detections: {detection_count}")
pipeline.stop()
print("Test complete!")
