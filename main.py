"""
GoodLight Core Daemon Service.
Supports independent multi-group circadian lighting and dynamic timezone/simulation adjustments.
"""

__version__ = "0.1.0"

import os
import time
import asyncio
import logging
from datetime import datetime, timezone, timedelta

# Default to Asia/Shanghai (UTC+8) if TZ not specified, ensuring container log time alignment
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
from weather import WeatherService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("GoodLight.Core")

class LightGroup:
    """Independent lighting control group with its own adaptive model and priority queue."""
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
            logger.warning(f"Config {config_path} not found, falling back to config.example.yaml")
            self.config_path = "config.example.yaml"

        with open(self.config_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)

        ha_cfg = self.cfg["home_assistant"]
        loc_cfg = self.cfg["location"]
        
        self.tz_offset = float(loc_cfg.get("timezone_offset", 8.0))
        self.time_offset_seconds = 0  # Simulation clock offset in seconds
        self.tz = timezone(timedelta(hours=self.tz_offset))
        self.ui_language = self.cfg.get("ui_language", "zh")

        ha_url = os.environ.get("GOODLIGHT_HA_URL", ha_cfg["url"])
        ha_token = os.environ.get("GOODLIGHT_HA_TOKEN", ha_cfg.get("token", ""))

        self.solar = SolarCalculator(
            latitude=loc_cfg["latitude"],
            longitude=loc_cfg["longitude"],
            tz_offset_hours=self.tz_offset
        )
        self.client = HAClient(base_url=ha_url, token=ha_token)
        self.weather = WeatherService(
            lat=loc_cfg.get("latitude", 39.9042),
            lon=loc_cfg.get("longitude", 116.4074),
            enabled=self.cfg.get("weather", {}).get("enabled", True),
            provider=self.cfg.get("weather", {}).get("provider", "auto"),
            log_callback=add_log
        )
        self.weather.set_ha_client(self.client)
        self.season_factor_override: Optional[float] = None
        self.weather_factor_override: Optional[float] = None

        self.db = HistoryDB(db_path="history.db")
        self.ignore_updates = set()
        self.light_states: dict[str, dict] = {}
        self.last_manual_adjust: dict[str, float] = {}
        self.last_command_time: dict[str, float] = {}
        self.last_command_brightness: dict[str, float] = {}

        # Initialize lighting groups
        self.groups: dict[str, LightGroup] = {}
        self.entity_to_group: dict[str, LightGroup] = {}
        self._init_groups()

        self.web_panel = WebPanel(self, host="0.0.0.0", port=8787)

    def update_cached_state(self, entity_id: str, st_data: dict):
        """Update cached entity attributes, detecting hardware physical capabilities."""
        state_str = st_data.get("state", "off")
        attrs = st_data.get("attributes", {})
        modes = attrs.get("supported_color_modes") or []

        # Detect fixture hardware capabilities
        if modes:
            has_b = any(m in modes for m in ["brightness", "color_temp", "hs", "xy", "rgb", "rgbw", "rgbww"])
            has_ct = ("color_temp" in modes)
        else:
            has_b = ("brightness" in attrs)
            has_ct = ("color_temp_kelvin" in attrs or "color_temp" in attrs)

        b = attrs.get("brightness")
        c = attrs.get("color_temp_kelvin") or attrs.get("color_temp")
        if c and c < 1000:
            try:
                c = int(1000000 / c)
            except Exception:
                pass

        min_k = attrs.get("min_color_temp_kelvin")
        max_k = attrs.get("max_color_temp_kelvin")

        pct_b = round((b / 255.0) * 100, 1) if (state_str == "on" and b is not None) else (100.0 if (state_str == "on" and not has_b) else 0.0)
        friendly_name = attrs.get("friendly_name")
        
        cur = self.light_states.get(entity_id, {})
        cur["state"] = state_str
        cur["has_brightness"] = has_b
        cur["has_color_temp"] = has_ct
        if min_k:
            cur["min_kelvin"] = min_k
        if max_k:
            cur["max_kelvin"] = max_k
        cur["brightness"] = pct_b
        if c:
            cur["color_temp"] = c
        elif "color_temp" not in cur and has_ct:
            cur["color_temp"] = 4000
        if friendly_name:
            cur["friendly_name"] = friendly_name
        self.light_states[entity_id] = cur

    def get_light_params(self, entity_id: str, target_b_pct: float, target_k: int):
        """
        Adapt control parameters to physical hardware capabilities and clamp to Kelvin limits.
        Prevents oscillation caused by commanding out-of-range parameters.
        """
        st = self.light_states.get(entity_id, {})
        has_b = st.get("has_brightness", True)
        has_ct = st.get("has_color_temp", True)

        item_cfg = {}
        grp = self.entity_to_group.get(entity_id)
        if grp:
            item_cfg = next((it for it in grp.lights if it.get("entity_id") == entity_id), {})

        min_k = st.get("min_kelvin") or item_cfg.get("min_kelvin", 2700)
        max_k = st.get("max_kelvin") or item_cfg.get("max_kelvin", 6500)

        clamped_k = max(min_k, min(max_k, int(target_k))) if has_ct else None
        clamped_b_pct = target_b_pct if has_b else 100.0
        clamped_b_255 = max(1, min(255, round((target_b_pct / 100.0) * 255))) if has_b else None

        service_data = {"entity_id": entity_id}
        if has_b and clamped_b_255 is not None:
            service_data["brightness"] = clamped_b_255
        if has_ct and clamped_k is not None:
            service_data["color_temp_kelvin"] = clamped_k

        return {
            "has_brightness": has_b,
            "has_color_temp": has_ct,
            "min_kelvin": min_k,
            "max_kelvin": max_k,
            "clamped_brightness_pct": clamped_b_pct,
            "clamped_kelvin": clamped_k,
            "service_data": service_data
        }

    def _init_groups(self):
        """Initialize lighting groups from configuration."""
        self.groups.clear()
        self.entity_to_group.clear()
        
        raw_groups = self.cfg.get("groups")
        if not raw_groups:
            # Backward compatibility for legacy single-group config
            old_group = self.cfg.get("lighting_group", {})
            raw_groups = [{
                "id": "main_group",
                "name": old_group.get("name", "Default Group"),
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
        """Dynamically update timezone offset."""
        self.tz_offset = offset_hours
        self.tz = timezone(timedelta(hours=offset_hours))
        set_log_tz(self.tz)
        self.cfg["location"]["timezone_offset"] = offset_hours
        self.solar.tz_offset = offset_hours
        self.solar.tz = self.tz
        add_log(f"Timezone updated to: UTC{'+' if offset_hours>=0 else ''}{offset_hours:g}")

    def update_time_offset(self, delta_minutes: int):
        """Dynamically adjust simulation time offset."""
        self.time_offset_seconds += delta_minutes * 60
        add_log(f"Simulation time offset adjusted: {self.time_offset_seconds // 60} min")

    def reset_time_offset(self):
        """Reset simulation time offset back to real-time system clock."""
        self.time_offset_seconds = 0
        add_log("Simulation time offset reset to real system clock")

    def get_effective_season_factor(self, dt: datetime = None) -> float:
        """Return season factor respecting manual override if set [-1.0, 1.0]."""
        if self.season_factor_override is not None:
            return max(-1.0, min(1.0, float(self.season_factor_override)))
        if dt is None:
            dt = self.get_current_time()
        return self.solar.get_season_factor(dt)

    def predict_for_group(self, grp: LightGroup, dt: datetime = None) -> dict:
        """Unified circadian prediction for a lighting group using live or overridden factors."""
        if dt is None:
            dt = self.get_current_time()
        h_float = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
        elevation = self.solar.get_solar_elevation(dt)
        season_factor = self.get_effective_season_factor(dt)
        w_summary = self.weather.get_summary() if self.weather.enabled else {}
        curr_temp = w_summary.get("apparent_temperature") or w_summary.get("temperature")
        curr_clouds = w_summary.get("cloud_cover")
        return grp.model.predict(
            hour_float=h_float,
            solar_elevation=elevation,
            season_factor=season_factor,
            temp_celsius=curr_temp,
            cloud_cover=curr_clouds,
            env_b_factor_override=self.weather_factor_override
        )

    def set_factors_override(self, season_factor: Optional[float], weather_factor: Optional[float]):
        """Manually override season and weather factors."""
        self.season_factor_override = season_factor
        self.weather_factor_override = weather_factor
        s_txt = f"{season_factor:.2f}" if season_factor is not None else "自动推算 (Auto)"
        w_txt = f"{weather_factor:.2f}x" if weather_factor is not None else "自动计算 (Auto)"
        add_log(f"⚙️ [因子调优] 已更新 -> 季节因子: {s_txt} | 气象补偿倍率: {w_txt}")

    async def set_weather_source(self, provider: str, manual_params: dict = None):
        """Switch weather source and force immediate refresh."""
        self.weather.provider = provider
        if manual_params:
            if "temp" in manual_params and manual_params["temp"] is not None:
                self.weather.manual_temp = float(manual_params["temp"])
            if "apparent_temp" in manual_params and manual_params["apparent_temp"] is not None:
                self.weather.manual_apparent_temp = float(manual_params["apparent_temp"])
            if "cloud_cover" in manual_params and manual_params["cloud_cover"] is not None:
                self.weather.manual_cloud_cover = int(manual_params["cloud_cover"])
            if "desc" in manual_params and manual_params["desc"]:
                self.weather.manual_desc = str(manual_params["desc"])
        if "weather" not in self.cfg:
            self.cfg["weather"] = {}
        self.cfg["weather"]["provider"] = provider
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.cfg, f, allow_unicode=True, sort_keys=False)
        except Exception as e:
            logger.debug(f"Failed to persist weather config: {e}")
        add_log(f"⚙️ [气象源切换] 用户切换气象数据源至: {provider}")
        await self.weather.fetch_weather(force=True)

    def save_and_reload_config(self, setup_data: dict) -> bool:
        """Save new configuration from setup wizard and hot-reload engine."""
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

            # Weather toggle
            weather_enabled = bool(setup_data.get("weather_enabled", True))
            if "weather" not in self.cfg:
                self.cfg["weather"] = {}
            self.cfg["weather"]["enabled"] = weather_enabled
            self.weather.enabled = weather_enabled

            if "ui_language" in setup_data:
                self.ui_language = setup_data["ui_language"]
                self.cfg["ui_language"] = self.ui_language

            # Persist configuration to disk
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.cfg, f, allow_unicode=True, sort_keys=False)

            # Update client credentials
            self.client.update_credentials(ha_url, ha_token)
            # Update solar calculator coordinates and timezone
            self.solar.latitude = lat
            self.solar.longitude = lng
            self.update_timezone(tz_offset)
            asyncio.create_task(self.weather.update_location(lat, lng))
            # Reload groups
            self._init_groups()
            asyncio.create_task(self._init_light_states())
            add_log(f"Configuration applied successfully! Active groups: {len(self.groups)}")
            return True
        except Exception as e:
            logger.error(f"Failed to save and reload config: {e}")
            add_log(f"Config reload error: {e}")
            return False

    def set_ui_language(self, lang: str):
        """Set UI language preference and persist to config."""
        self.ui_language = lang
        self.cfg["ui_language"] = lang
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.cfg, f, allow_unicode=True, sort_keys=False)
        except Exception as e:
            logger.warning(f"Failed to persist language setting: {e}")

    async def sync_history_from_ha(self, days: int = 14) -> dict:
        """Backfill historical state records from Home Assistant to bootstrap learning curves instantly."""
        total_samples = 0
        entity_stats = {}
        add_log(f"Starting historical backfill from Home Assistant (past {days} days)...")

        for gid, grp in self.groups.items():
            grp_samples = 0
            for ent in grp.light_entities:
                states = await self.client.get_entity_history(ent, days=days)
                ent_on_samples = 0
                for st in states:
                    if st.get("state") == "on":
                        attrs = st.get("attributes", {})
                        b = attrs.get("brightness")
                        c = attrs.get("color_temp_kelvin") or attrs.get("color_temp")
                        if c and c < 1000:
                            try:
                                c = int(1000000 / c)
                            except Exception:
                                c = None

                        last_updated_str = st.get("last_updated")
                        if last_updated_str:
                            try:
                                dt_utc = datetime.fromisoformat(last_updated_str)
                                dt_local = dt_utc.astimezone(self.tz)
                                h_float = dt_local.hour + dt_local.minute / 60.0 + dt_local.second / 3600.0
                                ts = int(dt_utc.timestamp())

                                b_pct = round((b / 255.0) * 100, 1) if b is not None else 80.0
                                c_val = c if c is not None else 4000

                                # Train model anchors
                                grp.model.learn(
                                    hour_float=h_float,
                                    actual_brightness=b_pct,
                                    actual_color_temp=c_val,
                                    actual_count=1
                                )

                                # Record to local timeline db for chart rendering
                                self.db.record_light_state(
                                    entity_id=ent,
                                    brightness=b_pct,
                                    color_temp=c_val,
                                    state="on",
                                    timestamp=ts
                                )
                                ent_on_samples += 1
                            except Exception as ex:
                                logger.debug(f"Error parsing historical state: {ex}")

                grp_samples += ent_on_samples
                entity_stats[ent] = ent_on_samples

            grp.model.save_profile()
            total_samples += grp_samples

        add_log(f"Historical backfill complete! Imported {total_samples} samples, circadian baseline updated.")
        return {
            "ok": True,
            "days": days,
            "total_samples": total_samples,
            "entity_stats": entity_stats
        }

    async def toggle_light(self, entity_id: str, target_state: str) -> dict:
        """Handle manual light toggle from dashboard checkbox."""
        grp = self.entity_to_group.get(entity_id)
        if target_state == "on":
            now = self.get_current_time()
            pred = self.predict_for_group(grp, now) if grp else {"brightness": 80, "color_temp": 4000}

            params = self.get_light_params(entity_id, pred["brightness"], pred["color_temp"])
            self.ignore_updates.add(entity_id)
            svc_data = dict(params["service_data"])
            svc_data["transition"] = 1
            await self.client.call_service("light", "turn_on", svc_data)

            cur = self.light_states.get(entity_id, {})
            cur["state"] = "on"
            rec_b = params["clamped_brightness_pct"] if params["has_brightness"] else 100.0
            rec_k = params["clamped_kelvin"] if params["has_color_temp"] else None
            cur["brightness"] = rec_b
            if rec_k is not None:
                cur["color_temp"] = rec_k
            self.light_states[entity_id] = cur
            self.last_command_time[entity_id] = time.time()
            self.last_command_brightness[entity_id] = rec_b
            self.db.record_light_state(entity_id, rec_b, rec_k, "on")
            grp_name = grp.name if grp else "Light"
            log_str = f"{rec_b}%" if params["has_brightness"] else "ON"
            if rec_k is not None:
                log_str += f" / {rec_k}K"
            add_log(f"[{grp_name}] Turned ON fixture: {entity_id} (Target: {log_str})")
        else:
            self.ignore_updates.add(entity_id)
            self.last_command_time[entity_id] = time.time()
            self.last_command_brightness[entity_id] = 0.0
            await self.client.call_service("light", "turn_off", {
                "entity_id": entity_id,
                "transition": 1
            })
            cur = self.light_states.get(entity_id, {})
            cur["state"] = "off"
            cur["brightness"] = 0
            self.light_states[entity_id] = cur
            self.db.record_light_state(entity_id, 0, cur.get("color_temp", 4000), "off")
            grp_name = grp.name if grp else "Light"
            add_log(f"[{grp_name}] Turned OFF fixture: {entity_id}")

        return {
            "ok": True,
            "entity_id": entity_id,
            "state": target_state,
            "light": self.light_states.get(entity_id, {})
        }

    async def apply_suggested_lights(self, group_id: str) -> dict:
        """Apply recommended light count according to model prediction."""
        target_groups = []
        if group_id == "__all__":
            target_groups = list(self.groups.values())
        elif group_id in self.groups:
            target_groups = [self.groups[group_id]]

        if not target_groups:
            return {"ok": False, "message": "Group not found"}

        now = self.get_current_time()
        total_turned_on = 0
        for grp in target_groups:
            pred = self.predict_for_group(grp, now)
            target_count = pred.get("light_count", 1)

            for idx, ent in enumerate(grp.light_entities):
                if idx < target_count:
                    params = self.get_light_params(ent, pred["brightness"], pred["color_temp"])
                    self.ignore_updates.add(ent)
                    svc_data = dict(params["service_data"])
                    svc_data["transition"] = 1
                    await self.client.call_service("light", "turn_on", svc_data)

                    cur = self.light_states.get(ent, {})
                    cur["state"] = "on"
                    rec_b = params["clamped_brightness_pct"] if params["has_brightness"] else 100.0
                    rec_k = params["clamped_kelvin"] if params["has_color_temp"] else None
                    cur["brightness"] = rec_b
                    if rec_k is not None:
                        cur["color_temp"] = rec_k
                    self.light_states[ent] = cur
                    self.db.record_light_state(ent, rec_b, rec_k, "on")
                    total_turned_on += 1
                else:
                    self.ignore_updates.add(ent)
                    await self.client.call_service("light", "turn_off", {
                        "entity_id": ent,
                        "transition": 1
                    })
                    cur = self.light_states.get(ent, {})
                    cur["state"] = "off"
                    cur["brightness"] = 0
                    self.light_states[ent] = cur
                    self.db.record_light_state(ent, 0, cur.get("color_temp", 4000), "off")

            add_log(f"[{grp.name}] Applied suggestion: Turn on top {target_count} light(s)")

        return {"ok": True, "turned_on": total_turned_on}

    def set_light_mode(self, entity_id: str, mode: str) -> bool:
        """Switch operating mode for a single light: active | turn_on | passive."""
        found = False
        for g in self.cfg.get("groups", []):
            for l in g.get("lights", []):
                if l.get("entity_id") == entity_id:
                    l["mode"] = mode
                    found = True
                    break
        if not found and "lighting_group" in self.cfg:
            for l in self.cfg["lighting_group"].get("lights", []):
                if l.get("entity_id") == entity_id:
                    l["mode"] = mode
                    found = True
                    break

        grp = self.entity_to_group.get(entity_id)
        if grp:
            for l in grp.lights:
                if l.get("entity_id") == entity_id:
                    l["mode"] = mode
                    break

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.cfg, f, allow_unicode=True, sort_keys=False)
            mode_names = {
                "active": "Active Cruise",
                "turn_on": "Turn-On Only",
                "passive": "Passive Learn"
            }
            add_log(f"Light {entity_id} mode switched to: {mode_names.get(mode, mode)}")
            return True
        except Exception as e:
            logger.error(f"Failed to save light mode: {e}")
            return False

    def get_current_time(self) -> datetime:
        """Get current effective datetime including simulation offset."""
        return datetime.now(self.tz) + timedelta(seconds=self.time_offset_seconds)

    async def start(self):
        """Start all services and background event loops."""
        msg = f"GoodLight v{__version__} started, loaded {len(self.groups)} independent group(s)"
        logger.info(msg)
        add_log(msg)

        await self.web_panel.start()
        asyncio.create_task(self._weather_loop())
        asyncio.create_task(self._metrics_sampler_loop())
        asyncio.create_task(self._active_cruise_loop())
        self.client.register_event_listener(self.on_state_changed)
        asyncio.create_task(self._init_light_states())
        await self.client.connect()

    async def _active_cruise_loop(self):
        """Active cruise loop: gently transition active lights along circadian curve over time."""
        await asyncio.sleep(10)
        while True:
            try:
                now = self.get_current_time()
                for gid, grp in self.groups.items():
                    if not grp.enabled:
                        continue

                    pred = self.predict_for_group(grp, now)
                    target_b_pct = pred["brightness"]
                    target_k = pred["color_temp"]

                    for item in grp.lights:
                        ent = item["entity_id"]
                        mode = item.get("mode", "active")
                        if mode != "active":
                            continue

                        st = self.light_states.get(ent, {})
                        if st.get("state") != "on":
                            continue

                        # If user manually adjusted in past 5 minutes, hold preference
                        last_man = self.last_manual_adjust.get(ent, 0)
                        if time.time() - last_man < 300:
                            continue

                        params = self.get_light_params(ent, target_b_pct, target_k)
                        has_b = params["has_brightness"]
                        has_ct = params["has_color_temp"]
                        clamped_k = params["clamped_kelvin"]
                        clamped_b = params["clamped_brightness_pct"]

                        curr_b = st.get("brightness", 0)
                        curr_k = st.get("color_temp", 4000)

                        b_diff = abs(curr_b - clamped_b) >= 1.5 if has_b else False
                        k_diff = abs(curr_k - clamped_k) >= 30 if has_ct else False

                        if b_diff or k_diff:
                            self.ignore_updates.add(ent)
                            svc_data = dict(params["service_data"])
                            svc_data["transition"] = 15  # Smooth 15s easing curve
                            await self.client.call_service("light", "turn_on", svc_data)
                            if has_b:
                                st["brightness"] = clamped_b
                            if has_ct:
                                st["color_temp"] = clamped_k
                            self.light_states[ent] = st
                            rec_b = clamped_b if has_b else 100.0
                            rec_k = clamped_k if has_ct else None
                            self.last_command_time[ent] = time.time()
                            self.last_command_brightness[ent] = rec_b
                            self.db.record_light_state(ent, rec_b, rec_k, "on")
                            logger.debug(f"[{grp.name}] Active cruise transition: {ent} -> {rec_b}% / {rec_k}K")
            except Exception as e:
                logger.debug(f"Exception in active cruise loop: {e}")
            await asyncio.sleep(30)

    async def _weather_loop(self):
        """Periodic background weather polling loop with adaptive backoff."""
        while True:
            poll_interval = 600
            try:
                summary = await self.weather.fetch_weather()
                if summary.get("temperature") is None and self.weather.enabled:
                    poll_interval = 15
            except Exception as e:
                logger.debug(f"Weather fetch exception: {e}")
                poll_interval = 15
            await asyncio.sleep(poll_interval)

    async def _init_light_states(self):
        """Initial state synchronization from Home Assistant."""
        await asyncio.sleep(2)
        for ent in self.entity_to_group.keys():
            try:
                st = await self.client.get_state(ent)
                if st:
                    self.update_cached_state(ent, st)
                    state_str = st.get("state", "off")
                    cached = self.light_states.get(ent, {})
                    has_b = cached.get("has_brightness", True)
                    has_ct = cached.get("has_color_temp", True)
                    b = cached.get("brightness", 0.0)
                    c = cached.get("color_temp") if has_ct else None
                    self.db.record_light_state(ent, b, c, state_str)
            except Exception as e:
                logger.debug(f"Initial sync failed for {ent}: {e}")

    async def _metrics_sampler_loop(self):
        """Sample system and fixture performance metrics every 30s."""
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
                        self.update_cached_state(ent, st)
                        state_str = st.get("state", "off")
                        cached = self.light_states.get(ent, {})
                        has_b = cached.get("has_brightness", True)
                        has_ct = cached.get("has_color_temp", True)
                        b = cached.get("brightness", 0.0)
                        c = cached.get("color_temp") if has_ct else None
                        self.db.record_light_state(ent, b, c, state_str)
                self.db.cleanup_old_data(max_days=30)
            except Exception as e:
                logger.debug(f"Metrics sampling error: {e}")
            await asyncio.sleep(30)

    async def on_state_changed(self, event_data: dict):
        """Handle incoming Home Assistant state_changed WebSocket event."""
        entity_id = event_data.get("entity_id")
        grp = self.entity_to_group.get(entity_id)
        if not grp or not grp.enabled:
            return

        old_state = event_data.get("old_state") or {}
        new_state = event_data.get("new_state") or {}

        if new_state:
            self.update_cached_state(entity_id, new_state)

        old_s = old_state.get("state")
        new_s = new_state.get("state")

        cmd_time = self.last_command_time.get(entity_id, 0)
        time_since_cmd = time.time() - cmd_time

        # Ignore self-generated command echoes during transition (4s grace window)
        if entity_id in self.ignore_updates or time_since_cmd < 4.0:
            if entity_id in self.ignore_updates:
                self.ignore_updates.remove(entity_id)
            if new_s:
                old_attrs = old_state.get("attributes", {})
                new_attrs = new_state.get("attributes", {})
                new_b = new_attrs.get("brightness")
                new_c = new_attrs.get("color_temp_kelvin") or new_attrs.get("color_temp")
                pct_b = round((new_b / 255.0) * 100, 1) if new_b is not None else 0
                self.db.record_light_state(entity_id, pct_b, new_c, new_s)
            return

        now = self.get_current_time()
        hour_float = now.hour + now.minute / 60.0 + now.second / 3600.0

        # Turn ON trigger (physical switch or sensor turn on)
        if old_s != "on" and new_s == "on":
            logger.info(f"[{grp.name}] Fixture turned ON: {entity_id}")
            await self.handle_light_turned_on(grp, entity_id, now, hour_float)
            return

        # Genuine manual dimming / adjustment while light is already on
        if old_s == "on" and new_s == "on":
            old_attrs = old_state.get("attributes", {})
            new_attrs = new_state.get("attributes", {})

            old_b = old_attrs.get("brightness")
            new_b = new_attrs.get("brightness")
            new_c = new_attrs.get("color_temp_kelvin") or new_attrs.get("color_temp")

            pct_b = round((new_b / 255.0) * 100, 1) if new_b is not None else 0
            self.db.record_light_state(entity_id, pct_b, new_c, new_s)

            b_changed = (old_b is not None and new_b is not None and abs(old_b - new_b) >= 5)
            last_cmd_b = self.last_command_brightness.get(entity_id, -999)
            # Only learn if user manually altered brightness significantly away from commanded target
            if b_changed and time_since_cmd >= 5.0 and abs(pct_b - last_cmd_b) >= 5:
                self.last_manual_adjust[entity_id] = time.time()
                self.schedule_learning(grp, hour_float, actual_b=pct_b)

    async def handle_light_turned_on(self, grp: LightGroup, triggered_entity: str, dt: datetime, hour_float: float):
        """Apply circadian target when fixture turns on."""
        t0 = time.perf_counter()
        pred = self.predict_for_group(grp, dt)
        t_model_ms = (time.perf_counter() - t0) * 1000.0
        target_count = pred["light_count"]

        # Concurrently dispatch commands to active fixtures
        t_io_start = time.perf_counter()
        io_tasks = []
        for idx, ent in enumerate(grp.light_entities):
            item_cfg = next((item for item in grp.lights if item.get("entity_id") == ent), {})
            mode = item_cfg.get("mode", "active")

            # In passive mode, GoodLight does not actively command dimming
            if mode == "passive":
                continue

            if idx < target_count:
                params = self.get_light_params(ent, pred["brightness"], pred["color_temp"])
                self.ignore_updates.add(ent)
                svc_data = dict(params["service_data"])
                svc_data["transition"] = 1
                io_tasks.append(self.client.call_service("light", "turn_on", svc_data))
                rec_b = params["clamped_brightness_pct"] if params["has_brightness"] else 100.0
                rec_k = params["clamped_kelvin"] if params["has_color_temp"] else None
                self.last_command_time[ent] = time.time()
                self.last_command_brightness[ent] = rec_b
                self.db.record_light_state(ent, rec_b, rec_k, "on")

        if io_tasks:
            await asyncio.gather(*io_tasks, return_exceptions=True)
        t_io_ms = (time.perf_counter() - t_io_start) * 1000.0
        total_ms = (time.perf_counter() - t0) * 1000.0

        log_msg = f"[{grp.name}] Turn-on response -> Model compute: {t_model_ms:.3f}ms | Network I/O: {t_io_ms:.1f}ms | Total: {total_ms:.1f}ms (Target: {pred['brightness']}% / {pred['color_temp']}K / {target_count} light(s))"
        logger.info(log_msg)
        add_log(log_msg)

    def schedule_learning(self, grp: LightGroup, hour_float: float, actual_b: float = None, actual_c: int = None, actual_count: int = None):
        """Debounce manual adjustments before updating model weights."""
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
            add_log(f"[{grp.name}] Triggered learning: manual adjustment to {actual_b}% (Time: {hour_float:.1f}h, local curve updated)")

        if "learn" in grp.debounce_tasks:
            grp.debounce_tasks["learn"].cancel()
        grp.debounce_tasks["learn"] = asyncio.create_task(_do_learn())

if __name__ == "__main__":
    service = GoodLightService("config.yaml")
    asyncio.run(service.start())
