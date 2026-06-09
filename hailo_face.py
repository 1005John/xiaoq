"""hailo_face.py — Hailo-8L 端侧人脸检测 + 渐进追踪 (替代 baidu_face.py)

与 baidu_face.py 接口一致，robot_face_v11.py 只需改一行 import。
"""

import time
import queue
import threading
import sys
import os

# 确保 hailo-apps 和本地模块在 PYTHONPATH
sys.path.insert(0, os.path.expanduser("~/hailo-apps"))
sys.path.insert(0, os.path.expanduser("~"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hailo_face_pipeline import HailoFacePipeline

PAN_MIN, PAN_MAX = 70.0, 110.0
TILT_MIN, TILT_MAX = 138.0, 162.0
PC, TC = 90.0, 150.0


class HailoFace:
    """与 BaiduFace 完全一致的接口, 内部使用 Hailo-8L SCRFD 2.5G"""

    def __init__(self, gimbal_ctrl):
        self.gimbal = gimbal_ctrl
        self.running = False
        self.face_detected = False
        self.face_pan = PC
        self.face_tilt = TC
        self.lock = threading.Lock()

        self._pipeline = None
        self._queue = queue.Queue(maxsize=5)
        self._track_thread = None

    def start(self):
        if self.running:
            return
        self.running = True

        # 启动 Hailo 推理管线
        self._pipeline = HailoFacePipeline(self._queue)
        self._pipeline.start()

        # 启动追踪线程
        self._track_thread = threading.Thread(
            target=self._run_tracking, daemon=True, name="hailo-track"
        )
        self._track_thread.start()

    def stop(self):
        self.running = False
        if self._pipeline:
            self._pipeline.stop()
            self._pipeline = None
        self.face_detected = False

    # ── 追踪线程 ────────────────────────────────────────

    def _run_tracking(self):
        """渐进追踪逻辑, 复用 BaiduFace 的追踪策略"""

        # Phase 1: sweep [90, 70, 110] 找脸
        found = False
        if self.gimbal:
            for pan in [90, 70, 110]:
                if not self.running:
                    break
                self.gimbal.move_to(pan, TC, 400, blocking=True)
                # 在当前角度等 1.5s, 期间检查 queue
                t0 = time.time()
                while time.time() - t0 < 1.5:
                    if not self.running:
                        break
                    try:
                        detections = self._queue.get(timeout=0.2)
                        if detections:
                            try:
                                target_pan, target_tilt = self._face_to_angles(detections)
                            except Exception as e:
                                print(f"[HailoFace] _face_to_angles error: {e}, detections={detections}")
                                continue
                            if target_pan is not None:
                                self.face_pan = target_pan
                                self.face_tilt = target_tilt
                                self.face_detected = True
                                print(f"[HailoFace] FOUND sweep pan={pan} "
                                      f"-> pan={target_pan:.0f} tilt={target_tilt:.0f}")
                                found = True
                                break
                    except queue.Empty:
                        pass
                if found:
                    break

        # Phase 2: incremental tracking (pan + tilt)
        if found:
            cur_pan = float(self.face_pan)
            cur_tilt = float(self.face_tilt)
            lost = 0

            while self.running:
                try:
                    detections = self._queue.get(timeout=0.15)
                except queue.Empty:
                    detections = None

                if detections:
                    lost = 0
                    try:
                        target_pan, target_tilt = self._face_to_angles(detections)
                    except Exception as e:
                        print(f"[HailoFace] _face_to_angles error: {e}")
                        continue
                    if target_pan is not None:
                        target_pan = max(PAN_MIN, min(PAN_MAX, target_pan))
                        target_tilt = max(TILT_MIN, min(TILT_MAX, target_tilt))
                        # 渐进追踪
                        cur_pan += (target_pan - cur_pan) * 0.35
                        cur_tilt += (target_tilt - cur_tilt) * 0.35
                        cur_pan = max(PAN_MIN, min(PAN_MAX, cur_pan))
                        cur_tilt = max(TILT_MIN, min(TILT_MAX, cur_tilt))
                        self.face_pan = cur_pan
                        self.face_tilt = cur_tilt
                        self.face_detected = True
                        if self.gimbal:
                            self.gimbal.move_to(
                                int(cur_pan), int(cur_tilt), 200, blocking=False)
                else:
                    lost += 1
                    if lost >= 5:
                        self.face_detected = False
                    if lost >= 20:  # ~3s 无脸 → 放弃
                        break

                time.sleep(0.05)

        # 清理
        self.face_detected = False
        self.stop()
        print("[HailoFace] Exit")

    def _face_to_angles(self, detections):
        """检测结果 → (pan, tilt) 角度"""
        if not detections:
            return None, None
        best = max(detections, key=lambda d: d.confidence)
        if best.confidence < 0.3:
            return None, None
        bbox = best.bbox
        cx = (bbox[0] + bbox[2]) / 2.0  # 归一化 0~1
        cy = (bbox[1] + bbox[3]) / 2.0
        # 偏离画面中心 → 角度偏移
        dx = (cx - 0.5) / 0.5  # -1.0 ~ +1.0
        dy = (cy - 0.5) / 0.5
        target_pan = PC - dx * 20   # max ±20°
        target_tilt = TC + dy * 12  # max ±12° (垂直范围小)
        return target_pan, target_tilt
