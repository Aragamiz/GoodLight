"""
GoodLight 现代可视化 Web Dashboard 控制面板 (带时区调整、时间微调与多分组控制)
"""

import os
import time
import json
import collections
from datetime import datetime
from aiohttp import web

LOG_BUFFER = collections.deque(maxlen=200)

def add_log(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    LOG_BUFFER.append(f"[{timestamp}] {msg}")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GoodLight Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    :root {
      --bg: #0b1329;
      --card-bg: #152238;
      --border: #233554;
      --text: #f8fafc;
      --subtext: #8892b0;
      --primary: #38bdf8;
      --accent: #fbbf24;
      --success: #4ade80;
      --rose: #fb7185;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      padding: 20px;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
    }
    .title { font-size: 24px; font-weight: 700; color: var(--primary); display: flex; align-items: center; gap: 8px; }
    .badge {
      background: rgba(74, 222, 128, 0.15);
      color: var(--success);
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 13px;
      font-weight: 600;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
      margin-bottom: 20px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 18px;
      margin-bottom: 20px;
    }
    .card-title {
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--subtext);
      margin-bottom: 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .stat-val { font-size: 24px; font-weight: 700; color: var(--text); }
    .stat-sub { font-size: 13px; color: var(--subtext); margin-top: 4px; }
    
    .range-selector {
      display: flex;
      gap: 6px;
      background: #090e1a;
      padding: 3px;
      border-radius: 8px;
      border: 1px solid var(--border);
    }
    .range-btn {
      background: transparent;
      border: none;
      color: var(--subtext);
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 12px;
      cursor: pointer;
      font-weight: 500;
      transition: all 0.2s;
    }
    .range-btn.active {
      background: var(--primary);
      color: #0b1329;
      font-weight: 700;
    }
    .btn-action {
      background: #1e293b;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 5px 12px;
      border-radius: 6px;
      font-size: 12px;
      cursor: pointer;
      transition: 0.2s;
    }
    .btn-action:hover {
      background: var(--primary);
      color: #0b1329;
    }
    .chart-box {
      position: relative;
      width: 100%;
      height: 240px;
    }
    .log-box {
      background: #070c18;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px;
      height: 180px;
      overflow-y: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
      line-height: 1.6;
      color: #cbd5e1;
    }
    .curve-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    .curve-table th, .curve-table td {
      padding: 6px 10px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }
    .curve-table th { color: var(--subtext); font-weight: 500; }
    .highlight-row { background: rgba(56, 189, 248, 0.12); color: var(--primary); font-weight: 600; }
    select {
      background: #090e1a;
      color: var(--text);
      border: 1px solid var(--border);
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 13px;
      outline: none;
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="title">🌟 GoodLight 控制面板</div>
    <div style="display: flex; gap: 10px; align-items: center;">
      <div id="sim-time-badge" style="font-size: 13px; color: var(--accent);">时间: --:--:--</div>
      <div class="badge" id="status-badge">● 正在运行</div>
    </div>
  </div>

  <!-- 时间与时区控制条 -->
  <div class="card" style="padding: 14px 18px; margin-bottom: 16px;">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
      <div style="display: flex; align-items: center; gap: 10px;">
        <span style="font-size: 13px; color: var(--subtext);">🌐 时区选择:</span>
        <select id="tz-select" onchange="onTimezoneChange(this.value)">
          <option value="8.0">UTC+8 (北京 / 上海 / 香港 / 台北)</option>
          <option value="9.0">UTC+9 (东京 / 首尔)</option>
          <option value="0.0">UTC+0 (伦敦 / GMT)</option>
          <option value="1.0">UTC+1 (巴黎 / 柏林)</option>
          <option value="-5.0">UTC-5 (纽约 / 美东)</option>
          <option value="-8.0">UTC-8 (旧金山 / 洛杉矶 / 太平洋)</option>
        </select>
      </div>

      <div style="display: flex; align-items: center; gap: 8px;">
        <span style="font-size: 13px; color: var(--subtext);">⏳ 时间微调测试:</span>
        <button class="btn-action" onclick="adjustTime(-60)">-1小时</button>
        <button class="btn-action" onclick="adjustTime(-15)">-15分</button>
        <button class="btn-action" onclick="adjustTime(15)">+15分</button>
        <button class="btn-action" onclick="adjustTime(60)">+1小时</button>
        <button class="btn-action" style="border-color: var(--accent); color: var(--accent);" onclick="resetTime()">重置当前时间</button>
      </div>
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <div class="card-title">天体与节气感知 <span>☀️</span></div>
      <div class="stat-val" id="solar-term">--</div>
      <div class="stat-sub" id="solar-elevation">太阳高度角: --°</div>
    </div>
    <div class="card">
      <div class="card-title">分组选择与预测 <span>💡</span></div>
      <div style="margin-bottom: 8px;">
        <select id="group-select" onchange="onGroupChange(this.value)"></select>
      </div>
      <div class="stat-val" id="predict-target" style="font-size: 20px;">--% / --K</div>
      <div class="stat-sub" id="predict-count">建议开灯数: -- 盏</div>
    </div>
    <div class="card">
      <div class="card-title">系统性能占用 <span>⚡</span></div>
      <div class="stat-val" id="proc-cpu">CPU: --%</div>
      <div class="stat-sub" id="proc-mem">内存: -- MB | 运行: --</div>
    </div>
    <div class="card">
      <div class="card-title">当前分组灯具 <span>🎛️</span></div>
      <div class="stat-val" style="font-size: 16px;" id="current-group-name">--</div>
      <div class="stat-sub" id="current-group-lights">--</div>
    </div>
  </div>

  <!-- 性能时序曲线图 -->
  <div class="card">
    <div class="card-title">
      <span>系统性能时序曲线 (CPU % & 内存占用)</span>
      <div class="range-selector">
        <button class="range-btn active" onclick="changePerfRange(1, this)">1小时</button>
        <button class="range-btn" onclick="changePerfRange(24, this)">24小时</button>
        <button class="range-btn" onclick="changePerfRange(168, this)">7天</button>
        <button class="range-btn" onclick="changePerfRange(720, this)">30天</button>
      </div>
    </div>
    <div class="chart-box">
      <canvas id="perfChart"></canvas>
    </div>
  </div>

  <!-- 每一个灯的独立曲线图容器 -->
  <div id="lights-charts-container"></div>

  <!-- 运行日志 -->
  <div class="card">
    <div class="card-title">实时运行与学习日志 <span>📋</span></div>
    <div class="log-box" id="log-box"></div>
  </div>

  <!-- 24小时自适应偏好曲线表 -->
  <div class="card">
    <div class="card-title"><span id="table-title">当前分组 24小时自适应曲线</span> <span>📈</span></div>
    <div style="max-height: 200px; overflow-y: auto;">
      <table class="curve-table">
        <thead>
          <tr>
            <th>时间点</th>
            <th>学习亮度</th>
            <th>学习色温</th>
            <th>协同开灯数</th>
            <th>调教样本数</th>
          </tr>
        </thead>
        <tbody id="curve-tbody"></tbody>
      </table>
    </div>
  </div>

  <script>
    let currentPerfHours = 1;
    let currentLightHours = 24;
    let perfChart = null;
    let lightCharts = {};
    let selectedGroupId = null;
    let groupsData = {};

    function initPerfChart() {
      const ctx = document.getElementById('perfChart').getContext('2d');
      perfChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'CPU 占用率 (%)',
              data: [],
              borderColor: '#38bdf8',
              backgroundColor: 'rgba(56, 189, 248, 0.1)',
              tension: 0.3,
              yAxisID: 'y'
            },
            {
              label: '物理内存 (MB)',
              data: [],
              borderColor: '#fbbf24',
              backgroundColor: 'rgba(251, 191, 36, 0.1)',
              tension: 0.3,
              yAxisID: 'y1'
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          scales: {
            x: { grid: { color: '#1e293b' }, ticks: { color: '#8892b0' } },
            y: {
              type: 'linear', display: true, position: 'left',
              title: { display: true, text: 'CPU (%)', color: '#38bdf8' },
              grid: { color: '#1e293b' }, ticks: { color: '#8892b0' }
            },
            y1: {
              type: 'linear', display: true, position: 'right',
              title: { display: true, text: '内存 (MB)', color: '#fbbf24' },
              grid: { drawOnChartArea: false }, ticks: { color: '#8892b0' }
            }
          },
          plugins: { legend: { labels: { color: '#f8fafc' } } }
        }
      });
    }

    async function changePerfRange(hours, btn) {
      currentPerfHours = hours;
      document.querySelectorAll('.range-selector button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      await updatePerfData();
    }

    async function changeLightRange(hours, btn) {
      currentLightHours = hours;
      document.querySelectorAll('.light-range-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      await updateLightData();
    }

    async function onTimezoneChange(val) {
      await fetch('/api/control/timezone', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ timezone_offset: parseFloat(val) })
      });
      await updateDashboard();
    }

    async function adjustTime(minutes) {
      await fetch('/api/control/time_adjust', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ delta_minutes: minutes })
      });
      await updateDashboard();
    }

    async function resetTime() {
      await fetch('/api/control/time_reset', { method: 'POST' });
      await updateDashboard();
    }

    function onGroupChange(gid) {
      selectedGroupId = gid;
      renderCurrentGroup();
    }

    async function updatePerfData() {
      try {
        const resp = await fetch(`/api/history/perf?hours=${currentPerfHours}`);
        const data = await resp.json();
        if (perfChart) {
          perfChart.data.labels = data.labels;
          perfChart.data.datasets[0].data = data.cpu;
          perfChart.data.datasets[1].data = data.memory;
          perfChart.update();
        }
      } catch (e) {
        console.error("更新性能数据失败:", e);
      }
    }

    async function updateLightData() {
      try {
        const resp = await fetch(`/api/history/lights?hours=${currentLightHours}`);
        const data = await resp.json();
        const container = document.getElementById('lights-charts-container');

        for (const [entityId, hData] of Object.entries(data)) {
          let safeId = entityId.replace(/[^a-zA-Z0-9_]/g, '_');
          let card = document.getElementById(`card-${safeId}`);

          if (!card) {
            card = document.createElement('div');
            card.className = 'card';
            card.id = `card-${safeId}`;
            card.innerHTML = `
              <div class="card-title">
                <span>💡 灯具曲线: ${entityId} (亮度 & 色温)</span>
                <div class="range-selector">
                  <button class="range-btn light-range-btn ${currentLightHours==1?'active':''}" onclick="changeLightRange(1, this)">1小时</button>
                  <button class="range-btn light-range-btn ${currentLightHours==24?'active':''}" onclick="changeLightRange(24, this)">24小时</button>
                  <button class="range-btn light-range-btn ${currentLightHours==168?'active':''}" onclick="changeLightRange(168, this)">7天</button>
                  <button class="range-btn light-range-btn ${currentLightHours==720?'active':''}" onclick="changeLightRange(720, this)">30天</button>
                </div>
              </div>
              <div class="chart-box">
                <canvas id="canvas-${safeId}"></canvas>
              </div>
            `;
            container.appendChild(card);

            const ctx = document.getElementById(`canvas-${safeId}`).getContext('2d');
            lightCharts[entityId] = new Chart(ctx, {
              type: 'line',
              data: {
                labels: hData.labels,
                datasets: [
                  {
                    label: '亮度 (%)',
                    data: hData.brightness,
                    borderColor: '#4ade80',
                    backgroundColor: 'rgba(74, 222, 128, 0.1)',
                    tension: 0.3,
                    yAxisID: 'y'
                  },
                  {
                    label: '色温 (K)',
                    data: hData.color_temp,
                    borderColor: '#fb7185',
                    backgroundColor: 'rgba(251, 113, 133, 0.1)',
                    tension: 0.3,
                    yAxisID: 'y1'
                  }
                ]
              },
              options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                scales: {
                  x: { grid: { color: '#1e293b' }, ticks: { color: '#8892b0' } },
                  y: {
                    type: 'linear', display: true, position: 'left',
                    min: 0, max: 100,
                    title: { display: true, text: '亮度 (%)', color: '#4ade80' },
                    grid: { color: '#1e293b' }, ticks: { color: '#8892b0' }
                  },
                  y1: {
                    type: 'linear', display: true, position: 'right',
                    title: { display: true, text: '色温 (K)', color: '#fb7185' },
                    grid: { drawOnChartArea: false }, ticks: { color: '#8892b0' }
                  }
                },
                plugins: { legend: { labels: { color: '#f8fafc' } } }
              }
            });
          } else {
            const chart = lightCharts[entityId];
            if (chart) {
              chart.data.labels = hData.labels;
              chart.data.datasets[0].data = hData.brightness;
              chart.data.datasets[1].data = hData.color_temp;
              chart.update();
            }
          }
        }
      } catch (e) {
        console.error("更新灯具历史数据失败:", e);
      }
    }

    function renderCurrentGroup() {
      if (!selectedGroupId || !groupsData[selectedGroupId]) return;
      const g = groupsData[selectedGroupId];

      document.getElementById('current-group-name').innerText = g.name;
      document.getElementById('current-group-lights').innerText = g.lights.join(', ');
      document.getElementById('predict-target').innerText = `${g.prediction.brightness}% / ${g.prediction.color_temp}K`;
      document.getElementById('predict-count').innerText = `建议开启灯具: ${g.prediction.light_count} 盏`;
      document.getElementById('table-title').innerText = `[${g.name}] 24小时自适应曲线`;

      const currentHour = new Date().getHours();
      const tbody = document.getElementById('curve-tbody');
      tbody.innerHTML = '';
      for (let h = 0; h < 24; h++) {
        const item = g.profile[h.toString()] || {};
        const isCurrent = (h === currentHour);
        const tr = document.createElement('tr');
        if (isCurrent) tr.className = 'highlight-row';
        tr.innerHTML = `
          <td>${h.toString().padStart(2, '0')}:00 ${isCurrent ? '👈 (当前)' : ''}</td>
          <td>${item.brightness || '--'}%</td>
          <td>${item.color_temp || '--'}K</td>
          <td>${item.light_count || 1} 盏</td>
          <td>${item.samples_count || 0} 次</td>
        `;
        tbody.appendChild(tr);
      }
    }

    async function updateDashboard() {
      try {
        const resp = await fetch('/api/status');
        const data = await resp.json();

        document.getElementById('sim-time-badge').innerText = `当前系统时间: ${data.time.current_time} (UTC${data.time.timezone_offset>=0?'+':''}${data.time.timezone_offset})`;
        document.getElementById('tz-select').value = data.time.timezone_offset.toFixed(1);

        document.getElementById('solar-term').innerText = `${data.solar.term} (进度: ${(data.solar.term_progress * 100).toFixed(0)}%)`;
        document.getElementById('solar-elevation').innerText = `太阳高度角: ${data.solar.elevation.toFixed(1)}° | 季节因子: ${data.solar.season_factor.toFixed(2)}`;

        document.getElementById('proc-cpu').innerText = `CPU: ${data.process.cpu_percent}%`;
        document.getElementById('proc-mem').innerText = `物理内存: ${data.process.mem_rss_mb} MB | 虚拟内存: ${data.process.mem_vms_mb} MB | 运行: ${data.process.uptime}`;

        // 分组下拉框更新
        groupsData = data.groups;
        const gSelect = document.getElementById('group-select');
        const existingKeys = Object.keys(groupsData);
        if (existingKeys.length > 0 && !selectedGroupId) {
          selectedGroupId = existingKeys[0];
        }
        gSelect.innerHTML = '';
        for (const [gid, ginfo] of Object.entries(groupsData)) {
          const opt = document.createElement('option');
          opt.value = gid;
          opt.innerText = `${ginfo.name} (${ginfo.lights.length} 盏灯)`;
          if (gid === selectedGroupId) opt.selected = true;
          gSelect.appendChild(opt);
        }

        renderCurrentGroup();

        const logBox = document.getElementById('log-box');
        logBox.innerHTML = data.logs.join('<br>');
        logBox.scrollTop = logBox.scrollHeight;
      } catch (e) {
        console.error("更新数据失败:", e);
      }
    }

    window.onload = async () => {
      initPerfChart();
      await updateDashboard();
      await updatePerfData();
      await updateLightData();
      setInterval(updateDashboard, 3000);
      setInterval(updatePerfData, 10000);
      setInterval(updateLightData, 15000);
    };
  </script>
</body>
</html>
"""

class WebPanel:
    def __init__(self, service_instance, host="0.0.0.0", port=8787):
        self.service = service_instance
        self.host = host
        self.port = port
        self.start_time = time.time()
        self.app = web.Application()
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/api/status", self.handle_api_status)
        self.app.router.add_get("/api/history/perf", self.handle_api_history_perf)
        self.app.router.add_get("/api/history/lights", self.handle_api_history_lights)
        self.app.router.add_post("/api/control/timezone", self.handle_control_timezone)
        self.app.router.add_post("/api/control/time_adjust", self.handle_control_time_adjust)
        self.app.router.add_post("/api/control/time_reset", self.handle_control_time_reset)

    def get_process_metrics(self):
        cpu_percent = 0.0
        rss_mb = 0.0
        vms_mb = 0.0
        uptime_str = "--"

        try:
            elapsed = int(time.time() - self.start_time)
            h = elapsed // 3600
            m = (elapsed % 3600) // 60
            s = elapsed % 60
            uptime_str = f"{h}h {m}m {s}s"

            with open("/proc/self/statm", "r") as f:
                parts = f.read().split()
                if len(parts) >= 2:
                    page_size = 4096
                    vms_mb = round((int(parts[0]) * page_size) / (1024 * 1024), 1)
                    rss_mb = round((int(parts[1]) * page_size) / (1024 * 1024), 1)

            with open("/proc/self/stat", "r") as f:
                stat_line = f.read().split()
                utime = float(stat_line[13])
                stime = float(stat_line[14])
                total_time = (utime + stime) / 100.0
                cpu_percent = round((total_time / max(1, elapsed)) * 100, 1)
        except Exception:
            pass

        return {
            "cpu_percent": cpu_percent,
            "mem_rss_mb": rss_mb,
            "mem_vms_mb": vms_mb,
            "uptime": uptime_str
        }

    async def handle_index(self, request):
        return web.Response(text=HTML_TEMPLATE, content_type="text/html")

    async def handle_api_status(self, request):
        now = self.service.get_current_time()
        h_float = now.hour + now.minute / 60.0 + now.second / 3600.0

        elev = self.service.solar.get_solar_elevation(now)
        term, term_prog = self.service.solar.get_solar_term(now)
        season = self.service.solar.get_season_factor(now)

        proc_stats = self.get_process_metrics()

        groups_dict = {}
        for gid, grp in self.service.groups.items():
            pred = grp.model.predict(h_float, elev, season)
            groups_dict[gid] = {
                "id": grp.id,
                "name": grp.name,
                "enabled": grp.enabled,
                "lights": grp.light_entities,
                "prediction": pred,
                "profile": grp.model.anchors
            }

        data = {
            "time": {
                "current_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "timezone_offset": self.service.tz_offset,
                "time_offset_seconds": self.service.time_offset_seconds
            },
            "solar": {
                "term": term,
                "term_progress": round(term_prog, 2),
                "elevation": round(elev, 2),
                "season_factor": round(season, 2)
            },
            "process": proc_stats,
            "groups": groups_dict,
            "logs": list(LOG_BUFFER)
        }
        return web.json_response(data)

    async def handle_control_timezone(self, request):
        req_data = await request.json()
        offset = float(req_data.get("timezone_offset", 8.0))
        self.service.update_timezone(offset)
        return web.json_response({"ok": True, "offset": offset})

    async def handle_control_time_adjust(self, request):
        req_data = await request.json()
        delta = int(req_data.get("delta_minutes", 0))
        self.service.update_time_offset(delta)
        return web.json_response({"ok": True, "delta_minutes": delta})

    async def handle_control_time_reset(self, request):
        self.service.reset_time_offset()
        return web.json_response({"ok": True})

    async def handle_api_history_perf(self, request):
        hours = float(request.query.get("hours", 24))
        data = self.service.db.query_metrics(hours=hours)
        return web.json_response(data)

    async def handle_api_history_lights(self, request):
        hours = float(request.query.get("hours", 24))
        data = self.service.db.query_light_history(hours=hours)
        return web.json_response(data)

    async def start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        add_log(f"Web 控制面板已就绪: http://{self.host}:{self.port}")
