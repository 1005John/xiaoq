#!/usr/bin/env python3
"""
camera_proxy.py — 主进程侧的摄像头子进程代理

通过 subprocess 运行 camera_worker.py，用 JSON 行协议通信。
替代直接在主进程里创建 HailoFace（避免 picamera2 segfault）。
"""

import json, subprocess, threading, queue, os, time, sys

CAMERA_WORKER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "camera_worker.py")


class CameraProxy:
    """与 camera_worker 子进程通信的代理类"""

    def __init__(self, gimbal=None):
        self.proc = None
        self._lock = threading.Lock()
        self._events = queue.Queue(maxsize=100)
        self._last_face = None  # (pan, tilt, track_id, name, score)
        self._frame_path = "/dev/shm/xiaoq_camera_latest.jpg"
        self._running = False
        # 兼容 HailoFace 的属性
        self.face_pan = 90.0
        self.face_tilt = 145.0
        self.face_detected = False
        self.following_target = False
        self.gimbal = gimbal  # 主进程的云台控制器
        self._track_thread = None
        # 平滑跟踪参数
        self._cur_pan = 90.0      # 当前云台角度
        self._cur_tilt = 145.0    # 当前云台倾斜
        self._dead_zone = 0.08    # 死区：人脸中心偏离画面中心 <8% 不移动
        self._follow_gain = 0.25  # 跟踪增益（每次移动 25% 距离，避免振荡）
        self._last_move_time = 0.0  # 上次移动时间
        self._min_move_interval = 0.15  # 最小移动间隔 150ms
        self._frame_path = "/dev/shm/xiaoq_camera_latest.jpg"
        self._running = False
        # 兼容 HailoFace 的属性
        self.face_pan = 90.0
        self.face_tilt = 145.0
        self.face_detected = False
        self.following_target = False

    def start(self):
        """启动子进程"""
        with self._lock:
            if self.proc is not None:
                return True
            try:
                self.proc = subprocess.Popen(
                    ["python3", CAMERA_WORKER_PATH],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )
                # 启动读取线程
                t = threading.Thread(target=self._read_loop, daemon=True, name="cam-read")
                t.start()
                # 等待 ready
                # 等待 ready 事件（跳过 gimbal_fail 等非关键事件）
                for _ in range(10):
                    try:
                        evt = self._events.get(timeout=15)
                        ev = evt.get("event", "")
                        if ev == "ready":
                            self._running = True
                            print("[Camera] worker ready", flush=True)
                            return True
                        elif ev in ("gimbal_fail", "gimbal_ok"):
                            print(f"[Camera] gimbal: {evt.get('msg', 'ok')}", flush=True)
                            continue
                        else:
                            print(f"[Camera] event: {evt}", flush=True)
                            continue
                    except queue.Empty:
                        print("[Camera] worker timeout", flush=True)
                        break
                self.stop()
                return False
            except Exception as e:
                print(f"[Camera] start error: {e}", flush=True)
                self.proc = None
                return False

    def _read_loop(self):
        """读取子进程 stdout"""
        while self.proc and self.proc.poll() is None:
            try:
                line = self.proc.stdout.readline()
                if not line:
                    break
                evt = json.loads(line.strip())
                # 处理事件
                ev = evt.get("event", "")
                if ev == "face_detected":
                    self.face_pan = float(evt.get("pan", 90.0))
                    self.face_tilt = float(evt.get("tilt", 145.0))
                    self.face_detected = True
                    self.following_target = True
                    bbox = evt.get("bbox", [0.5, 0.5, 0.5, 0.5])
                    # 计算人脸中心偏离量
                    cx = (bbox[0] + bbox[2]) / 2.0
                    cy = (bbox[1] + bbox[3]) / 2.0
                    dx = abs(cx - 0.5)
                    dy = abs(cy - 0.5)
                    # 死区：偏离 <8% 不移动云台
                    if dx < self._dead_zone and dy < self._dead_zone:
                        # 人脸在中心区域，不移动
                        pass
                    else:
                        # 平滑跟踪：每次移动 25% 距离
                        import time as _t
                        now = _t.monotonic()
                        if now - self._last_move_time >= self._min_move_interval:
                            self._last_move_time = now
                            # 平滑插值
                            self._cur_pan += (self.face_pan - self._cur_pan) * self._follow_gain
                            self._cur_tilt += (self.face_tilt - self._cur_tilt) * self._follow_gain
                            # 限制范围
                            self._cur_pan = max(50.0, min(130.0, self._cur_pan))
                            self._cur_tilt = max(138.0, min(162.0, self._cur_tilt))
                            if self.gimbal:
                                try:
                                    self.gimbal.move_to(int(self._cur_pan), int(self._cur_tilt), 200, blocking=False)
                                except:
                                    pass
                    self._last_face = (
                        self.face_pan,
                        self.face_tilt,
                        evt.get("track_id", 0),
                        evt.get("name"),
                        evt.get("score", 0.0),
                    )
                elif ev == "face_lost":
                    self.face_detected = False
                    self.following_target = False
                    self._last_face = None
                # 入队列
                try:
                    self._events.put_nowait(evt)
                except queue.Full:
                    pass
            except (json.JSONDecodeError, ValueError):
                pass
            except Exception:
                pass

    def send(self, cmd):
        """发送命令到子进程"""
        with self._lock:
            if self.proc is None or self.proc.poll() is not None:
                return None
            try:
                self.proc.stdin.write(json.dumps(cmd, ensure_ascii=False) + "\n")
                self.proc.stdin.flush()
                # 等待响应
                return self._events.get(timeout=10)
            except Exception:
                return None

    def face_detected(self):
        """是否检测到人脸"""
        return self._last_face is not None

    def face_info(self):
        """返回人脸信息 (pan, tilt, track_id, name, score)"""
        return self._last_face

    def following_target(self):
        """是否正在跟随"""
        return self._last_face is not None

    def capture(self, timeout=15):
        """拍照，返回文件路径"""
        evt = self.send({"cmd": "capture"})
        if evt and evt.get("event") == "capture_done":
            return evt.get("path")
        return None

    def enroll(self, name):
        """开始注册人脸"""
        evt = self.send({"cmd": "enroll", "name": name})
        return evt

    def stop(self):
        """停止子进程"""
        with self._lock:
            self._running = False
            if self.proc:
                try:
                    self.proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
                    self.proc.stdin.flush()
                except:
                    pass
                try:
                    self.proc.terminate()
                    self.proc.wait(timeout=3)
                except:
                    try:
                        self.proc.kill()
                    except:
                        pass
                self.proc = None
            self._last_face = None

    def is_running(self):
        """子进程是否运行中"""
        return self._running and self.proc and self.proc.poll() is None

    def get_status(self):
        """获取状态"""
        evt = self.send({"cmd": "status"})
        return evt
