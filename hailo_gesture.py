"""Hailo-8L hand-landmark gesture trigger for XiaoQ.

The face pipeline supplies frames and a tracked face box, so this module never
opens Picamera2 itself.  The landmark network is intentionally used as a
secondary inference stage; the first MVP recognizes a held open palm near the
tracked face, which is a predictable photo command for the user.
"""

from __future__ import annotations

import os
import queue
import threading
import time
from pathlib import Path


class HailoPhotoGesture:
    """Detect a stable open-palm gesture from frames supplied by HailoFace."""

    PRESENCE_THRESHOLD = 0.80
    HOLD_SECONDS = 1.5

    def __init__(self, on_trigger=None, hef_path=""):
        self.on_trigger = on_trigger
        self.hef_path = hef_path or os.environ.get(
            "XIAOQ_HAND_LANDMARK_HEF",
            os.path.expanduser("~/xiaoq/models_hand_landmark_lite.hef"),
        )
        self.running = False
        self.available = False
        self.last_error = ""
        self.last_presence = 0.0
        self.last_gesture = False
        self._frames = queue.Queue(maxsize=1)
        self._latest_frame = None
        self._latest_lock = threading.Lock()
        self._thread = None
        self._positive_since = None
        self._cooldown_until = 0.0
        self._last_submit = 0.0

    def start(self):
        if self.running:
            return
        if not Path(self.hef_path).exists():
            self.last_error = f"HEF not found: {self.hef_path}"
            print(f"[Gesture] {self.last_error}")
            return
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="hailo-gesture")
        self._thread.start()

    def stop(self):
        self.running = False
        try:
            self._frames.put_nowait(None)
        except queue.Full:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        self.available = False

    def submit_frame(self, frame, face_bbox):
        """Submit a frame from HailoFace without blocking its GStreamer callback."""
        if not self.running or frame is None or face_bbox is None:
            return
        now = time.monotonic()
        if now - self._last_submit < 0.18:
            return
        self._last_submit = now
        with self._latest_lock:
            self._latest_frame = frame.copy()
        item = (frame, face_bbox)
        try:
            self._frames.put_nowait(item)
        except queue.Full:
            try:
                self._frames.get_nowait()
            except queue.Empty:
                pass
            try:
                self._frames.put_nowait(item)
            except queue.Full:
                pass

    def latest_frame(self):
        """Return a copy of the latest RGB frame for a delayed photo capture."""
        with self._latest_lock:
            return None if self._latest_frame is None else self._latest_frame.copy()

    def _run(self):
        try:
            import cv2
            import numpy as np
            from hailo_platform import (
                HEF,
                VDevice,
                HailoSchedulingAlgorithm,
                ConfigureParams,
                HailoStreamInterface,
                InferVStreams,
                InputVStreamParams,
                OutputVStreamParams,
                FormatType,
            )

            hef = HEF(self.hef_path)
            params = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
            input_name = hef.get_input_vstream_infos()[0].name
            # hailonet in hailo-apps uses the SHARED vdevice group. Reusing
            # that group is required on a single Hailo-8L physical device.
            vdevice_params = VDevice.create_params()
            vdevice_params.group_id = "SHARED"
            vdevice_params.multi_process_service = True
            vdevice_params.scheduling_algorithm = HailoSchedulingAlgorithm.ROUND_ROBIN
            with VDevice(vdevice_params) as device:
                network_group = device.configure(hef, params)[0]
                input_params = InputVStreamParams.make(network_group, format_type=FormatType.UINT8)
                output_params = OutputVStreamParams.make(network_group, format_type=FormatType.FLOAT32)
                with InferVStreams(network_group, input_params, output_params) as infer:
                    with network_group.activate():
                        self.available = True
                        print(f"[Gesture] Hailo hand landmark ready: {self.hef_path}")
                        while self.running:
                            try:
                                item = self._frames.get(timeout=0.5)
                            except queue.Empty:
                                continue
                            if item is None:
                                break
                            frame, face_bbox = item
                            observed = False
                            best_presence = 0.0
                            for crop in self._candidate_crops(frame, face_bbox, cv2):
                                resized = cv2.resize(crop, (224, 224), interpolation=cv2.INTER_LINEAR)
                                result = infer.infer({input_name: resized[None, ...].astype(np.uint8)})
                                points, presence = self._decode_result(result, np)
                                best_presence = max(best_presence, presence)
                                if presence >= self.PRESENCE_THRESHOLD and self._is_open_palm(points, np):
                                    observed = True
                                    break
                            self.last_presence = best_presence
                            self._update_stability(observed)
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            print(f"[Gesture] unavailable: {self.last_error}")
        finally:
            self.available = False

    @staticmethod
    def _candidate_crops(frame, face_bbox, cv2):
        height, width = frame.shape[:2]
        xmin, ymin, xmax, ymax = [float(value) for value in face_bbox]
        fx = ((xmin + xmax) * 0.5) * width
        fy = ((ymin + ymax) * 0.5) * height
        fw = max(80.0, (xmax - xmin) * width)
        fh = max(80.0, (ymax - ymin) * height)
        # The first version asks the user to hold an open palm beside the face.
        # Four overlapping zones cover either side, above, and below the face.
        side = max(180.0, min(520.0, max(fw, fh) * 1.35))
        centers = [
            (fx - fw * 1.1, fy),
            (fx + fw * 1.1, fy),
            (fx, fy - fh * 1.15),
            (fx, fy + fh * 1.15),
        ]
        for cx, cy in centers:
            x0 = max(0, int(cx - side * 0.5))
            y0 = max(0, int(cy - side * 0.5))
            x1 = min(width, int(cx + side * 0.5))
            y1 = min(height, int(cy + side * 0.5))
            if x1 - x0 >= 80 and y1 - y0 >= 80:
                yield frame[y0:y1, x0:x1]

    @staticmethod
    def _decode_result(result, np):
        def output(name):
            for key, value in result.items():
                if key.endswith(name):
                    return np.asarray(value).reshape(-1)
            return np.asarray([])

        landmark = output("/fc1")
        presence_values = output("/fc2")
        presence = float(presence_values[0]) if presence_values.size else 0.0
        if landmark.size < 63:
            return None, presence
        return landmark[:63].reshape(21, 3), presence

    @staticmethod
    def _is_open_palm(points, np):
        if points is None:
            return False
        xy = points[:, :2]
        if not np.isfinite(xy).all():
            return False
        # MediaPipe landmark indices: wrist 0, finger PIPs 6/10/14/18,
        # finger tips 8/12/16/20.  Requiring all four long fingers avoids
        # treating a partial hand, face contour, or casual movement as a palm.
        wrist = xy[0]
        pip_indices = (6, 10, 14, 18)
        tip_indices = (8, 12, 16, 20)
        extended = 0
        for pip_idx, tip_idx in zip(pip_indices, tip_indices):
            if np.linalg.norm(xy[tip_idx] - wrist) > np.linalg.norm(xy[pip_idx] - wrist) * 1.08:
                extended += 1
        return extended == 4

    def _update_stability(self, observed):
        now = time.monotonic()
        self.last_gesture = bool(observed)
        if observed:
            if self._positive_since is None:
                self._positive_since = now
            if now - self._positive_since >= self.HOLD_SECONDS and now >= self._cooldown_until:
                self._cooldown_until = now + 10.0
                self._positive_since = None
                print("[Gesture] open palm confirmed")
                if self.on_trigger:
                    try:
                        self.on_trigger()
                    except Exception as exc:
                        print(f"[Gesture] trigger callback failed: {exc}")
        else:
            self._positive_since = None
