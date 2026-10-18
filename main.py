"""
GoodLight 守护服务核心主程序 (支持多灯光独立分组与动态时区调节)
"""

import os
import time
import asyncio
import logging
from datetime import datetime, timezone, timedelta

# 默认设置上海/北京时区 (UTC+8)，确保 Linux Docker 环境中 localtime 与日志时间对齐
if "TZ" not in os.environ:
    os.environ["TZ"] = "Asia/Shanghai"
if hasattr(time, "tzset"):
    try:
        time.tzset()
    except Exception:
        pass

import yaml
from solar import SolarCalculator
from model import GoodLightModel
from ha_client import HAClient
from web_panel import WebPanel, add_log, set_log_tz
from db import HistoryDB

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("GoodLight.Core")

class LightGroup:
    """独立的灯光受控组，每个组拥有独立模型和灯具优先级"""
    def __init__(self, group_dict: dict, base_dir: str = "."):
        self.id = group_dict.get("id", "default")
        self.name = group_dict.get("name", "Light Group")
        self.enabled = group_dict.get("enabled", True)
        profile_file = group_dict.get("profile_path", f"profile_{self.id}.json")
        self.model = GoodLightModel(profile_path=os.path.join(base_dir, profile_file))
        self.lights = group_dict.get("lights", [])
        self.light_entities = [item["entity_id"] for item in self.lights]
        self.debounce_tasks = {}

class GoodLightService:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        if not os.path.exists(config_path) and os.path.exists("config.example.yaml"):
            logger.warning(f"未找到 {config_path}，使用 config.example.yaml 默认模板")
            self.config_path = "config.example.yaml"

        with open(self.config_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)

        ha_cfg = self.cfg["home_assistant"]
        loc_cfg = self.cfg["location"]
        
        self.tz_offset = float(loc_cfg.get("timezone_offset", 8.0))
        self.time_offset_seconds = 0  # 允许在 Panel 中微调时间偏移量 (秒)
        self.tz = timezone(timedelta(hours=self.tz_offset))

        ha_url = os.environ.get("GOODLIGHT_HA_URL", ha_cfg["url"])
        ha_token = os.environ.get("GOODLIGHT_HA_TOKEN", ha_cfg.get("token", ""))

        self.solar = SolarCalculator(
            latitude=loc_cfg["latitude"],
            longitude=loc_cfg["longitude"],
            tz_offset_hours=self.tz_offset
        )
        self.client = HAClient(base_url=ha_url, token=ha_token)
        self.db = HistoryDB(db_path="history.db")
        self.ignore_updates = set()

        # 初始化分组
        self.groups: dict[str, LightGroup] = {}
        self.entity_to_group: dict[str, LightGroup] = {}
        self._init_groups()

        self.web_panel = WebPanel(self, host="0.0.0.0", port=8787)

    def _init_groups(self):
        self.groups.clear()
        self.entity_to_group.clear()
        
        raw_groups = self.cfg.get("groups")
        if not raw_groups:
            # 兼容旧单组配置
            old_group = self.cfg.get("lighting_group", {})
            raw_groups = [{
                "id": "main_group",
                "name": old_group.get("name", "默认灯光组"),
                "enabled": True,
                "profile_path": "light_profile.json",
                "lights": old_group.get("lights", [])
            }]

        for g_dict in raw_groups:
            grp = LightGroup(g_dict)
            self.groups[grp.id] = grp
            for ent in grp.light_entities:
                self.entity_to_group[ent] = grp

    def update_timezone(self, offset_hours: float):
        """动态更新时区"""
        self.tz_offset = offset_hours
        self.tz = timezone(timedelta(hours=offset_hours))
        set_log_tz(self.tz)
        self.cfg["location"]["timezone_offset"] = offset_hours
        self.solar.tz_offset = offset_hours
        self.solar.tz = self.tz
        add_log(f"时区已更新为: UTC{'+' if offset_hours>=0 else ''}{offset_hours:g}")

    def update_time_offset(self, delta_minutes: int):
        """动态微调模拟时间偏移"""
        self.time_offset_seconds += delta_minutes * 60
        add_log(f"时间偏移量已调整: {self.time_offset_seconds // 60} 分钟")

    def reset_time_offset(self):
        self.time_offset_seconds = 0
        add_log("时间偏移量已重置为系统实时时间")

    def save_and_reload_config(self, setup_data: dict) -> bool:
        """从预装向导保存新配置并热生效"""
        try:
            ha_url = setup_data.get("ha_url") or self.cfg["home_assistant"]["url"]
            ha_token = setup_data.get("ha_token") or self.cfg["home_assistant"]["token"]
            lat = float(setup_data.get("latitude", self.cfg["location"].get("latitude", 39.9042)))
            lng = float(setup_data.get("longitude", self.cfg["location"].get("longitude", 116.4074)))
            tz_offset = float(setup_data.get("timezone_offset", self.tz_offset))
            groups = setup_data.get("groups")

            if "home_assistant" not in self.cfg:
                self.cfg["home_assistant"] = {}
            if "location" not in self.cfg:
                self.cfg["location"] = {}

            self.cfg["home_assistant"]["url"] = ha_url
            self.cfg["home_assistant"]["token"] = ha_token
            self.cfg["location"]["latitude"] = lat
            self.cfg["location"]["longitude"] = lng
            self.cfg["location"]["timezone_offset"] = tz_offset
            if groups:
                self.cfg["groups"] = groups

            # 持久化写入配置文件
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.cfg, f, allow_unicode=True, sort_keys=False)

            # 更新客户端鉴权
            self.client.update_credentials(ha_url, ha_token)
            # 更新太阳计算器经纬度与时区
            self.solar.latitude = lat
            self.solar.longitude = lng
            self.update_timezone(tz_offset)
            # 重新加载分组
            self._init_groups()
            asyncio.create_task(self._init_light_states())
            add_log(f"已成功应用新配置！受控灯组数: {len(self.groups)}")
            return True
        except Exception as e:
            logger.error(f"保存或重载配置失败: {e}")
            add_log(f"保存配置失败: {e}")
            return False

    def get_current_time(self) -> datetime:
        return datetime.now(self.tz) + timedelta(seconds=self.time_offset_seconds)

    async def start(self):
        msg = f"GoodLight 智能感知服务启动，已加载 {len(self.groups)} 个独立灯光分组"
        logger.info(msg)
        add_log(msg)

        await self.web_panel.start()
        asyncio.create_task(self._metrics_sampler_loop())
        self.client.register_event_listener(self.on_state_changed)
        asyncio.create_task(self._init_light_states())
        await self.client.connect()

    async def _init_light_states(self):
        await asyncio.sleep(2)
        for ent in self.entity_to_group.keys():
            try:
                st = await self.client.get_state(ent)
                if st:
                    state_str = st.get("state", "off")
                    attrs = st.get("attributes", {})
                    b = attrs.get("brightness")
                    c = attrs.get("color_temp_kelvin") or attrs.get("color_temp")
                    pct_b = round((b / 255.0) * 100, 1) if b is not None else 0
                    self.db.record_light_state(ent, pct_b, c, state_str)
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
                for ent in self.entity_to_group.keys():
                    st = await self.client.get_state(ent)
                    if st:
                        state_str = st.get("state", "off")
                        attrs = st.get("attributes", {})
                        b = attrs.get("brightness")
                        c = attrs.get("color_temp_kelvin") or attrs.get("color_temp")
                        pct_b = round((b / 255.0) * 100, 1) if (state_str == "on" and b is not None) else 0
                        self.db.record_light_state(ent, pct_b, c, state_str)
                self.db.cleanup_old_data(max_days=30)
            except Exception as e:
                logger.debug(f"性能采集异常: {e}")
            await asyncio.sleep(30)

    async def on_state_changed(self, event_data: dict):
        entity_id = event_data.get("entity_id")
        grp = self.entity_to_group.get(entity_id)
        if not grp or not grp.enabled:
            return

        old_state = event_data.get("old_state") or {}
        new_state = event_data.get("new_state") or {}

        old_s = old_state.get("state")
        new_s = new_state.get("state")

        if entity_id in self.ignore_updates:
            self.ignore_updates.remove(entity_id)
            return

        now = self.get_current_time()
        hour_float = now.hour + now.minute / 60.0 + now.second / 3600.0

        if old_s != "on" and new_s == "on":
            logger.info(f"[{grp.name}] 检测到灯具开启: {entity_id}")
            await self.handle_light_turned_on(grp, entity_id, now, hour_float)
            return

        if old_s == "on" and new_s == "on":
            old_attrs = old_state.get("attributes", {})
            new_attrs = new_state.get("attributes", {})

            old_b = old_attrs.get("brightness")
            new_b = new_attrs.get("brightness")
            new_c = new_attrs.get("color_temp_kelvin") or new_attrs.get("color_temp")

            pct_b = round((new_b / 255.0) * 100, 1) if new_b is not None else 0
            self.db.record_light_state(entity_id, pct_b, new_c, new_s)

            b_changed = (old_b is not None and new_b is not None and abs(old_b - new_b) >= 3)
            if b_changed:
                self.schedule_learning(grp, hour_float, actual_b=pct_b)

    async def handle_light_turned_on(self, grp: LightGroup, triggered_entity: str, dt: datetime, hour_float: float):
        t0 = time.perf_counter()
        elevation = self.solar.get_solar_elevation(dt)
        term_name, term_prog = self.solar.get_solar_term(dt)
        season_factor = self.solar.get_season_factor(dt)

        pred = grp.model.predict(
            hour_float=hour_float,
            solar_elevation=elevation,
            season_factor=season_factor
        )
        t_model_ms = (time.perf_counter() - t0) * 1000.0

        b_val = max(1, min(255, round((pred["brightness"] / 100.0) * 255)))
        k_val = pred["color_temp"]
        target_count = pred["light_count"]

        # 并发或者按需下发指令，测量网络 I/O 耗时
        t_io_start = time.perf_counter()
        io_tasks = []
        for idx, ent in enumerate(grp.light_entities):
            if idx < target_count:
                self.ignore_updates.add(ent)
                io_tasks.append(self.client.call_service("light", "turn_on", {
                    "entity_id": ent,
                    "brightness": b_val,
                    "color_temp_kelvin": k_val,
                    "transition": 1
                }))
                self.db.record_light_state(ent, pred["brightness"], k_val, "on")

        if io_tasks:
            await asyncio.gather(*io_tasks, return_exceptions=True)
        t_io_ms = (time.perf_counter() - t_io_start) * 1000.0
        total_ms = (time.perf_counter() - t0) * 1000.0

        log_msg = f"[{grp.name}] 开灯响应 -> 模型纯推算耗时: {t_model_ms:.3f}ms | 网络下发耗时: {t_io_ms:.1f}ms | 总响应: {total_ms:.1f}ms (推荐: {pred['brightness']}% / {pred['color_temp']}K / {target_count}盏)"
        logger.info(log_msg)
        add_log(log_msg)

    def schedule_learning(self, grp: LightGroup, hour_float: float, actual_b: float = None, actual_c: int = None, actual_count: int = None):
        debounce_sec = self.cfg.get("learning", {}).get("debounce_seconds", 3.0)
        lr = self.cfg.get("learning", {}).get("learning_rate", 0.25)

        async def _do_learn():
            await asyncio.sleep(debounce_sec)
            grp.model.learn_user_adjustment(
                hour_float=hour_float,
                actual_brightness=actual_b,
                actual_color_temp=actual_c,
                actual_count=actual_count,
                learning_rate=lr
            )
            add_log(f"[{grp.name}] 收到手动调光并完成局部学习 (时刻: {hour_float:.1f}h -> 亮度: {actual_b}%)")

        if "learn" in grp.debounce_tasks:
            grp.debounce_tasks["learn"].cancel()
        grp.debounce_tasks["learn"] = asyncio.create_task(_do_learn())

if __name__ == "__main__":
    service = GoodLightService("config.yaml")
    asyncio.run(service.start())
