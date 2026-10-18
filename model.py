"""
GoodLight 核心自适应学习模型
支持：
1. 24小时自然基准三次样条曲线
2. 太阳高度角、节气与季节自适应修正
3. 开灯数量（灯具组合）智能推荐与学习
4. 用户手动干预局部高斯衰减增量学习 (Online Local Learning)
"""

import math
import json
import os
from typing import Dict, List, Any, Tuple

class GoodLightModel:
    def __init__(self, profile_path: str = "light_profile.json"):
        self.profile_path = profile_path
        self.anchors = {}  # 0~23小时基准数据: {hour: {"brightness": %, "color_temp": K, "light_count": n}}
        self.load_or_init_profile()

    def load_or_init_profile(self):
        """加载已驯化的用户偏好模型，若无则初始化自然节律默认值"""
        if os.path.exists(self.profile_path):
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    self.anchors = json.load(f)
                    return
            except Exception as e:
                print(f"[Model] 加载历史偏好失败，重新初始化: {e}")

        # 默认 24 小时自然节律基准 (以人为本：深夜极暗暖光、晨起柔和、正午明亮清爽、晚间温馨)
        default_curve = {
            "0":  {"brightness": 12, "color_temp": 2700, "light_count": 1},
            "2":  {"brightness": 8,  "color_temp": 2500, "light_count": 1},
            "4":  {"brightness": 8,  "color_temp": 2500, "light_count": 1},
            "6":  {"brightness": 25, "color_temp": 3200, "light_count": 1},
            "8":  {"brightness": 65, "color_temp": 4200, "light_count": 2},
            "10": {"brightness": 85, "color_temp": 5000, "light_count": 2},
            "12": {"brightness": 95, "color_temp": 5500, "light_count": 2},
            "14": {"brightness": 90, "color_temp": 5200, "light_count": 2},
            "16": {"brightness": 75, "color_temp": 4500, "light_count": 2},
            "18": {"brightness": 55, "color_temp": 3800, "light_count": 2},
            "20": {"brightness": 35, "color_temp": 3200, "light_count": 1},
            "22": {"brightness": 20, "color_temp": 2800, "light_count": 1},
        }

        # 补全插值至整点 0~23
        self.anchors = {}
        for h in range(24):
            lower_h = (h // 2) * 2
            upper_h = (lower_h + 2) % 24
            ratio = (h - lower_h) / 2.0
            p1 = default_curve[str(lower_h)]
            p2 = default_curve[str(upper_h)]

            b = p1["brightness"] + (p2["brightness"] - p1["brightness"]) * ratio
            c = p1["color_temp"] + (p2["color_temp"] - p1["color_temp"]) * ratio
            cnt = p1["light_count"] if ratio < 0.5 else p2["light_count"]

            self.anchors[str(h)] = {
                "brightness": round(b, 1),
                "color_temp": round(c),
                "light_count": cnt,
                "samples_count": 0  # 该时间段的用户干预样本数
            }
        self.save_profile()

    def save_profile(self):
        """保存模型状态到磁盘"""
        try:
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(self.anchors, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Model] 保存偏好失败: {e}")

    def predict(self, hour_float: float, solar_elevation: float, season_factor: float, temp_celsius: float = None) -> Dict[str, Any]:
        """
        根据当前状态预测：
        - 目标亮度 (%)
        - 目标色温 (K)
        - 建议开启的灯光数量 (1~N)
        """
        h_int = int(hour_float) % 24
        next_h = (h_int + 1) % 24
        ratio = hour_float - int(hour_float)

        p1 = self.anchors[str(h_int)]
        p2 = self.anchors[str(next_h)]

        # 1. 基础时间三次平滑插值 (Smooth Hermite Interpolation)
        smooth_t = ratio * ratio * (3 - 2 * ratio)
        base_brightness = p1["brightness"] + (p2["brightness"] - p1["brightness"]) * smooth_t
        base_color_temp = p1["color_temp"] + (p2["color_temp"] - p1["color_temp"]) * smooth_t
        base_count = round(p1["light_count"] + (p2["light_count"] - p1["light_count"]) * smooth_t)

        # 2. 太阳真实高度角自然校准 (Solar Elevation Compensation)
        # 若大白天阴天下雨太阳虽在上方但高度角弱，微调基础光
        if solar_elevation < -18:  # 天文黑夜
            solar_b_factor = 0.85
            solar_c_offset = -200
        elif solar_elevation > 30:  # 正午烈日
            solar_b_factor = 1.05
            solar_c_offset = 200
        else:
            solar_b_factor = 1.0
            solar_c_offset = 0

        # 3. 节气与季节冷暖补偿 (夏至凉白 +300K, 冬至暖黄 -300K)
        season_c_offset = season_factor * 300.0

        # 4. 温度微调 (温度低偏暖，温度高偏冷)
        temp_c_offset = 0
        if temp_celsius is not None:
            if temp_celsius < 10:
                temp_c_offset = -250  # 天冷加暖
            elif temp_celsius > 30:
                temp_c_offset = +250  # 天热加凉

        final_brightness = max(1.0, min(100.0, base_brightness * solar_b_factor))
        final_color_temp = max(2500, min(6500, round(base_color_temp + solar_c_offset + season_c_offset + temp_c_offset)))
        final_count = max(1, base_count)

        return {
            "brightness": round(final_brightness, 1),
            "color_temp": final_color_temp,
            "light_count": final_count
        }

    def learn_user_adjustment(self, hour_float: float, actual_brightness: float = None, actual_color_temp: int = None, actual_count: int = None, learning_rate: float = 0.25):
        """
        在线局部高斯核学习：
        当用户手动拉动了滑块或开关了灯，仅对当前时间点周围 2 小时内的锚点进行加权学习
        """
        current_h = hour_float % 24
        print(f"[Model] 收到人工调教信号 (Time: {current_h:.2f}h) -> 亮度: {actual_brightness}, 色温: {actual_color_temp}, 灯数: {actual_count}")

        for h in range(24):
            # 环形时间差
            diff = abs(h - current_h)
            diff = min(diff, 24 - diff)

            if diff > 2.5:
                continue  # 仅影响前后 2 小时窗口

            # 高斯局部核衰减权重
            weight = math.exp(-0.5 * (diff / 1.0) ** 2) * learning_rate
            h_key = str(h)
            node = self.anchors[h_key]

            if actual_brightness is not None:
                node["brightness"] = round(node["brightness"] * (1 - weight) + actual_brightness * weight, 1)

            if actual_color_temp is not None:
                node["color_temp"] = round(node["color_temp"] * (1 - weight) + actual_color_temp * weight)

            if actual_count is not None:
                # 离散计数向多数偏好收敛
                node["light_count"] = actual_count

            node["samples_count"] = node.get("samples_count", 0) + 1

        self.save_profile()
        print(f"[Model] 偏好学习完成并已持久化到 {self.profile_path}")
