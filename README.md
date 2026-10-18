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

**GoodLight** is a lightweight, edge-native circadian lighting system engineered specifically for **Home Assistant (HA)**. It runs locally on routers (OpenWrt / Docker), NAS, Mini PCs, PVE, or servers, harmonizing your smart home lights with natural astronomical rhythms, astronomical solar elevation angles, the 24 solar terms, and real-time global weather conditions.

Unlike traditional lighting scripts that continuously poll and force-reset brightness, **GoodLight respects the user**:
- **Non-Aggressive**: Never fights user adjustments. Adjusting a light manually in Home Assistant or via a physical wall switch teaches GoodLight your localized lighting preferences through online exponential moving average (EMA) learning.
- **Home Assistant Native**: Connects via high-speed asynchronous WebSocket & REST APIs, automatically discovers `light.*` entities, and dynamically coordinates multiple light groups.
- **Light Quantity Adaptation**: Intelligently decides not only **how bright** and **what color temperature (K)**, but also **how many lights to turn on** (e.g., single soft nightlight at 3 AM vs. multi-light synergy during productive daytime).
- **Global Weather & Cloud Compensation**: Integrates Open-Meteo's free, zero-token global weather service to compensate for outdoor temperatures and heavy cloud cover in real time.

---

## ✨ Key Features

### 1. 🏠 Deep Home Assistant (HA) Integration
- **Event-Driven WebSocket Engine**: Listens to Home Assistant state-change events in real time without high-overhead periodic polling.
- **Autonomous Light Discovery**: Scans and parses all `light.*` entities in Home Assistant, automatically categorizing dimmable, tunable-white, and switch-only capabilities.
- **Multi-Group Lighting Orchestration**: Organizes fixtures into independent groups (e.g., Main Ceiling Fixtures, Ambient LED Strips, Desk Lamps) with distinct circadian curves and priority queues.

### 2. ☀️ Astronomical Solar Tracking & 24 Solar Terms
- **Precise Solar Elevation Angle**: Calculates the exact position of the sun above/below the horizon for your exact geographical coordinates, smoothly guiding transitions through astronomical dawn, dusk, civil twilight, and golden hours.
- **24 Solar Terms & Seasonal Factor**: Leverages solar ecliptic longitude ($\lambda$) to seamlessly transition between crisp cool tones in summer (up to +300K) and cozy warm amber in winter (down to -300K).

### 3. ⛅ Global Weather & Ambient Temperature Adaptation
- **Open-Meteo Zero-Token Integration**: No API keys required, works globally out-of-the-box.
- **Thermal CCT Adaptation**: Adds warm ambiance (-250K) during freezing cold days (< 10°C) and refreshing cool clarity (+200K) during hot summer spells (> 28°C).
- **Cloud-Cover Daylight Compensation**: Automatically boosts indoor brightness up to **+20%** when outdoor daylight is muted by dense cloud cover (`cloud_cover > 50%`).

### 4. 🎛️ Modern Web Dashboard & 5-Step Setup Wizard
- **Built-in Web UI (Port 8787)**: Real-time solar metrics, CPU/memory performance graphs, 30-day historical brightness & color temperature curves, and interactive timezone offset tuning.
- **5-Step Onboarding Wizard**:
  1. Welcome & project overview
  2. Home Assistant token entry & connection validation
  3. Automatic fixture discovery and group assignment
  4. Global address geocoding search & weather toggle
  5. One-click config generation & engine deployment

---

## 📦 Project Structure

```text
GoodLight/
├── config.example.yaml   # Sanitized configuration template
├── solar.py              # Astronomical calculations (Elevation, 24 Solar Terms, Seasons)
├── model.py              # Adaptive learning model (Hermite splines, weather & user feedback)
├── ha_client.py          # Home Assistant WebSocket & REST API client with auto-discovery
├── weather.py            # Open-Meteo global weather & temperature service (Zero-Key)
├── db.py                 # SQLite historical metrics (Performance & light curves)
├── web_panel.py          # Modern web dashboard & 5-step onboarding wizard
├── main.py               # Core orchestrator and event loop
├── Dockerfile            # Lightweight Docker container definition
└── README.md
```

---

## 🚀 Quick Start

### 1. Run with Docker (Recommended)

GoodLight is designed to run seamlessly alongside your Home Assistant container:

```bash
docker run -d \
  --name goodlight \
  --restart unless-stopped \
  --net=host \
  -v /path/to/goodlight/config.yaml:/app/config.yaml \
  -v /path/to/goodlight/history.db:/app/history.db \
  goodlight:latest
```

Once started, open **`http://<YOUR_HOST_IP>:8787`** in your browser to launch the GoodLight Web Panel and complete the setup wizard.

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
home_assistant:
  url: "http://192.168.1.100:8123"
  token: "YOUR_HA_LONG_LIVED_ACCESS_TOKEN"

location:
  latitude: 39.9042
  longitude: 116.4074
  timezone_offset: 8.0

weather:
  enabled: true

groups:
  - id: "living_room_main"
    name: "Living Room Main Lights"
    profile_path: "profile_living_room_main.json"
    lights:
      - entity_id: "light.living_room_ceiling"
        name: "Ceiling Light"
        priority: 1
        min_kelvin: 2700
        max_kelvin: 6500
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
