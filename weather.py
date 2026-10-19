"""
GoodLight Global Weather and Ambient Temperature Adaptation Module.
Supports Home Assistant (Local), Open-Meteo API, wttr.in, and Manual Override.
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional, Callable
import aiohttp

logger = logging.getLogger("GoodLight.Weather")

class WeatherService:
    def __init__(
        self,
        lat: float = 39.9042,
        lon: float = 116.4074,
        enabled: bool = True,
        provider: str = "auto",
        log_callback: Optional[Callable[[str], None]] = None
    ):
        self.lat = lat
        self.lon = lon
        self.enabled = enabled
        self.provider = provider  # "auto", "ha_weather", "open_meteo", "wttr_in", "manual"
        self.session: Optional[aiohttp.ClientSession] = None
        self.ha_client = None
        self.ha_weather_entity: Optional[str] = None
        self.log_callback = log_callback

        # Cached weather metrics
        self.current_temp: Optional[float] = None
        self.apparent_temp: Optional[float] = None
        self.cloud_cover: int = 0  # 0 - 100%
        self.weather_code: int = 0
        self.weather_desc: str = "Clear ☀️"
        self.last_update_ts: float = 0.0
        self.active_source: str = "none"
        self.last_status_msg: str = "Initializing weather service..."
        self.last_error: Optional[str] = None

        # Manual override parameters
        self.manual_temp: float = 22.0
        self.manual_apparent_temp: float = 22.0
        self.manual_cloud_cover: int = 20
        self.manual_desc: str = "Clear ☀️"

    def _log(self, msg: str):
        logger.info(msg)
        if self.log_callback:
            try:
                self.log_callback(msg)
            except Exception as e:
                logger.debug(f"Log callback failed: {e}")

    async def ensure_session(self):
        """Ensure active aiohttp client session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    def set_ha_client(self, client):
        """Register HAClient for local Home Assistant weather queries."""
        self.ha_client = client

    async def update_location(self, lat: float, lon: float):
        """Update geographic coordinates and immediately fetch new weather data."""
        self.lat = lat
        self.lon = lon
        await self.fetch_weather(force=True)

    def _parse_weather_code(self, code: int) -> str:
        """Map WMO weather interpretation codes to descriptive strings with emoji."""
        if code == 0:
            return "Clear ☀️"
        elif code in (1, 2):
            return "Partly Cloudy ⛅"
        elif code == 3:
            return "Overcast ☁️"
        elif code in (45, 48):
            return "Foggy 🌫️"
        elif code in (51, 53, 55, 61, 63, 65):
            return "Light Rain 🌧️"
        elif code in (66, 67, 80, 81, 82):
            return "Heavy / Showers ⛈️"
        elif code in (71, 73, 75, 77, 85, 86):
            return "Snow ❄️"
        elif code >= 95:
            return "Thunderstorm 🌩️"
        return "Fair 🌤️"

    def _parse_ha_weather_state(self, state: str) -> str:
        """Map Home Assistant weather entity state to descriptive strings with emoji."""
        s = str(state).lower().replace("_", "-")
        mapping = {
            "clear-night": "Clear Night 🌙",
            "cloudy": "Cloudy ☁️",
            "exceptional": "Severe Weather ⚠️",
            "fog": "Foggy 🌫️",
            "hail": "Hail 🌨️",
            "lightning": "Thunderstorm 🌩️",
            "lightning-rainy": "Thunderstorm Rain ⛈️",
            "partlycloudy": "Partly Cloudy ⛅",
            "pouring": "Heavy Rain 🌧️",
            "rainy": "Rainy 🌧️",
            "snowy": "Snowy ❄️",
            "snowy-rainy": "Sleet 🌨️",
            "sunny": "Sunny ☀️",
            "windy": "Windy 🍃",
            "windy-variant": "Windy 🍃"
        }
        return mapping.get(s, f"{state.capitalize()} 🌤️")

    async def fetch_from_ha(self) -> bool:
        """Fetch weather data from local Home Assistant."""
        if not self.ha_client:
            self.last_error = "Home Assistant client not initialized"
            return False

        ent = self.ha_weather_entity
        try:
            await self.ensure_session()
            if not ent:
                url = f"{self.ha_client.base_url}/api/states"
                headers = {"Authorization": f"Bearer {self.ha_client.token}", "Content-Type": "application/json"}
                async with self.session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                    if resp.status == 200:
                        states = await resp.json()
                        w_ents = [s["entity_id"] for s in states if s["entity_id"].startswith("weather.")]
                        if w_ents:
                            ent = w_ents[0]
                            self.ha_weather_entity = ent

            if not ent:
                self.last_error = "No weather.* entity found in Home Assistant"
                return False

            st = await self.ha_client.get_state(ent)
            if not st:
                self.last_error = f"Entity {ent} state not found in HA"
                return False

            state_val = st.get("state", "clear")
            attrs = st.get("attributes", {})
            temp = attrs.get("temperature")
            if temp is None:
                self.last_error = f"No temperature attribute in {ent}"
                return False

            self.current_temp = float(temp)
            self.apparent_temp = float(attrs.get("apparent_temperature", self.current_temp))
            self.cloud_cover = int(attrs.get("cloud_coverage", attrs.get("cloud_cover", 0)))
            self.weather_desc = self._parse_ha_weather_state(state_val)
            self.last_update_ts = time.time()
            self.active_source = f"Home Assistant ({ent})"
            self.last_status_msg = f"Synced via {self.active_source}"
            self.last_error = None
            self._log(f"⛅ [气象感知] 成功从 Home Assistant ({ent}) 同步: {self.weather_desc}, 气温 {self.current_temp}°C (体感 {self.apparent_temp}°C), 云量 {self.cloud_cover}%")
            return True
        except Exception as e:
            self.last_error = f"HA sync error: {e}"
            return False

    async def fetch_from_open_meteo(self) -> bool:
        """Fetch weather data from Open-Meteo Global API."""
        await self.ensure_session()
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={self.lat}&longitude={self.lon}"
            f"&current=temperature_2m,apparent_temperature,weather_code,cloud_cover"
            f"&timezone=auto"
        )
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    curr = data.get("current", {})
                    self.current_temp = float(curr.get("temperature_2m", 20.0))
                    self.apparent_temp = float(curr.get("apparent_temperature", self.current_temp))
                    self.cloud_cover = int(curr.get("cloud_cover", 0))
                    self.weather_code = int(curr.get("weather_code", 0))
                    self.weather_desc = self._parse_weather_code(self.weather_code)
                    self.last_update_ts = time.time()
                    self.active_source = "Open-Meteo API"
                    self.last_status_msg = f"Synced via Open-Meteo"
                    self.last_error = None
                    self._log(f"⛅ [气象感知] 成功从 Open-Meteo API 同步: {self.weather_desc}, 气温 {self.current_temp}°C (体感 {self.apparent_temp}°C), 云量 {self.cloud_cover}%")
                    return True
                else:
                    self.last_error = f"Open-Meteo HTTP {resp.status}"
                    return False
        except Exception as e:
            self.last_error = f"Open-Meteo error: {e}"
            return False

    async def fetch_from_wttr_in(self) -> bool:
        """Fetch weather data from wttr.in Public API."""
        await self.ensure_session()
        url = f"https://wttr.in/{self.lat:.4f},{self.lon:.4f}?format=j1"
        try:
            headers = {"User-Agent": "curl/7.68.0"}
            async with self.session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    cc = data.get("current_condition", [{}])[0]
                    self.current_temp = float(cc.get("temp_C", 20.0))
                    self.apparent_temp = float(cc.get("FeelsLikeC", self.current_temp))
                    self.cloud_cover = int(cc.get("cloudcover", 0))
                    w_desc = cc.get("weatherDesc", [{}])[0].get("value", "Clear")
                    self.weather_desc = f"{w_desc} 🌤️"
                    self.last_update_ts = time.time()
                    self.active_source = "wttr.in"
                    self.last_status_msg = f"Synced via wttr.in"
                    self.last_error = None
                    self._log(f"⛅ [气象感知] 成功从 wttr.in 同步: {self.weather_desc}, 气温 {self.current_temp}°C (体感 {self.apparent_temp}°C), 云量 {self.cloud_cover}%")
                    return True
                else:
                    self.last_error = f"wttr.in HTTP {resp.status}"
                    return False
        except Exception as e:
            self.last_error = f"wttr.in error: {e}"
            return False

    async def fetch_from_manual(self) -> bool:
        """Apply manual override weather metrics."""
        self.current_temp = self.manual_temp
        self.apparent_temp = self.manual_apparent_temp
        self.cloud_cover = self.manual_cloud_cover
        self.weather_desc = self.manual_desc
        self.last_update_ts = time.time()
        self.active_source = "Manual Override"
        self.last_status_msg = "Manual Override"
        self.last_error = None
        self._log(f"⚙️ [气象感知] 应用手动预设气象: {self.weather_desc}, 气温 {self.current_temp}°C (体感 {self.apparent_temp}°C), 云量 {self.cloud_cover}%")
        return True

    async def fetch_weather(self, force: bool = False) -> Dict[str, Any]:
        """Fetch current weather metrics based on configured provider with 10-minute cache."""
        now = time.time()
        if not force and (now - self.last_update_ts < 600) and self.current_temp is not None:
            return self.get_summary()

        if not self.enabled:
            return self.get_summary()

        provider = self.provider or "auto"
        success = False

        if provider == "manual":
            success = await self.fetch_from_manual()
        elif provider == "ha_weather":
            success = await self.fetch_from_ha()
        elif provider == "open_meteo":
            success = await self.fetch_from_open_meteo()
        elif provider == "wttr_in":
            success = await self.fetch_from_wttr_in()
        else:  # "auto": HA local first -> Open-Meteo -> wttr.in
            if self.ha_client:
                success = await self.fetch_from_ha()
            if not success:
                success = await self.fetch_from_open_meteo()
            if not success:
                success = await self.fetch_from_wttr_in()

        if not success:
            err = self.last_error or "All weather sources unreachable"
            self._log(f"⚠️ [气象感知] 气象源 [{provider}] 同步未完成: {err}，系统将保持当前光照节律并稍后重试")

        return self.get_summary()

    def get_summary(self) -> Dict[str, Any]:
        """Return summary dictionary of cached weather metrics."""
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "providers_available": ["auto", "ha_weather", "open_meteo", "wttr_in", "manual"],
            "active_source": self.active_source,
            "temperature": self.current_temp,
            "apparent_temperature": self.apparent_temp,
            "cloud_cover": self.cloud_cover,
            "weather_code": self.weather_code,
            "weather_desc": self.weather_desc,
            "last_update": self.last_update_ts,
            "last_status_msg": self.last_status_msg,
            "last_error": self.last_error,
            "manual_temp": self.manual_temp,
            "manual_apparent_temp": self.manual_apparent_temp,
            "manual_cloud_cover": self.manual_cloud_cover,
            "manual_desc": self.manual_desc
        }
