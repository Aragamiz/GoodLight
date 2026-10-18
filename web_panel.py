"""
GoodLight 轻量 Web 控制面板服务 (基于 aiohttp.web)
提供：
- 实时天体状态 (太阳高度角、二十四节气进度、季节因子)
- 进程与系统状态 (CPU 占用率、内存 RSS/虚拟内存、运行时间、线程数)
- 24小时偏好曲线可视化 (当前亮度、色温、开灯数量)
- 实时运行日志查看器 (带自动滚动刷新)
- 选项信息查看 (配置与灯具组列表)
"""

import os
import time
import json
import collections
from datetime import datetime
from aiohttp import web

# 内存日志环形缓冲区 (保留最近 200 条日志)
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
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --subtext: #94a3b8;
      --primary: #38bdf8;
      --accent: #fbbf24;
      --success: #4ade80;
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
      margin-bottom: 24px;
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
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 18px;
    }
    .card-title {
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--subtext);
      margin-bottom: 12px;
      display: flex;
      justify-content: space-between;
    }
    .stat-val { font-size: 26px; font-weight: 700; color: var(--text); }
    .stat-sub { font-size: 13px; color: var(--subtext); margin-top: 4px; }
    .log-box {
      background: #090d16;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
      height: 260px;
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
      margin-top: 8px;
    }
    .curve-table th, .curve-table td {
      padding: 6px 10px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }
    .curve-table th { color: var(--subtext); font-weight: 500; }
    .highlight-row { background: rgba(56, 189, 248, 0.12); color: var(--primary); font-weight: 600; }
  </style>
</head>
<body>
  <div class="header">
    <div class="title">🌟 GoodLight 控制面板</div>
    <div class="badge" id="status-badge">● 正在运行</div>
  </div>

  <div class="grid">
    <div class="card">
      <div class="card-title">天体与节气感知 <span>☀️</span></div>
      <div class="stat-val" id="solar-term">--</div>
      <div class="stat-sub" id="solar-elevation">太阳高度角: --°</div>
    </div>
    <div class="card">
      <div class="card-title">当前目标预测 <span>💡</span></div>
      <div class="stat-val" id="predict-target">--% / --K</div>
      <div class="stat-sub" id="predict-count">建议开灯数: -- 盏</div>
    </div>
    <div class="card">
      <div class="card-title">进程性能占用 <span>⚡</span></div>
      <div class="stat-val" id="proc-cpu">CPU: --%</div>
      <div class="stat-sub" id="proc-mem">内存: -- MB | 运行时间: --</div>
    </div>
    <div class="card">
      <div class="card-title">受控协同灯具 <span>🎛️</span></div>
      <div class="stat-val" style="font-size: 16px;" id="light-group-name">--</div>
      <div class="stat-sub" id="light-entities">--</div>
    </div>
  </div>

  <div class="card" style="margin-bottom: 24px;">
    <div class="card-title">实时运行与学习日志 <span>📋</span></div>
    <div class="log-box" id="log-box"></div>
  </div>

  <div class="card">
    <div class="card-title">24小时自适应偏好曲线 (已驯化模型) <span>📈</span></div>
    <div style="max-height: 220px; overflow-y: auto;">
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
    async function updateDashboard() {
      try {
        const resp = await fetch('/api/status');
        const data = await resp.json();

        document.getElementById('solar-term').innerText = `${data.solar.term} (进度: ${(data.solar.term_progress * 100).toFixed(0)}%)`;
        document.getElementById('solar-elevation').innerText = `太阳真实高度角: ${data.solar.elevation.toFixed(1)}° | 季节因子: ${data.solar.season_factor.toFixed(2)}`;

        document.getElementById('predict-target').innerText = `${data.prediction.brightness}% / ${data.prediction.color_temp}K`;
        document.getElementById('predict-count').innerText = `建议开启灯具: ${data.prediction.light_count} 盏`;

        document.getElementById('proc-cpu').innerText = `CPU: ${data.process.cpu_percent}%`;
        document.getElementById('proc-mem').innerText = `物理内存: ${data.process.mem_rss_mb} MB | 虚拟内存: ${data.process.mem_vms_mb} MB | 运行: ${data.process.uptime}`;

        document.getElementById('light-group-name').innerText = data.config.group_name;
        document.getElementById('light-entities').innerText = data.config.lights.join(', ');

        const logBox = document.getElementById('log-box');
        logBox.innerHTML = data.logs.join('<br>');
        logBox.scrollTop = logBox.scrollHeight;

        const currentHour = new Date().getHours();
        const tbody = document.getElementById('curve-tbody');
        tbody.innerHTML = '';
        for (let h = 0; h < 24; h++) {
          const item = data.profile[h.toString()] || {};
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
      } catch (e) {
        console.error("更新数据失败:", e);
      }
    }
    updateDashboard();
    setInterval(updateDashboard, 3000);
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

    def get_process_metrics(self):
        """读取 /proc 纯标准 Linux 统计 (零第三方依赖)"""
        cpu_percent = 0.0
        rss_mb = 0.0
        vms_mb = 0.0
        uptime_str = "--"

        try:
            # 运行时间
            elapsed = int(time.time() - self.start_time)
            h = elapsed // 3600
            m = (elapsed % 3600) // 60
            s = elapsed % 60
            uptime_str = f"{h}h {m}m {s}s"

            # 内存 (/proc/self/statm)
            with open("/proc/self/statm", "r") as f:
                parts = f.read().split()
                if len(parts) >= 2:
                    page_size = 4096
                    vms_mb = round((int(parts[0]) * page_size) / (1024 * 1024), 1)
                    rss_mb = round((int(parts[1]) * page_size) / (1024 * 1024), 1)

            # CPU / 线程数 (/proc/self/stat)
            with open("/proc/self/stat", "r") as f:
                stat_line = f.read().split()
                # 简易 CPU 时间计算
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
        now = datetime.now(self.service.tz)
        h_float = now.hour + now.minute / 60.0 + now.second / 3600.0

        elev = self.service.solar.get_solar_elevation(now)
        term, term_prog = self.service.solar.get_solar_term(now)
        season = self.service.solar.get_season_factor(now)

        pred = self.service.model.predict(h_float, elev, season)
        proc_stats = self.get_process_metrics()

        data = {
            "solar": {
                "term": term,
                "term_progress": round(term_prog, 2),
                "elevation": round(elev, 2),
                "season_factor": round(season, 2)
            },
            "prediction": pred,
            "process": proc_stats,
            "config": {
                "group_name": self.service.cfg.get("lighting_group", {}).get("name", "GoodLight Group"),
                "lights": self.service.light_entities,
                "learning_rate": self.service.cfg.get("learning", {}).get("learning_rate", 0.25)
            },
            "profile": self.service.model.anchors,
            "logs": list(LOG_BUFFER)
        }
        return web.json_response(data)

    async def start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        add_log(f"Web 控制面板已就绪: http://{self.host}:{self.port}")
