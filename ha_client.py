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
