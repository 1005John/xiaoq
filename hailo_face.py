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

PAN_MIN, PAN_MAX = 50.0, 130.0
TILT_MIN, TILT_MAX = 138.0, 162.0
PC, TC = 90.0, 145.0


class HailoFace:
    """Hailo face detector plus optional enrolled-person following."""

    def __init__(self, gimbal_ctrl, frame_callback=None, registry=None):
        self.gimbal = gimbal_ctrl
        self.frame_callback = frame_callback
        self.registry = registry
        self.running = False
        self.face_detected = False
        self.following_target = False
        self.face_pan = PC
        self.face_tilt = TC
        self.lock = threading.Lock()
        # Once the selected identity has been confirmed, keep following its
        # Hailo tracker ID between ArcFace refreshes. ArcFace is intentionally
        # sampled at a lower rate than detection, so requiring a fresh vector
        # on every frame makes the gimbal fall back to expressions.
        self._locked_track_id: int | None = None
        self._last_follow_log = 0.0

        self._pipeline = None
        self._queue = queue.Queue(maxsize=5)
        self._track_thread = None

    def start(self):
        if self.running:
            return
        self.running = True

        # 启动 Hailo 推理管线
        self._pipeline = HailoFacePipeline(self._queue, self._on_pipeline_frame, self.registry)
        self._pipeline.start()

        # 启动追踪线程
        self._track_thread = threading.Thread(
            target=self._run_tracking, daemon=True, name="hailo-track"
        )
        self._track_thread.start()

    def _on_pipeline_frame(self, frame, detections):
        """Forward every camera frame; a face box is optional."""
        self._record_active_identity_match(detections)
        if self.frame_callback is None:
            return
        try:
            best = self._choose_target(detections)
            bbox = best.bbox if best is not None and best.confidence >= 0.3 else None
            self.frame_callback(frame, bbox)
        except Exception as exc:
            print(f"[HailoFace] frame callback error: {exc}")

    def _record_active_identity_match(self, detections):
        """Refresh authorization only when ArcFace sees the App-selected face."""
        if not self.registry:
            return
        active_person_id = self.registry.active_person_id()
        if not active_person_id:
            return
        matches = [item for item in detections if item.person_id == active_person_id]
        if not matches:
            return
        best = max(matches, key=lambda item: item.identity_score)
        self.registry.record_authorization(best.person_id, best.person_name, best.identity_score)

    def stop(self):
        self.running = False
        if self._pipeline:
            self._pipeline.stop()
            self._pipeline = None
        self.face_detected = False
        self.following_target = False
        self._locked_track_id = None

    # ── 追踪线程 ────────────────────────────────────────

    def _run_tracking(self):
        """渐进追踪逻辑, 复用 BaiduFace 的追踪策略"""
        # Keep cycling between sweep and tracking. A single missed sweep must
        # not permanently disable the pipeline or the P/T status HUD.
        while self.running:
            found = False
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break

            # Phase 1: sweep [90, 70, 110] 找脸
            if self.gimbal:
                for pan in [90, 70, 110]:
                    if not self.running:
                        break
                    # Slow the search sweep for smoother, less abrupt motion.
                    self.gimbal.move_to(pan, TC, 1000, blocking=True)
                    t0 = time.time()
                    while time.time() - t0 < 1.5 and self.running:
                        try:
                            detections = self._queue.get(timeout=0.2)
                        except queue.Empty:
                            continue
                        if not detections:
                            continue
                        try:
                            target_pan, target_tilt = self._face_to_angles(detections)
                        except Exception as exc:
                            print(f"[HailoFace] _face_to_angles error: {exc}, detections={detections}")
                            continue
                        if target_pan is not None:
                            self.face_pan = target_pan
                            self.face_tilt = target_tilt
                            self.face_detected = True
                            self.following_target = True
                            print(f"[HailoFace] FOUND sweep pan={pan} "
                                  f"-> pan={target_pan:.0f} tilt={target_tilt:.0f}")
                            found = True
                            break
                    if found:
                        break

            if not self.running:
                break
            if not found:
                self.face_detected = False
                self.following_target = False
                time.sleep(0.2)
                continue

            # Phase 2: incremental tracking (pan + tilt)
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
                    except Exception as exc:
                        print(f"[HailoFace] _face_to_angles error: {exc}")
                        continue
                    if target_pan is None:
                        # Other people can remain in frame after the selected
                        # person leaves.  They must not keep target ownership.
                        lost += 1
                        self.face_detected = False
                        self.following_target = False
                        if lost >= 20:
                            break
                        time.sleep(0.05)
                        continue
                    target_pan = max(PAN_MIN, min(PAN_MAX, target_pan))
                    target_tilt = max(TILT_MIN, min(TILT_MAX, target_tilt))
                    cur_pan += (target_pan - cur_pan) * 0.25
                    cur_tilt += (target_tilt - cur_tilt) * 0.25
                    cur_pan = max(PAN_MIN, min(PAN_MAX, cur_pan))
                    cur_tilt = max(TILT_MIN, min(TILT_MAX, cur_tilt))
                    self.face_pan = cur_pan
                    self.face_tilt = cur_tilt
                    self.face_detected = True
                    self.following_target = True
                    if self.gimbal:
                        self.gimbal.move_to(int(cur_pan), int(cur_tilt), 200, blocking=False)
                    now = time.monotonic()
                    if now - self._last_follow_log >= 2.0:
                        self._last_follow_log = now
                        print(f"[HailoFace] FOLLOW track={self._locked_track_id or 0} "
                              f"pan={cur_pan:.0f} tilt={cur_tilt:.0f}")
                else:
                    lost += 1
                    if lost >= 5:
                        self.face_detected = False
                        self.following_target = False
                    if lost >= 20:  # ~3s 无脸 -> 重新扫描
                        break
                time.sleep(0.05)

            self.face_detected = False
            self.following_target = False
            time.sleep(0.1)

        self.face_detected = False
        self.following_target = False
        print("[HailoFace] Exit")

    def _choose_target(self, detections):
        """Return the requested enrolled person, or preserve legacy behavior."""
        if not detections:
            return None
        active_person_id = self.registry.active_person_id() if self.registry else None
        if active_person_id:
            if self._locked_track_id is not None:
                locked = [item for item in detections if item.track_id == self._locked_track_id]
                if locked:
                    return max(locked, key=lambda item: item.confidence)
            candidates = [item for item in detections if item.person_id == active_person_id]
            if candidates:
                best = max(candidates, key=lambda item: item.identity_score)
                self._locked_track_id = best.track_id
                return best
            return None
        self._locked_track_id = None
        return max(detections, key=lambda item: item.confidence)

    def _face_to_angles(self, detections):
        """检测结果 → (pan, tilt) 角度"""
        if not detections:
            return None, None
        best = self._choose_target(detections)
        if best is None:
            return None, None
        if best.confidence < 0.3:
            return None, None
        bbox = best.bbox
        cx = (bbox[0] + bbox[2]) / 2.0  # 归一化 0~1
        cy = (bbox[1] + bbox[3]) / 2.0
        # 偏离画面中心 → 角度偏移
        dx = (cx - 0.5) / 0.5  # -1.0 ~ +1.0
        dy = (cy - 0.5) / 0.5
        target_pan = PC - dx * 15   # max ±20°
        target_tilt = TC + dy * 12  # max ±12° (垂直范围小)
        return target_pan, target_tilt
