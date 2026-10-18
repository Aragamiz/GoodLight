"""
GoodLight 全球气象与环境温度感知模块 (基于 Open-Meteo 免 Key 全球公开气象服务)
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional
import aiohttp

logger = logging.getLogger("GoodLight.Weather")

class WeatherService:
    def __init__(self, lat: float = 39.9042, lon: float = 116.4074, enabled: bool = True):
        self.lat = lat
        self.lon = lon
        self.enabled = enabled
        self.session = None
        
        # 缓存状态
        self.current_temp: Optional[float] = None
        self.apparent_temp: Optional[float] = None
        self.cloud_cover: int = 0  # 0 - 100%
        self.weather_code: int = 0
        self.weather_desc: str = "晴朗 ☀️"
        self.last_update_ts: float = 0.0

    async def ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def update_location(self, lat: float, lon: float):
        self.lat = lat
        self.lon = lon
        await self.fetch_weather(force=True)

    def _parse_weather_code(self, code: int) -> str:
        if code == 0:
            return "晴朗 ☀️"
        elif code in (1, 2):
            return "多云间晴 ⛅"
        elif code == 3:
            return "阴天 ☁️"
        elif code in (45, 48):
            return "雾霭 🌫️"
        elif code in (51, 53, 55, 61, 63, 65):
            return "细雨 🌧️"
        elif code in (66, 67, 80, 81, 82):
            return "大雨/阵雨 ⛈️"
        elif code in (71, 73, 75, 77, 85, 86):
            return "降雪 ❄️"
        elif code >= 95:
            return "雷暴 🌩️"
        return "良好 🌤️"

    async def fetch_weather(self, force: bool = False) -> Dict[str, Any]:
        """抓取最新天气与温度，内置 10 分钟缓存"""
        now = time.time()
        if not force and (now - self.last_update_ts < 600) and self.current_temp is not None:
            return self.get_summary()

        if not self.enabled:
            return self.get_summary()

        await self.ensure_session()
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={self.lat}&longitude={self.lon}"
            f"&current=temperature_2m,apparent_temperature,weather_code,cloud_cover"
            f"&timezone=auto"
        )
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    curr = data.get("current", {})
                    self.current_temp = curr.get("temperature_2m")
                    self.apparent_temp = curr.get("apparent_temperature", self.current_temp)
                    self.cloud_cover = int(curr.get("cloud_cover", 0))
                    self.weather_code = int(curr.get("weather_code", 0))
                    self.weather_desc = self._parse_weather_code(self.weather_code)
                    self.last_update_ts = now
                    logger.info(f"实时气象已更新: {self.weather_desc}, 气温 {self.current_temp}°C (体感 {self.apparent_temp}°C), 云量 {self.cloud_cover}%")
        except Exception as e:
            logger.debug(f"获取公开天气信息暂时跳过: {e}")

        return self.get_summary()

    def get_summary(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "temperature": self.current_temp,
            "apparent_temperature": self.apparent_temp,
            "cloud_cover": self.cloud_cover,
            "weather_code": self.weather_code,
            "weather_desc": self.weather_desc,
            "last_update": self.last_update_ts
        }
