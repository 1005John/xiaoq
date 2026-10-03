#!/usr/bin/env python3
"""PC 端文件接收服务 — 保存到 D:\\XiaoQ_Share

XiaoQ (Pi1) 上 MW 生成的 PPT/文件会自动 curl 上传到这个服务。
需要保持运行，关机后重启执行：python xiaoq_share_server.py
"""
import os, time
from http.server import HTTPServer, BaseHTTPRequestHandler

SAVE_DIR = os.environ.get("XIAOQ_SHARE_DIR", "D:\\XiaoQ_Share")
PORT = int(os.environ.get("XIAOQ_SHARE_PORT", "9998"))
os.makedirs(SAVE_DIR, exist_ok=True)

class FileHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """健康检查"""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"XiaoQ Share Server OK")

    def do_POST(self):
        """接收文件上传"""
        content_length = int(self.headers.get("Content-Length", 0))
        filename = ""
        if "?" in self.path:
            params = self.path.split("?")[1]
            for param in params.split("&"):
                if param.startswith("filename="):
                    import urllib.parse
                    filename = urllib.parse.unquote(param.split("=")[1])
                    filename = filename.replace("/", "_").replace("\\", "_")
        if not filename:
            filename = "upload_" + str(int(time.time()))
        filepath = os.path.join(SAVE_DIR, filename)
        data = self.rfile.read(content_length)
        with open(filepath, "wb") as f:
            f.write(data)
        print(f"[File] {filename} ({len(data)} bytes)")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(f'{{"ok":true,"filename":"{filename}","size":{len(data)}}}'.encode())

if __name__ == "__main__":
    print(f"XiaoQ Share Server on http://0.0.0.0:{PORT}")
    print(f"Save to: {SAVE_DIR}")
    HTTPServer(("0.0.0.0", PORT), FileHandler).serve_forever()
