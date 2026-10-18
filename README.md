# GoodLight 🌟

> **A fully autonomous, self-learning adaptive circadian lighting engine.**  
> Runs locally on edge devices (Routers, PVE, NAS, or Docker), naturally synchronizing with geographical solar rhythms, the 24 solar terms, and real-time environmental factors to intelligently predict and adaptively adjust **brightness, color temperature, and the number of active lights**.

---

## 💡 Core Philosophy

1. **Zero Aggressive Overrides (Respecting the User)**:
   - Traditional automation components continuously poll and forcefully reset lights, fighting manual user adjustments.
   - **GoodLight Principle: Intervene only upon turn-on or ambient shifts**. Once the light is on, the user has full manual control. GoodLight will **never fight back**; instead, it silently learns user adjustments as localized training feedback.
2. **True Astronomical & Seasonal Harmony**:
   - **Real Solar Elevation Angle**: Pure mathematical calculation based on local coordinates. Dawn, dusk, golden hour, and twilight are accurately tracked in real time.
   - **24 Solar Terms & Astronomical Seasons**: Derived from solar ecliptic longitude ($\lambda$), automatically modulating cooler tones in summer and warmer ambiance in winter.
   - **Environmental Temperature Compensation**: Naturally offsets indoor/outdoor seasonal temperature shifts.
3. **Multi-Light Synergy & Quantity Learning**:
   - Manages groups of lights (e.g., ceiling main lights, ambient strips, and desk lamps).
   - Dynamically determines **how many lights to activate** (e.g., minimal single accent light late at night vs. full multi-light illumination during daytime peak).
4. **Lightweight Mathematical Engine (Zero Heavy Dependencies)**:
   - Powered by localized anchor-based cubic Hermite splines with online Gaussian decay weighting (EMA).
   - Ultra-fast inference (`<0.01 ms`), minuscule memory footprint (`<20 MB`), with state persisted in clean, human-readable JSON files.

---

## 📦 Project Structure

```text
GoodLight/
├── config.example.yaml       # Configuration template (sanitized)
├── solar.py                  # Astronomical calculations (Elevation, Terms, Seasons)
├── model.py                  # Adaptive learning model (Spline interpolation & feedback)
├── ha_client.py              # Home Assistant WebSocket & REST event engine
├── main.py                   # Service entry point & orchestration
├── Dockerfile                # Ultra-lightweight Alpine Python container
└── README.md
```

---

## 🚀 Quick Start

### 1. Configuration
Copy the template and configure your local settings:
```bash
cp config.example.yaml config.yaml
```
Edit `config.yaml` with your Home Assistant URL, Long-Lived Access Token, local coordinates, and target light entity IDs.

### 2. Run Locally
```bash
pip install aiohttp pyyaml
python main.py
```

### 3. Run with Docker
```bash
docker build -t goodlight:latest .
docker run -d \
  --name goodlight \
  --restart unless-stopped \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -v $(pwd)/light_profile.json:/app/light_profile.json \
  goodlight:latest
```

---

## 📄 License
MIT License.
