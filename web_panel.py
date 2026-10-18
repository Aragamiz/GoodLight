"""
GoodLight 现代可视化 Web Dashboard 控制面板 (带时区调整、时间微调与多分组控制)
"""

import os
import time
import json
import collections
from datetime import datetime, timezone, timedelta
from aiohttp import web

LOG_BUFFER = collections.deque(maxlen=200)
_CURRENT_TZ = timezone(timedelta(hours=8))

def set_log_tz(tz):
    global _CURRENT_TZ
    _CURRENT_TZ = tz

def add_log(msg: str):
    now = datetime.now(_CURRENT_TZ) if _CURRENT_TZ else datetime.now(timezone(timedelta(hours=8)))
    timestamp = now.strftime("%H:%M:%S")
    LOG_BUFFER.append(f"[{timestamp}] {msg}")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GoodLight Dashboard</title>
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiIgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiBmaWxsPSJub25lIj4KICA8ZGVmcz4KICAgIDxsaW5lYXJHcmFkaWVudCBpZD0iZ2xHcmFkIiB4MT0iMCUiIHkxPSIwJSIgeDI9IjEwMCUiIHkyPSIxMDAlIj4KICAgICAgPHN0b3Agb2Zmc2V0PSIwJSIgc3RvcC1jb2xvcj0iIzM4YmRmOCIvPgogICAgICA8c3RvcCBvZmZzZXQ9IjUwJSIgc3RvcC1jb2xvcj0iIzgxOGNmOCIvPgogICAgICA8c3RvcCBvZmZzZXQ9IjEwMCUiIHN0b3AtY29sb3I9IiNmYmJmMjQiLz4KICAgIDwvbGluZWFyR3JhZGllbnQ+CiAgICA8bGluZWFyR3JhZGllbnQgaWQ9ImdsQmciIHgxPSIwJSIgeTE9IjAlIiB4Mj0iMTAwJSIgeTI9IjEwMCUiPgogICAgICA8c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjMGUxNzI2Ii8+CiAgICAgIDxzdG9wIG9mZnNldD0iMTAwJSIgc3RvcC1jb2xvcj0iIzFlMjkzYiIvPgogICAgPC9saW5lYXJHcmFkaWVudD4KICAgIDxyYWRpYWxHcmFkaWVudCBpZD0iZ2xHbG93IiBjeD0iNTAlIiBjeT0iNDUlIiByPSI1MCUiPgogICAgICA8c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjZmJiZjI0IiBzdG9wLW9wYWNpdHk9IjAuNDUiLz4KICAgICAgPHN0b3Agb2Zmc2V0PSI2MCUiIHN0b3AtY29sb3I9IiMzOGJkZjgiIHN0b3Atb3BhY2l0eT0iMC4xNSIvPgogICAgICA8c3RvcCBvZmZzZXQ9IjEwMCUiIHN0b3AtY29sb3I9IiMzOGJkZjgiIHN0b3Atb3BhY2l0eT0iMCIvPgogICAgPC9yYWRpYWxHcmFkaWVudD4KICA8L2RlZnM+CiAgPHJlY3QgeD0iMS41IiB5PSIxLjUiIHdpZHRoPSIyOSIgaGVpZ2h0PSIyOSIgcng9IjcuNSIgZmlsbD0idXJsKCNnbEJnKSIgc3Ryb2tlPSJ1cmwoI2dsR3JhZCkiIHN0cm9rZS13aWR0aD0iMS40Ii8+CiAgPGNpcmNsZSBjeD0iMTYiIGN5PSIxNCIgcj0iMTAiIGZpbGw9InVybCgjZ2xHbG93KSIvPgogIDxwYXRoIGQ9Ik0xNiA2LjUgQzEyIDYuNSA5LjUgOS41IDkuNSAxMy41IEM5LjUgMTYuMiAxMS4yIDE4LjIgMTIuNSAxOS44IEwxMi41IDIxLjggQzEyLjUgMjIuNCAxMi45IDIyLjggMTMuNSAyMi44IEwxOC41IDIyLjggQzE5LjEgMjIuOCAxOS41IDIyLjQgMTkuNSAyMS44IEwxOS41IDE5LjggQzIwLjggMTguMiAyMi41IDE2LjIgMjIuNSAxMy41IEMyMi41IDkuNSAyMCA2LjUgMTYgNi41IFoiIGZpbGw9Im5vbmUiIHN0cm9rZT0idXJsKCNnbEdyYWQpIiBzdHJva2Utd2lkdGg9IjEuOCIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+CiAgPHBhdGggZD0iTTEzLjggMjQuOCBMMTguMiAyNC44IiBzdHJva2U9IiNmYmJmMjQiIHN0cm9rZS13aWR0aD0iMS42IiBzdHJva2UtbGluZWNhcD0icm91bmQiLz4KICA8cGF0aCBkPSJNMTYgOS41IEwxNi44IDEyLjIgTDE5LjUgMTMgQzE5LjggMTMuMSAxOS44IDEzLjUgMTkuNSAxMy42IEwxNi44IDE0LjQgTDE2IDE3LjEgQzE1LjkgMTcuNCAxNS41IDE3LjQgMTUuNCAxNy4xIEwxNC42IDE0LjQgTDExLjkgMTMuNiBDMTEuNiAxMy41IDExLjYgMTMuMSAxMS45IDEzIEwxNC42IDEyLjIgTDE1LjQgOS41IEMxNS41IDkuMiAxNS45IDkuMiAxNiA5LjUgWiIgZmlsbD0iI2ZmZmZmZiIvPgogIDxjaXJjbGUgY3g9IjE2IiBjeT0iMTMuMyIgcj0iMS4yIiBmaWxsPSIjZmJiZjI0Ii8+Cjwvc3ZnPg==">
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
    .mode-select {
      background: #090e1a;
      border: 1px solid var(--border);
      color: #94a3b8;
      font-size: 11px;
      border-radius: 5px;
      padding: 2px 4px;
      cursor: pointer;
      outline: none;
      transition: all 0.2s;
    }
    .mode-select:hover, .mode-select:focus {
      border-color: var(--primary);
      color: #f8fafc;
    }

    /* 预装与配置向导 (Onboarding Wizard) 样式 */
    .modal-overlay {
      position: fixed;
      inset: 0;
      background: rgba(5, 10, 24, 0.88);
      backdrop-filter: blur(10px);
      z-index: 9999;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 16px;
    }
    .modal-content {
      background: #111b2f;
      border: 1px solid var(--border);
      border-radius: 16px;
      width: 100%;
      max-width: 780px;
      max-height: 90vh;
      overflow-y: auto;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.75);
      padding: 28px;
      position: relative;
    }
    .wizard-steps {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
      position: relative;
    }
    .step-item {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      color: var(--subtext);
      font-weight: 500;
    }
    .step-item.active {
      color: var(--primary);
      font-weight: 700;
    }
    .step-item.done {
      color: var(--success);
    }
    .step-num {
      width: 22px;
      height: 22px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #1e293b;
      font-size: 12px;
    }
    .step-item.active .step-num {
      background: var(--primary);
      color: #0b1329;
      font-weight: bold;
    }
    .step-item.done .step-num {
      background: var(--success);
      color: #0b1329;
    }
    .wiz-input {
      width: 100%;
      background: #090e1a;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 10px 14px;
      border-radius: 8px;
      font-size: 14px;
      outline: none;
      margin-top: 6px;
      margin-bottom: 14px;
      box-sizing: border-box;
      transition: border 0.2s;
    }
    .wiz-input:focus {
      border-color: var(--primary);
    }
    .wiz-btn-primary {
      background: var(--primary);
      color: #0b1329;
      border: none;
      padding: 9px 18px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
      transition: 0.2s;
    }
    .wiz-btn-primary:hover {
      opacity: 0.9;
    }
    .wiz-btn-secondary {
      background: #1e293b;
      color: var(--text);
      border: 1px solid var(--border);
      padding: 9px 18px;
      border-radius: 8px;
      font-size: 14px;
      cursor: pointer;
      transition: 0.2s;
    }
    .wiz-btn-secondary:hover {
      background: #334155;
    }
    .light-item-card {
      background: #090e1a;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px 16px;
      margin-bottom: 10px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
    }
    .tag-badge {
      display: inline-block;
      font-size: 11px;
      padding: 2px 7px;
      border-radius: 9999px;
      font-weight: 600;
    }
    .tag-blue { background: rgba(56, 189, 248, 0.15); color: var(--primary); }
    .tag-green { background: rgba(74, 222, 128, 0.15); color: var(--success); }
    .tag-amber { background: rgba(251, 191, 36, 0.15); color: var(--accent); }
    .city-pill {
      background: #1e293b;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 12px;
      cursor: pointer;
      display: inline-block;
      margin-right: 6px;
      margin-bottom: 6px;
    }
    .city-pill:hover {
      background: var(--primary);
      color: #0b1329;
      font-weight: 600;
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="title" style="display: flex; align-items: center; gap: 10px;">
      <svg width="28" height="28" viewBox="0 0 32 32" fill="none" style="filter: drop-shadow(0 2px 8px rgba(56, 189, 248, 0.4)); flex-shrink: 0;">
        <defs>
          <linearGradient id="hdrGlGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#38bdf8"/>
            <stop offset="50%" stop-color="#818cf8"/>
            <stop offset="100%" stop-color="#fbbf24"/>
          </linearGradient>
          <linearGradient id="hdrGlBg" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#0e1726"/>
            <stop offset="100%" stop-color="#1e293b"/>
          </linearGradient>
          <radialGradient id="hdrGlGlow" cx="50%" cy="45%" r="50%">
            <stop offset="0%" stop-color="#fbbf24" stop-opacity="0.45"/>
            <stop offset="60%" stop-color="#38bdf8" stop-opacity="0.15"/>
            <stop offset="100%" stop-color="#38bdf8" stop-opacity="0"/>
          </radialGradient>
        </defs>
        <rect x="1.5" y="1.5" width="29" height="29" rx="7.5" fill="url(#hdrGlBg)" stroke="url(#hdrGlGrad)" stroke-width="1.4"/>
        <circle cx="16" cy="14" r="10" fill="url(#hdrGlGlow)"/>
        <path d="M16 6.5 C12 6.5 9.5 9.5 9.5 13.5 C9.5 16.2 11.2 18.2 12.5 19.8 L12.5 21.8 C12.5 22.4 12.9 22.8 13.5 22.8 L18.5 22.8 C19.1 22.8 19.5 22.4 19.5 21.8 L19.5 19.8 C20.8 18.2 22.5 16.2 22.5 13.5 C22.5 9.5 20 6.5 16 6.5 Z" fill="none" stroke="url(#hdrGlGrad)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M13.8 24.8 L18.2 24.8" stroke="#fbbf24" stroke-width="1.6" stroke-linecap="round"/>
        <path d="M16 9.5 L16.8 12.2 L19.5 13 C19.8 13.1 19.8 13.5 19.5 13.6 L16.8 14.4 L16 17.1 C15.9 17.4 15.5 17.4 15.4 17.1 L14.6 14.4 L11.9 13.6 C11.6 13.5 11.6 13.1 11.9 13 L14.6 12.2 L15.4 9.5 C15.5 9.2 15.9 9.2 16 9.5 Z" fill="#ffffff"/>
        <circle cx="16" cy="13.3" r="1.2" fill="#fbbf24"/>
      </svg>
      <span id="page-title">GoodLight 控制面板</span>
    </div>
    <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
      <button class="btn-action" id="btn-lang-toggle" onclick="toggleLanguage()" style="font-weight: 600; border-color: var(--primary); color: var(--primary);">🌐 English</button>
      <button class="btn-action" id="btn-open-wizard" style="border-color: var(--primary); color: var(--primary); font-weight: 600;" onclick="openWizard()">🚀 启动与配置向导</button>
      <div id="sim-time-badge" style="font-size: 13px; color: var(--accent);">时间: --:--:--</div>
      <div class="badge" id="status-badge">● 正在运行</div>
    </div>
  </div>

  <!-- 预装启动与配置向导模态弹窗 -->
  <div id="wizard-modal" class="modal-overlay" style="display: none;">
    <div class="modal-content">
      <!-- 步骤指示器与语言切换 -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div class="wizard-steps" style="margin-bottom: 0; flex: 1;">
          <div class="step-item active" id="step-nav-1"><span class="step-num">1</span> <span id="nav-text-1">欢迎</span></div>
          <div class="step-item" id="step-nav-2"><span class="step-num">2</span> <span id="nav-text-2">填写令牌</span></div>
          <div class="step-item" id="step-nav-3"><span class="step-num">3</span> <span id="nav-text-3">加入灯组</span></div>
          <div class="step-item" id="step-nav-4"><span class="step-num">4</span> <span id="nav-text-4">补足信息</span></div>
          <div class="step-item" id="step-nav-5"><span class="step-num">5</span> <span id="nav-text-5">完成启动</span></div>
        </div>
        <button class="btn-action" id="btn-wiz-lang" onclick="toggleLanguage()" style="margin-left: 12px; font-size: 12px; font-weight: 600; padding: 4px 10px; border-color: var(--primary); color: var(--primary);">🌐 English</button>
      </div>

      <!-- Step 1: 欢迎界面 GoodLight -->
      <div id="wizard-step-1">
        <div style="text-align: center; padding: 20px 0 24px;">
          <div style="display: flex; justify-content: center; margin-bottom: 14px;">
            <svg width="60" height="60" viewBox="0 0 32 32" fill="none" style="filter: drop-shadow(0 4px 16px rgba(56, 189, 248, 0.45));">
              <rect x="1.5" y="1.5" width="29" height="29" rx="7.5" fill="url(#hdrGlBg)" stroke="url(#hdrGlGrad)" stroke-width="1.4"/>
              <circle cx="16" cy="14" r="10" fill="url(#hdrGlGlow)"/>
              <path d="M16 6.5 C12 6.5 9.5 9.5 9.5 13.5 C9.5 16.2 11.2 18.2 12.5 19.8 L12.5 21.8 C12.5 22.4 12.9 22.8 13.5 22.8 L18.5 22.8 C19.1 22.8 19.5 22.4 19.5 21.8 L19.5 19.8 C20.8 18.2 22.5 16.2 22.5 13.5 C22.5 9.5 20 6.5 16 6.5 Z" fill="none" stroke="url(#hdrGlGrad)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M13.8 24.8 L18.2 24.8" stroke="#fbbf24" stroke-width="1.6" stroke-linecap="round"/>
              <path d="M16 9.5 L16.8 12.2 L19.5 13 C19.8 13.1 19.8 13.5 19.5 13.6 L16.8 14.4 L16 17.1 C15.9 17.4 15.5 17.4 15.4 17.1 L14.6 14.4 L11.9 13.6 C11.6 13.5 11.6 13.1 11.9 13 L14.6 12.2 L15.4 9.5 C15.5 9.2 15.9 9.2 16 9.5 Z" fill="#ffffff"/>
              <circle cx="16" cy="13.3" r="1.2" fill="#fbbf24"/>
            </svg>
          </div>
          <h1 style="font-size: 38px; font-weight: 800; background: linear-gradient(135deg, #38bdf8 0%, #fbbf24 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px;">GoodLight</h1>
          <div style="font-size: 15px; color: var(--subtext); margin-bottom: 24px;">智能天体节气自适应全屋照明系统</div>
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; text-align: left; margin-bottom: 28px;">
            <div style="background: #090e1a; padding: 16px; border-radius: 10px; border: 1px solid var(--border);">
              <div style="font-size: 16px; font-weight: 600; color: var(--primary); margin-bottom: 6px;">☀️ 自然日光感知</div>
              <div style="font-size: 12px; color: var(--subtext); line-height: 1.5;">精准解算太阳真实高度角与真太阳时，实现生理昼夜节律自适应光照。</div>
            </div>
            <div style="background: #090e1a; padding: 16px; border-radius: 10px; border: 1px solid var(--border);">
              <div style="font-size: 16px; font-weight: 600; color: var(--accent); margin-bottom: 6px;">🌾 二十四节气温感</div>
              <div style="font-size: 12px; color: var(--subtext); line-height: 1.5;">夏至清凉、冬至温煦，四季变换动态补偿室内温差氛围感。</div>
            </div>
            <div style="background: #090e1a; padding: 16px; border-radius: 10px; border: 1px solid var(--border);">
              <div style="font-size: 16px; font-weight: 600; color: var(--success); margin-bottom: 6px;">⚡ 边缘极简低开销</div>
              <div style="font-size: 12px; color: var(--subtext); line-height: 1.5;">为路由器/Docker定制，纯Python高效引擎，内存仅~40MB。</div>
            </div>
          </div>
          <div style="display: flex; justify-content: center; gap: 12px;">
            <button class="wiz-btn-primary" style="padding: 11px 28px; font-size: 15px;" onclick="goToStep(2)">开始配置向导 →</button>
            <button class="wiz-btn-secondary" onclick="closeWizard()">进入控制台</button>
          </div>
        </div>
      </div>

      <!-- Step 2: 填写令牌 -->
      <div id="wizard-step-2" style="display: none;">
        <h2 style="font-size: 18px; color: var(--primary); margin-bottom: 6px;">🔑 填写 Home Assistant 访问令牌</h2>
        <div style="font-size: 13px; color: var(--subtext); margin-bottom: 20px;">
          GoodLight 通过 WebSocket 与 REST API 和 Home Assistant 实时同步，请填入连接信息。
        </div>

        <label style="font-size: 13px; font-weight: 600; color: var(--text);">Home Assistant 地址 (URL):</label>
        <input type="text" id="wiz-ha-url" class="wiz-input" value="http://192.168.6.1:8123" placeholder="例如: http://192.168.6.1:8123">

        <label style="font-size: 13px; font-weight: 600; color: var(--text);">长期访问令牌 (Long-Lived Access Token):</label>
        <div style="position: relative;">
          <input type="password" id="wiz-ha-token" class="wiz-input" style="padding-right: 40px;" placeholder="粘贴你的 HA 长期访问令牌 (eyJhbGci...)">
          <span onclick="toggleTokenVisibility()" style="position: absolute; right: 12px; top: 14px; cursor: pointer; font-size: 16px;" title="显示/隐藏令牌">👁️</span>
        </div>
        <div style="font-size: 12px; color: var(--subtext); margin-top: -6px; margin-bottom: 16px;">
          💡 获取方式：在 Home Assistant 点击左下角头像 ➔ 滚动到底部【长期访问令牌】➔ 点击【创建令牌】并复制。
        </div>

        <div style="margin-bottom: 16px;">
          <button class="wiz-btn-secondary" id="btn-wiz-test" onclick="testHAConnection()">🔍 测试连接并自动扫描全屋灯具</button>
        </div>

        <div id="wiz-conn-status" style="margin-bottom: 20px; font-size: 13px; padding: 10px 14px; border-radius: 8px; display: none;"></div>

        <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 18px;">
          <button class="wiz-btn-secondary" onclick="goToStep(1)">← 上一步</button>
          <button class="wiz-btn-primary" id="btn-step2-next" onclick="goToStep(3)">下一步：加入灯组 →</button>
        </div>
      </div>

      <!-- Step 3: 加入灯组 (自主识别灯具) -->
      <div id="wizard-step-3" style="display: none;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 8px;">
          <h2 style="font-size: 18px; color: var(--primary);">💡 自主识别全屋灯具与分组</h2>
          <div style="display: flex; gap: 8px;">
            <button class="btn-action" onclick="autoRecommendGroups()">⚡ 智能自动分组</button>
            <button class="btn-action" onclick="rescanLights()">🔄 重新扫描</button>
          </div>
        </div>
        <div style="font-size: 13px; color: var(--subtext); margin-bottom: 16px;">
          系统已自主识别出全屋灯具，请选择各灯具归属的自适应控制分组（不需要托管的灯可设为“不纳入托管”）：
        </div>

        <div id="wiz-lights-list" style="max-height: 380px; overflow-y: auto; padding-right: 4px; margin-bottom: 14px;">
          <div style="color: var(--subtext); text-align: center; padding: 30px;">正在扫描或未连接，请先返回第二步测试连接...</div>
        </div>

        <!-- 历史回溯学习功能 -->
        <div style="background: #090e1a; border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; margin-bottom: 16px;">
          <label style="font-size: 13px; font-weight: 600; color: var(--text); display: flex; align-items: center; gap: 8px; cursor: pointer;">
            <input type="checkbox" id="wiz-sync-history-toggle" checked style="width: 16px; height: 16px;">
            <span id="txt-wiz-sync-title">🔄 自动从 Home Assistant 历史数据库回溯学习光照习惯 (过去 14 天)</span>
          </label>
          <div style="font-size: 12px; color: var(--subtext); margin-top: 6px; margin-left: 24px; line-height: 1.5;" id="txt-wiz-sync-desc">
            直接读取所选灯具在 Home Assistant 中的真实历史调光与色温样本，瞬间生成个性化自适应昼夜曲线，无需从零等待数周日常学习。
          </div>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 18px;">
          <button class="wiz-btn-secondary" onclick="goToStep(2)">← 上一步</button>
          <button class="wiz-btn-primary" onclick="goToStep(4)">下一步：补足信息 →</button>
        </div>
      </div>

      <!-- Step 4: 补足各种信息 (全球地址与气象配置) -->
      <div id="wizard-step-4" style="display: none;">
        <h2 style="font-size: 18px; color: var(--primary); margin-bottom: 6px;">🌍 全球地址搜索与环境气象配置</h2>
        <div style="font-size: 13px; color: var(--subtext); margin-bottom: 16px;">
          GoodLight 面向全球用户，输入任何城市或地址即可自动定位经纬度、推算太阳高度角与本地时区。
        </div>

        <label style="font-size: 13px; font-weight: 600; color: var(--text);">全球地址/城市搜索 (支持中文或英文)：</label>
        <div style="display: flex; gap: 8px; margin: 8px 0 10px;">
          <input type="text" id="wiz-geo-search" class="wiz-input" style="margin: 0; flex: 1;" placeholder="输入全球任意城市，如: London, Tokyo, New York, 巴黎, 武汉, 悉尼..." onkeydown="if(event.key==='Enter') searchLocation()">
          <button class="wiz-btn-primary" style="white-space: nowrap;" onclick="searchLocation()">🔍 全球搜索</button>
        </div>

        <!-- 搜索结果下拉候选框 -->
        <div id="geo-results-box" style="display: none; background: #090e1a; border: 1px solid var(--border); border-radius: 8px; max-height: 160px; overflow-y: auto; margin-bottom: 14px; padding: 6px;"></div>

        <div style="font-size: 12px; color: var(--subtext); margin-bottom: 6px;">热门全球大都市快捷填充：</div>
        <div style="margin-bottom: 16px;">
          <span class="city-pill" onclick="setCity(39.9042, 116.4074, 8.0, '北京, 中国')">🇨🇳 北京</span>
          <span class="city-pill" onclick="setCity(35.6895, 139.6917, 9.0, 'Tokyo, Japan')">🇯🇵 东京</span>
          <span class="city-pill" onclick="setCity(51.5074, -0.1278, 0.0, 'London, UK')">🇬🇧 伦敦</span>
          <span class="city-pill" onclick="setCity(48.8566, 2.3522, 1.0, 'Paris, France')">🇫🇷 巴黎</span>
          <span class="city-pill" onclick="setCity(52.5200, 13.4050, 1.0, 'Berlin, Germany')">🇩🇪 柏林</span>
          <span class="city-pill" onclick="setCity(40.7128, -74.0060, -5.0, 'New York, USA')">🇺🇸 纽约</span>
          <span class="city-pill" onclick="setCity(34.0522, -118.2437, -8.0, 'Los Angeles, USA')">🇺🇸 洛杉矶</span>
          <span class="city-pill" onclick="setCity(-33.8688, 151.2093, 10.0, 'Sydney, Australia')">🇦🇺 悉尼</span>
          <span class="city-pill" onclick="setCity(1.3521, 103.8198, 8.0, 'Singapore')">🇸🇬 新加坡</span>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
          <div>
            <label style="font-size: 13px; font-weight: 600; color: var(--text);">纬度 (Latitude):</label>
            <input type="number" id="wiz-lat" class="wiz-input" step="0.0001" value="39.9042" onchange="previewWeatherForCoords()">
          </div>
          <div>
            <label style="font-size: 13px; font-weight: 600; color: var(--text);">经度 (Longitude):</label>
            <input type="number" id="wiz-lng" class="wiz-input" step="0.0001" value="116.4074" onchange="previewWeatherForCoords()">
          </div>
        </div>

        <label style="font-size: 13px; font-weight: 600; color: var(--text);">本地时区 (Timezone):</label>
        <select id="wiz-tz" class="wiz-input" style="height: 42px;">
          <option value="12.0">UTC+12 (奥克兰 / 斐济)</option>
          <option value="10.0">UTC+10 (悉尼 / 墨尔本)</option>
          <option value="9.0">UTC+9 (东京 / 首尔)</option>
          <option value="8.0" selected>UTC+8 (北京 / 上海 / 香港 / 台北 / 新加坡)</option>
          <option value="7.0">UTC+7 (曼谷 / 雅加达)</option>
          <option value="5.5">UTC+5.5 (新德里 / 孟买)</option>
          <option value="4.0">UTC+4 (迪拜)</option>
          <option value="3.0">UTC+3 (莫斯科 / 伊斯坦布尔)</option>
          <option value="2.0">UTC+2 (开罗 / 雅典)</option>
          <option value="1.0">UTC+1 (巴黎 / 柏林 / 罗马 / 马德里)</option>
          <option value="0.0">UTC+0 (伦敦 / 都柏林 / 格林尼治 GMT)</option>
          <option value="-3.0">UTC-3 (圣保罗 / 布宜诺斯艾利斯)</option>
          <option value="-5.0">UTC-5 (纽约 / 多伦多 / 华盛顿)</option>
          <option value="-6.0">UTC-6 (芝加哥 / 墨西哥城)</option>
          <option value="-7.0">UTC-7 (丹佛 / 凤凰城)</option>
          <option value="-8.0">UTC-8 (旧金山 / 洛杉矶 / 西雅图 / 温哥华)</option>
          <option value="-10.0">UTC-10 (夏威夷檀香山)</option>
        </select>

        <!-- 天气与环境温度联动开关 -->
        <div style="background: #090e1a; border: 1px solid var(--border); border-radius: 10px; padding: 14px; margin-top: 14px;">
          <label style="font-size: 13px; font-weight: 600; color: var(--text); display: flex; align-items: center; gap: 8px; cursor: pointer;">
            <input type="checkbox" id="wiz-weather-toggle" checked style="width: 16px; height: 16px;">
            <span>⛅ 启用全球实时气象与温度自适应联动 (基于 Open-Meteo 免 Key 公开气象服务)</span>
          </label>
          <div style="font-size: 12px; color: var(--subtext); margin-top: 6px; margin-left: 24px; line-height: 1.5;">
            • <strong>环境气温色温补偿</strong>：寒冷时自动增添温暖色调 (-250K)，炎热时增加冷静清爽感 (+200K)<br>
            • <strong>阴雨云量采光补偿</strong>：白天厚重云层 (云量>50%) 自动调高室内亮度，补偿天然采光不足
          </div>
          <div id="wiz-weather-preview" style="font-size: 12px; color: var(--primary); margin-top: 8px; margin-left: 24px;"></div>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 18px; margin-top: 18px;">
          <button class="wiz-btn-secondary" onclick="goToStep(3)">← 上一步</button>
          <button class="wiz-btn-primary" onclick="goToStep(5)">下一步：完成确认 →</button>
        </div>
      </div>

      <!-- Step 5: 完成流程 -->
      <div id="wizard-step-5" style="display: none;">
        <h2 style="font-size: 18px; color: var(--success); margin-bottom: 6px;">🎉 配置完成，准备启动！</h2>
        <div style="font-size: 13px; color: var(--subtext); margin-bottom: 20px;">
          请核对以下配置清单，确认无误后点击下方按钮立即启动 GoodLight 自适应光照系统：
        </div>

        <div style="background: #090e1a; border: 1px solid var(--border); border-radius: 12px; padding: 18px; margin-bottom: 24px; font-size: 13px; line-height: 1.8;">
          <div><strong style="color: var(--primary);">Home Assistant 地址:</strong> <span id="summary-url">--</span></div>
          <div><strong style="color: var(--primary);">长期访问令牌:</strong> <span id="summary-token">已配置</span></div>
          <div><strong style="color: var(--primary);">自适应托管灯组:</strong> <span id="summary-groups">--</span></div>
          <div><strong style="color: var(--primary);">地理坐标与时区:</strong> <span id="summary-loc">--</span></div>
          <div><strong style="color: var(--primary);">全球气象与温度感知:</strong> <span id="summary-weather">--</span></div>
          <div><strong style="color: var(--primary);" id="summary-lbl-history">HA 历史数据回溯:</strong> <span id="summary-history">已启用 (从过去 14 天记录回溯)</span></div>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 18px;">
          <button class="wiz-btn-secondary" onclick="goToStep(4)">← 返回修改</button>
          <button class="wiz-btn-primary" id="btn-wiz-finish" style="background: var(--success); font-size: 15px; padding: 11px 24px;" onclick="finishWizard()">🎉 保存并启动 GoodLight 自适应巡航</button>
        </div>
      </div>
    </div>
  </div>

  <!-- 调试与开发者模式 (Debug Panel, 默认折叠收起) -->
  <details class="card" style="margin-bottom: 16px; padding: 12px 18px;">
    <summary style="font-size: 13px; color: var(--subtext); cursor: pointer; user-select: none; font-weight: 600; display: flex; align-items: center; justify-content: space-between; list-style: none;">
      <span style="display: flex; align-items: center; gap: 8px;">
        <span>🛠️ 开发者与调试工具 (Debug Tools)</span>
        <span style="font-size: 11px; background: rgba(56, 189, 248, 0.15); color: var(--primary); padding: 2px 8px; border-radius: 4px;">时区自由选择 / 仿真时间测试</span>
      </span>
      <span id="debug-toggle-icon" style="font-size: 12px; color: var(--primary);">展开 ▼</span>
    </summary>
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-top: 14px; padding-top: 14px; border-top: 1px dashed var(--border);">
      <div style="display: flex; align-items: center; gap: 10px;">
        <span style="font-size: 13px; color: var(--subtext);">🌐 时区自由选择:</span>
        <select id="tz-select" onchange="onTimezoneChange(this.value)">
          <option value="8.0">UTC+8 (北京 / 上海 / 香港 / 台北)</option>
          <option value="9.0">UTC+9 (东京 / 首尔)</option>
          <option value="0.0">UTC+0 (伦敦 / 格林尼治 GMT)</option>
          <option value="1.0">UTC+1 (巴黎 / 柏林)</option>
          <option value="-5.0">UTC-5 (纽约 / 美东)</option>
          <option value="-8.0">UTC-8 (旧金山 / 洛杉矶 / 太平洋)</option>
        </select>
      </div>

      <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
        <span style="font-size: 13px; color: var(--subtext);">⏳ 时间微调仿真:</span>
        <button class="btn-action" onclick="adjustTime(-60)">-1小时</button>
        <button class="btn-action" onclick="adjustTime(-15)">-15分</button>
        <button class="btn-action" onclick="adjustTime(15)">+15分</button>
        <button class="btn-action" onclick="adjustTime(60)">+1小时</button>
        <button class="btn-action" style="border-color: var(--accent); color: var(--accent);" onclick="resetTime()">重置为实时时间</button>
      </div>
    </div>
  </details>

  <div class="grid">
    <div class="card">
      <div class="card-title"><span id="card-title-solar">天体与节气感知</span> <span>☀️</span></div>
      <div class="stat-val" id="solar-term">--</div>
      <div class="stat-sub" id="solar-elevation">太阳高度角: --°</div>
      <div class="stat-sub" id="weather-line" style="color: var(--primary); margin-top: 4px;">⛅ 实时气象: 获取中...</div>
    </div>
    <div class="card">
      <div class="card-title"><span id="card-title-group">分组选择与预测</span> <span>💡</span></div>
      <div style="margin-bottom: 8px;">
        <select id="group-select" onchange="onGroupChange(this.value)"></select>
      </div>
      <div class="stat-val" id="predict-target" style="font-size: 20px;">--% / --K</div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
        <div class="stat-sub" id="predict-count" style="margin-top: 0;">建议开启灯具: -- 盏</div>
        <button id="btn-apply-suggestion" class="btn-action" style="padding: 2px 8px; font-size: 11px;" onclick="applySuggestedLights()">⚡ 应用建议</button>
      </div>
    </div>
    <div class="card">
      <div class="card-title"><span id="card-title-perf">系统性能占用</span> <span>⚡</span></div>
      <div class="stat-val" id="proc-cpu">CPU: --%</div>
      <div class="stat-sub" id="proc-mem">内存: -- MB | 运行: --</div>
    </div>
    <div class="card" style="display: flex; flex-direction: column; justify-content: space-between;">
      <div>
        <div class="card-title">
          <span id="card-title-current">受控灯光状态与勾选控制</span> <span>🎛️</span>
        </div>
        <div style="font-size: 12px; color: var(--subtext); margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
          <span id="current-group-name" style="font-weight: 500;">--</span>
          <span id="active-summary" style="font-size: 11px; color: var(--primary); font-weight: 600;">--</span>
        </div>

        <!-- 首页只显示勾选开启的灯具 -->
        <div id="active-lights-container" style="display: flex; flex-direction: column; gap: 6px;">
          <div style="font-size: 12px; color: var(--subtext); padding: 4px 0;">--</div>
        </div>
      </div>

      <!-- 未勾选灯具放入二级菜单 -->
      <div style="margin-top: 10px;">
        <details id="inactive-lights-details" class="secondary-menu" style="background: #090e1a; border: 1px solid var(--border); border-radius: 8px; padding: 6px 10px;">
          <summary style="font-size: 12px; color: var(--subtext); cursor: pointer; display: flex; justify-content: space-between; align-items: center; user-select: none;">
            <span id="lbl-inactive-menu">📁 未勾选灯具 (二级菜单)</span>
            <span id="inactive-badge" style="background: #1e293b; color: #94a3b8; font-size: 11px; padding: 1px 6px; border-radius: 10px; font-weight: 600;">0</span>
          </summary>
          <div id="inactive-lights-container" style="display: flex; flex-direction: column; gap: 6px; margin-top: 8px; max-height: 140px; overflow-y: auto;">
            <!-- 动态填充未勾选关闭的灯具 -->
          </div>
        </details>
      </div>
    </div>
  </div>

  <!-- 性能时序曲线图 -->
  <div class="card">
    <div class="card-title">
      <span id="card-title-perf-chart">系统性能时序曲线 (CPU % & 内存占用)</span>
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
    <div class="card-title"><span id="card-title-logs">实时运行与学习日志</span> <span>📋</span></div>
    <div class="log-box" id="log-box"></div>
  </div>

  <!-- 24小时自适应偏好曲线表 -->
  <div class="card">
    <div class="card-title">
      <span id="table-title">当前分组 24小时自适应曲线</span>
      <div style="display: flex; gap: 8px; align-items: center;">
        <button class="btn-action" style="padding: 4px 10px; font-size: 12px; border-color: var(--primary); color: var(--primary);" onclick="triggerSyncHAHistory(14)" id="btn-sync-history-dash">🔄 从 HA 历史回溯学习曲线 (14天)</button>
        <span>📈</span>
      </div>
    </div>
    <div style="max-height: 200px; overflow-y: auto;">
      <table class="curve-table">
        <thead>
          <tr>
            <th id="th-time">时间点</th>
            <th id="th-bright">学习亮度</th>
            <th id="th-cct">学习色温</th>
            <th id="th-count">协同开灯数</th>
            <th id="th-samples">调教样本数</th>
          </tr>
        </thead>
        <tbody id="curve-tbody"></tbody>
      </table>
    </div>
  </div>

  <script>
    let currentStep = 1;
    let discoveredLights = [];
    let lightGroupAssignments = {};
    let existingConfig = {};
    let currentLang = 'zh';

    const I18N = {
      zh: {
        pageTitle: "GoodLight 控制面板",
        langBtn: "🌐 English",
        openWizard: "🚀 启动与配置向导",
        running: "● 正在运行",
        cardSolar: "天体与节气感知",
        cardGroup: "分组选择与预测",
        cardPerf: "系统性能占用",
        cardCurrent: "受控灯光状态与勾选控制",
        cardPerfChart: "系统性能时序曲线 (CPU % & 内存占用)",
        cardLogs: "实时运行与学习日志",
        tableTitle: "24小时自适应曲线",
        btnSyncHistoryDash: "🔄 从 HA 历史回溯学习曲线 (14天)",
        lblInactiveMenu: "📁 未勾选灯具 (二级菜单)",
        btnApplySuggestion: "⚡ 应用建议",
        modeActive: "全主动巡航",
        modeTurnOn: "打断模式",
        modePassive: "被动学习",
        modeActiveTitle: "全主动巡航：开灯自动对齐 + 开灯期间随时间平滑渐变调光调色",
        modeTurnOnTitle: "打断模式：仅在开灯瞬间设定为曲线目标，开灯期间保持恒定",
        modePassiveTitle: "被动学习：不主动改光，仅记录并学习用户日常调光偏好",
        thTime: "时间点",
        thBright: "学习亮度",
        thCct: "学习色温",
        thCount: "协同开灯数",
        thSamples: "调教样本数",
        nav1: "欢迎",
        nav2: "填写令牌",
        nav3: "加入灯组",
        nav4: "补足信息",
        nav5: "完成启动",
        txtWizSyncTitle: "🔄 自动从 Home Assistant 历史数据库回溯学习光照习惯 (过去 14 天)",
        txtWizSyncDesc: "直接读取所选灯具在 Home Assistant 中的真实历史调光与色温样本，瞬间生成个性化自适应昼夜曲线，无需从零等待数周日常学习。"
      },
      en: {
        pageTitle: "GoodLight Dashboard",
        langBtn: "🌐 中文",
        openWizard: "🚀 Setup Wizard",
        running: "● Running",
        cardSolar: "Solar & Seasonal Terms",
        cardGroup: "Group Target & Prediction",
        cardPerf: "System Performance",
        cardCurrent: "Light Controls & Status",
        cardPerfChart: "System Performance Timeline (CPU % & RAM)",
        cardLogs: "Live Cruise & Learning Logs",
        tableTitle: "24-Hour Adaptive Curve Profile",
        btnSyncHistoryDash: "🔄 Sync HA History (14 Days)",
        lblInactiveMenu: "📁 Inactive Lights (Secondary Menu)",
        btnApplySuggestion: "⚡ Apply Suggestion",
        modeActive: "Active Cruise",
        modeTurnOn: "Turn-On Only",
        modePassive: "Passive Learn",
        modeActiveTitle: "Active Cruise: Auto smooth transition along circadian curve over time",
        modeTurnOnTitle: "Turn-On Only: Align on turn-on only, keep steady during cruise",
        modePassiveTitle: "Passive Learn: Never auto-dim, only learn manual adjustments",
        thTime: "Time",
        thBright: "Learned Brightness",
        thCct: "Learned CCT",
        thCount: "Active Lights",
        thSamples: "Samples",
        nav1: "Welcome",
        nav2: "Token",
        nav3: "Group Lights",
        nav4: "Location & Weather",
        nav5: "Launch",
        txtWizSyncTitle: "🔄 Auto-Backfill Learning from Home Assistant History (Past 14 Days)",
        txtWizSyncDesc: "Directly parses your past 14 days of lighting adjustments from HA to bootstrap your personalized circadian curves instantly without waiting for weeks."
      }
    };

    function toggleLanguage() {
      setLanguage(currentLang === 'zh' ? 'en' : 'zh');
    }

    async function setLanguage(lang) {
      currentLang = lang;
      localStorage.setItem('goodlight_lang', lang);
      applyTranslations();
      try {
        await fetch('/api/control/language', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ language: lang })
        });
      } catch (e) {}
    }

    function applyTranslations() {
      const t = I18N[currentLang] || I18N.zh;
      const el = (id, text) => { const node = document.getElementById(id); if (node) node.innerText = text; };

      el('page-title', t.pageTitle);
      el('btn-lang-toggle', t.langBtn);
      el('btn-wiz-lang', t.langBtn);
      el('btn-open-wizard', t.openWizard);
      el('status-badge', t.running);

      el('card-title-solar', t.cardSolar);
      el('card-title-group', t.cardGroup);
      el('card-title-perf', t.cardPerf);
      el('card-title-current', t.cardCurrent);
      el('card-title-perf-chart', t.cardPerfChart);
      el('card-title-logs', t.cardLogs);
      el('btn-sync-history-dash', t.btnSyncHistoryDash);
      el('lbl-inactive-menu', t.lblInactiveMenu);
      el('btn-apply-suggestion', t.btnApplySuggestion);

      el('th-time', t.thTime);
      el('th-bright', t.thBright);
      el('th-cct', t.thCct);
      el('th-count', t.thCount);
      el('th-samples', t.thSamples);

      el('nav-text-1', t.nav1);
      el('nav-text-2', t.nav2);
      el('nav-text-3', t.nav3);
      el('nav-text-4', t.nav4);
      el('nav-text-5', t.nav5);

      el('txt-wiz-sync-title', t.txtWizSyncTitle);
      el('txt-wiz-sync-desc', t.txtWizSyncDesc);
    }

    async function triggerSyncHAHistory(days) {
      const btn = document.getElementById('btn-sync-history-dash');
      const originalText = btn ? btn.innerText : '';
      if (btn) {
        btn.disabled = true;
        btn.innerText = (currentLang === 'en') ? '⏳ Syncing HA History...' : '⏳ 正在从 HA 回溯历史...';
      }

      try {
        const resp = await fetch('/api/setup/sync_ha_history', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ days: days || 14 })
        });
        const res = await resp.json();
        if (res.ok) {
          const msg = (currentLang === 'en')
            ? `🎉 Successfully synced from Home Assistant! Imported ${res.total_samples} samples across past ${res.days} days.`
            : `🎉 成功从 Home Assistant 历史回溯学习！过去 ${res.days} 天共提取到 ${res.total_samples} 条真实样本，自适应曲线已完成校准更新。`;
          alert(msg);
          await updateDashboard();
          await updateLightData();
        } else {
          alert(((currentLang === 'en') ? 'Sync failed: ' : '回溯失败: ') + (res.message || 'Error'));
        }
      } catch (e) {
        alert(((currentLang === 'en') ? 'Sync request error: ' : '请求异常: ') + e.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerText = originalText;
        }
      }
    }

    function openWizard() {
      document.getElementById('wizard-modal').style.display = 'flex';
      loadCurrentConfigIntoWizard();
      goToStep(1);
    }

    function closeWizard() {
      document.getElementById('wizard-modal').style.display = 'none';
    }

    function goToStep(step) {
      currentStep = step;
      for (let i = 1; i <= 5; i++) {
        const stepDiv = document.getElementById(`wizard-step-${i}`);
        if (stepDiv) stepDiv.style.display = (i === step) ? 'block' : 'none';
        const nav = document.getElementById(`step-nav-${i}`);
        if (nav) {
          nav.classList.remove('active', 'done');
          if (i === step) nav.classList.add('active');
          else if (i < step) nav.classList.add('done');
        }
      }
      if (step === 3 && discoveredLights.length === 0) {
        rescanLights();
      }
      if (step === 5) {
        renderSummary();
      }
    }

    function toggleTokenVisibility() {
      const inp = document.getElementById('wiz-ha-token');
      inp.type = (inp.type === 'password') ? 'text' : 'password';
    }

    async function loadCurrentConfigIntoWizard() {
      try {
        const resp = await fetch('/api/setup/current_config');
        const data = await resp.json();
        existingConfig = data;
        if (data.ha_url) document.getElementById('wiz-ha-url').value = data.ha_url;
        if (data.latitude) document.getElementById('wiz-lat').value = data.latitude;
        if (data.longitude) document.getElementById('wiz-lng').value = data.longitude;
        if (data.timezone_offset) document.getElementById('wiz-tz').value = data.timezone_offset.toFixed(1);
        if (data.weather_enabled !== undefined) {
          document.getElementById('wiz-weather-toggle').checked = !!data.weather_enabled;
        }
        if (data.ui_language) {
          setLanguage(data.ui_language);
        }
        previewWeatherForCoords();

        if (data.groups) {
          data.groups.forEach(g => {
            (g.lights || []).forEach(l => {
              lightGroupAssignments[l.entity_id] = {
                group_id: g.id,
                group_name: g.name,
                priority: l.priority || 1,
                min_kelvin: l.min_kelvin || 2700,
                max_kelvin: l.max_kelvin || 6500,
                name: l.name
              };
            });
          });
        }
      } catch (e) {
        console.error("加载向导初始配置失败:", e);
      }
    }

    async function testHAConnection() {
      const url = document.getElementById('wiz-ha-url').value.trim();
      const token = document.getElementById('wiz-ha-token').value.trim();
      const statusBox = document.getElementById('wiz-conn-status');
      const testBtn = document.getElementById('btn-wiz-test');
      const nextBtn = document.getElementById('btn-step2-next');

      if (!token && !existingConfig.has_token) {
        statusBox.style.display = 'block';
        statusBox.style.background = 'rgba(251, 113, 133, 0.15)';
        statusBox.style.color = '#fb7185';
        statusBox.innerText = '⚠️ 请先输入或粘贴长期访问令牌 (Long-Lived Access Token)';
        return;
      }

      testBtn.disabled = true;
      testBtn.innerText = '⏳ 正在连接测试并扫描实体...';
      statusBox.style.display = 'block';
      statusBox.style.background = 'rgba(56, 189, 248, 0.15)';
      statusBox.style.color = '#38bdf8';
      statusBox.innerText = '正在验证 Home Assistant WebSocket/REST 连通性...';

      try {
        const resp = await fetch('/api/setup/test_connection', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: url, token: token })
        });
        const res = await resp.json();

        if (res.ok) {
          statusBox.style.background = 'rgba(74, 222, 128, 0.15)';
          statusBox.style.color = '#4ade80';
          statusBox.innerText = `✅ 连接成功！已自主识别到 ${res.lights_count} 盏全屋灯具设备。`;
          discoveredLights = res.lights || [];
          renderDiscoveredLights();
          nextBtn.disabled = false;
        } else {
          statusBox.style.background = 'rgba(251, 113, 133, 0.15)';
          statusBox.style.color = '#fb7185';
          statusBox.innerText = `❌ 连接失败: ${res.message}`;
          nextBtn.disabled = true;
        }
      } catch (e) {
        statusBox.style.background = 'rgba(251, 113, 133, 0.15)';
        statusBox.style.color = '#fb7185';
        statusBox.innerText = `❌ 请求发生异常: ${e.message}`;
      } finally {
        testBtn.disabled = false;
        testBtn.innerText = '🔍 测试连接并自动扫描全屋灯具';
      }
    }

    async function rescanLights() {
      const listContainer = document.getElementById('wiz-lights-list');
      listContainer.innerHTML = '<div style="color:var(--primary);text-align:center;padding:30px;">⏳ 正在向 Home Assistant 扫描全量灯具列表...</div>';
      try {
        const resp = await fetch('/api/setup/discover_lights');
        const res = await resp.json();
        if (res.ok) {
          discoveredLights = res.lights || [];
          renderDiscoveredLights();
        } else {
          listContainer.innerHTML = `<div style="color:var(--rose);text-align:center;padding:30px;">扫描失败: ${res.message}</div>`;
        }
      } catch (e) {
        listContainer.innerHTML = `<div style="color:var(--rose);text-align:center;padding:30px;">网络请求失败: ${e.message}</div>`;
      }
    }

    function renderDiscoveredLights() {
      const container = document.getElementById('wiz-lights-list');
      if (discoveredLights.length === 0) {
        container.innerHTML = '<div style="color:var(--subtext);text-align:center;padding:30px;">未发现任何以 light.* 开头的实体，请确认HA已正确接入灯具。</div>';
        return;
      }

      container.innerHTML = '';
      discoveredLights.forEach((light) => {
        const ent = light.entity_id;
        const assigned = lightGroupAssignments[ent] || {};
        const currentGroup = assigned.group_id || 'none';

        const card = document.createElement('div');
        card.className = 'light-item-card';

        let badges = '';
        if (light.has_brightness) badges += '<span class="tag-badge tag-green" style="margin-right:4px;">☀️ 调光</span>';
        if (light.has_color_temp) badges += '<span class="tag-badge tag-blue" style="margin-right:4px;">🌈 色温</span>';
        if (!light.has_brightness && !light.has_color_temp) badges += '<span class="tag-badge tag-amber" style="margin-right:4px;">💡 开关</span>';

        const stateColor = (light.state === 'on') ? 'var(--success)' : 'var(--subtext)';

        card.innerHTML = `
          <div style="flex: 1; min-width: 220px;">
            <div style="font-weight: 600; font-size: 14px; display: flex; align-items: center; gap: 8px;">
              <span>${light.name}</span>
              <span style="font-size: 11px; color: ${stateColor};">● ${light.state.toUpperCase()}</span>
            </div>
            <div style="font-size: 12px; color: var(--subtext); font-family: monospace; margin: 3px 0 6px;">${ent}</div>
            <div>${badges}</div>
          </div>
          <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 12px; color: var(--subtext);">分配到分组:</span>
            <select class="light-group-select" data-ent="${ent}" data-name="${light.name}" onchange="onAssignLightGroup('${ent}', this.value, '${light.name}', ${light.min_kelvin}, ${light.max_kelvin})">
              <option value="living_room_main" ${currentGroup==='living_room_main'?'selected':''}>🛋️ 客厅主灯组</option>
              <option value="living_room_ambient" ${currentGroup==='living_room_ambient'?'selected':''}>✨ 客厅氛围灯组</option>
              <option value="desk_lamp" ${currentGroup==='desk_lamp'?'selected':''}>🖥️ 工作台/台灯组</option>
              <option value="none" ${currentGroup==='none'?'selected':''}>🚫 不纳入自适应托管</option>
            </select>
          </div>
        `;
        container.appendChild(card);
      });
    }

    function onAssignLightGroup(ent, groupId, name, minK, maxK) {
      if (groupId === 'none') {
        delete lightGroupAssignments[ent];
      } else {
        lightGroupAssignments[ent] = {
          group_id: groupId,
          name: name,
          priority: groupId === 'living_room_ambient' ? 2 : 1,
          min_kelvin: minK || 2700,
          max_kelvin: maxK || 6500
        };
      }
    }

    function autoRecommendGroups() {
      discoveredLights.forEach(light => {
        const n = light.name.toLowerCase();
        const ent = light.entity_id.toLowerCase();
        let targetGroup = 'none';

        if (n.includes('主灯') || n.includes('吸顶') || ent.includes('light_2') || (!n.includes('氛围') && !n.includes('台灯') && !n.includes('插座') && !n.includes('指示') && light.has_brightness)) {
          targetGroup = 'living_room_main';
        } else if (n.includes('氛围') || n.includes('灯带') || ent.includes('ambient')) {
          targetGroup = 'living_room_ambient';
        } else if (n.includes('台灯') || n.includes('工作') || n.includes('desk') || ent.includes('lamp')) {
          targetGroup = 'desk_lamp';
        }

        onAssignLightGroup(light.entity_id, targetGroup, light.name, light.min_kelvin, light.max_kelvin);
      });
      renderDiscoveredLights();
    }

    function setCity(lat, lng, tz, label) {
      document.getElementById('wiz-lat').value = lat;
      document.getElementById('wiz-lng').value = lng;
      if (tz !== undefined) {
        document.getElementById('wiz-tz').value = parseFloat(tz).toFixed(1);
      }
      previewWeatherForCoords();
    }

    async function searchLocation() {
      const q = document.getElementById('wiz-geo-search').value.trim();
      const resultsBox = document.getElementById('geo-results-box');
      if (!q) return;
      resultsBox.style.display = 'block';
      resultsBox.innerHTML = '<div style="color:var(--primary);padding:10px;font-size:12px;">⏳ 正在通过全球地理编码引擎检索地址...</div>';
      try {
        const resp = await fetch(`/api/setup/geocode?query=${encodeURIComponent(q)}`);
        const res = await resp.json();
        if (res.ok && res.results && res.results.length > 0) {
          resultsBox.innerHTML = '';
          res.results.forEach(item => {
            const div = document.createElement('div');
            div.style.padding = '8px 12px';
            div.style.borderBottom = '1px solid var(--border)';
            div.style.cursor = 'pointer';
            div.style.fontSize = '13px';
            div.style.display = 'flex';
            div.style.justifyContent = 'space-between';
            div.style.alignItems = 'center';
            div.onmouseover = () => { div.style.background = 'rgba(56, 189, 248, 0.1)'; };
            div.onmouseout = () => { div.style.background = 'transparent'; };

            const title = [item.name, item.admin1, item.country].filter(Boolean).join(', ');
            const tzStr = item.timezone ? `时区: ${item.timezone} (UTC${item.timezone_offset >= 0 ? '+' : ''}${item.timezone_offset})` : '';

            div.innerHTML = `
              <div>
                <span style="font-weight:600;color:var(--text);">📍 ${title}</span>
                <span style="color:var(--subtext);font-size:11px;margin-left:8px;">${tzStr}</span>
              </div>
              <div style="font-family:monospace;font-size:11px;color:var(--primary);">
                ${item.latitude.toFixed(4)}°, ${item.longitude.toFixed(4)}°
              </div>
            `;
            div.onclick = () => {
              document.getElementById('wiz-lat').value = item.latitude.toFixed(4);
              document.getElementById('wiz-lng').value = item.longitude.toFixed(4);
              if (item.timezone_offset !== undefined) {
                document.getElementById('wiz-tz').value = item.timezone_offset.toFixed(1);
              }
              resultsBox.style.display = 'none';
              previewWeatherForCoords();
            };
            resultsBox.appendChild(div);
          });
        } else {
          resultsBox.innerHTML = '<div style="color:var(--subtext);padding:10px;font-size:12px;">未检索到对应地名，可尝试输入英文或拼音。</div>';
        }
      } catch (e) {
        resultsBox.innerHTML = `<div style="color:var(--rose);padding:10px;font-size:12px;">检索失败: ${e.message}</div>`;
      }
    }

    async function previewWeatherForCoords() {
      const lat = parseFloat(document.getElementById('wiz-lat').value);
      const lng = parseFloat(document.getElementById('wiz-lng').value);
      const previewBox = document.getElementById('wiz-weather-preview');
      if (!previewBox || isNaN(lat) || isNaN(lng)) return;
      previewBox.innerText = '⏳ 正在预览当地气象与体感温度...';
      try {
        const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lng}&current=temperature_2m,apparent_temperature,weather_code,cloud_cover&timezone=auto`;
        const resp = await fetch(url);
        if (resp.ok) {
          const d = await resp.json();
          const curr = d.current || {};
          const t = curr.temperature_2m;
          const ap = curr.apparent_temperature;
          const cc = curr.cloud_cover;
          previewBox.innerHTML = `📍 <strong>当地实时气象</strong>: 气温 <strong>${t}°C</strong> (体感 ${ap}°C) | 云量 <strong>${cc}%</strong> | 时区偏移: UTC${d.utc_offset_seconds>=0?'+':''}${d.utc_offset_seconds/3600}h`;
        } else {
          previewBox.innerText = '（坐标已就绪，保存后将自动感知气象）';
        }
      } catch (e) {
        previewBox.innerText = '（坐标已更新，将在后台自动同步）';
      }
    }

    function renderSummary() {
      const url = document.getElementById('wiz-ha-url').value;
      const token = document.getElementById('wiz-ha-token').value;
      const lat = document.getElementById('wiz-lat').value;
      const lng = document.getElementById('wiz-lng').value;
      const tz = document.getElementById('wiz-tz').value;
      const weatherOn = document.getElementById('wiz-weather-toggle').checked;

      document.getElementById('summary-url').innerText = url;
      document.getElementById('summary-token').innerText = token ? (token.substring(0, 10) + '...' + token.slice(-8)) : (existingConfig.has_token ? '保持现有已配置令牌' : '未提供');
      
      const assignedEnts = Object.keys(lightGroupAssignments);
      const groupsFound = new Set(Object.values(lightGroupAssignments).map(v => v.group_id));
      document.getElementById('summary-groups').innerText = `${assignedEnts.length} 盏灯具分配在 ${groupsFound.size} 个独立受控组中`;
      document.getElementById('summary-loc').innerText = `纬度: ${lat}°, 经度: ${lng}°, 时区: UTC+${tz}`;
      document.getElementById('summary-weather').innerText = weatherOn ? '已启用 (基于 Open-Meteo 实时气温与云量双重光补偿)' : '已停用';

      const syncHistoryOn = document.getElementById('wiz-sync-history-toggle') ? document.getElementById('wiz-sync-history-toggle').checked : false;
      const historySummaryEl = document.getElementById('summary-history');
      if (historySummaryEl) {
        historySummaryEl.innerText = syncHistoryOn ? ((currentLang === 'en') ? 'Enabled (Backfill from past 14 days)' : '已启用 (从过去 14 天记录回溯训练)') : ((currentLang === 'en') ? 'Disabled' : '已跳过');
      }
    }

    async function finishWizard() {
      const finishBtn = document.getElementById('btn-wiz-finish');
      finishBtn.disabled = true;
      finishBtn.innerText = (currentLang === 'en') ? '⏳ Saving configuration...' : '⏳ 正在保存配置并重启引擎...';

      const ha_url = document.getElementById('wiz-ha-url').value.trim();
      const ha_token = document.getElementById('wiz-ha-token').value.trim();
      const lat = parseFloat(document.getElementById('wiz-lat').value) || 39.9042;
      const lng = parseFloat(document.getElementById('wiz-lng').value) || 116.4074;
      const tz = parseFloat(document.getElementById('wiz-tz').value) || 8.0;
      const weather_enabled = document.getElementById('wiz-weather-toggle').checked;

      // 构建 groups
      const groupMap = {
        'living_room_main': { id: 'living_room_main', name: '客厅主吸顶灯', profile_path: 'profile_living_room_main.json', lights: [] },
        'living_room_ambient': { id: 'living_room_ambient', name: '客厅氛围灯带', profile_path: 'profile_living_room_ambient.json', lights: [] },
        'desk_lamp': { id: 'desk_lamp', name: '书房/工作台灯', profile_path: 'profile_desk_lamp.json', lights: [] }
      };

      for (const [ent, info] of Object.entries(lightGroupAssignments)) {
        const gid = info.group_id;
        if (!groupMap[gid]) {
          groupMap[gid] = { id: gid, name: info.group_name || gid, profile_path: `profile_${gid}.json`, lights: [] };
        }
        groupMap[gid].lights.push({
          entity_id: ent,
          name: info.name,
          priority: info.priority || 1,
          min_kelvin: info.min_kelvin || 2700,
          max_kelvin: info.max_kelvin || 6500
        });
      }

      const activeGroups = Object.values(groupMap).filter(g => g.lights.length > 0);

      const payload = {
        ha_url: ha_url,
        ha_token: ha_token,
        latitude: lat,
        longitude: lng,
        timezone_offset: tz,
        weather_enabled: weather_enabled,
        ui_language: currentLang,
        groups: activeGroups.length > 0 ? activeGroups : existingConfig.groups
      };

      try {
        const resp = await fetch('/api/setup/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const res = await resp.json();
        if (res.ok) {
          const syncHist = document.getElementById('wiz-sync-history-toggle') ? document.getElementById('wiz-sync-history-toggle').checked : false;
          if (syncHist) {
            try {
              finishBtn.innerText = (currentLang === 'en') ? '⏳ Backfilling history from HA...' : '⏳ 正在从 Home Assistant 提取历史光照记录...';
              const hResp = await fetch('/api/setup/sync_ha_history', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ days: 14 })
              });
              const hRes = await hResp.json();
              if (hRes.ok) {
                const msg = (currentLang === 'en')
                  ? `🎉 GoodLight launched! Imported ${hRes.total_samples} historical samples from HA.`
                  : `🎉 GoodLight 启动向导已保存！并已成功从 Home Assistant 回溯学习了 ${hRes.total_samples} 条真实光照历史！`;
                alert(msg);
              }
            } catch (ex) {
              console.error('History sync error:', ex);
            }
          } else {
            alert((currentLang === 'en') ? '🎉 GoodLight configuration saved successfully!' : '🎉 GoodLight 启动向导配置已保存成功！自适应光照引擎已就绪。');
          }
          closeWizard();
          await updateDashboard();
          await updatePerfData();
          await updateLightData();
        } else {
          alert(((currentLang === 'en') ? 'Save failed: ' : '保存配置失败: ') + (res.message || '未知错误'));
        }
      } catch (e) {
        alert(((currentLang === 'en') ? 'Save error: ' : '请求保存异常: ') + e.message);
      } finally {
        finishBtn.disabled = false;
        finishBtn.innerText = (currentLang === 'en') ? '🎉 Save & Launch GoodLight Cruise' : '🎉 保存并启动 GoodLight 自适应巡航';
      }
    }

    let currentPerfHours = 1;
    let currentLightHours = 24;
    let perfChart = null;
    let lightCharts = {};
    let selectedGroupId = null;
    let allLightsData = [];
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
      await updatePerfData();
      await updateLightData();
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

    let serverCurrentTimeStr = null;

    async function toggleLightState(entityId, willTurnOn) {
      try {
        const resp = await fetch('/api/control/light_toggle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            entity_id: entityId,
            state: willTurnOn ? 'on' : 'off'
          })
        });
        const res = await resp.json();
        if (res.ok) {
          await updateDashboard();
        }
      } catch (e) {
        console.error('切换灯光失败:', e);
      }
    }

    async function applySuggestedLights() {
      if (!selectedGroupId) return;
      try {
        const btn = document.getElementById('btn-apply-suggestion');
        if (btn) btn.disabled = true;
        const resp = await fetch('/api/control/apply_suggestion', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ group_id: selectedGroupId })
        });
        const res = await resp.json();
        if (res.ok) {
          await updateDashboard();
        }
      } catch (e) {
        console.error('应用建议失败:', e);
      } finally {
        const btn = document.getElementById('btn-apply-suggestion');
        if (btn) btn.disabled = false;
      }
    }

    async function setLightMode(entityId, mode) {
      try {
        const resp = await fetch('/api/control/light_mode', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ entity_id: entityId, mode: mode })
        });
        const res = await resp.json();
        if (res.ok) {
          await updateDashboard();
        }
      } catch (e) {
        console.error('设置模式失败:', e);
      }
    }

    function renderCurrentGroup() {
      if (!selectedGroupId) return;
      const isAll = (selectedGroupId === '__all__');
      const g = isAll ? null : groupsData[selectedGroupId];
      const t = I18N[currentLang] || I18N.zh;

      const curNameEl = document.getElementById('current-group-name');
      if (curNameEl) {
        curNameEl.innerText = isAll ? (currentLang === 'en' ? '🌐 All Monitored Lights' : '🌐 全屋受控灯具') : (g ? g.name : '--');
      }

      const targetEl = document.getElementById('predict-target');
      const countEl = document.getElementById('predict-count');
      const tableTitleEl = document.getElementById('table-title');

      if (isAll) {
        const gKeys = Object.keys(groupsData);
        if (gKeys.length > 0) {
          const firstG = groupsData[gKeys[0]];
          targetEl.innerText = `${firstG.prediction.brightness}% / ${firstG.prediction.color_temp}K`;
        }
        countEl.innerText = (currentLang === 'en' ? 'Total: ' : '全屋总计: ') + allLightsData.length + ' ' + (currentLang === 'en' ? 'lights' : '盏');
        tableTitleEl.innerText = (currentLang === 'en' ? '[All Groups] 24-Hour Adaptive Curve' : '[全屋基线] 24小时自适应曲线');
      } else if (g) {
        targetEl.innerText = `${g.prediction.brightness}% / ${g.prediction.color_temp}K`;
        countEl.innerText = (currentLang === 'en' ? 'Recommended: ' : '建议开启灯具: ') + `${g.prediction.light_count} ` + (currentLang === 'en' ? 'lights' : '盏');
        tableTitleEl.innerText = `[${g.name}] ` + (currentLang === 'en' ? '24-Hour Adaptive Curve' : '24小时自适应曲线');
      }

      // 渲染受控灯光列表：首页只显示勾选的，未勾选放入二级菜单
      const lights = isAll ? allLightsData : (g ? (g.lights || []) : []);
      const activeLights = lights.filter(l => l.state === 'on');
      const inactiveLights = lights.filter(l => l.state !== 'on');

      const activeContainer = document.getElementById('active-lights-container');
      const inactiveContainer = document.getElementById('inactive-lights-container');
      const inactiveBadge = document.getElementById('inactive-badge');
      const activeSummary = document.getElementById('active-summary');

      if (activeSummary) {
        activeSummary.innerText = `${activeLights.length} / ${lights.length} ` + (currentLang === 'en' ? 'Active' : '已开启');
      }
      if (inactiveBadge) {
        inactiveBadge.innerText = inactiveLights.length;
      }

      // 1. 首页只显示勾选开启的
      if (activeContainer) {
        if (activeLights.length > 0) {
          activeContainer.innerHTML = activeLights.map(l => {
            const curMode = l.mode || 'active';
            return `
            <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px; background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 6px; padding: 5px 8px; transition: 0.2s;">
              <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; margin: 0; user-select: none; flex: 1; min-width: 0;">
                <input type="checkbox" checked onchange="toggleLightState('${l.entity_id}', false)" style="width: 15px; height: 15px; accent-color: #38bdf8; cursor: pointer; flex-shrink: 0;">
                <span style="font-size: 13px; font-weight: 600; color: #f8fafc; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">💡 ${l.name}</span>
              </label>
              <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
                <span style="font-size: 11px; font-weight: 600; color: #38bdf8; background: #0b172a; padding: 2px 6px; border-radius: 4px;">${l.brightness}% · ${l.color_temp}K</span>
                <select class="mode-select" onchange="setLightMode('${l.entity_id}', this.value)">
                  <option value="active" ${curMode==='active'?'selected':''} title="${t.modeActiveTitle}">🌊 ${t.modeActive}</option>
                  <option value="turn_on" ${curMode==='turn_on'?'selected':''} title="${t.modeTurnOnTitle}">⚡ ${t.modeTurnOn}</option>
                  <option value="passive" ${curMode==='passive'?'selected':''} title="${t.modePassiveTitle}">🧠 ${t.modePassive}</option>
                </select>
              </div>
            </div>`;
          }).join('');
        } else {
          activeContainer.innerHTML = `<div style="font-size: 12px; color: var(--subtext); padding: 6px 0; text-align: center;">⚪ ${currentLang === 'en' ? 'No active lights (All off in secondary menu)' : '暂无开启灯具 (均在二级菜单中)'}</div>`;
        }
      }

      // 2. 未勾选放入二级菜单
      if (inactiveContainer) {
        if (inactiveLights.length > 0) {
          inactiveContainer.innerHTML = inactiveLights.map(l => {
            const curMode = l.mode || 'active';
            return `
            <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px; background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border); border-radius: 6px; padding: 5px 8px;">
              <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; margin: 0; user-select: none; flex: 1; min-width: 0;">
                <input type="checkbox" onchange="toggleLightState('${l.entity_id}', true)" style="width: 15px; height: 15px; accent-color: #38bdf8; cursor: pointer; flex-shrink: 0;">
                <span style="font-size: 12px; color: #94a3b8; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${l.name}</span>
              </label>
              <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
                <span style="font-size: 11px; color: #64748b;">${currentLang === 'en' ? 'Off' : '关闭'}</span>
                <select class="mode-select" onchange="setLightMode('${l.entity_id}', this.value)">
                  <option value="active" ${curMode==='active'?'selected':''} title="${t.modeActiveTitle}">🌊 ${t.modeActive}</option>
                  <option value="turn_on" ${curMode==='turn_on'?'selected':''} title="${t.modeTurnOnTitle}">⚡ ${t.modeTurnOn}</option>
                  <option value="passive" ${curMode==='passive'?'selected':''} title="${t.modePassiveTitle}">🧠 ${t.modePassive}</option>
                </select>
              </div>
            </div>`;
          }).join('');
        } else {
          inactiveContainer.innerHTML = `<div style="font-size: 11px; color: var(--subtext); padding: 4px 0; text-align: center;">${currentLang === 'en' ? 'All lights are active on Home' : '所有灯具均已开启在首页'}</div>`;
        }
      }

      // 3. 渲染24小时曲线表
      const profileSource = isAll ? (groupsData[Object.keys(groupsData)[0]] || {}).profile : (g ? g.profile : {});
      let currentHour = new Date().getHours();
      if (serverCurrentTimeStr) {
        try {
          const parts = serverCurrentTimeStr.split(' ')[1].split(':');
          currentHour = parseInt(parts[0], 10);
        } catch (e) {}
      }

      const tbody = document.getElementById('curve-tbody');
      if (tbody) {
        tbody.innerHTML = '';
        for (let h = 0; h < 24; h++) {
          const item = (profileSource && profileSource[h.toString()]) || {};
          const isCurrent = (h === currentHour);
          const tr = document.createElement('tr');
          if (isCurrent) tr.className = 'highlight-row';
          const curLabel = isCurrent ? (currentLang === 'en' ? '👈 (Now)' : '👈 (当前)') : '';
          const unit = currentLang === 'en' ? 'lights' : '盏';
          const times = currentLang === 'en' ? 'samples' : '次';
          tr.innerHTML = `
            <td>${h.toString().padStart(2, '0')}:00 ${curLabel}</td>
            <td>${item.brightness || '--'}%</td>
            <td>${item.color_temp || '--'}K</td>
            <td>${item.light_count || 1} ${unit}</td>
            <td>${item.samples_count || 0} ${times}</td>
          `;
          tbody.appendChild(tr);
        }
      }
    }

    async function updateDashboard() {
      try {
        const resp = await fetch('/api/status');
        const data = await resp.json();

        if (!localStorage.getItem('goodlight_lang') && data.ui_language && data.ui_language !== currentLang) {
          setLanguage(data.ui_language);
        }

        serverCurrentTimeStr = data.time.current_time;
        const timePrefix = currentLang === 'en' ? 'System Time: ' : '当前系统时间: ';
        document.getElementById('sim-time-badge').innerText = `${timePrefix}${data.time.current_time} (UTC${data.time.timezone_offset>=0?'+':''}${data.time.timezone_offset})`;
        document.getElementById('tz-select').value = data.time.timezone_offset.toFixed(1);

        const progLabel = currentLang === 'en' ? 'Progress' : '进度';
        document.getElementById('solar-term').innerText = `${data.solar.term} (${progLabel}: ${(data.solar.term_progress * 100).toFixed(0)}%)`;
        const elevLabel = currentLang === 'en' ? 'Solar Elevation: ' : '太阳高度角: ';
        const seasonLabel = currentLang === 'en' ? 'Season Factor: ' : '季节因子: ';
        document.getElementById('solar-elevation').innerText = `${elevLabel}${data.solar.elevation.toFixed(1)}° | ${seasonLabel}${data.solar.season_factor.toFixed(2)}`;

        const weatherLine = document.getElementById('weather-line');
        if (weatherLine) {
          if (data.weather && data.weather.enabled && data.weather.temperature !== null) {
            const wLabel = currentLang === 'en' ? 'Live Weather: ' : '实时气象: ';
            const tempLabel = currentLang === 'en' ? 'Temp: ' : '气温: ';
            const feelsLabel = currentLang === 'en' ? 'Feels: ' : '体感: ';
            const cloudLabel = currentLang === 'en' ? 'Clouds: ' : '云量: ';
            weatherLine.innerText = `⛅ ${wLabel}${data.weather.weather_desc} | ${tempLabel}${data.weather.temperature}°C (${feelsLabel}${data.weather.apparent_temperature}°C) | ${cloudLabel}${data.weather.cloud_cover}%`;
          } else if (data.weather && !data.weather.enabled) {
            weatherLine.innerText = currentLang === 'en' ? '⛅ Live Weather: Disabled' : '⛅ 实时气象: 未启用环境气象感知';
          } else {
            weatherLine.innerText = currentLang === 'en' ? '⛅ Live Weather: Syncing...' : '⛅ 实时气象: 正在同步中...';
          }
        }

        document.getElementById('proc-cpu').innerText = `CPU: ${data.process.cpu_percent}%`;
        const memLabel = currentLang === 'en' ? 'RAM: ' : '物理内存: ';
        const uptimeLabel = currentLang === 'en' ? 'Uptime: ' : '运行: ';
        document.getElementById('proc-mem').innerText = `${memLabel}${data.process.mem_rss_mb} MB | ${uptimeLabel}${data.process.uptime}`;

        // 分组下拉框更新
        groupsData = data.groups;
        allLightsData = data.all_lights || [];
        const gSelect = document.getElementById('group-select');
        const existingKeys = Object.keys(groupsData);
        if (existingKeys.length > 0 && !selectedGroupId) {
          selectedGroupId = existingKeys[0];
        }
        gSelect.innerHTML = '';

        // 全屋受控灯具选项
        const allOpt = document.createElement('option');
        allOpt.value = '__all__';
        const allSuffix = currentLang === 'en' ? 'All Monitored Lights' : '全屋受控灯具 (全部分组)';
        allOpt.innerText = `🌐 ${allSuffix} (${allLightsData.length})`;
        if (selectedGroupId === '__all__') allOpt.selected = true;
        gSelect.appendChild(allOpt);

        for (const [gid, ginfo] of Object.entries(groupsData)) {
          const opt = document.createElement('option');
          opt.value = gid;
          const lightsSuffix = currentLang === 'en' ? 'lights' : '盏灯';
          opt.innerText = `${ginfo.name} (${ginfo.lights.length} ${lightsSuffix})`;
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
      const debugDetails = document.querySelector('details');
      if (debugDetails) {
        debugDetails.addEventListener('toggle', function() {
          const icon = document.getElementById('debug-toggle-icon');
          if (icon) icon.innerText = this.open ? (currentLang === 'en' ? 'Collapse ▲' : '收起 ▲') : (currentLang === 'en' ? 'Expand ▼' : '展开 ▼');
        });
      }
      const savedLang = localStorage.getItem('goodlight_lang');
      if (savedLang) {
        setLanguage(savedLang);
      }
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
        set_log_tz(self.service.tz)
        self.start_time = time.time()
        self.app = web.Application()
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/api/status", self.handle_api_status)
        self.app.router.add_get("/api/history/perf", self.handle_api_history_perf)
        self.app.router.add_get("/api/history/lights", self.handle_api_history_lights)
        self.app.router.add_post("/api/control/timezone", self.handle_control_timezone)
        self.app.router.add_post("/api/control/language", self.handle_control_language)
        self.app.router.add_post("/api/control/time_adjust", self.handle_control_time_adjust)
        self.app.router.add_post("/api/control/time_reset", self.handle_control_time_reset)
        self.app.router.add_post("/api/control/light_toggle", self.handle_control_light_toggle)
        self.app.router.add_post("/api/control/light_mode", self.handle_control_light_mode)
        self.app.router.add_post("/api/control/apply_suggestion", self.handle_control_apply_suggestion)
        self.app.router.add_post("/api/setup/test_connection", self.handle_api_setup_test)
        self.app.router.add_get("/api/setup/discover_lights", self.handle_api_setup_discover)
        self.app.router.add_get("/api/setup/geocode", self.handle_api_setup_geocode)
        self.app.router.add_get("/api/setup/current_config", self.handle_api_setup_get_config)
        self.app.router.add_post("/api/setup/sync_ha_history", self.handle_api_setup_sync_history)
        self.app.router.add_post("/api/setup/save", self.handle_api_setup_save)
        self._last_cpu_time = 0.0
        self._last_sample_time = time.time()

    def get_process_metrics(self):
        cpu_percent = 0.0
        rss_mb = 0.0
        vms_mb = 0.0
        uptime_str = "--"

        now = time.time()
        time_delta = max(0.001, now - self._last_sample_time)

        try:
            elapsed = int(now - self.start_time)
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
                # 累加进程的用户态与内核态时钟嘀嗒数
                utime = float(stat_line[13])
                stime = float(stat_line[14])
                total_cpu_time = (utime + stime) / 100.0  # USER_HZ = 100 on Linux

                # 真实瞬时 CPU 使用率计算：ΔCPU时间 / Δ自然流逝时间 * 100%
                if self._last_cpu_time > 0:
                    cpu_delta = max(0.0, total_cpu_time - self._last_cpu_time)
                    cpu_percent = round((cpu_delta / time_delta) * 100.0, 1)
                else:
                    cpu_percent = 0.0

                self._last_cpu_time = total_cpu_time
                self._last_sample_time = now
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
        all_lights_list = []
        for gid, grp in self.service.groups.items():
            pred = grp.model.predict(h_float, elev, season)
            grp_lights_data = []
            for item in grp.lights:
                ent = item.get("entity_id")
                st = self.service.light_states.get(ent, {})
                name = item.get("name") or st.get("friendly_name") or ent
                light_obj = {
                    "entity_id": ent,
                    "name": name,
                    "group_id": gid,
                    "group_name": grp.name,
                    "priority": item.get("priority", 1),
                    "mode": item.get("mode", "active"),
                    "state": st.get("state", "off"),
                    "brightness": st.get("brightness", 0),
                    "color_temp": st.get("color_temp", 4000)
                }
                grp_lights_data.append(light_obj)
                all_lights_list.append(light_obj)

            groups_dict[gid] = {
                "id": grp.id,
                "name": grp.name,
                "enabled": grp.enabled,
                "lights": grp_lights_data,
                "light_entities": grp.light_entities,
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
            "weather": self.service.weather.get_summary() if hasattr(self.service, "weather") else {},
            "process": proc_stats,
            "groups": groups_dict,
            "all_lights": all_lights_list,
            "logs": list(LOG_BUFFER),
            "ui_language": getattr(self.service, "ui_language", "zh")
        }
        return web.json_response(data)

    async def handle_control_light_toggle(self, request):
        try:
            req_data = await request.json()
            ent = req_data.get("entity_id")
            target_state = req_data.get("state", "off")
            res = await self.service.toggle_light(ent, target_state)
            return web.json_response(res)
        except Exception as e:
            return web.json_response({"ok": False, "message": str(e)})

    async def handle_control_light_mode(self, request):
        try:
            req_data = await request.json()
            ent = req_data.get("entity_id")
            mode = req_data.get("mode", "active")
            ok = self.service.set_light_mode(ent, mode)
            return web.json_response({"ok": ok, "entity_id": ent, "mode": mode})
        except Exception as e:
            return web.json_response({"ok": False, "message": str(e)})

    async def handle_control_apply_suggestion(self, request):
        try:
            req_data = await request.json()
            gid = req_data.get("group_id")
            res = await self.service.apply_suggested_lights(gid)
            return web.json_response(res)
        except Exception as e:
            return web.json_response({"ok": False, "message": str(e)})

    async def handle_control_language(self, request):
        req_data = await request.json()
        lang = req_data.get("language", "zh")
        self.service.set_ui_language(lang)
        return web.json_response({"ok": True, "language": lang})

    async def handle_control_timezone(self, request):
        req_data = await request.json()
        offset = float(req_data.get("timezone_offset", 8.0))
        self.service.update_timezone(offset)
        set_log_tz(self.service.tz)
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
        data = self.service.db.query_metrics(hours=hours, tz=self.service.tz)
        return web.json_response(data)

    async def handle_api_history_lights(self, request):
        hours = float(request.query.get("hours", 24))
        data = self.service.db.query_light_history(hours=hours, tz=self.service.tz)
        return web.json_response(data)

    async def handle_api_setup_test(self, request):
        try:
            req_data = await request.json()
            url = req_data.get("url", "").strip()
            token = req_data.get("token", "").strip()
            res = await self.service.client.test_connection(url, token)
            return web.json_response(res)
        except Exception as e:
            return web.json_response({"ok": False, "message": str(e)})

    async def handle_api_setup_discover(self, request):
        try:
            lights = await self.service.client.discover_lights()
            return web.json_response({"ok": True, "lights": lights, "lights_count": len(lights)})
        except Exception as e:
            return web.json_response({"ok": False, "message": str(e), "lights": []})

    async def handle_api_setup_geocode(self, request):
        query = request.query.get("query", "").strip()
        if not query:
            return web.json_response({"ok": False, "results": [], "message": "请输入要检索的地名或城市"})

        url = f"https://geocoding-api.open-meteo.com/v1/search?name={query}&count=6&language=zh,en&format=json"
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        return web.json_response({"ok": False, "results": [], "message": f"HTTP {resp.status}"})
                    data = await resp.json()
                    raw_results = data.get("results", []) or []
                    results = []
                    for r in raw_results:
                        lat = float(r.get("latitude", 0.0))
                        lng = float(r.get("longitude", 0.0))
                        tz_name = r.get("timezone", "")
                        tz_offset = 8.0
                        if tz_name:
                            try:
                                from zoneinfo import ZoneInfo
                                now_tz = datetime.now(ZoneInfo(tz_name))
                                if now_tz.utcoffset() is not None:
                                    tz_offset = round(now_tz.utcoffset().total_seconds() / 3600.0, 1)
                            except Exception:
                                tz_offset = round(lng / 15.0, 1)
                        else:
                            tz_offset = round(lng / 15.0, 1)

                        results.append({
                            "name": r.get("name", ""),
                            "country": r.get("country", ""),
                            "admin1": r.get("admin1", ""),
                            "latitude": lat,
                            "longitude": lng,
                            "timezone": tz_name,
                            "timezone_offset": tz_offset
                        })
                    return web.json_response({"ok": True, "results": results})
        except Exception as e:
            return web.json_response({"ok": False, "results": [], "message": str(e)})

    async def handle_api_setup_get_config(self, request):
        cfg = self.service.cfg
        ha_cfg = cfg.get("home_assistant", {})
        loc_cfg = cfg.get("location", {})
        tok = ha_cfg.get("token", "")
        masked_tok = (tok[:10] + "..." + tok[-8:]) if len(tok) > 20 else tok
        return web.json_response({
            "ha_url": ha_cfg.get("url", "http://192.168.6.1:8123"),
            "token_masked": masked_tok,
            "has_token": bool(tok and tok != "YOUR_HA_LONG_LIVED_ACCESS_TOKEN"),
            "latitude": loc_cfg.get("latitude", 39.9042),
            "longitude": loc_cfg.get("longitude", 116.4074),
            "timezone_offset": self.service.tz_offset,
            "weather_enabled": self.service.weather.enabled if hasattr(self.service, "weather") else True,
            "ui_language": getattr(self.service, "ui_language", "zh"),
            "groups": cfg.get("groups", [])
        })

    async def handle_api_setup_sync_history(self, request):
        try:
            req_data = await request.json()
            days = int(req_data.get("days", 14))
            res = await self.service.sync_history_from_ha(days=days)
            return web.json_response(res)
        except Exception as e:
            return web.json_response({"ok": False, "message": str(e)})

    async def handle_api_setup_save(self, request):
        try:
            data = await request.json()
            success = self.service.save_and_reload_config(data)
            return web.json_response({"ok": success})
        except Exception as e:
            return web.json_response({"ok": False, "message": str(e)})

    async def start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        add_log(f"Web 控制面板已就绪: http://{self.host}:{self.port}")
