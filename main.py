"""
GoodLight 守护服务核心主程序
实现逻辑：
1. 开灯感知：开灯时毫秒级下发模型计算出的最佳亮度、色温以及协同开启的灯泡个数。
2. 平滑运行：灯亮着时绝不主动干扰或强行覆盖用户。
3. 行为学习：用户手动在 App 或墙壁开关调光或增减开灯个数时，自动触发局部加权学习。
"""

import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
import yaml
from solar import SolarCalculator
from model import GoodLightModel
from ha_client import HAClient
from web_panel import WebPanel, add_log
from db import HistoryDB

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("GoodLight.Core")

class GoodLightService:
    def __init__(self, config_path: str = "config.yaml"):
        if not os.path.exists(config_path) and os.path.exists("config.example.yaml"):
            logger.warning(f"未找到 {config_path}，使用 config.example.yaml 默认模板")
            config_path = "config.example.yaml"

        with open(config_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)

        ha_cfg = self.cfg["home_assistant"]
        loc_cfg = self.cfg["location"]
        self.tz = timezone(timedelta(hours=loc_cfg.get("timezone_offset", 8.0)))

        # 支持环境变量优先注入 token 和 url，避免明文写在配置文件中
        ha_url = os.environ.get("GOODLIGHT_HA_URL", ha_cfg["url"])
        ha_token = os.environ.get("GOODLIGHT_HA_TOKEN", ha_cfg.get("token", ""))

        self.solar = SolarCalculator(
            latitude=loc_cfg["latitude"],
            longitude=loc_cfg["longitude"],
            tz_offset_hours=loc_cfg.get("timezone_offset", 8.0)
        )
        self.model = GoodLightModel(profile_path="light_profile.json")
        self.client = HAClient(base_url=ha_url, token=ha_token)
        self.db = HistoryDB(db_path="history.db")

        self.light_entities = [item["entity_id"] for item in self.cfg["lighting_group"]["lights"]]
        self.debounce_tasks = {}
        self.ignore_updates = set()  # 防止自身下发指令触发回环学习
        self.web_panel = WebPanel(self, host="0.0.0.0", port=8787)

    async def start(self):
        msg = f"GoodLight 智能感知服务启动完成，协同组: {self.light_entities}"
        logger.info(msg)
        add_log(msg)

        # 启动 Web 监控面板
        await self.web_panel.start()

        # 启动后台性能统计与灯光快照采样循环 (每 30 秒采集一次并入库)
        asyncio.create_task(self._metrics_sampler_loop())

        self.client.register_event_listener(self.on_state_changed)
        # 连接并在就绪后主动拉取当前灯光初始状态
        asyncio.create_task(self._init_light_states())
        await self.client.connect()

    async def _init_light_states(self):
        await asyncio.sleep(2)
        for ent in self.light_entities:
            try:
                st = await self.client.get_state(ent)
                if st:
                    state_str = st.get("state", "off")
                    attrs = st.get("attributes", {})
                    b = attrs.get("brightness")
                    c = attrs.get("color_temp_kelvin") or attrs.get("color_temp")
                    pct_b = round((b / 255.0) * 100, 1) if b is not None else 0
                    self.db.record_light_state(ent, pct_b, c, state_str)
                    logger.debug(f"初始同步灯光状态: {ent} -> {state_str}, {pct_b}%, {c}K")
            except Exception as e:
                logger.debug(f"初始同步灯光状态失败 {ent}: {e}")

    async def _metrics_sampler_loop(self):
        while True:
            try:
                stats = self.web_panel.get_process_metrics()
                self.db.record_metrics(
                    cpu=stats["cpu_percent"],
                    rss_mb=stats["mem_rss_mb"],
                    vms_mb=stats["mem_vms_mb"]
                )
                # 周期性为每个灯打点快照
                for ent in self.light_entities:
                    st = await self.client.get_state(ent)
                    if st:
                        state_str = st.get("state", "off")
                        attrs = st.get("attributes", {})
                        b = attrs.get("brightness")
                        c = attrs.get("color_temp_kelvin") or attrs.get("color_temp")
                        pct_b = round((b / 255.0) * 100, 1) if (state_str == "on" and b is not None) else 0
                        self.db.record_light_state(ent, pct_b, c, state_str)
                # 每日一次清理过期数据
                self.db.cleanup_old_data(max_days=30)
            except Exception as e:
                logger.debug(f"性能采集异常: {e}")
            await asyncio.sleep(30)

    async def on_state_changed(self, event_data: dict):
        entity_id = event_data.get("entity_id")
        if entity_id not in self.light_entities:
            return

        old_state = event_data.get("old_state") or {}
        new_state = event_data.get("new_state") or {}

        old_s = old_state.get("state")
        new_s = new_state.get("state")

        # 检查是否是我们系统自己刚刚下发的指令，若是则忽略
        if entity_id in self.ignore_updates:
            self.ignore_updates.remove(entity_id)
            return

        now = datetime.now(self.tz)
        hour_float = now.hour + now.minute / 60.0 + now.second / 3600.0

        # 场景 1：开灯事件 (Turn On) -> 介入并给出自适应建议
        if old_s != "on" and new_s == "on":
            logger.info(f"检测到灯具开启: {entity_id}")
            await self.handle_light_turned_on(entity_id, now, hour_float)
            return

        # 场景 2：灯亮着期间手动调光或调色温 (User Manual Adjustment) -> 学习偏好
        if old_s == "on" and new_s == "on":
            old_attrs = old_state.get("attributes", {})
            new_attrs = new_state.get("attributes", {})

            old_b = old_attrs.get("brightness")
            new_b = new_attrs.get("brightness")

            new_c = new_attrs.get("color_temp_kelvin") or new_attrs.get("color_temp")

            # 存入历史数据库
            pct_b = round((new_b / 255.0) * 100, 1) if new_b is not None else 0
            self.db.record_light_state(entity_id, pct_b, new_c, new_s)

            # 判定是否有明显手动调光动作
            b_changed = (old_b is not None and new_b is not None and abs(old_b - new_b) >= 3)
            if b_changed:
                self.schedule_learning(hour_float, actual_b=pct_b)

    async def handle_light_turned_on(self, triggered_entity: str, dt: datetime, hour_float: float):
        elevation = self.solar.get_solar_elevation(dt)
        term_name, term_prog = self.solar.get_solar_term(dt)
        season_factor = self.solar.get_season_factor(dt)

        pred = self.model.predict(
            hour_float=hour_float,
            solar_elevation=elevation,
            season_factor=season_factor
        )

        log_msg = f"[自适应开灯] 节气: {term_name} | 太阳高度: {elevation:.1f}° -> 推荐亮度: {pred['brightness']}% | 色温: {pred['color_temp']}K | 协同灯数: {pred['light_count']}"
        logger.info(log_msg)
        add_log(log_msg)

        # 准备下发指令
        b_val = max(1, min(255, round((pred["brightness"] / 100.0) * 255)))
        k_val = pred["color_temp"]

        target_count = pred["light_count"]
        # 按优先级激活灯具
        for idx, ent in enumerate(self.light_entities):
            if idx < target_count:
                self.ignore_updates.add(ent)
                await self.client.call_service("light", "turn_on", {
                    "entity_id": ent,
                    "brightness": b_val,
                    "color_temp_kelvin": k_val,
                    "transition": 1
                })
                # 记录开灯历史点
                self.db.record_light_state(ent, pred["brightness"], k_val, "on")
            else:
                pass

    def schedule_learning(self, hour_float: float, actual_b: float = None, actual_c: int = None, actual_count: int = None):
        """防抖异步学习调度"""
        debounce_sec = self.cfg.get("learning", {}).get("debounce_seconds", 3.0)
        lr = self.cfg.get("learning", {}).get("learning_rate", 0.25)

        async def _do_learn():
            await asyncio.sleep(debounce_sec)
            self.model.learn_user_adjustment(
                hour_float=hour_float,
                actual_brightness=actual_b,
                actual_color_temp=actual_c,
                actual_count=actual_count,
                learning_rate=lr
            )
            add_log(f"[偏好学习] 检测到手动调光并完成局部学习 (当前时刻: {hour_float:.1f}h -> 亮度: {actual_b}%)")

        if "learn" in self.debounce_tasks:
            self.debounce_tasks["learn"].cancel()
        self.debounce_tasks["learn"] = asyncio.create_task(_do_learn())

if __name__ == "__main__":
    service = GoodLightService("config.yaml")
    asyncio.run(service.start())
