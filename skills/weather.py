"""
skills/weather.py — 天气技能

从 weather_news.py WeatherService 迁移。
Sidecar编排和v10 L3均可调用。

L3意图: weather → Skill "weather", params: {}
TTS模板: 「今天{weather_desc}，{temperature}度。」
side_effects: card_show(type="weather")
"""

import asyncio
import json
import logging
from pathlib import Path
from .base import Skill, SkillResult, SideEffect

log = logging.getLogger("skills.weather")

try:
    import aiohttp
    _aiohttp = True
except ImportError:
    _aiohttp = False

MOCK_WEATHER = {
    "temperature": 25.0,
    "weather_desc": "多云",
    "humidity": 60,
    "wind_speed": 3.2,
}


class WeatherSkill(Skill):
    """天气查询技能 — Open-Meteo免Key API"""
    
    name = "weather"
    description = "天气查询 (Open-Meteo免Key)"
    
    def __init__(self, cfg: dict = None):
        super().__init__(cfg)
        self.lat = self.cfg.get("latitude", 39.9042)
        self.lon = self.cfg.get("longitude", 116.4074)
        self.timeout = self.cfg.get("timeout", 10)
        self.mock_path = Path(self.cfg.get("mock_path", "data/mock_weather.json"))
    
    async def fetch(self) -> dict:
        """获取天气：先HTTP Open-Meteo，失败再mock"""
        # API优先，不走mock文件优先
        if _aiohttp:
            try:
                url = (
                    f"https://api.open-meteo.com/v1/forecast?"
                    f"latitude={self.lat}&longitude={self.lon}"
                    f"&daily=temperature_2m_max,temperature_2m_min,weather_code,wind_speed_10m_max"
                    f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
                    f"&timezone=Asia/Shanghai&forecast_days=5"
                )
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=self.timeout)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            current = data.get("current", {})
                            daily = data.get("daily", {})
                            # 构建5天预报
                            forecast = []
                            if daily and daily.get("time"):
                                for i in range(min(5, len(daily["time"]))):
                                    forecast.append({
                                        "date": daily["time"][i],
                                        "temp_max": daily["temperature_2m_max"][i] if daily.get("temperature_2m_max") else "?",
                                        "temp_min": daily["temperature_2m_min"][i] if daily.get("temperature_2m_min") else "?",
                                        "weather_desc": self._weather_code_desc(daily["weather_code"][i] if daily.get("weather_code") else 0),
                                        "wind_speed": daily["wind_speed_10m_max"][i] if daily.get("wind_speed_10m_max") else "?",
                                    })
                            result = {
                                "temperature": current.get("temperature_2m", "?"),
                                "humidity": current.get("relative_humidity_2m", "?"),
                                "weather_desc": self._weather_code_desc(current.get("weather_code", 0)),
                                "wind_speed": current.get("wind_speed_10m", "?"),
                                "forecast": forecast,
                            }
                            log.info(f"Weather API: {result.get('weather_desc')}, {len(forecast)} days")
                            return result
                        else:
                            log.warning(f"Weather API status {resp.status}")
            except Exception as e:
                log.warning(f"Weather fetch failed: {e}, falling back to mock")
        else:
            log.warning("aiohttp not available, using mock weather")

        # 失败/无网时：先试mock文件，再硬编码mock
        if self.mock_path.exists():
            try:
                return json.loads(self.mock_path.read_text())
            except Exception:
                pass
        return self._mock()

    def _mock(self) -> dict:
        log.info("Using mock weather (fallback)")
        return dict(MOCK_WEATHER)

    @staticmethod
    def _weather_code_desc(code: int) -> str:
        mapping = {
            0: "晴", 1: "大部晴", 2: "多云", 3: "阴",
            45: "雾", 48: "雾凇", 51: "小雨", 53: "中雨", 55: "大雨",
            61: "小雨", 63: "中雨", 65: "大雨", 71: "小雪", 73: "中雪", 75: "大雪",
            80: "阵雨", 81: "中阵雨", 82: "大阵雨", 95: "雷阵雨",
        }
        return mapping.get(code, f"天气代码{code}")

    def format_summary(self, data: dict) -> str:
        """短口播模板 ≤20字"""
        return f"今天{data.get('weather_desc', '未知')}，{data.get('temperature', '?')}度。"

    def execute(self, params: dict = None) -> SkillResult:
        """实时获取天气，不读缓存"""
        try:
            data = asyncio.get_event_loop().run_until_complete(self.fetch())
        except RuntimeError:
            data = asyncio.run(self.fetch())
        return self._build_result(data)

    async def execute_async(self, params: dict = None) -> SkillResult:
        """异步接口: 实际请求API"""
        data = await self.fetch()
        return self._build_result(data)

    def _build_result(self, data: dict) -> SkillResult:
        tts_text = self.format_summary(data)
        forecast = data.get("forecast", [])
        lines = []
        for day in forecast:
            d = day.get("date", "?")[-5:]  # MM-DD
            desc = day.get("weather_desc", "?")
            hi = day.get("temp_max", "?")
            lo = day.get("temp_min", "?")
            lines.append(f"{d}: {desc} {lo}~{hi}°C")
        return SkillResult(
            success=True,
            data=data,
            side_effects=[
                SideEffect("card_show", {"title": "天气预报 (5天)", "lines": lines, "card_type": "todo"}),
                SideEffect("voice_tts", {"text": tts_text}),
            ],
        )
