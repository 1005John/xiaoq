"""
skills/bgm.py — BGM技能

从 sidecar.py BgmPlayer 迁移。
Sidecar编排和v10 L3均可调用。

L3意图: (无直接L3意图，Bgm由编排器触发)
Sidecar: wake_bgm / eod_bgm
side_effects: (无，BGM直接播放不走WS)
"""

import logging
import os
from .base import Skill, SkillResult, SideEffect

log = logging.getLogger("skills.bgm")


class BgmSkill(Skill):
    """BGM播放技能 — wake_bgm / eod_bgm
    
    优先 pygame.mixer，回退 simpleaudio，都没有则静默。
    音量约束: eod_bgm 音量 < TTS音量。
    """
    
    name = "bgm"
    description = "背景音乐播放 (wake_bgm/eod_bgm)"

    def __init__(self, cfg: dict = None):
        super().__init__(cfg)
        self._player = None
        self._init_player()
        # 音量上限约束 (eod_bgm不能盖过TTS)
        self.eod_volume_cap = self.cfg.get("eod_volume_cap", 0.25)

    def _init_player(self):
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self._player = "pygame"
            return
        except Exception:
            pass
        try:
            import simpleaudio
            self._player = "simpleaudio"
            return
        except Exception:
            pass
        log.info("No audio backend (pygame/simpleaudio), BGM will be silent")

    async def play(self, cfg: dict, base_dir: str = "."):
        """异步播放一段BGM
        
        cfg: {"enabled": bool, "path": str, "volume": float, "loop": bool,
              "fade_in_sec": float, "fade_out_sec": float}
        """
        if not cfg.get("enabled", False):
            log.debug("BGM skipped: enabled=false")
            return

        path = cfg.get("path", "")
        if not path:
            log.debug("BGM skipped: no path")
            return

        if not os.path.isabs(path):
            path = os.path.join(base_dir, path)

        if not os.path.isfile(path):
            log.warning(f"BGM file not found: {path}, skipping")
            return

        volume = max(0.0, min(1.0, cfg.get("volume", 0.3)))
        # eod_bgm音量约束: 不超过cap
        if cfg.get("_type") == "eod":
            volume = min(volume, self.eod_volume_cap)

        loop = cfg.get("loop", False)
        fade_in = cfg.get("fade_in_sec", 0.5)

        log.info(f"BGM playing: {path} (volume={volume:.2f}, loop={loop})")

        if self._player == "pygame":
            await self._play_pygame(path, volume, loop, fade_in)
        elif self._player == "simpleaudio":
            await self._play_simpleaudio(path, volume)

    async def _play_pygame(self, path, volume, loop, fade_in):
        import pygame
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(volume)
            loops = -1 if loop else 0
            pygame.mixer.music.play(loops, fade_ms=int(fade_in * 1000))
        except Exception as e:
            log.warning(f"pygame BGM play failed: {e}")

    async def _play_simpleaudio(self, path, volume):
        try:
            import simpleaudio as sa
            wave = sa.WaveObject.from_wave_file(path)
            wave.play()
        except Exception as e:
            log.warning(f"simpleaudio BGM play failed: {e}")

    async def stop(self, fade_out_sec: float = 1.0):
        if self._player == "pygame":
            import pygame
            try:
                pygame.mixer.music.fadeout(int(fade_out_sec * 1000))
            except Exception:
                pass

    def execute(self, params: dict = None) -> SkillResult:
        """同步接口: 仅返回状态，实际播放用 play()
        
        params:
          action: "status" | "stop"
        """
        params = params or {}
        action = params.get("action", "status")

        if action == "status":
            return SkillResult(
                success=True,
                data={"player": self._player or "none", "eod_volume_cap": self.eod_volume_cap},
            )
        elif action == "stop":
            # 同步停止 (pygame only)
            if self._player == "pygame":
                import pygame
                try:
                    pygame.mixer.music.fadeout(1000)
                except Exception:
                    pass
            return SkillResult(success=True, data={"stopped": True})
        else:
            return SkillResult(success=False, error=f"Unknown action: {action}")
