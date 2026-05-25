#!/usr/bin/env python3
"""
글로벌 시장 예측 PWA 웹앱 서버
iPad Safari에서 "홈 화면에 추가"하면 네이티브 앱처럼 동작.

사용법:
  python -m market_prediction.webapp.app
  # http://localhost:8080 접속
"""
import json
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from urllib.parse import urlparse

from market_prediction.utils.db import init_db
from market_prediction.analysis.predictor import get_latest_prediction
from market_prediction.analysis.backtest import get_score_history
from market_prediction.ui.html_report import generate_report
from market_prediction.config import DISCLAIMER

WEBAPP_DIR = os.path.dirname(os.path.abspath(__file__))


APP_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="MarketAI">
<link rel="manifest" href="/manifest.json">
<title>Global Market Forecast</title>
<style>
  :root {{
    --bg: #0a0a0f;
    --card: #111118;
    --border: #1a1a24;
    --text: #e0e0e0;
    --muted: #888;
    --accent: #4fc3f7;
    --up: #ef5350;
    --down: #42a5f5;
    --flat: #ffd54f;
    --safe-top: env(safe-area-inset-top, 0px);
    --safe-bottom: env(safe-area-inset-bottom, 0px);
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding-top: var(--safe-top);
    padding-bottom: calc(70px + var(--safe-bottom));
    -webkit-user-select: none;
    user-select: none;
  }}

  /* 탭 바 */
  .tab-bar {{
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: calc(60px + var(--safe-bottom));
    padding-bottom: var(--safe-bottom);
    background: #0d0d14;
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: space-around;
    align-items: center;
    z-index: 100;
  }}
  .tab {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    color: var(--muted);
    font-size: 10px;
    cursor: pointer;
    padding: 8px 16px;
    border: none;
    background: none;
    -webkit-tap-highlight-color: transparent;
  }}
  .tab.active {{ color: var(--accent); }}
  .tab-icon {{ font-size: 22px; }}

  /* 페이지 */
  .page {{
    display: none;
    padding: 16px;
    max-width: 520px;
    margin: 0 auto;
    animation: fadeIn 0.2s ease;
  }}
  .page.active {{ display: block; }}
  @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}

  /* 공용 */
  .card {{
    background: var(--card);
    border-radius: 14px;
    padding: 16px;
    margin: 10px 0;
  }}
  h2 {{
    font-size: 18px;
    margin-bottom: 12px;
  }}
  .loading {{
    text-align: center;
    padding: 60px 0;
    color: var(--muted);
  }}
  .spinner {{
    width: 32px;
    height: 32px;
    border: 3px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto 12px;
  }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  .btn {{
    display: block;
    width: 100%;
    padding: 14px;
    border: none;
    border-radius: 12px;
    background: var(--accent);
    color: #000;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    margin: 12px 0;
    -webkit-tap-highlight-color: transparent;
  }}
  .btn:active {{ opacity: 0.7; }}
  .btn.secondary {{
    background: var(--border);
    color: var(--text);
  }}
  .status {{ font-size: 12px; color: var(--muted); text-align: center; margin: 8px 0; }}
  .disclaimer {{
    background: #1a1a2e;
    padding: 10px;
    border-radius: 8px;
    font-size: 10px;
    color: #f0ad4e;
    text-align: center;
    line-height: 1.5;
    margin: 12px 0;
  }}

  /* 리포트 iframe */
  .report-frame {{
    width: 100%;
    border: none;
    border-radius: 14px;
    background: var(--bg);
    min-height: 70vh;
  }}
</style>
</head>
<body>

<!-- 탭 페이지들 -->
<div class="page active" id="page-home">
  <div style="text-align:center;padding:20px 0 10px;">
    <div style="font-size:28px;font-weight:700;">📊 MarketAI</div>
    <div style="font-size:12px;color:var(--muted);margin-top:4px;">Global Market Forecast</div>
  </div>
  <div class="disclaimer">{disclaimer}</div>
  <div class="card" id="home-summary">
    <div class="loading">
      <div class="spinner"></div>
      최신 예측 불러오는 중...
    </div>
  </div>
  <button class="btn" onclick="refreshData()">🔄 새로 분석하기</button>
  <button class="btn secondary" onclick="collectOnly()">📥 데이터 수집만</button>
  <div class="status" id="home-status"></div>
</div>

<div class="page" id="page-report">
  <h2>📋 분석 리포트</h2>
  <div id="report-container">
    <div class="loading">
      <div class="spinner"></div>
      리포트 로딩 중...
    </div>
  </div>
</div>

<div class="page" id="page-scores">
  <h2>🎯 예측 정확도</h2>
  <div class="card" id="scores-container">
    <div class="loading">
      <div class="spinner"></div>
      히스토리 로딩 중...
    </div>
  </div>
</div>

<div class="page" id="page-settings">
  <h2>⚙️ 설정</h2>
  <div class="card">
    <p style="font-size:13px;color:var(--muted);line-height:1.6;">
      <strong>Version:</strong> 0.2.0 Global<br>
      <strong>Engine:</strong> Claude API<br>
      <strong>Data:</strong> KR (KRX, ECOS) + US (Yahoo, FRED) + Crypto (Bithumb)<br>
      <strong>News:</strong> 한경, 이투데이, 매경, Reuters, CNBC, MarketWatch, WSJ<br><br>
      iPad Safari에서 "공유 → 홈 화면에 추가"를 누르면<br>
      네이티브 앱처럼 사용할 수 있습니다.
    </p>
  </div>
  <div class="card">
    <p style="font-size:11px;color:var(--muted);line-height:1.6;">
      <strong>API 키 설정 (서버 .env):</strong><br>
      CLAUDE_API_KEY — Claude 분석 엔진<br>
      ECOS_API_KEY — 한국은행 거시지표<br>
      FRED_API_KEY — 미국 연준 경제데이터<br>
    </p>
  </div>
</div>

<!-- 탭 바 -->
<div class="tab-bar">
  <button class="tab active" onclick="switchTab('home')">
    <span class="tab-icon">🏠</span>홈
  </button>
  <button class="tab" onclick="switchTab('report')">
    <span class="tab-icon">📋</span>리포트
  </button>
  <button class="tab" onclick="switchTab('scores')">
    <span class="tab-icon">🎯</span>정확도
  </button>
  <button class="tab" onclick="switchTab('settings')">
    <span class="tab-icon">⚙️</span>설정
  </button>
</div>

<script>
function switchTab(name) {{
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  event.currentTarget.classList.add('active');

  if (name === 'report') loadReport();
  if (name === 'scores') loadScores();
}}

async function loadSummary() {{
  try {{
    const resp = await fetch('/api/prediction');
    if (!resp.ok) {{
      document.getElementById('home-summary').innerHTML =
        '<p style="text-align:center;color:var(--muted);padding:20px;">아직 예측 결과가 없습니다.<br>"새로 분석하기"를 눌러주세요.</p>';
      return;
    }}
    const data = await resp.json();
    const p = data.prediction;
    const kr = p.korea || {{}};
    const us = p.us || {{}};
    const crypto = p.crypto || {{}};

    let html = '<div style="font-size:12px;color:var(--muted);margin-bottom:10px;">'
      + p.target_period + ' | 신뢰도 ' + Math.round((p.confidence||0)*100) + '%</div>';

    html += '<div style="margin:8px 0;"><strong>🇰🇷 KOSPI</strong></div>';
    (kr.scenarios || []).forEach(s => {{
      const color = s.name==='상승'?'var(--up)':s.name==='하락'?'var(--down)':'var(--flat)';
      html += '<div style="display:flex;justify-content:space-between;padding:4px 0;">'
        + '<span>' + s.name + '</span>'
        + '<span style="color:'+color+';font-weight:700;">' + Math.round(s.probability*100) + '%</span></div>';
    }});

    html += '<div style="margin:10px 0 4px;"><strong>🇺🇸 S&P 500</strong></div>';
    (us.scenarios || []).forEach(s => {{
      const color = s.name==='Bullish'?'var(--up)':s.name==='Bearish'?'var(--down)':'var(--flat)';
      html += '<div style="display:flex;justify-content:space-between;padding:4px 0;">'
        + '<span>' + s.name + '</span>'
        + '<span style="color:'+color+';font-weight:700;">' + Math.round(s.probability*100) + '%</span></div>';
    }});

    html += '<div style="margin:10px 0 4px;"><strong>₿ BTC</strong>: '
      + (crypto.btc_scenario || '-') + '</div>';

    html += '<div style="font-size:11px;color:var(--muted);margin-top:8px;">분석일: '
      + (data.created_at || '').slice(0,16) + '</div>';

    document.getElementById('home-summary').innerHTML = html;
  }} catch(e) {{
    document.getElementById('home-summary').innerHTML =
      '<p style="text-align:center;color:var(--up);">서버 연결 실패</p>';
  }}
}}

async function loadReport() {{
  try {{
    const resp = await fetch('/report');
    const html = await resp.text();
    document.getElementById('report-container').innerHTML =
      '<iframe class="report-frame" srcdoc="' + html.replace(/"/g, '&quot;') + '"></iframe>';
  }} catch(e) {{
    document.getElementById('report-container').innerHTML =
      '<p style="color:var(--up);">리포트 로딩 실패</p>';
  }}
}}

async function loadScores() {{
  try {{
    const resp = await fetch('/api/scores');
    const scores = await resp.json();
    if (!scores.length) {{
      document.getElementById('scores-container').innerHTML =
        '<p style="text-align:center;color:var(--muted);padding:20px;">아직 채점 기록이 없습니다.</p>';
      return;
    }}
    let html = '<table style="width:100%;font-size:12px;">'
      + '<tr style="color:var(--muted);"><td>날짜</td><td>점수</td><td>모델</td></tr>';
    scores.forEach(s => {{
      const pct = Math.round(s.accuracy_score * 100);
      const color = pct >= 60 ? 'var(--accent)' : pct >= 40 ? 'var(--flat)' : 'var(--up)';
      html += '<tr><td>' + s.target_date + '</td>'
        + '<td style="color:'+color+';font-weight:700;">' + pct + '%</td>'
        + '<td>' + (s.model||'-') + '</td></tr>';
    }});
    html += '</table>';
    document.getElementById('scores-container').innerHTML = html;
  }} catch(e) {{
    document.getElementById('scores-container').innerHTML =
      '<p style="color:var(--up);">로딩 실패</p>';
  }}
}}

async function refreshData() {{
  const status = document.getElementById('home-status');
  status.textContent = '데이터 수집 + AI 분석 중... (1~2분 소요)';
  document.querySelector('.btn').disabled = true;
  try {{
    const resp = await fetch('/api/run', {{ method: 'POST' }});
    const result = await resp.json();
    status.textContent = result.message || '완료!';
    loadSummary();
  }} catch(e) {{
    status.textContent = '오류: ' + e.message;
  }}
  document.querySelector('.btn').disabled = false;
}}

async function collectOnly() {{
  const status = document.getElementById('home-status');
  status.textContent = '데이터 수집 중...';
  try {{
    const resp = await fetch('/api/collect', {{ method: 'POST' }});
    const result = await resp.json();
    status.textContent = result.message || '수집 완료!';
  }} catch(e) {{
    status.textContent = '오류: ' + e.message;
  }}
}}

if ('serviceWorker' in navigator) {{
  navigator.serviceWorker.register('/static/sw.js');
}}

loadSummary();
</script>
</body>
</html>"""


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            self._html(APP_HTML.format(disclaimer=DISCLAIMER))
        elif path == "/report":
            latest = get_latest_prediction()
            if latest:
                html = generate_report(latest["prediction_json"])
                self._html(html)
            else:
                self._html("<h1>아직 예측 없음</h1>")
        elif path == "/api/prediction":
            latest = get_latest_prediction()
            if latest:
                self._json({
                    "prediction": latest["prediction_json"],
                    "created_at": latest["created_at"],
                    "model": latest["model"],
                })
            else:
                self._respond(404, '{"error":"no predictions"}')
        elif path == "/api/scores":
            scores = get_score_history()
            self._json(scores)
        elif path == "/manifest.json":
            manifest_path = os.path.join(WEBAPP_DIR, "manifest.json")
            with open(manifest_path, encoding="utf-8") as f:
                self._respond(200, f.read(), "application/json")
        elif path.startswith("/static/"):
            self._serve_static(path[8:])
        elif path == "/health":
            self._json({"status": "ok"})
        else:
            self._respond(404, "Not Found", "text/plain")

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/run":
            threading.Thread(target=self._run_pipeline_bg, daemon=True).start()
            self._json({"message": "파이프라인 시작됨. 완료 후 새로고침하세요."})
        elif path == "/api/collect":
            try:
                from market_prediction.run_pipeline import collect
                total = collect()
                self._json({"message": f"수집 완료: {total}건"})
            except Exception as exc:
                self._json({"message": f"오류: {exc}"})
        else:
            self._respond(404, "Not Found", "text/plain")

    def _run_pipeline_bg(self):
        try:
            from market_prediction.run_pipeline import collect, predict
            collect()
            predict()
        except Exception as exc:
            print(f"[파이프라인 오류] {exc}")

    def _html(self, body):
        self._respond(200, body, "text/html; charset=utf-8")

    def _json(self, obj):
        self._respond(200, json.dumps(obj, ensure_ascii=False, default=str),
                      "application/json")

    def _respond(self, code, body, content_type="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.wfile.write(body)

    def _serve_static(self, filename):
        static_dir = os.path.join(WEBAPP_DIR, "static")
        filepath = os.path.join(static_dir, filename)
        if not os.path.isfile(filepath):
            self._respond(404, "Not Found", "text/plain")
            return
        ext = filename.rsplit(".", 1)[-1]
        ct = {"js": "application/javascript", "css": "text/css",
              "png": "image/png", "json": "application/json"}.get(ext, "text/plain")
        with open(filepath, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        print(f"[{datetime.now():%H:%M:%S}] {args[0]}")


def run(port=8080):
    init_db()
    server = HTTPServer(("0.0.0.0", port), AppHandler)
    print(f"""
╔══════════════════════════════════════════╗
║   Global Market Forecast PWA Server      ║
╠══════════════════════════════════════════╣
║   http://localhost:{port}                   ║
║                                          ║
║   iPad에서:                               ║
║   1. Safari로 위 URL 접속                  ║
║   2. 공유 → "홈 화면에 추가"                 ║
║   3. 네이티브 앱처럼 실행!                   ║
╚══════════════════════════════════════════╝
    """)
    server.serve_forever()


if __name__ == "__main__":
    run()
