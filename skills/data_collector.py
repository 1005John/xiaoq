"""
skills/data_collector.py — 定时数据采集器

每 30 分钟后台采集新闻、天气、灵畿任务，缓存到本地 JSON 文件。
技能执行时优先读缓存，减少网络请求。

采集内容:
  - WeatherSkill.fetch() → data/weather_cache.json
  - NewsSkill.fetch()    → data/news_cache.json
  - lc req list          → data/lingji_cache.json

启动方式: 在 v10 主循环入口调用 DataCollector.start()
"""

import asyncio
import json
import logging
import os
import subprocess
import time
import threading
from pathlib import Path
from typing import Optional

log = logging.getLogger("skills.data_collector")

# ── 缓存文件路径 ──
CACHE_DIR = Path(__file__).parent.parent / "data"
WEATHER_CACHE = CACHE_DIR / "weather_cache.json"
NEWS_CACHE = CACHE_DIR / "news_cache.json"
LINGJI_CACHE = CACHE_DIR / "lingji_cache.json"
BUG_CACHE = CACHE_DIR / "bug_cache.json"
BUG_CACHE = CACHE_DIR / "bug_cache.json"
BUG_CACHE = CACHE_DIR / "bug_cache.json"


# ═══════════════════════════════════════════
# 缓存管理器
# ═══════════════════════════════════════════

class CacheManager:
    """本地缓存读写"""

    @staticmethod
    def ensure_dir():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def save(path: Path, data):
        """保存数据到缓存"""
        CacheManager.ensure_dir()
        payload = {
            "timestamp": time.time(),
            "data": data,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        log.info(f"Cache saved: {path.name} ({len(json.dumps(data, ensure_ascii=False))} chars)")

    @staticmethod
    def load(path: Path, max_age: float = 1800) -> Optional[dict]:
        """读取缓存，超过 max_age 秒视为过期返回 None"""
        if not path.exists():
            log.debug(f"Cache not found: {path.name}")
            return None
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
            age = time.time() - payload.get("timestamp", 0)
            if age > max_age:
                log.info(f"Cache expired: {path.name} (age={age:.0f}s > {max_age}s)")
                return None
            log.info(f"Cache hit: {path.name} (age={age:.0f}s)")
            return payload["data"]
        except Exception as e:
            log.warning(f"Cache load failed: {path.name}: {e}")
            return None

    @staticmethod
    def age(path: Path) -> float:
        """返回缓存距今秒数，不存在返回 -1"""
        if not path.exists():
            return -1
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
            return time.time() - payload.get("timestamp", 0)
        except Exception:
            return -1


# ═══════════════════════════════════════════
# 数据采集器
# ═══════════════════════════════════════════


# ═══════════════════════════════════════════
# 数据采集器
# ═══════════════════════════════════════════

class DataCollector:
    """定时后台采集器，每 interval_sec 秒执行一轮采集"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.interval = self.config.get("interval_sec", 1800)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._latest = {"weather": None, "news": None, "lingji": None}

    def get_latest(self, key: str):
        return self._latest.get(key)

    def start(self):
        if self._thread and self._thread.is_alive():
            log.warning("DataCollector already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="data-collector")
        self._thread.start()
        log.info(f"DataCollector started (interval={self.interval}s)")

    def stop(self):
        self._stop_event.set()
        log.info("DataCollector stopped")

    def _run_loop(self):
        log.info("DataCollector: first collection round...")
        self._collect_all()
        while not self._stop_event.is_set():
            if self._stop_event.wait(self.interval):
                break
            log.info("DataCollector: periodic collection round...")
            self._collect_all()

    def _collect_all(self):
        self._collect_weather()
        self._collect_news()
        self._collect_lingji()

    async def _fetch_weather_async(self) -> dict:
        try:
            import aiohttp
            lat = self.config.get("latitude", 39.9042)
            lon = self.config.get("longitude", 116.4074)
            timeout = self.config.get("timeout", 10)
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}"
                f"&daily=temperature_2m_max,temperature_2m_min,weather_code,wind_speed_10m_max"
                f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
                f"&timezone=Asia/Shanghai&forecast_days=5"
            )
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        current = data.get("current", {})
                        wdesc = {0:"晴",1:"大部晴",2:"多云",3:"阴",45:"雾",51:"小雨",53:"中雨",
                                 55:"大雨",61:"小雨",63:"中雨",65:"大雨",71:"小雪",73:"中雪",75:"大雪",
                                 80:"阵雨",81:"中阵雨",82:"大阵雨",95:"雷阵雨"}.get(current.get("weather_code",0), "?")
                        daily = data.get("daily", {})
                        forecast = []
                        if daily and daily.get("time"):
                            for i in range(min(5, len(daily["time"]))):
                                wc = daily["weather_code"][i] if daily.get("weather_code") else 0
                                wd = {0:"晴",1:"大部晴",2:"多云",3:"阴",45:"雾",51:"小雨",53:"中雨",
                                     55:"大雨",61:"小雨",63:"中雨",65:"大雨",71:"小雪",73:"中雪",75:"大雪",
                                     80:"阵雨",81:"中阵雨",82:"大阵雨",95:"雷阵雨"}.get(wc, "?")
                                forecast.append({
                                    "date": daily["time"][i],
                                    "temp_max": daily["temperature_2m_max"][i] if daily.get("temperature_2m_max") else "?",
                                    "temp_min": daily["temperature_2m_min"][i] if daily.get("temperature_2m_min") else "?",
                                    "weather_desc": wd,
                                })
                        return {"temperature": current.get("temperature_2m","?"),
                                "humidity": current.get("relative_humidity_2m","?"),
                                "weather_desc": wdesc, "wind_speed": current.get("wind_speed_10m","?"),
                                "forecast": forecast}
        except Exception as e:
            log.warning(f"Weather collect failed: {e}")
        return {}

    def _collect_weather(self):
        try:
            data = asyncio.run(self._fetch_weather_async())
            if data:
                CacheManager.save(WEATHER_CACHE, data)
                self._latest["weather"] = data
                log.info(f"Weather cached: {data.get('weather_desc')}, {data.get('temperature')}C")
        except Exception as e:
            log.error(f"Weather collect error: {e}")

    async def _fetch_news_async(self, count: int = 5) -> list:
        try:
            import aiohttp
            rss_urls = self.config.get("rss_urls", [])
            timeout = self.config.get("timeout", 10)
            for url in rss_urls[:3]:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                            if resp.status == 200:
                                text = await resp.text()
                                items = self._parse_rss(text)
                                if items:
                                    return items[:count]
                except Exception as e:
                    log.warning(f"RSS failed ({url}): {e}")
        except Exception as e:
            log.warning(f"News collect failed: {e}")
        return []

    def _parse_rss(self, text: str) -> list:
        items = []
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(text)
            for item in root.iter("item"):
                title = ""
                desc = ""
                for child in item:
                    if child.tag == "title" and child.text:
                        title = child.text.strip()
                    elif child.tag in ("description", "summary") and child.text:
                        desc = child.text.strip()[:100]
                if title:
                    items.append({"title": title, "summary": desc})
        except Exception:
            pass
        return items

    def _collect_news(self):
        try:
            items = asyncio.run(self._fetch_news_async(5))
            if items:
                CacheManager.save(NEWS_CACHE, items)
                self._latest["news"] = items
                log.info(f"News cached: {len(items)} items")
        except Exception as e:
            log.error(f"News collect error: {e}")

    def _collect_lingji(self):
        try:
            import subprocess, json as _json
            workspace = self.config.get("lingji_workspace", "")
            cmd = ["lc", "req", "list", "-l", "20", "--pretty"]
            if workspace:
                cmd.extend(["-w", workspace])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout.strip():
                data = _json.loads(result.stdout)
                raw_items = data
                if isinstance(data, dict):
                    inner = data.get("data", data)
                    if isinstance(inner, dict):
                        raw_items = inner.get("items", inner)
                    else:
                        raw_items = inner
                tasks = raw_items if isinstance(raw_items, list) else []
                if isinstance(tasks, list):
                    # 只保留负责人是傅强的任务
                    tasks = [t for t in tasks if t.get("assignee") == "傅强"]
                    simplified = []
                    for t in tasks:
                        simplified.append({
                            "id": t.get("key", t.get("id", "")),
                            "title": t.get("name", t.get("title", "")),
                            "status": t.get("status", ""),
                            "key": t.get("key", ""),
                        })
                    CacheManager.save(LINGJI_CACHE, simplified)
                    self._latest["lingji"] = simplified
                    log.info(f"Lingji tasks cached: {len(simplified)} items")
        except subprocess.TimeoutExpired:
            log.warning("Lingji CLI timed out")
        except Exception as e:
            log.error(f"Lingji collect error: {e}")


# ═══════════════════════════════════════════
# 便捷函数：技能直接调用的缓存读取
# ═══════════════════════════════════════════

def get_cached_weather(max_age: float = 3600) -> Optional[dict]:
    """获取缓存的天气数据（1小时内有效）"""
    return CacheManager.load(WEATHER_CACHE, max_age)


def get_cached_news(max_age: float = 3600) -> Optional[list]:
    """获取缓存的新闻数据（1小时内有效）"""
    return CacheManager.load(NEWS_CACHE, max_age)


def get_cached_lingji(max_age: float = 3600) -> Optional[list]:
    """获取缓存的灵畿任务数据（1小时内有效）"""
    return CacheManager.load(LINGJI_CACHE, max_age)


def get_cached_bugs(max_age: float = 3600) -> Optional[list]:
    """获取缓存的缺陷数据（1小时内有效）"""
    return CacheManager.load(BUG_CACHE, max_age)
