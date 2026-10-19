"""
GoodLight Asynchronous WebSocket Client and Event Engine for Home Assistant.
Features:
1. Listen to Home Assistant state change events (state_changed) in real-time
2. Zero-latency turn-on interception with instant circadian target application
3. Discerning user manual adjustments vs automated cruise changes
4. Smooth fixture command dispatching with transition curves
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Any, List
import aiohttp

logger = logging.getLogger("GoodLight.HA")

class HAClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
        self.session = None
        self.ws = None
        self._msg_id = 1
        self._callbacks = []

    async def connect(self):
        """Establish persistent WebSocket connection with Home Assistant and handle event loop."""
        self.session = aiohttp.ClientSession()
        while True:
            try:
                logger.info(f"Connecting to Home Assistant WebSocket: {self.ws_url} ...")
                self.ws = await self.session.ws_connect(self.ws_url)
                # 1. Authentication phase
                auth_req = await self.ws.receive_json()
                if auth_req.get("type") == "auth_required":
                    await self.ws.send_json({"type": "auth", "access_token": self.token})
                    auth_resp = await self.ws.receive_json()
                    if auth_resp.get("type") == "auth_ok":
                        logger.info("Home Assistant WebSocket authenticated successfully!")
                    else:
                        logger.error(f"WebSocket authentication failed: {auth_resp}")
                        await asyncio.sleep(10)
                        continue

                # 2. Subscribe to state_changed events
                sub_id = self._msg_id
                self._msg_id += 1
                await self.ws.send_json({
                    "id": sub_id,
                    "type": "subscribe_events",
                    "event_type": "state_changed"
                })
                logger.info("Successfully subscribed to state_changed events")

                # 3. Message dispatching loop
                async for msg in self.ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if data.get("type") == "event":
                            event_data = data.get("event", {}).get("data", {})
                            for cb in self._callbacks:
                                try:
                                    await cb(event_data)
                                except Exception as e:
                                    logger.error(f"Error in event callback: {e}")
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        break
            except Exception as e:
                logger.warning(f"WebSocket connection lost: {e}, reconnecting in 5s...")
                await asyncio.sleep(5)

    def register_event_listener(self, callback: Callable):
        """Register a callback coroutine for state_changed events."""
        self._callbacks.append(callback)

    async def ensure_session(self):
        """Ensure active aiohttp client session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def call_service(self, domain: str, service: str, service_data: Dict[str, Any]):
        """Call a Home Assistant service via REST API."""
        await self.ensure_session()
        url = f"{self.base_url}/api/services/{domain}/{service}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        try:
            async with self.session.post(url, headers=headers, json=service_data, timeout=5) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Failed to call service {domain}.{service} [{resp.status}]: {text}")
                else:
                    logger.debug(f"Service call successful: {domain}.{service} -> {service_data}")
        except Exception as e:
            logger.error(f"Network error calling service: {e}")

    async def get_state(self, entity_id: str) -> Dict[str, Any]:
        """Fetch current state of a single entity."""
        await self.ensure_session()
        url = f"{self.base_url}/api/states/{entity_id}"
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            async with self.session.get(url, headers=headers, timeout=5) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logger.debug(f"Error fetching state for {entity_id}: {e}")
        return {}

    def update_credentials(self, base_url: str, token: str):
        """Update HA URL and access token dynamically."""
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"

    async def get_all_entities(self, test_url: str = None, test_token: str = None) -> List[Dict[str, Any]]:
        """Fetch all entity states from Home Assistant."""
        await self.ensure_session()
        base = (test_url or self.base_url).rstrip("/")
        tok = test_token or self.token
        url = f"{base}/api/states"
        headers = {"Authorization": f"Bearer {tok}"}
        try:
            async with self.session.get(url, headers=headers, timeout=6) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    text = await resp.text()
                    logger.warning(f"Failed to fetch entities [{resp.status}]: {text}")
        except Exception as e:
            logger.error(f"Network error fetching entities: {e}")
        return []

    async def discover_lights(self, test_url: str = None, test_token: str = None) -> List[Dict[str, Any]]:
        """Discover all light entities and parse friendly names and hardware capabilities."""
        states = await self.get_all_entities(test_url=test_url, test_token=test_token)
        lights = []
        for st in states:
            ent = st.get("entity_id", "")
            if ent.startswith("light."):
                attrs = st.get("attributes", {})
                friendly_name = attrs.get("friendly_name") or ent
                supported_color_modes = attrs.get("supported_color_modes", [])
                
                # Check dimming brightness support
                has_brightness = (
                    ("brightness" in attrs) or 
                    any(m in supported_color_modes for m in ["brightness", "color_temp", "hs", "xy", "rgb", "rgbw", "rgbww"])
                )
                
                # Check tunable color temperature support
                has_color_temp = (
                    ("color_temp" in attrs) or 
                    ("color_temp_kelvin" in attrs) or 
                    ("color_temp" in supported_color_modes)
                )
                
                min_k = attrs.get("min_color_temp_kelvin")
                max_k = attrs.get("max_color_temp_kelvin")
                if not min_k and attrs.get("max_mireds"):
                    min_k = int(1000000 / attrs["max_mireds"])
                if not max_k and attrs.get("min_mireds"):
                    max_k = int(1000000 / attrs["min_mireds"])

                lights.append({
                    "entity_id": ent,
                    "name": friendly_name,
                    "state": st.get("state", "off"),
                    "has_brightness": bool(has_brightness),
                    "has_color_temp": bool(has_color_temp),
                    "min_kelvin": min_k or 2700,
                    "max_kelvin": max_k or 6500
                })
        return lights

    async def test_connection(self, url: str, token: str) -> Dict[str, Any]:
        """Validate HA connection credentials and discover lights for setup wizard."""
        await self.ensure_session()
        base = url.rstrip("/")
        headers = {"Authorization": f"Bearer {token}"}
        try:
            async with self.session.get(f"{base}/api/", headers=headers, timeout=6) as resp:
                if resp.status == 200:
                    api_info = await resp.json()
                    lights = await self.discover_lights(test_url=base, test_token=token)
                    return {
                        "ok": True,
                        "message": api_info.get("message", "API running"),
                        "lights": lights,
                        "lights_count": len(lights)
                    }
                elif resp.status == 401:
                    return {"ok": False, "message": "401 Unauthorized: Invalid or expired Long-Lived Access Token"}
                else:
                    return {"ok": False, "message": f"Connection returned HTTP status {resp.status}"}
        except Exception as e:
            return {"ok": False, "message": f"Cannot connect to Home Assistant: {str(e)}"}

    async def get_entity_history(self, entity_id: str, days: int = 14) -> List[Dict[str, Any]]:
        """Fetch historical state changes for an entity from Home Assistant REST API (with automatic fallback days)."""
        await self.ensure_session()
        headers = {"Authorization": f"Bearer {self.token}"}

        # Try requested days; fallback gracefully if recorder retention is shorter
        day_candidates = [days]
        for fallback in [7, 3, 1]:
            if fallback < days:
                day_candidates.append(fallback)

        for d in day_candidates:
            start_time = (datetime.now(timezone.utc) - timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%SZ")
            url = f"{self.base_url}/api/history/period/{start_time}?filter_entity_id={entity_id}"
            try:
                async with self.session.get(url, headers=headers, timeout=12) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data and isinstance(data, list) and len(data) > 0:
                            return data[0]
            except Exception as e:
                logger.debug(f"Error fetching history for {entity_id} ({d} days): {e}")
        return []
