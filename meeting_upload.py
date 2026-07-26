#!/usr/bin/env python3
"""LAN upload service for XiaoQ meeting recordings."""

from __future__ import annotations

import hmac
import html
import json
import os
import secrets
import threading
import time
from urllib.parse import quote
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename


ROOT = Path(os.environ.get("XIAOQ_MEETING_ROOT", "/home/johnf/xiaoq/data/meetings"))
INBOX = ROOT / "inbox"
OUTPUT = ROOT / "output"
JOBS = ROOT / "jobs"
TOKEN_PATH = ROOT.parent / "meeting_upload_token"
PORT = int(os.environ.get("XIAOQ_MEETING_PORT", "8787"))
ALLOWED_EXTENSIONS = {".m4a", ".mp3", ".wav", ".aac", ".ogg", ".wma"}

for directory in (INBOX, OUTPUT, JOBS):
    directory.mkdir(parents=True, exist_ok=True)


def load_token() -> str:
    if not TOKEN_PATH.exists():
        TOKEN_PATH.write_text(secrets.token_urlsafe(24), encoding="utf-8")
        TOKEN_PATH.chmod(0o600)
    return TOKEN_PATH.read_text(encoding="utf-8").strip()


TOKEN = load_token()
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024


def authorized() -> bool:
    supplied = (request.headers.get("X-XiaoQ-Token", "") or request.form.get("token", "")
                or request.args.get("token", ""))
    return bool(supplied) and hmac.compare_digest(supplied, TOKEN)


def trigger_meeting() -> bool:
    """Ask the running XiaoQ process to consume the newest inbox recording."""
    try:
        from websockets.sync.client import connect

        with connect("ws://127.0.0.1:8766", open_timeout=3, close_timeout=3) as ws:
            ws.send(json.dumps({"type": "voice_inject", "text": "生成会议纪要"}, ensure_ascii=False))
        return True
    except Exception as exc:
        app.logger.warning("Could not trigger XiaoQ: %s", exc)
        return False


@app.get("/")
def index():
    return """<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>小Q会议录音上传</title>
<style>body{font-family:system-ui,sans-serif;max-width:620px;margin:8vh auto;padding:24px;color:#18202a}
form{display:grid;gap:16px;padding:24px;border:1px solid #d7dde5;border-radius:12px}
input,button{font:inherit;padding:12px}button{cursor:pointer;background:#1769e0;color:white;border:0;border-radius:6px}
#msg{white-space:pre-wrap}</style>
<h1>小Q会议录音</h1>
<form action="/upload" method="post" enctype="multipart/form-data">
<label>访问令牌<input name="token" type="password" required></label>
<label>录音文件<input name="file" type="file" accept="audio/*,.m4a,.mp3,.wav,.aac,.ogg,.wma" required></label>
<button type="submit">上传并生成会议纪要</button>
</form><p id="msg">上传完成后小Q会自动开始转写。</p>"""


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "xiaoq-meeting-upload"})


@app.post("/upload")
def upload():
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"ok": False, "error": "file is required"}), 400
    original = secure_filename(uploaded.filename)
    extension = Path(original).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        return jsonify({"ok": False, "error": "unsupported audio format"}), 400

    job_id = time.strftime("%Y%m%d_%H%M%S") + "_" + secrets.token_hex(4)
    final_name = f"{job_id}_{original}"
    partial_path = INBOX / f".{final_name}.part"
    final_path = INBOX / final_name
    uploaded.save(partial_path)
    os.replace(partial_path, final_path)
    metadata = {
        "job_id": job_id,
        "filename": original,
        "stored_file": final_name,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "status": "queued",
    }
    (JOBS / f"{job_id}.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    triggered = threading.Thread(target=trigger_meeting, daemon=True)
    triggered.start()
    return jsonify({"ok": True, "job_id": job_id, "filename": original, "status": "queued"}), 202


@app.get("/outputs")
def outputs():
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    files = sorted((p.name for p in OUTPUT.iterdir() if p.is_file()), reverse=True)
    return jsonify({"ok": True, "files": files})


@app.get("/results")
def results():
    if not authorized():
        return "<h2>需要访问令牌</h2><p>请在地址后附加 ?token=你的令牌</p>", 401
    token = quote(request.args.get("token", ""), safe="")
    files = sorted((p.name for p in OUTPUT.iterdir() if p.is_file()), reverse=True)
    links = "".join(
        f'<li><a href="/view/{quote(name, safe="")}?token={token}">{html.escape(name)} 在线查看</a> '
        f'<a href="/outputs/{quote(name, safe="")}?token={token}">下载</a></li>'
        if name.lower().endswith(".html") else
        f'<li><a href="/outputs/{quote(name, safe="")}?token={token}">{html.escape(name)} 下载</a></li>'
        for name in files
    ) or "<li>暂无会议纪要</li>"
    return f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>小Q会议纪要</title><style>body{{font-family:system-ui,sans-serif;max-width:720px;margin:8vh auto;padding:24px}}
li{{margin:14px 0}}a{{color:#1769e0;font-size:18px}}</style><h1>小Q会议纪要</h1><ul>{links}</ul>"""


@app.get("/view/<path:filename>")
def view_file(filename: str):
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    requested = Path(filename)
    output_root = OUTPUT.resolve()
    resolved = (OUTPUT / requested).resolve()
    if requested.name != filename or output_root not in resolved.parents or requested.suffix.lower() != ".html":
        return jsonify({"ok": False, "error": "invalid filename"}), 400
    return send_from_directory(OUTPUT, filename, as_attachment=False)


@app.get("/outputs/<path:filename>")
def output_file(filename: str):
    if not authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    requested = Path(filename)
    output_root = OUTPUT.resolve()
    resolved = (OUTPUT / requested).resolve()
    if requested.name != filename or output_root not in resolved.parents:
        return jsonify({"ok": False, "error": "invalid filename"}), 400
    return send_from_directory(OUTPUT, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
