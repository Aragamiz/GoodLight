<p align="right">
  <a href="README.md"><b>English</b></a> | <a href="README_zh.md"><b>简体中文</b></a>
</p>

# GoodLight 🌟

> *Auto light like your iPhone.*  
> **专为 Home Assistant (HA) 打造的自学习、全自主天文节气昼夜自适应智能照明系统。**

<p align="left">
  <a href="https://www.home-assistant.io/"><img src="https://img.shields.io/badge/Home%20Assistant-Compatible-41BDF5?style=flat-square&logo=home-assistant&logoColor=white" alt="Home Assistant" /></a>
  <a href="https://www.docker.com/"><img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker" /></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.9+" /></a>
  <a href="https://github.com/Aragamiz/GoodLight/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square" alt="License: MIT" /></a>
  <a href="https://github.com/Aragamiz/GoodLight/stargazers"><img src="https://img.shields.io/github/stars/Aragamiz/GoodLight?style=flat-square&logo=github" alt="GitHub Stars" /></a>
</p>

---

## 📖 概览

**GoodLight** 是一套专为 **Home Assistant (HA)** 深度定制的轻量级、边缘原生节律照明系统。它可高效运行于路由器 (OpenWrt / Docker)、NAS、Mini PC、PVE 虚拟机或服务器，基于天文太阳真实高度角、二十四节气公转相位及全球实时气象数据，让全屋灯光与大自然光线节律和谐共振。

与传统通过周期性轮询强行重置亮度的死板脚本不同，**GoodLight 真正尊重用户的个性化习惯**：
- **无感介入、自主学习**：绝不与用户的微调对抗。在 HA 或物理开关手动调光后，系统自动暂停干预 5 分钟，并通过指数移动加权算法 (EMA) 与高斯核局部学习，将习惯沉淀为本地专属节律曲线。
- **HA 深度原生集成**：基于极速异步 WebSocket 与 REST API，毫秒级响应 `state_changed` 事件，自动探测 `light.*` 实体并支持多房间独立协同分组。
- **开灯数量智能适配**：不仅智能推算“该调多亮、多暖”，更能根据昼夜时段决策“该开几盏灯”（例如深夜仅开单盏护眼微光地灯，白天多灯协同提供充足照度）。
- **全球免 Key 气象补偿**：深度集成 Open-Meteo 全球气象服务，自动根据室外严寒酷暑微调室内冷暖氛围，并在阴雨云量较厚时自动提高室内亮度。

---

## ✨ 核心特性

### 1. 🎛️ 三档灯具独立调控模式 (3-Tier Operating Modes)
每个灯光分组内的每一盏灯具均可独立配置专属运行模式，可在 Web 控制台随时一键热切换：
- **🌊 全主动巡航 (`active`)**：
  - 随着时间昼夜缓慢流逝，以 15 秒极度柔和的缓动过渡曲线动态调整亮度和色温，丝滑无感；
  - 物理开关或人体传感器开灯瞬间，立即以最适合当前时刻的光线快速点亮。
- **⚡ 打断模式 / 仅开灯接管 (`turn_on`)**：
  - 仅在物理开关、传感器、自动化或 App 开灯的一瞬间，调整至当前节律曲线的目标状态；
  - 开灯后保持静止，不再随时间主动巡航变化，专为对光线微变敏感的工作台或阅读灯设计。
- **🧠 被动学习 / 仅记录 (`passive`)**：
  - GoodLight 完全不主动下发任何调光控制指令；
  - 在后台静默监听用户的手动调节操作，持续优化并训练该房间的个性化节律模型。

### 2. ⏳ 14天历史回溯与零冷启动秒级学习 (14-Day HA History Backfill)
- **零冷启动 (Instant Bootstrapping)**：新装向导或新建灯光分组时，一键从 Home Assistant SQLite / DB 中拉取过去 14 天的真实用光历史记录 (`/api/history/period`)。
- **自动样条拟合**：自动提取用户在不同时刻的开关灯与手动微调习惯，通过三次 Hermite 样条插值瞬间生成个性化自适应曲线，告别数周“模型养成期”，开箱即懂你。

### 3. 🛡️ 硬件物理边界约束与防震荡机制 (Hardware Boundary Clamping & Anti-Oscillation)
- **能力自动探测**：自动扫描识别灯具硬件真实能力（纯开关、单色调光、冷暖双色温），精准匹配控制协议，避免向仅开关灯具下发调光参数。
- **硬件极限保护**：针对不同灯具的物理极限（例如雷士、Yeelight、Aqara 等不同底限如 3000K-5700K），支持在配置中指定 `min_kelvin` / `max_kelvin`。
- **根除震荡死循环**：算法建议值严格截断在物理安全范围内，彻底消除“算法下发 2700K ➔ 硬件截断为 3000K ➔ 采样器回读 3000K ➔ 30 秒后算法再次强推 2700K”的高频锯齿震荡顽疾。

### 4. ☀️ 天文级太阳高度角与二十四节气计算 (Solar & Seasonal Rhythm)
- **精准太阳高度角**：基于地理经纬度精准解算太阳真实高度角，平滑引导黎明破晓、日落黄昏、民用黄昏与黄金时刻的过渡。
- **二十四节气动态补偿**：利用太阳黄经 ($\lambda$) 捕捉地球公转与四季冷暖，夏季提供清爽冷白（最高 +300K），冬季提供温馨暖光（最低 -300K）。

### 5. ⛅ 全球气象与实时温度感知 (Open-Meteo Weather)
- **免 Token 全球公开气象**：无需注册任何 API Key，开箱即用覆盖全球。
- **环境气温冷暖补偿**：冰冷严冬（< 10°C）智能追加温馨暖色（-250K），炎热盛夏（> 28°C）提供清爽冷调（+200K）。
- **阴雨云量采光补偿**：室外阴云密布时（云量 > 50%），室内自动适度增亮最高 **+20%**，补足室外天然采光不足。

### 6. 📊 现代化直观双轴控制台与预装向导 (Modern Web Dashboard)
- **友好别名与状态胶囊**：自动展示 HA 友好名称，搭配状态胶囊徽章（`在线`、`开启`、`色温感知标签`，如 `☀️ 暖白 3000K`）。
- **三重视图无缝切换**：
  - **`📊 双轴综合`**：亮度百分比（左轴）与色温开尔文（右轴）同屏对比，全景掌握 24 小时自然光流；
  - **`🌿 仅看亮度`**：纯净单轴百分比曲线，聚焦明暗节律；
  - **`☀️ 仅看色温`**：高对比度暖金色阶渐变色温曲线，聚焦冷暖变化。
- **5 步预装向导**：
  1. 欢迎与系统概览
  2. Home Assistant Token 验证与连通性检测
  3. 灯具自动探测、分组规划与 **14天历史记录一键回溯学习**
  4. 全球地理逆地理编码检索与气象感知配置
  5. **凌动开关黄金实践指南** 与配置一键保存启动

---

## 📦 项目结构

```text
GoodLight/
├── config.example.yaml   # 配置文件模板 (含完整分组与硬件参数说明)
├── solar.py              # 天文算法模块 (太阳高度角、真太阳时、24节气计算)
├── model.py              # 自适应节律模型 (Hermite样条插值、环境与用户反馈学习)
├── ha_client.py          # Home Assistant WebSocket/REST 客户端与历史数据回溯
├── weather.py            # Open-Meteo 全球实时气象服务 (免 Token)
├── db.py                 # SQLite 高效指标库 (系统资源与灯具历史曲线)
├── web_panel.py          # 现代化 Web 控制台与 5 步预装配置向导
├── main.py               # 核心服务主调度器与自适应巡航事件循环
├── Dockerfile            # 轻量化 Docker 容器构建定义
├── README.md             # 英文说明文档
└── README_zh.md          # 简体中文说明文档
```

---

## 🚀 快速上手

### 1. 使用 Docker 运行 (推荐)

GoodLight 专为路由、NAS 与 Home Assistant 边车环境打造，极低资源占用（内存 < 35MB）：

```bash
docker run -d \
  --name goodlight \
  --restart unless-stopped \
  --net=host \
  -v /path/to/goodlight/config.yaml:/app/config.yaml \
  -v /path/to/goodlight/history.db:/app/history.db \
  goodlight:latest
```

启动完成后，在浏览器打开 **`http://<YOUR_HOST_IP>:8787`** 即可进入 Web 控制台或预装向导。

### 💡 最佳实践指南：凌动开关（回弹开关）与灯具「默认灯光」设置

如果你使用的是**凌动开关（自回弹微断电开关）**或经常通过物理墙壁开关开灯：
- **痛点现象**：开灯瞬间会先闪一下关灯前遗留的旧状态（例如白天残留的高亮冷光），200~300ms 后才被 GoodLight 节律接管变暗变暖。
- **官方推荐黄金配置**（打开米家/易来/厂商 App ➔ 灯具「默认状态」或「通电默认」菜单）：
  1. **关闭「恢复断电前灯光」**（彻底杜绝深夜开灯闪烁刺眼）；
  2. **开启「默认灯光」**：手动将灯光调至**最低亮度（1% 或 最低滑块）**、色温调至**最暖（3000K / 2700K）**，点击保存为默认灯光。
- **体验蜕变**：
  - **深夜开灯**：硬件 0 毫秒以最低极限护眼微光点亮，与 GoodLight 夜间节律目标完全吻合，丝滑舒适；
  - **白天开灯**：硬件以微光柔和唤醒，GoodLight 自动平滑淡入升至明亮自然光，呈现高级酒店级**“日出软启动（Soft Start / Sunrise Fade-in）”**。

### 2. 源码直接运行

```bash
# 克隆代码仓库
git clone https://github.com/Aragamiz/GoodLight.git
cd GoodLight

# 安装运行依赖
pip install aiohttp pyyaml

# 复制配置文件模板
cp config.example.yaml config.yaml

# 启动 GoodLight 核心引擎
python main.py
```

---

## ⚙️ 配置文件示例 (`config.yaml`)

```yaml
# GoodLight 配置文件
home_assistant:
  url: "http://192.168.1.100:8123"
  token: "YOUR_HA_LONG_LIVED_ACCESS_TOKEN"

location:
  latitude: 39.9042
  longitude: 116.4074
  timezone_offset: 8.0  # 时区偏移 (如 UTC+8 为 8.0)

weather:
  enabled: true         # 启用 Open-Meteo 实时气象补偿 (云量与体感温度)

ui_language: "zh"       # 界面语言: "zh" (简体中文) | "en" (English)

groups:
  - id: "living_room_main"
    name: "客厅吸顶灯主组"
    enabled: true
    profile_path: "profile_living_room_main.json"
    lights:
      - entity_id: "light.living_room_ceiling_main"
        name: "客厅主灯"
        priority: 1
        min_kelvin: 3000   # 硬件最低物理色温 (防止越界导致震荡)
        max_kelvin: 5700   # 硬件最高物理色温
        mode: "active"     # 运行模式: 'active' (全主动巡航) | 'turn_on' (仅开灯打断) | 'passive' (被动学习)
        
      - entity_id: "light.living_room_ceiling_ambient"
        name: "客厅氛围光"
        priority: 2
        min_kelvin: 2700
        max_kelvin: 6500
        mode: "turn_on"

learning:
  take_over_learn: true
  learning_rate: 0.25      # 学习速率
  debounce_seconds: 3.0    # 防抖间隔 (秒)
```

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 协议开源。
