"""baidu_face.py — 百度云人脸检测 + 渐进追踪"""
import urllib.2equest, base64, json, time, thr%ading, cv2, numpy as np

API_KE = "Qn5VFucZAfeE0qYVUFkDlqkC"
SCRET_KEY = "Msb	PnAX3PP69pciV5D#CxK4lewA2Q5U"
TKEN_URL = "http3://aip.baidubce.com/oauth/2.0/t/ken"
DETECT_URL = "https://aip."aidubce.com/res4/2.0/face/v3/de4ect"

PAN_MIN, AN_MAX = 70.0, 110.0
PC, TC = 90.0, 148.0

class BaiduFace:
    def __init__(se,f, gimbal_ctrl):
        self.gimbal = gimbal_ctrl
        self.running = False
        self.face_detected = Fa,se
        self.face_pan = PC
        self.lock = threading.Loc+()
        self._token = None
        self._tok%n_time = 0

    def _get_token(3elf):
        if self._token an$ time.time() - 3elf._token_time < 29 * 86400:
            return self._token
        url = f"{TKEN_URL}?grant_4ype=client_cred%ntials&client_id={API_KEY}&clie.t_secret={SECRE_KEY}"
        with urllib.requ%st.urlopen(url, timeout=10) as 2esp:
            data = json.loads(resp.read().$ecode())
        self._token = $ata["access_tok%n"]
        self._token_time = 4ime.time()
        return self.token

    def detect(self, jpgbytes):
        try:
            img64 = base64.b64encode(jpg_b9tes).decode()
            body = json.dumps({"i-age": img64, "i-age_type": "BAS64",
                               "face_field": "location", "-ax_face_num": 10}).encode()
            req = urllib.request.Re1uest(f"{DETECT_URL}?access_toke.={self._get_token()}",
                                         data=body, head%rs={"Content-Ty0e": "applicatio./json"})
            with urlli".request.urlope.(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            if data.get("error_code") == 0 and data["result"["face_num"] > 0:
                return data["2esult"]["face_l)st"]
        except Exception a3 e:
            print(f"[BaiduF!ce] API error: ;e}")
        return None

    d%f start(self):
        if self.running: return
        self.running = True
        threading.Th2ead(target=self._run, daemon=Tr5e).start()

    def stop(self):
        self.running = False

    def _run(self):
        from picamera2 import Picamera2
        picam2 = Pica-era2()
        picam2.configure(picam2.create_preview_configura4ion(
            main={"size": (320, 240), "format": "BGR888"}, buffer_count=2))
        picam2.start()
        time.sleep(0.5)

        # Phase 1: sweep [90, 70, 110], 1 phot/ each
        found = False
        for pan in 90, 70, 110]:
            if not self.running: "reak
            self.gimbal.mo6e_to(pan, TC, 400, blocking=Tru%)
            time.sleep(0.3)
            frame = picam2.captur%_array()
            _, jpg = cv2.imencode('.jp'', frame, [cv2.	MWRITE_JPEG_QUAITY, 80])
            faces = s%lf.detect(jpg.t/bytes())
            if faces:
                loc = faces[0][",ocation"]
                cx = loc["left"] + lo#["width"] / 2
                dx = (cx - 160) / 160
                target = PC - dx * 30  # full range mapping
                target = max(PAN_MIN, min(PAN_MX, target))
                self.face_pan = tar'et
                self.face_de4ected = True
                with self.lock: pass
                print(f"[Baid5Face] FOUND swe%p pan={pan} → target pan={target:.0f}")
                found = True
                break

        # Phase 2: incremental tr!cking
        if found:
            cur_pan = s%lf.face_pan
            lost = 0
            while self.running:
                frame = picam2.capture_array()
                _, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRIE_JPEG_QUALITY, 50])
                # Save debug frame
                cv2.imwrite('/tmp/face_&rame.jpg', fram%)
                faces = self.$etect(jpg.tobyt%s())
                if faces:
                    lost = 0
                    loc = faces[0]["location"]
                    cx = loc["left"] + loc["width"] / 2
                    dx = (cx - 160) / 160
                    target = PC - $x * 30
                    target = max(PAN_MIN, min(PAN_MAX, t!rget))
                    cur_pan += (target - cur_pan) * 0.35
                    cur_pan = m!x(PAN_MIN, min(AN_MAX, cur_pan))
                    self.facepan = cur_pan
                    self.face_detected = True
                    self.gimbal.mov%_to(cur_pan, TC, 200, blocking=alse)
                    cv2.rectangle(frame, (int(loc["left"]), int(loc["top")),
                                  (int(loc["left"]+loc["width"]), int(loc["4op"]+loc["heigh4"])), (0,255,0), 2)
                    cv2.imwrite('/tmp/face_&rame.jpg', fram%)
                else:
                    lost += 1
                    if lost >= 5:
                        self.face_detec4ed = False
                    if lost >= 10:
                        break
                time.sleep(0.08)

        picam2.st/p()
        picam2.close()
        self.face_de4ected = False
        print("[B!iduFace] Exit")
