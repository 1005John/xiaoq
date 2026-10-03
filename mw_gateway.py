#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MW Agent Gateway v2 - 完整重写
使用 curl subprocess 做 SSE 流式读取
实时推送事件到浏览器
"""
import sys, time, json, http.server, threading, os, sqlite3, subprocess
import urllib.request, queue
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LISTEN_PORT = 9800
MW_TOKENS_FILE = "/home/pi/.mobilework/electron/openwork-server-tokens.json"
MW_SERVER_STATE = "/home/pi/.mobilework/electron/openwork-server-state.json"
MW_CONFIG = "/home/pi/.mobilework/config/server.json"
MW_DB = "/home/pi/.mobilework/xdg/data/opencode/opencode.db"

# 全局状态
owner_token = ""
mw_port = 35615
ws_id = ""
session_id = ""
sse_connected = False
current_status = "idle"
current_reply = ""
current_prompt = ""
initial_rowid = 0
last_events = []
event_queue = queue.Queue(maxsize=500)

def get_owner_token():
    try:
        with open(MW_TOKENS_FILE) as f:
            data = json.load(f)
        for ws_path, tokens in data.get("workspaces", {}).items():
            return tokens.get("ownerToken", "")
    except:
        pass
    return ""

def get_mw_server_port():
    try:
        with open(MW_SERVER_STATE) as f:
            data = json.load(f)
        ports = data.get("workspacePorts", {})
        for path, port in ports.items():
            if ("mobilework" in path.lower() or "MobileWork" in path) and "c:" not in path.lower():
                return port
        for path, port in ports.items():
            if "c:" not in path.lower() and "users" not in path.lower():
                return port
        return 33383
    except:
        return 33383

def get_workspace_id():
    try:
        with open(MW_CONFIG) as f:
            data = json.load(f)
        for ws in data.get("workspaces", []):
            return ws.get("id", "")
    except:
        pass
    return ""

def get_latest_local_session():
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{mw_port}/w/{ws_id}/opencode/session",
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read().decode())
        sessions = data if isinstance(data, list) else data.get("data", [])
        if sessions:
            return sessions[0].get("id", "")
    except:
        pass
    return ""

def get_db_max_rowid():
    try:
        db = sqlite3.connect(MW_DB)
        r = db.execute("SELECT MAX(rowid) FROM part").fetchone()
        db.close()
        return r[0] if r[0] else 0
    except:
        return 0

def get_db_parts_since(rowid):
    try:
        db = sqlite3.connect(MW_DB)
        rows = db.execute(
            "SELECT rowid, data FROM part WHERE rowid > ? ORDER BY rowid ASC LIMIT 200",
            (rowid,)
        ).fetchall()
        db.close()
        result = []
        for row in rows:
            d = json.loads(row[1])
            result.append({
                "rowid": row[0],
                "type": d.get("type", ""),
                "tool": d.get("tool", ""),
                "text": (d.get("text", "") or "")
            })
        return result
    except:
        return []

def get_latest_reply(rowid):
    try:
        db = sqlite3.connect(MW_DB)
        rows = db.execute(
            "SELECT data FROM part WHERE data LIKE '%\"type\":\"text\"%' ORDER BY rowid DESC LIMIT 30",
        ).fetchall()
        db.close()
        for row in rows:
            d = json.loads(row[0])
            text = d.get("text", "")
            if text and len(text.strip()) > 10 and "系统指令" not in text and "使用cmit" not in text:
                return text.strip()
        return ""
    except:
        return ""
def push_event(etype, data):
    evt = {"time": time.time(), "type": etype, "data": data}
    last_events.append(evt)
    if len(last_events) > 100:
        del last_events[:50]
    try:
        event_queue.put_nowait(evt)
    except:
        pass

def sse_loop():
    global sse_connected, current_status, current_reply
    while True:
        proc = None
        try:
            proc = subprocess.Popen(
                ["curl", "-s", "-N",
                 "-H", f"Authorization: Bearer {owner_token}",
                 f"http://127.0.0.1:{mw_port}/workspace/{ws_id}/opencode/event"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            sse_connected = True
            print(f"[SSE] Connected via curl", flush=True)
            
            while proc.poll() is None:
                line = proc.stdout.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                line = line.decode("utf-8", errors="replace").strip()
                if not line or line.startswith(":"):
                    continue
                if line.startswith("data: "):
                    raw = line[6:]
                    try:
                        d = json.loads(raw)
                        payload = d.get("payload", d)
                        etype = payload.get("type", "")
                        if etype:
                            push_event(etype, payload)
                            print(f"[SSE] {etype}", flush=True)
                            
                            if "step.started" in etype:
                                current_status = "running"
                            elif "session.idle" in etype:
                                current_status = "done"
                            
                            props = payload.get("properties", payload)
                            if "message.part" in etype or "text.delta" in etype:
                                ptext = props.get("text", "")
                                if ptext and len(ptext) > 3:
                                    current_reply = ptext[:500]
                    except:
                        pass
            
            proc.wait()
            sse_connected = False
            print("[SSE] curl exited, reconnecting...", flush=True)
        except Exception as e:
            sse_connected = False
            print(f"[SSE] Error: {str(e)[:60]}", flush=True)
            if proc:
                try:
                    proc.kill()
                except:
                    pass
        time.sleep(2)

def send_prompt_to_mw(prompt_text):
    global current_status, current_reply, current_prompt, initial_rowid, session_id
    try:
        local_sid = get_latest_local_session()
        if local_sid:
            session_id = local_sid
            print(f"[GW] Using local session: {session_id[:30]}", flush=True)
        else:
            print(f"[GW] No local session!", flush=True)
            return False
        
        body = json.dumps({"parts": [{"type": "text", "text": prompt_text}]}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{mw_port}/workspace/{ws_id}/opencode/session/{session_id}/prompt_async",
            data=body,
            headers={
                "Authorization": f"Bearer {owner_token}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        resp = urllib.request.urlopen(req, timeout=15)
        if resp.status == 204:
            current_status = "running"
            current_reply = ""
            current_prompt = prompt_text
            initial_rowid = get_db_max_rowid()
            print(f"[GW] Prompt sent!", flush=True)
            return True
    except Exception as e:
        print(f"[CMD] Error: {e}", flush=True)
    return False

class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            prompt = data.get("prompt", "") or data.get("text", "")
            if not prompt:
                self.send_json(400, {"error": "No prompt"})
                return
            
            print(f"\n[GW] Received: {prompt[:80]}", flush=True)
            
            if not sse_connected:
                self.send_json(503, {"error": "SSE not connected"})
                return
            
            success = send_prompt_to_mw(prompt)
            if success:
                self.send_json(200, {"ok": True, "session_id": session_id, "initial_rowid": initial_rowid})
            else:
                self.send_json(500, {"error": "Failed"})
        except Exception as e:
            self.send_json(500, {"error": str(e)})
    
    def do_GET(self):
        path = self.path.split("?")[0]
        
        if path == "/" or path == "/index":
            self.send_html()
        elif path == "/status":
            self.send_json(200, {
                "sse_connected": sse_connected, "status": current_status,
                "prompt": current_prompt[:80], "reply": current_reply[:200],
                "session_id": session_id
            })
        elif path == "/result":
            rowid = get_db_max_rowid()
            reply = get_latest_reply(rowid)
            self.send_json(200, {"reply": reply, "completed": current_status == "done"})
        elif path == "/events":
            self.send_json(200, {"events": last_events[-20:]})
        elif path == "/progress":
            parts = get_db_parts_since(initial_rowid)
            reply = get_latest_reply(get_db_max_rowid())
            self.send_json(200, {
                "status": current_status, "parts": parts, "reply": reply[:200],
                "initial_rowid": initial_rowid, "current_rowid": get_db_max_rowid()
            })
        elif path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"data: " + json.dumps({"type": "connected"}).encode() + b"\n\n")
            self.wfile.flush()
            while True:
                try:
                    evt = event_queue.get(timeout=15)
                    data = json.dumps({"type": evt["type"], "data": evt["data"]}, ensure_ascii=False)
                    self.wfile.write(f"data: {data}\n\n".encode())
                    self.wfile.flush()
                except:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
        else:
            self.send_json(404, {"error": "Not found"})
    
    def send_json(self, code, data):
        resp = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)
    
    def send_html(self):
        html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>MW Agent Gateway</title>
<style>
body{font-family:system-ui;max-width:900px;margin:20px auto;background:#1a1a2e;color:#e0e0e0}
input,button{padding:8px 12px;margin:5px;border:1px solid #444;border-radius:4px;background:#222;color:#fff}
button{cursor:pointer;background:#4a9;padding:8px 20px}
button:hover{background:#6bb}
#chat{margin:10px 0;padding:10px;background:#16213e;border-radius:8px;min-height:300px;max-height:500px;overflow-y:auto}
.msg{margin:8px 0;padding:8px;border-radius:4px}
.user{background:#0f3460;text-align:right}
.agent{background:#1b4332}
.progress{font-size:13px;color:#aaa;margin:2px 0;padding:4px;border-left:3px solid #4a9}
.reply{font-weight:bold;color:#5fd;background:#1b4332;padding:10px;border-radius:4px}
.step{font-size:12px;color:#8af;margin:2px 0}
.reasoning{font-size:12px;color:#fc8;margin:2px 0;font-style:italic}
#status{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px}
.idle{background:#333;color:#aaa}
.running{background:#0f3460;color:#8af}
.done{background:#1b4332;color:#5fd}
</style></head>
<body>
<h1>MW Agent Gateway</h1>
<p>SSE: <span id="sse">...</span> | Status: <span id="status" class="idle">idle</span></p>
<div>
<input id="prompt" placeholder="输入消息..." style="width:500px" onkeypress="if(event.key==='Enter')send()">
<button onclick="send()">发送</button>
</div>
<div id="chat"></div>
<script>
var ev=null;
function connectSSE(){
  ev=new EventSource('/stream');
  ev.onopen=function(){document.getElementById('sse').textContent='connected';};
  ev.onmessage=function(e){
    var d=JSON.parse(e.data);
    var t=d.type;
    var data=d.data||{};
    if(t==='connected')return;
    if(t.indexOf('step.started')>=0){
      setStatus('running');
      addProgress('step','Agent 开始处理...');
    }else if(t.indexOf('step.ended')>=0||t.indexOf('step.finish')>=0){
      addProgress('step','步骤完成');
    }else if(t.indexOf('session.idle')>=0){
      setStatus('done');
      checkResult();
    }else if(t.indexOf('reasoning')>=0){
      var text=data.properties&&data.properties.text||data.properties&&data.properties.delta||'';
      if(text)addProgress('reasoning','思考: '+text.substring(0,80));
    }else if(t.indexOf('text.delta')>=0||t.indexOf('message.part')>=0){
      var text=data.properties&&data.properties.text||data.properties&&data.properties.delta||'';
      if(text&&text.length>3){
        addProgress('reply','回复: '+text.substring(0,100));
      }
    }else if(t.indexOf('tool')>=0){
      var tool=data.properties&&data.properties.tool||'';
      if(tool)addProgress('step','工具: '+tool);
    }else if(t.indexOf('sync')<0&&t.indexOf('heartbeat')<0){
      addProgress('step','['+t+']');
    }
  };
  ev.onerror=function(){document.getElementById('sse').textContent='reconnecting...';setTimeout(connectSSE,2000);};
}
function setStatus(s){var el=document.getElementById('status');el.className=s;el.textContent=s;}
function addMsg(cls,text){var d=document.getElementById('chat');var m=document.createElement('div');m.className='msg '+cls;m.innerHTML=text;d.appendChild(m);d.scrollTop=d.scrollHeight;}
function addProgress(cls,text){var d=document.getElementById('chat');var m=document.createElement('div');m.className='progress '+cls;m.textContent=text;d.appendChild(m);d.scrollTop=d.scrollHeight;}
function send(){
  var p=document.getElementById('prompt').value;
  if(!p)return;
  addMsg('user',p);
  document.getElementById('prompt').value='';
  setStatus('running');
  fetch('/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:p})})
    .then(r=>r.json()).then(d=>{
      if(d.ok){addProgress('step','已发送到MW Agent...');}
      else{addMsg('agent','错误: '+(d.error||'error'));setStatus('idle');}
    });
}
function checkResult(){
  fetch('/result').then(r=>r.json()).then(d=>{if(d.reply)addMsg('reply','回复: '+d.reply);});
  fetch('/progress').then(r=>r.json()).then(d=>{
    if(d.parts){
      d.parts.forEach(function(p){
        var icon={'step-start':'','step-finish':'','text':'','reasoning':'','tool':''}[p.type]||'';
        if(p.text||(p.tool&&p.tool.length>0)){
          addProgress('step',icon+'['+p.type+'] '+(p.tool||'')+' '+(p.text||'').substring(0,60));
        }
      });
    }
  });
}
connectSSE();
setInterval(function(){fetch('/status').then(r=>r.json()).then(d=>{document.getElementById('sse').textContent=d.sse_connected?'connected':'disconnected';});},5000);
</script>
</body></html>"""
        resp = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)
    
    def log_message(self, *a):
        pass

class TS(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

if __name__ == "__main__":
    print("[GW] MW Agent Gateway v2 starting...", flush=True)
    
    owner_token = get_owner_token()
    mw_port = get_mw_server_port()
    ws_id = get_workspace_id()
    
    print(f"[GW] Owner token: {owner_token[:20]}...", flush=True)
    print(f"[GW] Workspace: {ws_id}", flush=True)
    
    # Wait for MW server
    for i in range(30):
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{mw_port}/w/{ws_id}/opencode/session",
                headers={"Authorization": f"Bearer {owner_token}"}
            )
            resp = urllib.request.urlopen(req, timeout=3)
            data = json.loads(resp.read().decode())
            sessions = data if isinstance(data, list) else data.get("data", [])
            if sessions:
                session_id = sessions[0].get("id", "")
                print(f"[GW] Session: {session_id[:30]}", flush=True)
                break
        except:
            pass
        time.sleep(2)
    
    # Start SSE
    sse_thread = threading.Thread(target=sse_loop, daemon=True)
    sse_thread.start()
    time.sleep(3)
    
    server = TS(("0.0.0.0", LISTEN_PORT), Handler)
    print(f"[GW] Ready! http://192.168.137.82:{LISTEN_PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
