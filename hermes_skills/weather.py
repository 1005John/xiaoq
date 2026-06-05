"""天气_Hermes技能 - 查询实时天气"""
import json
import logging
import urllib.request
from hermes_skills.base import HermesSkill

log = logging.getLogger("hermes_skills.weather")

# 重庆默认
LAT, LON = 29.56, 106.55

class WeatherHermesSkill(HermesSkill):
    name = "weather"
    description = "查询天气、温度、降水、风力"

    def prepare(self, text: str) -> dict:
        """获取实时天气数据"""
        weather_info = ""
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                cur = data.get("current", {})
                temp = cur.get("temperature_2m", "?")
                humidity = cur.get("relative_humidity_2m", "?")
                wind = cur.get("wind_speed_10m", "?")
                wcode = cur.get("weather_code", 0)
            # 天气编码转文字
            wmap = {0:"晴朗",1:"大部晴",2:"多云",3:"阴",45:"雾",48:"雾凇",51:"小毛毛雨",53:"毛毛雨",55:"大毛毛雨",61:"小雨",63:"中雨",65:"大雨",71:"小雪",73:"中雪",75:"大雪",80:"阵雨",81:"中阵雨",82:"大阵雨",95:"雷暴"}
            weather_desc = wmap.get(wcode, f"码{wcode}")
            weather_info = f"【当前天气】重庆 {weather_desc}，{temp}°C，湿度{humidity}%，风速{wind}km/h"
        except Exception as e:
            weather_info = f"【天气】获取失败: {e}"

        return {"context": weather_info, "action": None, "skip_llm": False, "reply": ""}
