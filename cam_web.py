#!/usr/bin/env python3
"""
摄像头实时视频 + 人脸检测 Web 服务
通过浏览器访问 http://<ip>:5000 查看实时视频和识别结果
"""

import cv2
import time
import threading
from flask import Flask, Response, render_template_string
from picamera2 import Picamera2

app = Flask(__name__)

# 全局变量
frame_lock = threading.Lock()
output_frame = None
face_count = 0
fps_value = 0.0

# 初始化 picamera2
picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"size": (640, 480), "format": "RGB888"},
    buffer_count=2
)
picam2.configure(config)
picam2.start()

# 加载人脸检测器
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>小Q 摄像头</title>
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
    </style>
</head>
<body>
    <h1>🎥 小Q 摄像头实时监控</h1>
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
        }, 1000);
    </script>
</body>
</html>
"""


def capture_loop():
    """持续捕获帧并进行人脸检测"""
    global output_frame, face_count, fps_value
    
    face_cascade_local = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    )
    
    frame_count = 0
    start_time = time.time()
    
    while True:
        # 捕获帧
        frame = picam2.capture_array()
        frame = cv2.flip(frame, 0)
        
        # 转灰度用于检测
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        
        # 人脸检测
        faces = face_cascade_local.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )
        
        face_count = len(faces)
        
        # 绘制检测框
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, f"Face", (x, y - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # 计算 FPS
        frame_count += 1
        elapsed = time.time() - start_time
        if elapsed >= 1.0:
            fps_value = round(frame_count / elapsed, 1)
            frame_count = 0
            start_time = time.time()
        
        # 显示信息
        cv2.putText(frame, f"Faces: {face_count}  FPS: {fps_value}",
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        
        # 编码为 JPEG
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        
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
        time.sleep(0.05)  # ~20fps 上限


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
    # 启动捕获线程
    t = threading.Thread(target=capture_loop, daemon=True)
    t.start()
    
    print("=" * 50)
    print("摄像头 Web 服务已启动")
    print("访问: http://0.0.0.0:5000")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, threaded=True)
