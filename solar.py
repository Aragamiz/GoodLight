"""
GoodLight 天文与节气计算模块 (纯数学实现，零外部沉重依赖)
支持：
- 真实太阳高度角 (Solar Elevation) 与方位角 (Azimuth)
- 真实日出、日落与暮光时间 (Dawn, Dusk, Golden Hour)
- 太阳黄经 (Solar Ecliptic Longitude) 与二十四节气精确判定
- 四季相位 (Astronomical Seasons)
"""

import math
from datetime import datetime, timezone, timedelta

# 二十四节气名称 (按黄经 0度-春分 顺时针排列)
SOLAR_TERMS = [
    ("春分", 0),   ("清明", 15),  ("谷雨", 30),  ("立夏", 45),
    ("小满", 60),  ("芒种", 75),  ("夏至", 90),  ("小暑", 105),
    ("大暑", 120), ("立秋", 135), ("处暑", 150), ("白露", 165),
    ("秋分", 180), ("寒露", 195), ("霜降", 210), ("立冬", 225),
    ("小雪", 240), ("大雪", 255), ("冬至", 270), ("小寒", 285),
    ("大寒", 300), ("立春", 315), ("雨水", 330), ("惊蛰", 345)
]

class SolarCalculator:
    def __init__(self, latitude: float, longitude: float, tz_offset_hours: float = 8.0):
        self.lat = latitude
        self.lon = longitude
        self.tz = timezone(timedelta(hours=tz_offset_hours))

    def _julian_day(self, dt: datetime) -> float:
        """计算儒略日"""
        utc = dt.astimezone(timezone.utc)
        year, month, day = utc.year, utc.month, utc.day
        hour = utc.hour + utc.minute / 60.0 + utc.second / 3600.0
        if month <= 2:
            year -= 1
            month += 12
        A = math.floor(year / 100)
        B = 2 - A + math.floor(A / 4)
        jd = math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + B - 1524.5
        return jd + hour / 24.0

    def get_solar_longitude(self, dt: datetime) -> float:
        """计算太阳真黄经 (0~360度)，用于判定二十四节气"""
        jd = self._julian_day(dt)
        T = (jd - 2451545.0) / 36525.0
        # 太阳平黄经
        L0 = 280.46646 + 36000.76983 * T + 0.0003032 * T * T
        # 太阳平近点角
        M = 357.52911 + 35999.05029 * T - 0.0001537 * T * T
        M_rad = math.radians(M)
        # 太阳中心差
        C = (1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(M_rad) \
            + (0.019993 - 0.000101 * T) * math.sin(2 * M_rad) \
            + 0.000289 * math.sin(3 * M_rad)
        true_lon = (L0 + C) % 360.0
        return true_lon

    def get_solar_term(self, dt: datetime) -> tuple[str, float]:
        """获取当前二十四节气名称与节气相位进度 (0.0 ~ 1.0)"""
        lon = self.get_solar_longitude(dt)
        term_idx = int(lon // 15)
        name, base_lon = SOLAR_TERMS[term_idx]
        progress = (lon - base_lon) / 15.0
        return name, progress

    def get_season_factor(self, dt: datetime) -> float:
        """
        季节冷暖偏好因子 [-1.0, 1.0]
        冬至 (-1.0) -> 春分 (0.0) -> 夏至 (1.0) -> 秋分 (0.0)
        夏至偏凉白，冬至偏暖黄
        """
        lon = self.get_solar_longitude(dt)
        # 黄经 90度为夏至 (1.0)，270度为冬至 (-1.0)
        return math.sin(math.radians(lon))

    def get_solar_elevation(self, dt: datetime) -> float:
        """计算当前时刻的太阳真实高度角 (单位: 度，水平线上为正，线下为负)"""
        jd = self._julian_day(dt)
        T = (jd - 2451545.0) / 36525.0
        L0 = 280.46646 + 36000.76983 * T
        M = 357.52911 + 35999.05029 * T
        M_rad = math.radians(M)
        C = (1.914602 - 0.004817 * T) * math.sin(M_rad) + 0.02 * math.sin(2 * M_rad)
        true_lon = math.radians(L0 + C)
        # 黄赤交角
        obliquity = math.radians(23.439291 - 0.0130042 * T)
        # 太阳赤纬
        dec = math.asin(math.sin(obliquity) * math.sin(true_lon))
        # 均时差
        e_time = 4.0 * math.degrees(math.tan(obliquity / 2)**2 * math.sin(2 * true_lon) - 2 * 0.0167 * math.sin(M_rad))

        utc = dt.astimezone(timezone.utc)
        solar_noon_offset = 720 - 4.0 * self.lon - e_time
        time_minutes = utc.hour * 60 + utc.minute + utc.second / 60.0
        hour_angle = (time_minutes - solar_noon_offset) / 4.0
        ha_rad = math.radians(hour_angle)

        lat_rad = math.radians(self.lat)
        sin_elevation = math.sin(lat_rad) * math.sin(dec) + math.cos(lat_rad) * math.cos(dec) * math.cos(ha_rad)
        elevation = math.degrees(math.asin(max(-1.0, min(1.0, sin_elevation))))
        return elevation
