#!/usr/bin/env python3
"""
人脸位置 → 舵机角度 平滑追踪

功能:
- 从检测队列读取最新 FaceDetection 列表
- 人脸 bbox → 画面偏移 → 舵机角度偏移
- EMA 平滑 + 死区 + 速度钳位，避免云台抖动
- 人脸丢失超时后自动回中
"""

import time
import logging
from typing import List, Optional

log = logging.getLogger("gimbal_tracker")


class GimbalTracker:
    """基于人脸检测结果的舵机平滑追踪器

    坐标系约定:
      bbox: (xmin, ymin, xmax, ymax) 归一化 0~1
      pan:  水平旋转, 增大 = 右转
      tilt: 垂直旋转, 增大 = 上仰
    """

    def __init__(self, gimbal_controller,
                 pan_center: float = 90,
                 tilt_center: float = 150,
                 pan_range: tuple = (50, 130),
                 tilt_range: tuple = (120, 170),
                 dead_zone: float = 0.06,
                 smoothing: float = 0.25,
                 max_track_speed: float = 0.6,
                 lose_timeout: float = 2.0,
                 move_threshold: float = 2.0):
        """
        Args:
            gimbal_controller: GimbalController 实例
            pan_center: 水平中位角度 (度)
            tilt_center: 垂直中位角度 (度)
            pan_range: 水平允许范围 (min, max)
            tilt_range: 垂直允许范围 (min, max)
            dead_zone: 死区 (人脸偏离画面中心比例, 0~0.5)
                       此范围内不触发舵机移动
            smoothing: EMA 平滑系数 (0=无平滑, 0.3=较强)
            max_track_speed: 最大追踪速度 (度/秒, 用于钳位)
            lose_timeout: 检测丢失超时(秒), 超时后回中
            move_threshold: 最小移动角度(度), 小于此值不发送指令
        """
        self.gimbal = gimbal_controller
        self.pan_center = pan_center
        self.tilt_center = tilt_center
        self.pan_min, self.pan_max = pan_range
        self.tilt_min, self.tilt_max = tilt_range
        self.dead_zone = dead_zone
        self.smoothing = smoothing
        self.max_track_speed = max_track_speed
        self.lose_timeout = lose_timeout
        self.move_threshold = move_threshold

        # EMA 平滑状态
        self._pan_ema = float(pan_center)
        self._tilt_ema = float(tilt_center)

        # 目标角度
        self._target_pan = float(pan_center)
        self._target_tilt = float(tilt_center)

        # 追踪状态
        self._last_seen_time: float = 0.0
        self._last_sent_pan: float = float(pan_center)
        self._last_sent_tilt: float = float(tilt_center)
        self._last_update_time: float = 0.0
        self._active: bool = False
        self._enabled: bool = True

    # ── 公开接口 ────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, val: bool):
        if not val and self._enabled:
            # 禁用时回中
            self._set_target(self.pan_center, self.tilt_center)
            self._update_servo(force=True)
        self._enabled = val

    @property
    def is_tracking(self) -> bool:
        return self._active

    def toggle(self):
        """切换启用/禁用"""
        self.enabled = not self._enabled
        return self._enabled

    def update(self, detections: Optional[List]):
        """每帧调用 (在主线程约 60fps)

        Args:
            detections: List[FaceDetection] 或 None
        """
        if not self._enabled:
            return

        now = time.time()
        dt = now - self._last_update_time if self._last_update_time > 0 else 0.016
        self._last_update_time = now

        if not detections:
            self._active = False
            # 超时回中
            if (now - self._last_seen_time > self.lose_timeout
                    and self._last_seen_time > 0):
                self._set_target(self.pan_center, self.tilt_center)
            self._update_servo()
            return

        # 选择置信度最高的人脸
        best = max(detections, key=lambda d: d.confidence)
        self._last_seen_time = now
        self._active = True

        # 人脸中心 (归一化 0~1)
        face_cx = (best.bbox[0] + best.bbox[2]) / 2.0
        face_cy = (best.bbox[1] + best.bbox[3]) / 2.0

        # 偏离画面中心 (-0.5 ~ +0.5)
        offset_x = face_cx - 0.5
        offset_y = face_cy - 0.5

        # 死区
        if abs(offset_x) < self.dead_zone:
            offset_x = 0.0
        else:
            offset_x = offset_x - (self.dead_zone if offset_x > 0
                                   else -self.dead_zone)
        if abs(offset_y) < self.dead_zone:
            offset_y = 0.0
        else:
            offset_y = offset_y - (self.dead_zone if offset_y > 0
                                   else -self.dead_zone)

        # 偏移 → 角度 delta
        # offset_x > 0: 人脸偏右 → pan 增大 (云台右转)
        # offset_y > 0: 人脸偏下 → tilt 减小 (云台下俯)
        pan_delta = offset_x * (self.pan_max - self.pan_min) * 0.8
        tilt_delta = -offset_y * (self.tilt_max - self.tilt_min) * 0.8

        # 速度钳位
        max_delta = self.max_track_speed * dt
        pan_delta = max(-max_delta, min(max_delta, pan_delta))
        tilt_delta = max(-max_delta, min(max_delta, tilt_delta))

        self._set_target(
            self.pan_center + pan_delta,
            self.tilt_center + tilt_delta,
        )
        self._update_servo()

    # ── 内部方法 ────────────────────────────────────────

    def _set_target(self, pan: float, tilt: float):
        """设置目标角度并钳位"""
        self._target_pan = max(self.pan_min, min(self.pan_max, pan))
        self._target_tilt = max(self.tilt_min, min(self.tilt_max, tilt))

    def _update_servo(self, force: bool = False):
        """EMA 平滑 + 发送舵机指令"""
        # EMA
        alpha = 1.0 - self.smoothing
        self._pan_ema += alpha * (self._target_pan - self._pan_ema)
        self._tilt_ema += alpha * (self._target_tilt - self._tilt_ema)

        current_pan = self._pan_ema
        current_tilt = self._tilt_ema

        # 移动阈值
        if not force:
            if (abs(current_pan - self._last_sent_pan) < self.move_threshold
                    and abs(current_tilt - self._last_sent_tilt) < self.move_threshold):
                return

        self._last_sent_pan = current_pan
        self._last_sent_tilt = current_tilt

        if self.gimbal:
            pan_int = int(round(current_pan))
            tilt_int = int(round(current_tilt))
            self.gimbal.move_to(pan_int, tilt_int, time_ms=80, blocking=False)
