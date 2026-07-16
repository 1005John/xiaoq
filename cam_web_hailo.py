#!/usr/bin/env python3
"""
摄像头实时视频 + Hailo 人脸检测 Web 服务
使用与小Q相同的 Hailo 人脸检测管线
通过浏览器访问 http://<ip>:5000 查看实时视频和识别结果
"""

import os
import sys
import cv2
import time
import queue
import threading
import logging
from flask import Flask, Response, render_template_string
from picamera2 import Picamera2

# 加载 hailo-apps
_HAILO_ROOT = os.path.expanduser("~/hailo-apps")
if _HAILO_ROOT not in sys.path:
    sys.path.insert(0, _HAILO_ROOT)

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import hailo

from hailo_apps.python.core.common.core import (
    get_pipeline_parser, get_resource_path,
    handle_list_models_flag, configure_multi_model_hef_path, resolve_hef_paths,
)
from hailo_apps.python.core.gstreamer.gstreamer_app import GStreamerApp, app_callback_class
from hailo_apps.python.core.gstreamer.gstreamer_helper_pipelines import (
    INFERENCE_PIPELINE, INFERENCE_PIPELINE_WRAPPER,
    TRACKER_PIPELINE, USER_CALLBACK_PIPELINE,
)
from hailo_apps.python.core.common.defines import (
    RESOURCES_SO_DIR_NAME, FACE_RECOGNITION_PIPELINE,
    FACE_DETECTION_POSTPROCESS_SO_FILENAME,
    FACE_DETECTION_JSON_NAME, RESOURCES_JSON_DIR_NAME,
    SCRFD_10G_POSTPROCESS_FUNCTION, SCRFD_2_5G_POSTPROCESS_FUNCTION,
    HAILO8_ARCH, HAILO10H_ARCH, HAILO8L_ARCH,
)

app = Flask(__name__)

# 全局变量
frame_lock = threading.Lock()
output_frame = None
face_count = 0
fps_value = 0.0
face_detections = []  # 存储检测结果

W, H = 640, 480
FPS = 15

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("cam_web_hailo")


class _CallbackData(app_callback_class):
    def __init__(self):
        super().__init__()


def _hailo_callback(element, buf, udata):
    """Hailo 检测回调"""
    global face_detections
    
    if buf is None:
        return
    try:
        roi = hailo.get_roi_from_buffer(buf)
        dets = roi.get_objects_typed(hailo.HAILO_DETECTION)
    except Exception:
        return
    
    results = []
    for d in dets:
        if d.get_label() != "face":
            continue
        b = d.get_bbox()
        results.append({
            "bbox": (b.xmin(), b.ymin(), b.xmax(), b.ymax()),
            "confidence": d.get_confidence()
        })
    
    face_detections = results


class HailoFaceDetector(GStreamerApp):
    """Hailo 人脸检测管线"""
    
    def __init__(self):
        self._callback_data = _CallbackData()
        
        parser = get_pipeline_parser()
        parser.add_argument("--mode", default='run')
        configure_multi_model_hef_path(parser)
        handle_list_models_flag(parser, FACE_RECOGNITION_PIPELINE)
        parser.set_defaults(input="rpi", arch=None, show_fps=False,
                          width=W, height=H, frame_rate=FPS)
        
        super().__init__(parser, self._callback_data)
        
        if self.arch in (HAILO8_ARCH, HAILO10H_ARCH):
            self.det_func = SCRFD_10G_POSTPROCESS_FUNCTION
        elif self.arch == HAILO8L_ARCH:
            self.det_func = SCRFD_2_5G_POSTPROCESS_FUNCTION
        
        self.post_so = get_resource_path(
            pipeline_name=None, resource_type=RESOURCES_SO_DIR_NAME,
            arch=self.arch, model=FACE_DETECTION_POSTPROCESS_SO_FILENAME)
        
        models = resolve_hef_paths(
            hef_paths=self.options_menu.hef_path,
            app_name=FACE_RECOGNITION_PIPELINE, arch=self.arch)
        self.hef_det = models[0].path
        
        self.app_callback = _hailo_callback
        self.create_pipeline()
    
    def get_pipeline_string(self):
        src = self.get_source_pipeline()
        det = INFERENCE_PIPELINE(
            hef_path=self.hef_det, post_process_so=self.post_so,
            post_function_name=self.det_func, batch_size=1,
            config_json=get_resource_path(
                pipeline_name=None, resource_type=RESOURCES_JSON_DIR_NAME,
                arch=self.arch, model=FACE_DETECTION_JSON_NAME))
        wrap = INFERENCE_PIPELINE_WRAPPER(det)
        trk = TRACKER_PIPELINE(class_id=-1, kalman_dist_thr=0.7, iou_thr=0.8,
                               init_iou_thr=0.9, keep_new_frames=2,
                               keep_tracked_frames=6, keep_lost_frames=8,
                               keep_past_metadata=True, name='face_trk')
        cb = USER_CALLBACK_PIPELINE()
        return f'{src} ! {wrap} ! {trk} ! {cb} ! queue ! fakesink sync=false'


def capture_and_detect():
    """捕获帧并使用 Hailo 进行人脸检测"""
    global output_frame, face_count, fps_value, face_detections
    
    # 初始化 Hailo 检测器
    detector = HailoFaceDetector()
    
    # 启动检测管线
    def run_pipeline():
        detector.run()
    
    pipeline_thread = threading.Thread(target=run_pipeline, daemon=True)
    pipeline_thread.start()
    
    # 等待管线启动
    time.sleep(2)
    
    # 初始化 picamera2 用于显示
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"size": (W, H), "format": "RGB888"},
        buffer_count=2
    )
    picam2.configure(config)
    picam2.start()
    
    frame_count = 0
    start_time = time.time()
    
    log.info("开始捕获和检测...")
    
    while True:
        # 捕获帧
        frame = picam2.capture_array()
        
        # 上下翻转
        frame = cv2.flip(frame, 0)
        
        # 获取检测结果
        detections = face_detections.copy()
        face_count = len(detections)
        
        # 绘制检测框
        for det in detections:
            xmin, ymin, xmax, ymax = det["bbox"]
            # 转换为像素坐标
            x1 = int(xmin * W)
            y1 = int(ymin * H)
            x2 = int(xmax * W)
            y2 = int(ymax * H)
            
            # 绘制边界框
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # 绘制置信度
            conf = det["confidence"]
            label = f"Face: {conf:.2f}"
            cv2.putText(frame, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # 计算 FPS
        frame_count += 1
        elapsed = time.time() - start_time
        if elapsed >= 1.0:
            fps_value = round(frame_count / elapsed, 1)
            frame_count = 0
            start_time = time.time()
        
        # 显示信息
        cv2.putText(frame, f"Faces: {face_count}  FPS: {fps_value}",
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # 编码为 JPEG
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        
        with frame_lock:
            output_frame = buffer.tobytes()


def generate():
    """生成 MJPEG 流"""
    global output_frame
    
    while True:
        with frame_lock:
            if output_frame is None:
                time.sleep(0.1)
                continue
            frame = output_frame
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.03)  # ~30fps 上限


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>小Q Hailo 人脸检测</title>
    <style>
        body {
            background: #1a1a2e;
            color: #eee;
            font-family: 'Segoe UI', sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }
        h1 {
            color: #00d4ff;
            margin-bottom: 10px;
        }
        .info {
            display: flex;
            gap: 30px;
            margin-bottom: 15px;
            font-size: 18px;
        }
        .info span {
            background: #16213e;
            padding: 8px 20px;
            border-radius: 8px;
            border: 1px solid #0f3460;
        }
        .highlight {
            color: #00ff88;
            font-weight: bold;
        }
        img {
            border: 3px solid #0f3460;
            border-radius: 10px;
            box-shadow: 0 0 30px rgba(0, 212, 255, 0.3);
        }
        .badge {
            background: #e94560;
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 14px;
            margin-left: 10px;
        }
    </style>
</head>
<body>
    <h1>🎥 小Q Hailo 人脸检测 <span class="badge">HAILO-8L</span></h1>
    <div class="info">
        <span>人脸数: <span id="faces" class="highlight">0</span></span>
        <span>FPS: <span id="fps" class="highlight">0</span></span>
    </div>
    <img src="/video_feed" width="640" height="480">
    <script>
        setInterval(() => {
            fetch('/status')
                .then(r => r.json())
                .then(d => {
                    document.getElementById('faces').textContent = d.faces;
                    document.getElementById('fps').textContent = d.fps;
                });
        }, 500);
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/video_feed')
def video_feed():
    return Response(generate(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/status')
def status():
    return {"faces": face_count, "fps": fps_value}


if __name__ == '__main__':
    # 启动捕获和检测线程
    t = threading.Thread(target=capture_and_detect, daemon=True)
    t.start()
    
    print("=" * 50)
    print("Hailo 人脸检测 Web 服务已启动")
    print("访问: http://0.0.0.0:5000")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, threaded=True)
