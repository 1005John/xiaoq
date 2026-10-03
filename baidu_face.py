"""baidu_face.py — 百度云人脸检测 + 渐进追踪"""
import urllib.request, base64, json, time, threading, cv2, numpy as np

API_KEY = "Qn5VFucZAfeE0qYVUFkDlqkC"
SECRET_KEY = "MsbIPnAX3PP69pciV5DcCxK4lewA2Q5U"
TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
DETECT_URL = "https://aip.baidubce.com/rest/2.0/face/v3/detect"

PAN_MIN, PAN_MAX = 70.0, 110.0
PC, TC = 90.0, 148.0

class BaiduFace:
    def __init__(self, gimbal_ctrl):
        self.gimbal = gimbal_ctrl
        self.running = False
        self.face_detected = False
        self.face_pan = PC
        self.lock = threading.Lock()
        self._token = None
        self._token_time = 0

    def _get_token(self):
        if self._token and time.time() - self._token_time < 29 * 86400:
            return self._token
        url = f"{TOKEN_URL}?grant_type=client_credentials&client_id={API_KEY}&client_secret={SECRET_KEY}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        self._token = data["access_token"]
        self._token_time = time.time()
        return self._token

    def detect(self, jpg_bytes):
        try:
            img64 = base64.b64encode(jpg_bytes).decode()
            body = json.dumps({"image": img64, "image_type": "BASE64",
                               "face_field": "location", "max_face_num": 10}).encode()
            req = urllib.request.Request(f"{DETECT_URL}?access_token={self._get_token()}",
                                         data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            if data.get("error_code") == 0 and data["result"]["face_num"] > 0:
                return data["result"]["face_list"]
        except Exception as e:
            print(f"[BaiduFace] API error: {e}")
        return None

    def start(self):
        if self.running: return
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self.running = False

    def _run(self):
        from picamera2 import Picamera2
        picam2 = Picamera2()
        picam2.configure(picam2.create_preview_configuration(
            main={"size": (640, 480), "format": "BGR888"}, buffer_count=2))
        picam2.start()
        time.sleep(0.5)

        # Phase 1: sweep [90, 70, 110], 1 photo each
        found = False
        for pan in [90, 70, 110]:
            if not self.running: break
            self.gimbal.move_to(pan, TC, 400, blocking=True)
            for _ in range(3):
                time.sleep(0.1)
                if not self.running: break
                frame = picam2.capture_array()
                _, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                faces = self.detect(jpg.tobytes())
                if faces:
                    loc = faces[0]["location"]
                    cx = loc["left"] + loc["width"] / 2
                    dx = (cx - 320) / 320
                    target = PC - dx * 30
                    target = max(PAN_MIN, min(PAN_MAX, target))
                    self.face_pan = target
                    self.face_detected = True
                    print(f"[BaiduFace] FOUND sweep pan={pan} -> target pan={target:.0f}")
                    found = True
                    break
            if found: break

        # Phase 2: incremental tracking with speed prediction
        if found:
            cur_pan = self.face_pan
            lost = 0
            prev_cx = None
            while self.running:
                frame = picam2.capture_array()
                _, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                # Save debug frame
                cv2.imwrite('/tmp/face_frame.jpg', frame)
                faces = self.detect(jpg.tobytes())
                if faces:
                    lost = 0
                    loc = faces[0]["location"]
                    cx = loc["left"] + loc["width"] / 2
                    dx = (cx - 320) / 320
                    target = PC - dx * 30
                    target = max(PAN_MIN, min(PAN_MAX, target))
                    cur_pan += (target - cur_pan) * 0.35
                    cur_pan = max(PAN_MIN, min(PAN_MAX, cur_pan))
                    self.face_pan = cur_pan
                    self.face_detected = True
                    self.gimbal.move_to(cur_pan, TC, 200, blocking=False)
                    cv2.rectangle(frame, (int(loc["left"]), int(loc["top"])),
                                  (int(loc["left"]+loc["width"]), int(loc["top"]+loc["height"])), (0,255,0), 2)
                    cv2.imwrite('/tmp/face_frame.jpg', frame)
                else:
                    lost += 1
                    if lost >= 5:
                        self.face_detected = False
                    if lost >= 10:
                        break
                time.sleep(0.08)

        picam2.stop()
        picam2.close()
        self.face_detected = False
        print("[BaiduFace] Exit")
