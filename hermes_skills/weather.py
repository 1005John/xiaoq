"""天气_Hermes技能 - 读取缓存天气数据（data_collector 每30分钟更新）"""
import json
import logging
import time
from pathlib import Path
from hermes_skills.base import HermesSkill

log = logging.getLogger("hermes_skills.weather")

# 缓存路径：hermes_skills/../data/weather_cache.json
_CACHE_PATH = Path(__file__).parent.parent / "data" / "weather_cache.json"
_CACHE_MAX_AGE = 3600  # 超过1小时的缓存视为过期

class WeatherHermesSkill(HermesSkill):
    name = "weather"
    description = "查询天气、温度、降水、风力"

    def prepare(self, text: str) -> dict:
        """读取缓存的天气数据，由 data_collector 后台更新"""
        weather_info = ""
        try:
            if _CACHE_PATH.exists():
                with open(_CACHE_PATH, encoding="utf-8") as f:
                    cache = json.load(f)
                ts = cache.get("timestamp", 0)
                age = time.time() - ts
                data = cache.get("data", {})

                temp = data.get("temperature", "?")
                humidity = data.get("humidity", "?")
                wind = data.get("wind_speed", "?")
                wdesc = data.get("weather_desc", "?")

                # 构建当前天气信息
                freshness = "" if age < _CACHE_MAX_AGE else "（数据较旧）"
                weather_info = f"【当前天气】重庆 {wdesc}，{temp}°C，湿度{humidity}%，风速{wind}km/h{freshness}"

                # 追加5天预报
                forecast = data.get("forecast", [])
                if forecast:
                    lines = [weather_info, "【5天预报】"]
                    for f in forecast[:5]:
                        lines.append(f"  {f['date']}: {f['weather_desc']} {f['temp_min']}~{f['temp_max']}°C")
                    weather_info = "\n".join(lines)
            else:
                weather_info = "【天气】缓存文件不存在，等待后台采集..."
        except Exception as e:
            weather_info = f"【天气】读取缓存失败: {e}"

        return {"context": weather_info, "action": None, "skip_llm": False, "reply": ""}
