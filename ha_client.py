"""
GoodLight 异步 WebSocket 客户端与事件引擎
实现：
1. 监听 HA 实体状态变化 (state_changed)
2. 识别“开灯”瞬间并下发天体预测值 (零延迟介入)
3. 识别“人为手动调光/开关灯”行为并过滤自动化干扰
4. 下发平滑灯光控制命令
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
        self.session = aiohttp.ClientSession()
        while True:
            try:
                logger.info(f"正在连接 Home Assistant WebSocket: {self.ws_url} ...")
                self.ws = await self.session.ws_connect(self.ws_url)
                # 1. 认证阶段
                auth_req = await self.ws.receive_json()
                if auth_req.get("type") == "auth_required":
                    await self.ws.send_json({"type": "auth", "access_token": self.token})
                    auth_resp = await self.ws.receive_json()
                    if auth_resp.get("type") == "auth_ok":
                        logger.info("Home Assistant WebSocket 认证成功！")
                    else:
                        logger.error(f"WebSocket 认证失败: {auth_resp}")
                        await asyncio.sleep(10)
                        continue

                # 2. 订阅 state_changed 事件
                sub_id = self._msg_id
                self._msg_id += 1
                await self.ws.send_json({
                    "id": sub_id,
                    "type": "subscribe_events",
                    "event_type": "state_changed"
                })
                logger.info("已成功订阅实体状态变化事件 (state_changed)")

                # 3. 消息循环
                async for msg in self.ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if data.get("type") == "event":
                            event_data = data.get("event", {}).get("data", {})
                            for cb in self._callbacks:
                                try:
                                    await cb(event_data)
                                except Exception as e:
                                    logger.error(f"事件回调处理异常: {e}")
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        break
            except Exception as e:
                logger.warning(f"WebSocket 连接中断: {e}，5秒后自动重连...")
                await asyncio.sleep(5)

    def register_event_listener(self, callback: Callable):
        self._callbacks.append(callback)

    async def ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def call_service(self, domain: str, service: str, service_data: Dict[str, Any]):
        """调用 HA 服务 (REST 或 WS)"""
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
                    logger.error(f"调用服务 {domain}.{service} 失败 [{resp.status}]: {text}")
                else:
                    logger.debug(f"成功下发指令 {domain}.{service} -> {service_data}")
        except Exception as e:
            logger.error(f"调用服务网络异常: {e}")

    async def get_state(self, entity_id: str) -> Dict[str, Any]:
        """获取单个实体的实时状态"""
        await self.ensure_session()
        url = f"{self.base_url}/api/states/{entity_id}"
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            async with self.session.get(url, headers=headers, timeout=5) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logger.debug(f"获取状态异常 {entity_id}: {e}")
        return {}

    def update_credentials(self, base_url: str, token: str):
        """更新连接地址与令牌"""
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"

    async def get_all_entities(self, test_url: str = None, test_token: str = None) -> List[Dict[str, Any]]:
        """获取所有实体列表"""
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
                    logger.warning(f"获取实体列表失败 [{resp.status}]: {text}")
        except Exception as e:
            logger.error(f"获取实体列表网络异常: {e}")
        return []

    async def discover_lights(self, test_url: str = None, test_token: str = None) -> List[Dict[str, Any]]:
        """自主识别全屋所有灯具实体，并解析友善名称与支持特性"""
        states = await self.get_all_entities(test_url=test_url, test_token=test_token)
        lights = []
        for st in states:
            ent = st.get("entity_id", "")
            if ent.startswith("light."):
                attrs = st.get("attributes", {})
                friendly_name = attrs.get("friendly_name") or ent
                supported_color_modes = attrs.get("supported_color_modes", [])
                
                # 判断是否支持无级调光
                has_brightness = (
                    ("brightness" in attrs) or 
                    any(m in supported_color_modes for m in ["brightness", "color_temp", "hs", "xy", "rgb", "rgbw", "rgbww"])
                )
                
                # 判断是否支持色温切换
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
        """向导中用于验证 HA 地址与令牌有效性，并直接扫描灯具"""
        await self.ensure_session()
        base = url.rstrip("/")
        headers = {"Authorization": f"Bearer {token}"}
        try:
            async with self.session.get(f"{base}/api/", headers=headers, timeout=6) as resp:
                if resp.status == 200:
                    api_info = await resp.json()
                    # 进一步扫描灯具
                    lights = await self.discover_lights(test_url=base, test_token=token)
                    return {
                        "ok": True,
                        "message": api_info.get("message", "API running"),
                        "lights": lights,
                        "lights_count": len(lights)
                    }
                elif resp.status == 401:
                    return {"ok": False, "message": "401 Unauthorized: 令牌无效或已过期，请检查 Long-Lived Access Token"}
                else:
                    return {"ok": False, "message": f"连接返回状态码 {resp.status}"}
        except Exception as e:
            return {"ok": False, "message": f"无法连接到 Home Assistant: {str(e)}"}

    async def get_entity_history(self, entity_id: str, days: int = 14) -> List[Dict[str, Any]]:
        """获取指定灯具在 Home Assistant 中的历史状态记录 (支持自动回溯天数降级)"""
        await self.ensure_session()
        headers = {"Authorization": f"Bearer {self.token}"}

        # 尝试请求天数；如果HA录制器保留天数较短导致返回空，依次降级尝试
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
                logger.debug(f"获取 {entity_id} {d}天历史异常: {e}")
        return []

