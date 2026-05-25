"""HTML 리포트 생성 — Pythonista WebView 또는 브라우저용"""
import json
from datetime import datetime
from market_prediction.config import DISCLAIMER

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>시장 예측 리포트</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', sans-serif;
    background: #0a0a0f;
    color: #e0e0e0;
    padding: 16px;
    max-width: 480px;
    margin: 0 auto;
  }}
  .header {{
    text-align: center;
    padding: 20px 0;
    border-bottom: 1px solid #222;
  }}
  .header h1 {{ font-size: 20px; color: #fff; }}
  .header .date {{ font-size: 12px; color: #888; margin-top: 4px; }}
  .disclaimer {{
    background: #1a1a2e;
    padding: 10px;
    border-radius: 8px;
    font-size: 11px;
    color: #f0ad4e;
    margin: 12px 0;
    text-align: center;
  }}
  .confidence {{
    text-align: center;
    margin: 16px 0;
  }}
  .confidence-value {{
    font-size: 48px;
    font-weight: 700;
    color: {conf_color};
  }}
  .confidence-label {{ font-size: 12px; color: #888; }}
  .scenarios {{ margin: 16px 0; }}
  .scenario {{
    background: #111;
    border-radius: 12px;
    padding: 16px;
    margin: 8px 0;
    border-left: 4px solid {border_color};
  }}
  .scenario-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .scenario-name {{ font-size: 16px; font-weight: 600; }}
  .scenario-prob {{
    font-size: 24px;
    font-weight: 700;
    color: {prob_color};
  }}
  .bar-bg {{
    height: 6px;
    background: #222;
    border-radius: 3px;
    margin: 8px 0;
  }}
  .bar-fill {{
    height: 6px;
    border-radius: 3px;
    transition: width 0.5s;
  }}
  .drivers {{
    font-size: 13px;
    color: #aaa;
    margin-top: 8px;
  }}
  .drivers li {{ margin: 4px 0; }}
  .range {{ font-size: 12px; color: #666; margin-top: 6px; }}
  .events {{
    background: #111;
    border-radius: 12px;
    padding: 16px;
    margin: 16px 0;
  }}
  .events h3 {{ font-size: 14px; margin-bottom: 8px; color: #4fc3f7; }}
  .events li {{ font-size: 13px; margin: 4px 0; color: #ccc; }}
  .macro {{
    background: #111;
    border-radius: 12px;
    padding: 16px;
    margin: 16px 0;
  }}
  .macro h3 {{ font-size: 14px; margin-bottom: 8px; color: #81c784; }}
  .caveats {{
    background: #1a1a0a;
    border-radius: 12px;
    padding: 16px;
    margin: 16px 0;
  }}
  .caveats h3 {{ font-size: 14px; margin-bottom: 8px; color: #ffb74d; }}
  .caveats li {{ font-size: 12px; margin: 4px 0; color: #999; }}
  .footer {{
    text-align: center;
    font-size: 11px;
    color: #444;
    padding: 20px 0;
  }}
  .up {{ color: #ef5350; }}
  .down {{ color: #42a5f5; }}
  .flat {{ color: #ffd54f; }}
</style>
</head>
<body>
  <div class="header">
    <h1>AI 시장 예측 리포트</h1>
    <div class="date">{target_period}</div>
    <div class="date">분석일: {analysis_date}</div>
  </div>

  <div class="disclaimer">{disclaimer}</div>

  <div class="confidence">
    <div class="confidence-label">분석 신뢰도</div>
    <div class="confidence-value">{confidence_pct}%</div>
  </div>

  <div class="scenarios">
    {scenarios_html}
  </div>

  <div class="events">
    <h3>주목할 이벤트</h3>
    <ul>{events_html}</ul>
  </div>

  <div class="macro">
    <h3>거시 전망</h3>
    <p>원/달러: {usd_direction} | 금리: {rate_outlook}</p>
  </div>

  <div class="caveats">
    <h3>분석 한계</h3>
    <ul>{caveats_html}</ul>
  </div>

  <div class="footer">
    Powered by Claude API | v0.1.0<br>
    {generated_at}
  </div>
</body>
</html>"""

SCENARIO_TEMPLATE = """
<div class="scenario" style="border-left-color: {color};">
  <div class="scenario-header">
    <span class="scenario-name">{icon} {name}</span>
    <span class="scenario-prob" style="color: {color};">{prob_pct}%</span>
  </div>
  <div class="bar-bg">
    <div class="bar-fill" style="width: {prob_pct}%; background: {color};"></div>
  </div>
  <div class="range">
    KOSPI {kospi_lo:,.0f} ~ {kospi_hi:,.0f} |
    BTC {btc_lo:,.0f} ~ {btc_hi:,.0f}
  </div>
  <ul class="drivers">{drivers_html}</ul>
</div>
"""

SCENARIO_STYLES = {
    "상승": {"color": "#ef5350", "icon": "▲"},
    "하락": {"color": "#42a5f5", "icon": "▼"},
    "횡보": {"color": "#ffd54f", "icon": "◆"},
}


def generate_report(prediction, output_path=None):
    scenarios_html = ""
    for s in prediction.get("scenarios", []):
        name = s["name"]
        style = SCENARIO_STYLES.get(name, {"color": "#888", "icon": "?"})
        kr = s.get("kospi_range", [0, 0])
        br = s.get("btc_krw_range", [0, 0])
        drivers = "".join(f"<li>{d}</li>" for d in s.get("drivers", []))
        scenarios_html += SCENARIO_TEMPLATE.format(
            color=style["color"],
            icon=style["icon"],
            name=name,
            prob_pct=int(s["probability"] * 100),
            kospi_lo=kr[0], kospi_hi=kr[1],
            btc_lo=br[0], btc_hi=br[1],
            drivers_html=drivers,
        )

    events = prediction.get("key_events", [])
    events_html = "".join(f"<li>{e}</li>" for e in events)

    caveats = prediction.get("caveats", [])
    caveats_html = "".join(f"<li>{c}</li>" for c in caveats)

    macro = prediction.get("macro_outlook", {})
    conf = prediction.get("confidence", 0)
    if conf >= 0.7:
        conf_color = "#4caf50"
    elif conf >= 0.4:
        conf_color = "#ffd54f"
    else:
        conf_color = "#ef5350"

    html = HTML_TEMPLATE.format(
        target_period=prediction.get("target_period", ""),
        analysis_date=prediction.get("analysis_date", ""),
        disclaimer=DISCLAIMER,
        confidence_pct=int(conf * 100),
        conf_color=conf_color,
        scenarios_html=scenarios_html,
        events_html=events_html,
        usd_direction=macro.get("usd_krw_direction", "-"),
        rate_outlook=macro.get("rate_outlook", "-"),
        caveats_html=caveats_html,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        border_color="#333",
        prob_color="#fff",
    )

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

    return html
