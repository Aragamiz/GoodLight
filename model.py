"""
GoodLight Core Adaptive Circadian Learning Model.
Features:
1. 24-hour natural circadian baseline with Smooth Hermite cubic interpolation
2. Solar elevation angle, solar terms, and seasonal factor adaptations
3. Intelligent fixture count synergy and prioritization recommendation
4. Online Local Learning with Gaussian kernel decay for manual user adjustments
"""

import math
import json
import os
from typing import Dict, List, Any, Tuple

class GoodLightModel:
    def __init__(self, profile_path: str = "light_profile.json"):
        self.profile_path = profile_path
        self.anchors = {}  # 0~23 hour anchors: {hour: {"brightness": %, "color_temp": K, "light_count": n}}
        self.load_or_init_profile()

    def load_or_init_profile(self):
        """Load trained user preference profile or initialize with circadian default baseline."""
        if os.path.exists(self.profile_path):
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    self.anchors = json.load(f)
                    return
            except Exception as e:
                print(f"[Model] Failed to load saved profile, reinitializing: {e}")

        # Default 24-hour circadian rhythm baseline (human-centric: soft warm amber at night, bright neutral at noon)
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

        # Interpolate anchors to all 24 hours (0~23)
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
                "samples_count": 0  # Number of user manual intervention samples for this hour
            }
        self.save_profile()

    def save_profile(self):
        """Persist model anchor state to disk."""
        try:
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(self.anchors, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Model] Failed to save profile to disk: {e}")

    def save(self):
        """Alias for save_profile."""
        self.save_profile()

    def predict(self, hour_float: float, solar_elevation: float, season_factor: float, temp_celsius: float = None, cloud_cover: int = None, env_b_factor_override: float = None) -> Dict[str, Any]:
        """
        Predict target circadian metrics for current conditions:
        - Target brightness (%)
        - Target color temperature (K)
        - Recommended light fixture count (1~N)
        """
        h_int = int(hour_float) % 24
        next_h = (h_int + 1) % 24
        ratio = hour_float - int(hour_float)

        p1 = self.anchors[str(h_int)]
        p2 = self.anchors[str(next_h)]

        # 1. Base time smooth cubic interpolation (Smooth Hermite Interpolation)
        smooth_t = ratio * ratio * (3 - 2 * ratio)
        base_brightness = p1["brightness"] + (p2["brightness"] - p1["brightness"]) * smooth_t
        base_color_temp = p1["color_temp"] + (p2["color_temp"] - p1["color_temp"]) * smooth_t
        base_count = round(p1["light_count"] + (p2["light_count"] - p1["light_count"]) * smooth_t)

        # 2. Solar elevation angle calibration (Solar Elevation Compensation)
        if solar_elevation < -18:  # Astronomical night
            solar_b_factor = 0.85
            solar_c_offset = -200
        elif solar_elevation > 30:  # Direct bright midday sun
            solar_b_factor = 1.05
            solar_c_offset = 200
        else:
            solar_b_factor = 1.0
            solar_c_offset = 0

        # 3. 24 Solar terms and seasonal thermal compensation (+300K in summer, -300K in winter)
        season_c_offset = season_factor * 300.0

        # 4. Ambient outdoor temperature thermal compensation (warmer when cold, cooler when hot)
        temp_c_offset = 0
        if temp_celsius is not None:
            if temp_celsius < 10:
                temp_c_offset = -250  # Warmer in cold weather
            elif temp_celsius > 28:
                temp_c_offset = +200  # Cooler in hot weather

        # 5. Cloud cover daylight compensation (Cloud Cover Brightness Boost)
        # In daytime with heavy overcast (>50%), gently increase indoor brightness (up to +10%)
        cloud_b_factor = 1.0
        if cloud_cover is not None and solar_elevation > 0:
            if cloud_cover > 50:
                cloud_b_factor = 1.0 + 0.10 * ((cloud_cover - 50) / 50.0)

        # Cap combined environmental boost or use manual override
        if env_b_factor_override is not None:
            env_b_factor = max(0.70, min(1.30, float(env_b_factor_override)))
        else:
            env_b_factor = min(1.10, solar_b_factor * cloud_b_factor)

        final_brightness = max(1.0, min(88.0, base_brightness * env_b_factor))
        final_color_temp = max(2500, min(6500, round(base_color_temp + solar_c_offset + season_c_offset + temp_c_offset)))
        final_count = max(1, base_count)

        return {
            "brightness": round(final_brightness, 1),
            "color_temp": final_color_temp,
            "light_count": final_count
        }

    def learn(self, hour_float: float, actual_brightness: float = None, actual_color_temp: int = None, actual_count: int = None, learning_rate: float = 0.25):
        """Universal adaptive learning interface (alias for learn_user_adjustment)."""
        return self.learn_user_adjustment(hour_float, actual_brightness, actual_color_temp, actual_count, learning_rate)

    def learn_user_adjustment(self, hour_float: float, actual_brightness: float = None, actual_color_temp: int = None, actual_count: int = None, learning_rate: float = 0.25):
        """
        Online Local Learning with Gaussian kernel decay:
        When a user manually dims or switches lights, apply weighted learning to anchor points within a 2-hour window.
        """
        current_h = hour_float % 24
        print(f"[Model] Received user adjustment signal (Time: {current_h:.2f}h) -> Brightness: {actual_brightness}%, CCT: {actual_color_temp}K, Count: {actual_count}")

        for h in range(24):
            # Circular 24-hour time difference
            diff = abs(h - current_h)
            diff = min(diff, 24 - diff)

            if diff > 2.5:
                continue  # Only affect neighboring 2-hour window

            # Gaussian local kernel decay weight
            weight = math.exp(-0.5 * (diff / 1.0) ** 2) * learning_rate
            h_key = str(h)
            node = self.anchors[h_key]

            if actual_brightness is not None:
                node["brightness"] = round(node["brightness"] * (1 - weight) + actual_brightness * weight, 1)

            if actual_color_temp is not None:
                node["color_temp"] = round(node["color_temp"] * (1 - weight) + actual_color_temp * weight)

            if actual_count is not None:
                node["light_count"] = actual_count

            node["samples_count"] = node.get("samples_count", 0) + 1

        self.save_profile()
        print(f"[Model] Profile updated with learned preferences and saved to {self.profile_path}")
