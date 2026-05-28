"""HTML 리포트 생성 — 한국 + 미국 + 국제 종합 분석"""
from datetime import datetime
from market_prediction.config import DISCLAIMER

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>글로벌 시장 예측 리포트</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', sans-serif;
    background: #0a0a0f;
    color: #e0e0e0;
    padding: 16px;
    max-width: 520px;
    margin: 0 auto;
  }}
  .header {{
    text-align: center;
    padding: 20px 0 12px;
    border-bottom: 1px solid #222;
  }}
  .header h1 {{ font-size: 20px; color: #fff; }}
  .header .sub {{ font-size: 12px; color: #888; margin-top: 4px; }}
  .disclaimer {{
    background: #1a1a2e;
    padding: 10px;
    border-radius: 8px;
    font-size: 10px;
    color: #f0ad4e;
    margin: 12px 0;
    text-align: center;
    line-height: 1.5;
  }}
  .section {{
    background: #111;
    border-radius: 12px;
    padding: 16px;
    margin: 10px 0;
  }}
  .section-title {{
    font-size: 15px;
    font-weight: 700;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .flag {{ font-size: 18px; }}
  .confidence-row {{
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 20px;
    margin: 14px 0;
  }}
  .conf-box {{
    text-align: center;
  }}
  .conf-value {{
    font-size: 36px;
    font-weight: 700;
  }}
  .conf-label {{ font-size: 11px; color: #888; }}
  .scenario {{
    background: #0d0d14;
    border-radius: 10px;
    padding: 12px;
    margin: 6px 0;
    border-left: 4px solid #333;
  }}
  .sc-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .sc-name {{ font-size: 14px; font-weight: 600; }}
  .sc-prob {{ font-size: 22px; font-weight: 700; }}
  .bar-bg {{
    height: 5px;
    background: #1a1a1a;
    border-radius: 3px;
    margin: 6px 0;
  }}
  .bar-fill {{
    height: 5px;
    border-radius: 3px;
  }}
  .sc-range {{ font-size: 11px; color: #666; margin-top: 4px; }}
  .sc-drivers {{
    font-size: 12px;
    color: #aaa;
    margin-top: 6px;
    padding-left: 12px;
  }}
  .sc-drivers li {{ margin: 3px 0; }}
  .info-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-top: 8px;
  }}
  .info-item {{
    background: #0d0d14;
    border-radius: 8px;
    padding: 10px;
    text-align: center;
  }}
  .info-label {{ font-size: 10px; color: #888; }}
  .info-value {{ font-size: 16px; font-weight: 600; margin-top: 2px; }}
  .events-table {{
    width: 100%;
    font-size: 12px;
    margin-top: 8px;
  }}
  .events-table td {{
    padding: 6px 4px;
    border-bottom: 1px solid #1a1a1a;
    vertical-align: top;
  }}
  .events-table .ev-date {{ color: #888; white-space: nowrap; width: 70px; }}
  .events-table .ev-market {{ width: 50px; text-align: center; }}
  .impact-high {{ color: #ef5350; }}
  .impact-medium {{ color: #ffd54f; }}
  .impact-low {{ color: #81c784; }}
  .cross-market {{
    font-size: 13px;
    color: #ccc;
    line-height: 1.6;
  }}
  .cross-market p {{ margin: 6px 0; }}
  .risk-tag {{
    display: inline-block;
    background: #1a1010;
    color: #ef9a9a;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    margin: 3px 4px 3px 0;
  }}
  .caveats {{ background: #111; }}
  .caveats li {{ font-size: 11px; margin: 4px 0; color: #999; }}
  .footer {{
    text-align: center;
    font-size: 10px;
    color: #444;
    padding: 16px 0;
  }}
  .up {{ color: #ef5350; }}
  .down {{ color: #42a5f5; }}
  .flat {{ color: #ffd54f; }}
</style>
</head>
<body>
  <div class="header">
    <h1>Global Market Forecast</h1>
    <div class="sub">{target_period}</div>
    <div class="sub">Analysis: {analysis_date}</div>
  </div>

  <div class="disclaimer">{disclaimer}</div>

  <div class="confidence-row">
    <div class="conf-box">
      <div class="conf-label">Overall Confidence</div>
      <div class="conf-value" style="color:{conf_color}">{confidence_pct}%</div>
    </div>
  </div>

  <!-- 한국 시장 -->
  <div class="section">
    <div class="section-title"><span class="flag">🇰🇷</span> 한국 시장 (KOSPI)</div>
    {korea_scenarios_html}
    <div class="info-grid">
      <div class="info-item">
        <div class="info-label">원/달러 전망</div>
        <div class="info-value">{usd_krw_dir}</div>
      </div>
      <div class="info-item">
        <div class="info-label">한은 금리</div>
        <div class="info-value">{kr_rate}</div>
      </div>
    </div>
  </div>

  <!-- 미국 시장 -->
  <div class="section">
    <div class="section-title"><span class="flag">🇺🇸</span> US Market (S&P 500)</div>
    {us_scenarios_html}
    <div class="info-grid">
      <div class="info-item">
        <div class="info-label">Fed Outlook</div>
        <div class="info-value">{fed_outlook}</div>
      </div>
      <div class="info-item">
        <div class="info-label">DXY</div>
        <div class="info-value">{dxy_dir}</div>
      </div>
      <div class="info-item">
        <div class="info-label">VIX Level</div>
        <div class="info-value">{vix_level}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Commodities</div>
        <div class="info-value">Oil {oil_dir} / Gold {gold_dir}</div>
      </div>
    </div>
  </div>

  <!-- 암호화폐 -->
  <div class="section">
    <div class="section-title"><span class="flag">₿</span> Crypto (BTC)</div>
    <div class="info-grid">
      <div class="info-item">
        <div class="info-label">Outlook</div>
        <div class="info-value {crypto_class}">{crypto_outlook}</div>
      </div>
      <div class="info-item">
        <div class="info-label">BTC/KRW Range</div>
        <div class="info-value">{btc_range}</div>
      </div>
    </div>
    <ul class="sc-drivers">{crypto_drivers_html}</ul>
  </div>

  <!-- 시장간 연관 분석 -->
  <div class="section">
    <div class="section-title">🔗 Cross-Market Analysis</div>
    <div class="cross-market">
      <p><strong>US → KR Impact:</strong> {us_to_kr}</p>
      <p><strong>Correlation:</strong> {correlation}</p>
      <p><strong>Global Risks:</strong><br>{risk_tags_html}</p>
    </div>
  </div>

  <!-- 주요 이벤트 -->
  <div class="section">
    <div class="section-title">📅 Key Events</div>
    <table class="events-table">{events_html}</table>
  </div>

  <!-- 분석 한계 -->
  <div class="section caveats">
    <div class="section-title" style="color:#ffb74d;">⚠ Caveats</div>
    <ul>{caveats_html}</ul>
  </div>

  <div class="footer">
    Powered by Claude API | v0.2.0 Global<br>
    {generated_at}
  </div>
</body>
</html>"""

SCENARIO_TEMPLATE = """
<div class="scenario" style="border-left-color:{color};">
  <div class="sc-header">
    <span class="sc-name">{icon} {name}</span>
    <span class="sc-prob" style="color:{color};">{prob_pct}%</span>
  </div>
  <div class="bar-bg">
    <div class="bar-fill" style="width:{prob_pct}%;background:{color};"></div>
  </div>
  <div class="sc-range">{range_text}</div>
  <ul class="sc-drivers">{drivers_html}</ul>
</div>"""

SCENARIO_STYLES = {
    "상승": {"color": "#ef5350", "icon": "▲"},
    "하락": {"color": "#42a5f5", "icon": "▼"},
    "횡보": {"color": "#ffd54f", "icon": "◆"},
    "Bullish": {"color": "#ef5350", "icon": "▲"},
    "Bearish": {"color": "#42a5f5", "icon": "▼"},
    "Neutral": {"color": "#ffd54f", "icon": "◆"},
}

DIR_ARROWS = {"상승": "↑", "하락": "↓", "횡보": "→",
              "up": "↑", "down": "↓", "flat": "→"}


def _render_scenarios(scenarios, range_key):
    html = ""
    for s in scenarios:
        name = s["name"]
        style = SCENARIO_STYLES.get(name, {"color": "#888", "icon": "?"})
        rng = s.get(range_key, [0, 0])
        drivers = "".join(f"<li>{d}</li>" for d in s.get("drivers", []))

        range_text = f"{rng[0]:,.0f} ~ {rng[1]:,.0f}" if rng[0] else ""
        html += SCENARIO_TEMPLATE.format(
            color=style["color"], icon=style["icon"], name=name,
            prob_pct=int(s["probability"] * 100),
            range_text=range_text, drivers_html=drivers,
        )
    return html


def generate_report(prediction, output_path=None):
    korea = prediction.get("korea", {})
    us = prediction.get("us", {})
    crypto = prediction.get("crypto", {})
    cross = prediction.get("cross_market", {})
    commodities = prediction.get("commodities", {})

    korea_html = _render_scenarios(korea.get("scenarios", []), "kospi_range")
    us_html = _render_scenarios(us.get("scenarios", []), "sp500_range")

    events = prediction.get("key_events", [])
    if events and isinstance(events[0], dict):
        events_rows = ""
        for ev in events:
            impact_cls = f"impact-{ev.get('impact', 'low')}"
            events_rows += (
                f"<tr><td class='ev-date'>{ev.get('date','')}</td>"
                f"<td class='ev-market'>{ev.get('market','')}</td>"
                f"<td>{ev.get('event','')}</td>"
                f"<td class='{impact_cls}'>{ev.get('impact','').upper()}</td></tr>"
            )
    else:
        events_rows = "".join(
            f"<tr><td colspan='4'>{e}</td></tr>" for e in events
        )

    caveats = prediction.get("caveats", [])
    caveats_html = "".join(f"<li>{c}</li>" for c in caveats)

    risk_factors = cross.get("global_risk_factors", [])
    risk_tags = "".join(f'<span class="risk-tag">{r}</span>' for r in risk_factors)

    btc_rng = crypto.get("btc_krw_range", [0, 0])
    btc_range_str = f"{btc_rng[0]/1_000_000:,.0f}M ~ {btc_rng[1]/1_000_000:,.0f}M" if btc_rng[0] else "-"

    crypto_outlook = crypto.get("btc_scenario", "-")
    crypto_class = {"bullish": "up", "bearish": "down"}.get(crypto_outlook, "flat")
    crypto_drivers = "".join(f"<li>{d}</li>" for d in crypto.get("drivers", []))

    conf = prediction.get("confidence", 0)
    conf_color = "#4caf50" if conf >= 0.7 else "#ffd54f" if conf >= 0.4 else "#ef5350"

    oil_dir = DIR_ARROWS.get(commodities.get("oil_direction", ""), "→")
    gold_dir = DIR_ARROWS.get(commodities.get("gold_direction", ""), "→")

    html = HTML_TEMPLATE.format(
        target_period=prediction.get("target_period", ""),
        analysis_date=prediction.get("analysis_date", ""),
        disclaimer=DISCLAIMER,
        confidence_pct=int(conf * 100),
        conf_color=conf_color,
        korea_scenarios_html=korea_html,
        usd_krw_dir=korea.get("usd_krw_direction", "-"),
        kr_rate=korea.get("kr_rate_outlook", "-"),
        us_scenarios_html=us_html,
        fed_outlook=us.get("fed_outlook", "-"),
        dxy_dir=us.get("dxy_direction", "-"),
        vix_level=us.get("vix_level", "-"),
        oil_dir=oil_dir, gold_dir=gold_dir,
        crypto_outlook=crypto_outlook,
        crypto_class=crypto_class,
        btc_range=btc_range_str,
        crypto_drivers_html=crypto_drivers,
        us_to_kr=cross.get("us_to_kr_impact", "-"),
        correlation=cross.get("correlation_notes", "-"),
        risk_tags_html=risk_tags,
        events_html=events_rows,
        caveats_html=caveats_html,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

    return html
