<p align="right">
  <a href="README_zh.md"><b>简体中文</b></a> | <a href="README.md"><b>English</b></a>
</p>

# GoodLight 🌟

> *Auto light like your iPhone.*  
> **An autonomous, self-learning adaptive circadian lighting engine seamlessly integrated with Home Assistant (HA).**

<p align="left">
  <a href="https://www.home-assistant.io/"><img src="https://img.shields.io/badge/Home%20Assistant-Compatible-41BDF5?style=flat-square&logo=home-assistant&logoColor=white" alt="Home Assistant" /></a>
  <a href="https://www.docker.com/"><img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker" /></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.9+" /></a>
  <a href="https://github.com/Aragamiz/GoodLight/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square" alt="License: MIT" /></a>
  <a href="https://github.com/Aragamiz/GoodLight/stargazers"><img src="https://img.shields.io/github/stars/Aragamiz/GoodLight?style=flat-square&logo=github" alt="GitHub Stars" /></a>
</p>

---

## 📖 Overview

**GoodLight** is a lightweight, edge-native circadian lighting system engineered specifically for **Home Assistant (HA)**. It runs locally on routers (OpenWrt / Docker), NAS, Mini PCs, PVE, or servers, harmonizing your smart home lights with natural astronomical rhythms, solar elevation angles, the 24 solar terms, and real-time global weather conditions.

Unlike traditional lighting scripts that continuously poll and force-reset brightness, **GoodLight respects the user**:
- **Non-Aggressive & Self-Learning**: Never fights manual adjustments. Adjusting a light manually in Home Assistant or via a physical switch immediately pauses automation for 5 minutes and teaches GoodLight your localized lighting habits through exponential moving average (EMA) learning with local Gaussian kernel decay.
- **Home Assistant Native**: Connects via high-speed asynchronous WebSocket & REST APIs, automatically discovers `light.*` entities, and dynamically coordinates multiple light groups.
- **Light Quantity Adaptation**: Intelligently decides not only **how bright** and **what color temperature (K)**, but also **how many lights to turn on** (e.g., single soft nightlight at 3 AM vs. multi-light synergy during productive daytime).
- **Global Weather & Cloud Compensation**: Integrates Open-Meteo's free, zero-token global weather service to compensate for outdoor temperatures and heavy cloud cover in real time.

---

## ✨ Key Features

### 1. 🎛️ Per-Light 3-Tier Operating Modes
Every light within any group can be individually configured with its own operational mode, hot-switchable directly from the Web UI:
- **🌊 Active Cruise (`active`)**: 
  - Smoothly transitions brightness and color temperature along circadian curves with gentle 15-second easing transitions throughout the day;
  - Immediately aligns to optimal circadian light target upon being turned on via physical switches or motion sensors.
- **⚡ Turn-On Only (`turn_on`)**: 
  - Aligns to the circadian target only at the exact instant of turning on;
  - Remains static afterwards without continuous cruise adjustments, ideal for work desks or reading lamps where dynamic lighting shifts may cause distraction.
- **🧠 Passive Learn (`passive`)**: 
  - GoodLight never sends automated dimming commands;
  - Silently listens to user manual adjustments in the background to learn and refine personalized room curve models over time.

### 2. ⏳ 14-Day HA History Backfill & Instant Bootstrapping
- **Instant Bootstrapping**: During initial setup or when creating new light groups, pull up to 14 days of real lighting state history from Home Assistant SQLite/DB (`/api/history/period`) with one click.
- **Auto Spline Training**: Automatically extracts historical on/off events and manual dimming samples to fit Hermite cubic spline curves instantly, eliminating the weeks-long "model training phase".

### 3. 🛡️ Hardware Boundary Clamping & Anti-Oscillation
- **Automatic Capability Detection**: Detects whether each fixture supports on/off, dimming, or tunable white, preventing command errors.
- **Kelvin Boundary Clamping**: Supports per-light `min_kelvin` and `max_kelvin` physical limits (e.g., Yeelight, Leishi, Aqara hardware limits).
- **Eliminate Oscillation Deadlocks**: Strictly clamps algorithm suggestions to hardware-supported limits, completely eliminating cyclic oscillation where algorithms command out-of-bounds parameters that the bulb hardware truncates and the sampler reads back in a 30s loop.

### 4. ☀️ Astronomical Solar Tracking & 24 Solar Terms
- **Precise Solar Elevation Angle**: Calculates exact solar elevation angles and true solar time based on geographical coordinates, smoothly guiding transitions across dawn, dusk, civil twilight, and golden hours.
- **24 Solar Terms & Seasonal Factor**: Leverages solar ecliptic longitude ($\lambda$) to seamlessly transition between crisp cool whites in summer (+300K) and cozy warm amber in winter (-300K).

### 5. ⛅ Global Weather & Ambient Temperature Adaptation
- **Open-Meteo Zero-Token Integration**: Free, global, zero-token public weather integration without API keys.
- **Thermal CCT Adaptation**: Adds warm ambiance (-250K) during freezing cold days (< 10°C) and refreshing cool clarity (+200K) during hot summer spells (> 28°C).
- **Cloud-Cover Daylight Compensation**: Automatically boosts indoor brightness up to **+20%** when outdoor daylight is muted by dense cloud cover (`cloud_cover > 50%`).

### 6. 📊 Modern Intuitive Web Dashboard & 5-Step Setup Wizard
- **Friendly Names & Live Badges**: Displays HA friendly entity names and live status badges (`ON`, `OFF`, CCT perception tags).
- **Interactive Multi-View Filters**:
  - **`📊 Dual-Axis`**: Compare brightness percentage (left axis) and color temperature Kelvin (right axis) simultaneously;
  - **`🌿 Brightness Only`**: Clean single-axis percentage curve focusing on illumination;
  - **`☀️ Color Temp Only`**: Warm amber gold gradient curve focusing on color temperature.
- **Built-in 5-Step Onboarding Wizard**:
  1. Welcome & project overview
  2. Home Assistant token validation and connectivity test
  3. Automatic fixture discovery, grouping, and **14-day history backfill**
  4. Global geocoding search and weather adaptation toggle
  5. **Flex switch best practice guide** and one-click launch

---

## 📦 Project Structure

```text
GoodLight/
├── config.example.yaml   # Configuration template with parameter guides
├── solar.py              # Astronomical calculations (Elevation, 24 Solar Terms, Seasons)
├── model.py              # Adaptive learning model (Hermite splines & user feedback)
├── ha_client.py          # Home Assistant WebSocket & REST API client with history backfill
├── weather.py            # Open-Meteo global weather & temperature service (Zero-Token)
├── db.py                 # SQLite historical metrics storage (Performance & light curves)
├── web_panel.py          # Modern web dashboard & 5-step onboarding wizard
├── main.py               # Core daemon orchestrator and active cruise event loop
├── Dockerfile            # Lightweight Docker container definition
├── README.md             # English documentation
└── README_zh.md          # Simplified Chinese documentation
```

---

## 🚀 Quick Start

### 1. Run with Docker (Recommended)

GoodLight is designed to run seamlessly alongside your Home Assistant container with ultra-low resource usage (< 35MB RAM):

```bash
docker run -d \
  --name goodlight \
  --restart unless-stopped \
  --net=host \
  -v /path/to/goodlight/config.yaml:/app/config.yaml \
  -v /path/to/goodlight/history.db:/app/history.db \
  goodlight:latest
```

Once started, open **`http://<YOUR_HOST_IP>:8787`** in your browser to launch the GoodLight Web Panel.

### 💡 Pro Tip: Recommended Switch & Default Light Setup (For Flex / Momentary Switches)

If you use **Flex / Momentary bounce switches** or frequently turn lights on via wall switches:
- **Why the jump happens**: At the instant of power-on, the fixture's local chip restores previous memory state (e.g. bright cool daytime light) before GoodLight's circadian target arrives over the network ~300ms later.
- **Recommended Best Practice (In Mi Home / Vendor App ➔ Light "Default State" Menu)**:
  1. **Turn OFF "Restore Previous State"** (prevents blinding flash of daytime bright light at night);
  2. **Turn ON "Default Light"**, manually adjust light to **minimum brightness (1%) + warmest color temp (3000K/2700K)**, and save as Default Light.
- **The Result**:
  - **Nighttime Power-On**: Instantly lights up at 0ms in soothing eye-protection ambient light with zero glare;
  - **Daytime Power-On**: Acts like a luxurious hotel **Soft-Start / Sunrise Fade-In (gently ramping up from 1% to full daylight)**!

### 2. Run from Source

```bash
# Clone the repository
git clone https://github.com/Aragamiz/GoodLight.git
cd GoodLight

# Install dependencies
pip install aiohttp pyyaml

# Copy config template
cp config.example.yaml config.yaml

# Run the GoodLight engine
python main.py
```

---

## ⚙️ Configuration (`config.yaml`)

```yaml
# GoodLight Configuration
home_assistant:
  url: "http://192.168.1.100:8123"
  token: "YOUR_HA_LONG_LIVED_ACCESS_TOKEN"

location:
  latitude: 39.9042
  longitude: 116.4074
  timezone_offset: 8.0  # Timezone offset in hours (e.g. UTC+8 is 8.0)

weather:
  enabled: true         # Enable Open-Meteo ambient temperature and cloud cover compensation

ui_language: "en"       # Interface language: "en" (English) | "zh" (Simplified Chinese)

groups:
  - id: "living_room_main"
    name: "Living Room Main Lights"
    enabled: true
    profile_path: "profile_living_room_main.json"
    lights:
      - entity_id: "light.living_room_ceiling_main"
        name: "Ceiling Main Light"
        priority: 1
        min_kelvin: 3000   # Hardware minimum color temp (prevents out-of-range oscillation)
        max_kelvin: 5700   # Hardware maximum color temp
        mode: "active"     # Operating mode: 'active' | 'turn_on' | 'passive'
        
      - entity_id: "light.living_room_ceiling_ambient"
        name: "Ceiling Ambient Strip"
        priority: 2
        min_kelvin: 2700
        max_kelvin: 6500
        mode: "turn_on"

learning:
  take_over_learn: true
  learning_rate: 0.25      # Learning rate for manual user adjustments
  debounce_seconds: 3.0    # Debounce interval in seconds
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
