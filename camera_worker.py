#!/usr/bin/env python3
"""
camera_worker.py — HailoFace 子进程包装器

在独立进程里运行 HailoFace（picamera2 + GStreamer），避免跟 XiaoQ 主进程的
pygame/TTS 线程冲突导致 segfault。

通信协议（stdin/stdout JSON 行）:
  主进程→子进程:
    {"cmd": "start"}            启动人脸检测+跟踪
    {"cmd": "stop"}             停止
    {"cmd": "capture"}          拍一帧，返回 base64 JPEG
    {"cmd": "enroll", "name": "张三"}  开始注册人脸
    {"cmd": "enroll_cancel"}    取消注册
    {"cmd": "status"}           返回当前状态

  子进程→主进程:
    {"event": "started"}        已启动
    {"event": "face_detected", "pan": 90, "tilt": 145, "track_id": 1, "name": null, "score": 0.0}
    {"event": "face_lost"}      人脸丢失
    {"event": "frame", "path": "/dev/shm/xiaoq_camera_latest.jpg"}
    {"event": "enroll_progress", "collected": 3, "required": 8}
    {"event": "enroll_done", "name": "张三", "person_id": "abc123"}
    {"event": "capture_done", "path": "/tmp/cam_capture.jpg"}
    {"event": "error", "msg": "..."}
"""

import sys, os, json, time, base64, threading, signal

# 确保模块路径 + 环境变量（跟 start_xiaoq.sh 一致）
XIAOQ_DIR = os.path.expanduser("~/xiaoq-face-auth-demo")
sys.path.insert(0, XIAOQ_DIR)
# 设置 XIAOQ_ROOT，让 FaceRegistry 用跟主进程相同的文件路径
os.environ.setdefault("XIAOQ_ROOT", XIAOQ_DIR)
os.environ.setdefault("LIBCAMERA_LOG_LEVELS", "ERROR")

# 加载 hailo-apps
_HAILO_ROOT = os.path.expanduser("~/hailo-apps")
if _HAILO_ROOT not in sys.path:
    sys.path.insert(0, _HAILO_ROOT)
_parent = os.path.dirname(_HAILO_ROOT)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

# gimbal 驱动（串口云台）
gimbal_ctrl = None
try:
    from gimbal_driver import GimbalController
    gimbal_ctrl = GimbalController()
    print(json.dumps({"event": "gimbal_ok"}), flush=True)
except Exception as e:
    print(json.dumps({"event": "gimbal_fail", "msg": str(e)}), flush=True)

# 人脸注册表
from face_identity import FaceRegistry
face_registry = FaceRegistry()

# HailoFace
try:
    from hailo_face import HailoFace
except Exception as e:
    print(json.dumps({"event": "error", "msg": f"HailoFace import failed: {e}"}), flush=True)
    sys.exit(1)

# 全局
hf = None
running = True
frame_export_path = "/dev/shm/xiaoq_camera_latest.jpg"


def send(obj):
    """发送 JSON 到 stdout"""
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def on_frame(frame, bbox):
    """HailoFace 回调：保存帧 + 发送检测结果
    bbox: (xmin, ymin, xmax, ymax) 归一化坐标 或 None
    """
    import cv2
    try:
        cv2.imwrite(frame_export_path, frame)
        send({"event": "frame", "path": frame_export_path})
    except:
        pass

    if bbox:
        # 计算云台角度（从归一化坐标）
        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0
        dx = (cx - 0.5) / 0.5
        dy = (cy - 0.5) / 0.5
        # 跟 hailo_face.py 的 _face_to_angles 一致
        pan = 90.0 - dx * 25.0
        tilt = 145.0 + dy * 12.0
        # 限制范围
        pan = max(50.0, min(130.0, pan))
        tilt = max(138.0, min(162.0, tilt))
        if hf:
            hf.face_pan = pan
            hf.face_tilt = tilt
        send({
            "event": "face_detected",
            "pan": round(pan, 1),
            "tilt": round(tilt, 1),
            "bbox": [round(float(x), 3) for x in bbox],
        })
    else:
        send({"event": "face_lost"})


def handle_cmd(cmd):
    """处理主进程命令"""
    global hf
    c = cmd.get("cmd", "")

    if c == "start":
        if hf is not None:
            send({"event": "error", "msg": "already running"})
            return
        try:
            hf = HailoFace(None, frame_callback=on_frame, registry=face_registry)
            hf.start()
            send({"event": "started"})
        except Exception as e:
            send({"event": "error", "msg": f"start failed: {e}"})

    elif c == "stop":
        if hf is not None:
            # 不调用 stop()（会导致 segfault），直接标记不运行
            hf.running = False
            hf = None
            send({"event": "stopped"})
        else:
            send({"event": "stopped"})

    elif c == "capture":
        """拍一帧"""
        import cv2
        try:
            # 从 HailoFace 的帧文件获取
            if os.path.exists(frame_export_path):
                import shutil
                dest = "/tmp/cam_capture.jpg"
                shutil.copy2(frame_export_path, dest)
                send({"event": "capture_done", "path": dest})
            else:
                # 用 picamera2 直接拍
                from picamera2 import Picamera2
                picam = Picamera2()
                picam.configure(picam.create_preview_configuration(main={"size": (640, 480)}))
                picam.start()
                time.sleep(0.5)
                frame = picam.capture_array()
                picam.stop()
                picam.close()
                dest = "/tmp/cam_capture.jpg"
                cv2.imwrite(dest, frame)
                send({"event": "capture_done", "path": dest})
        except Exception as e:
            send({"event": "error", "msg": f"capture failed: {e}"})

    elif c == "enroll":
        name = cmd.get("name", "")
        ok, msg = face_registry.start_enrollment(name)
        send({"event": "enroll_started", "ok": ok, "msg": msg})

    elif c == "enroll_cancel":
        face_registry.cancel_enrollment()
        send({"event": "enroll_cancelled"})

    elif c == "status":
        snap = face_registry.snapshot()
        send({
            "event": "status",
            "running": hf is not None,
            "face_detected": hf.face_detected if hf else False,
            "following": hf.following_target if hf else False,
            "people": snap.get("people", []),
            "active_person_id": snap.get("active_person_id"),
            "enrollment": snap.get("enrollment"),
        })

    elif c == "list_people":
        snap = face_registry.snapshot()
        send({"event": "people_list", "people": snap.get("people", [])})

    elif c == "delete_person":
        person_id = cmd.get("person_id", "")
        ok, msg = face_registry.delete(person_id)
        send({"event": "delete_done", "ok": ok, "msg": msg})

    elif c == "select_active":
        person_id = cmd.get("person_id", "")
        ok, msg = face_registry.select_active(person_id)
        # 清除 HailoFace 的锁定 track_id，避免切换后仍跟踪旧目标
        if hf is not None:
            hf._locked_track_id = None
        send({"event": "select_done", "ok": ok, "msg": msg})

    elif c == "quit":
        send({"event": "bye"})
        return False

    return True


def main():
    send({"event": "ready"})
    keep_running = True
    while keep_running:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            cmd = json.loads(line.strip())
            keep_running = handle_cmd(cmd)
        except json.JSONDecodeError:
            send({"event": "error", "msg": "invalid JSON"})
        except Exception as e:
            send({"event": "error", "msg": str(e)})

    # 清理
    if hf is not None:
        hf.running = False
    send({"event": "bye"})


if __name__ == "__main__":
    main()
