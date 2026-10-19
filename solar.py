"""
GoodLight Astronomical and Circadian Solar Calculator (Pure math implementation, zero external heavy dependencies).
Features:
- Precise Solar Elevation and Azimuth angles
- Accurate Astronomical Dawn, Dusk, and Golden Hour
- Solar Ecliptic Longitude and 24 Solar Terms evaluation
- Astronomical Seasonal Factors
"""

import math
from datetime import datetime, timezone, timedelta

# 24 Solar Terms in astronomical solar longitude order (0 deg = Spring Equinox)
SOLAR_TERMS = [
    ("春分 / Spring Equinox", 0),    ("清明 / Pure Brightness", 15),  ("谷雨 / Grain Rain", 30),        ("立夏 / Start of Summer", 45),
    ("小满 / Grain Buds", 60),       ("芒种 / Grain in Ear", 75),     ("夏至 / Summer Solstice", 90),   ("小暑 / Minor Heat", 105),
    ("大暑 / Major Heat", 120),      ("立秋 / Start of Autumn", 135), ("处暑 / End of Heat", 150),      ("白露 / White Dew", 165),
    ("秋分 / Autumnal Equinox", 180),("寒露 / Cold Dew", 195),        ("霜降 / Frost's Descent", 210),  ("立冬 / Start of Winter", 225),
    ("小雪 / Minor Snow", 240),      ("大雪 / Major Snow", 255),      ("冬至 / Winter Solstice", 270),  ("小寒 / Minor Cold", 285),
    ("大寒 / Major Cold", 300),      ("立春 / Start of Spring", 315), ("雨水 / Rain Water", 330),       ("惊蛰 / Awakening of Insects", 345)
]

class SolarCalculator:
    def __init__(self, latitude: float, longitude: float, tz_offset_hours: float = 8.0):
        self.lat = latitude
        self.lon = longitude
        self.tz = timezone(timedelta(hours=tz_offset_hours))

    def _julian_day(self, dt: datetime) -> float:
        """Calculate astronomical Julian Day from datetime."""
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
        """Calculate true solar ecliptic longitude (0~360 deg) for 24 Solar Terms evaluation."""
        jd = self._julian_day(dt)
        T = (jd - 2451545.0) / 36525.0
        # Mean longitude
        L0 = 280.46646 + 36000.76983 * T + 0.0003032 * T * T
        # Mean anomaly
        M = 357.52911 + 35999.05029 * T - 0.0001537 * T * T
        M_rad = math.radians(M)
        # Equation of center
        C = (1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(M_rad) \
            + (0.019993 - 0.000101 * T) * math.sin(2 * M_rad) \
            + 0.000289 * math.sin(3 * M_rad)
        true_lon = (L0 + C) % 360.0
        return true_lon

    def get_solar_term(self, dt: datetime) -> tuple[str, float]:
        """Return current solar term name and phase progress (0.0 ~ 1.0)."""
        lon = self.get_solar_longitude(dt)
        term_idx = int(lon // 15)
        name, base_lon = SOLAR_TERMS[term_idx]
        progress = (lon - base_lon) / 15.0
        return name, progress

    def get_season_factor(self, dt: datetime) -> float:
        """
        Seasonal thermal preference factor [-1.0, 1.0].
        Winter Solstice (-1.0) -> Spring Equinox (0.0) -> Summer Solstice (1.0) -> Autumnal Equinox (0.0).
        Positive values skew towards cooler whites; negative values skew towards warmer ambers.
        """
        lon = self.get_solar_longitude(dt)
        # Solar longitude 90 deg is Summer Solstice (1.0), 270 deg is Winter Solstice (-1.0)
        return math.sin(math.radians(lon))

    def get_solar_elevation(self, dt: datetime) -> float:
        """Calculate true solar elevation angle (degrees, positive above horizon, negative below)."""
        jd = self._julian_day(dt)
        T = (jd - 2451545.0) / 36525.0
        L0 = 280.46646 + 36000.76983 * T
        M = 357.52911 + 35999.05029 * T
        M_rad = math.radians(M)
        C = (1.914602 - 0.004817 * T) * math.sin(M_rad) + 0.02 * math.sin(2 * M_rad)
        true_lon = math.radians(L0 + C)
        # Obliquity of the ecliptic
        obliquity = math.radians(23.439291 - 0.0130042 * T)
        # Solar declination
        dec = math.asin(math.sin(obliquity) * math.sin(true_lon))
        # Equation of time
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
