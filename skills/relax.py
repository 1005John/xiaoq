"""
skills/relax.py — 放松触点技能

从 relax.py RelaxManager 迁移。
Sidecar编排和v10 L3均可调用。

L3意图: relax → Skill "relax", params: {"action": "wooden_fish"}
L3意图: relax_stop → Skill "relax", params: {"action": "stop"}
side_effects: set_ambient(mode="woodfish"), card_show(type="relax")
"""

import asyncio
import logging
import os
import subprocess
import webbrowser
from .base import Skill, SkillResult, SideEffect

log = logging.getLogger("skills.relax")

RELAX_HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>敲木鱼 — 放松一下</title>
<style>
body { margin:0; display:flex; justify-content:center; align-items:center;
       min-height:100vh; background:#1a1a2e; color:#e0e0e0;
       font-family: system-ui, sans-serif; flex-direction:column; }
.fish { width:120px; height:120px; border-radius:50%; background:#8B4513;
        display:flex; align-items:center; justify-content:center;
        font-size:48px; cursor:pointer; transition: transform 0.1s;
        box-shadow: 0 4px 20px rgba(139,69,19,0.4); user-select:none; }
.fish:active { transform: scale(0.9); }
.counter { font-size:24px; margin-top:20px; color:#ffa500; }
.hint { font-size:14px; margin-top:10px; color:#888; }
.particle { position:fixed; pointer-events:none; animation: float 1.5s ease-out forwards;
            font-size:18px; }
@keyframes float { 0%{opacity:1;transform:translateY(0)} 100%{opacity:0;transform:translateY(-80px)} }
</style>
</head>
<body>
<div class="fish" id="fish" onclick="knock()">&#129424;</div>
<div class="counter">功德: <span id="cnt">0</span></div>
<div class="hint">点击木鱼积累功德 &#128591;</div>
<script>
let cnt = 0;
function knock() {
  cnt++;
  document.getElementById('cnt').textContent = cnt;
  const p = document.createElement('div');
  p.className = 'particle';
  p.textContent = '&#10024;';
  p.style.left = (Math.random()*60+20) + '%';
  p.style.top = '40%';
  document.body.appendChild(p);
  setTimeout(() => p.remove(), 1500);
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain); gain.connect(ctx.destination);
    osc.frequency.value = 800 + Math.random()*200;
    osc.type = 'sine';
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
    osc.start(); osc.stop(ctx.currentTime + 0.3);
  } catch(e) {}
}
</script>
</body>
</html>"""


class RelaxSkill(Skill):
    """放松触点技能 — 敲木鱼H5 / 背景音乐 / 停止"""
    
    name = "relax"
    description = "放松触点 (敲木鱼/音乐/停止)"
    
    def __init__(self, cfg: dict = None):
        super().__init__(cfg)
        self.assets_dir = self.cfg.get("assets_dir", "assets")
        self._html_path = os.path.join(self.assets_dir, "relax.html")
        self._ensure_assets()

    def _ensure_assets(self):
        os.makedirs(self.assets_dir, exist_ok=True)
        if not os.path.exists(self._html_path):
            with open(self._html_path, "w") as f:
                f.write(RELAX_HTML)
            log.info(f"Created relax page: {self._html_path}")

    async def open_relax_page(self):
        log.info(f"Opening relax page: {self._html_path}")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: webbrowser.open(f"file://{os.path.abspath(self._html_path)}"))

    async def play_music(self, path: str = None):
        if path and os.path.exists(path):
            log.info(f"Playing music: {path}")
            subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def execute(self, params: dict = None) -> SkillResult:
        """执行放松操作
        
        params:
          action: "wooden_fish" | "music" | "stop" (默认 wooden_fish)
          music_path: str (music时必填)
        """
        params = params or {}
        action = params.get("action", "wooden_fish")

        if action == "stop":
            # 停止木鱼/放松
            return SkillResult(
                success=True,
                data={"action": "stop"},
                side_effects=[
                    SideEffect("set_ambient", {"mode": "none"}),
                    SideEffect("card_hide", {}),
                    SideEffect("voice_tts", {"text": "好的，收一下～"}),
                ],
            )

        if action == "wooden_fish":
            return SkillResult(
                success=True,
                data={"action": "wooden_fish"},
                side_effects=[
                    SideEffect("set_ambient", {"mode": "woodfish"}),
                    SideEffect("voice_tts", {"text": "敲木鱼时间到，放松一下～"}),
                    SideEffect("trigger_squash", {"type": "happy"}),
                ],
            )

        elif action == "music":
            path = params.get("music_path", "")
            if path and os.path.exists(path):
                return SkillResult(
                    success=True,
                    data={"action": "music", "path": path},
                    side_effects=[
                        SideEffect("voice_tts", {"text": "来点音乐放松一下～"}),
                    ],
                )
            else:
                return SkillResult(
                    success=False,
                    error="music_path not provided or file not found",
                )

        else:
            return SkillResult(success=False, error=f"Unknown action: {action}")
