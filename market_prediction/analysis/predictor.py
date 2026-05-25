"""Claude API 기반 글로벌 시장 예측 엔진 — 한국 + 미국 + 국제"""
import json
import hashlib
from datetime import datetime, timedelta
from market_prediction.config import CLAUDE_API_KEY, CLAUDE_MODEL
from market_prediction.utils.db import get_db

try:
    import anthropic
except ImportError:
    anthropic = None

SYSTEM_PROMPT = """You are a senior global financial analyst covering Korean, US, and international markets.
You provide objective, data-driven scenario analysis in Korean.
You clearly state uncertainty when data is insufficient.
You never make investment recommendations — only probabilistic scenario analysis.
You analyze cross-market correlations (e.g., US rate decisions → KRW impact → KOSPI flow)."""

ANALYSIS_PROMPT = """아래 한국·미국·국제 데이터를 종합 분석하여 다음 주 글로벌 시장을 예측하세요.

=== 한국 뉴스 ===
{news_kr}

=== 미국/국제 뉴스 (English) ===
{news_global}

=== 한국 시장 가격 (OHLCV) ===
{prices_kr}

=== 미국 시장 가격 (OHLCV) ===
{prices_us}

=== 암호화폐 ===
{prices_crypto}

=== 한국 거시지표 ===
{macro_kr}

=== 미국 거시지표 ===
{macro_us}

=== 글로벌 센티먼트 ===
{macro_global}

다음 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만:
{{
  "analysis_date": "{today}",
  "target_period": "{target_start} ~ {target_end}",
  "korea": {{
    "scenarios": [
      {{"name": "상승", "probability": 0.0, "drivers": ["근거"], "kospi_range": [0, 0]}},
      {{"name": "횡보", "probability": 0.0, "drivers": ["근거"], "kospi_range": [0, 0]}},
      {{"name": "하락", "probability": 0.0, "drivers": ["근거"], "kospi_range": [0, 0]}}
    ],
    "usd_krw_direction": "상승/하락/횡보",
    "kr_rate_outlook": "동결/인상/인하"
  }},
  "us": {{
    "scenarios": [
      {{"name": "Bullish", "probability": 0.0, "drivers": ["driver"], "sp500_range": [0, 0]}},
      {{"name": "Neutral", "probability": 0.0, "drivers": ["driver"], "sp500_range": [0, 0]}},
      {{"name": "Bearish", "probability": 0.0, "drivers": ["driver"], "sp500_range": [0, 0]}}
    ],
    "fed_outlook": "hold/hike/cut",
    "dxy_direction": "up/down/flat",
    "vix_level": "low/moderate/elevated/high"
  }},
  "crypto": {{
    "btc_scenario": "bullish/neutral/bearish",
    "btc_krw_range": [0, 0],
    "drivers": ["근거"]
  }},
  "cross_market": {{
    "us_to_kr_impact": "미국 시장이 한국에 미치는 영향 분석",
    "global_risk_factors": ["글로벌 리스크 1", "리스크 2"],
    "correlation_notes": "시장간 상관관계 분석"
  }},
  "key_events": [
    {{"date": "날짜", "event": "이벤트", "market": "KR/US/GLOBAL", "impact": "high/medium/low"}}
  ],
  "commodities": {{
    "oil_direction": "up/down/flat",
    "gold_direction": "up/down/flat",
    "notes": "원자재 동향"
  }},
  "confidence": 0.0,
  "caveats": ["분석 한계 1", "불확실성 요인 2"]
}}

규칙:
- korea.scenarios의 probability 합 = 1.0
- us.scenarios의 probability 합 = 1.0
- confidence는 데이터 충분성과 시장 불확실성 반영 (0.0~1.0)
- cross_market에서 미국 → 한국 전이 효과를 반드시 분석
- key_events에 한국+미국+국제 이벤트를 모두 포함
- 근거는 제공된 데이터에서만 도출
- 한국 관련은 한국어, 미국 관련은 영어 혼용 가능"""


def _format_news(headlines, limit=30):
    lines = []
    for h in headlines[:limit]:
        lines.append(f"- [{h.get('source','')}] {h['title']}")
    return "\n".join(lines) if lines else "(데이터 없음 / No data)"


def _format_prices(price_dict):
    """심볼별 가격 딕셔너리를 포맷"""
    if not price_dict:
        return "(데이터 없음 / No data)"
    lines = []
    for symbol, prices in price_dict.items():
        lines.append(f"\n  [{symbol}]")
        for p in prices:
            lines.append(
                f"    {p['date']}: O={p['open']:,.1f} H={p['high']:,.1f} "
                f"L={p['low']:,.1f} C={p['close']:,.1f} V={p['volume']:,.0f}"
            )
    return "\n".join(lines)


def _format_prices_list(prices):
    """단순 리스트 포맷 (하위 호환)"""
    lines = []
    for p in prices:
        lines.append(
            f"  {p['date']}: O={p['open']:,.1f} H={p['high']:,.1f} "
            f"L={p['low']:,.1f} C={p['close']:,.1f} V={p['volume']:,.0f}"
        )
    return "\n".join(lines) if lines else "(데이터 없음)"


def _format_macro(macro_data):
    lines = []
    for m in macro_data:
        lines.append(f"  {m['indicator']} ({m['date']}): {m['value']} {m.get('unit','')}")
    return "\n".join(lines) if lines else "(데이터 없음 / No data)"


def _input_hash(*texts):
    combined = "".join(texts)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def run_prediction(news_kr, news_global, prices_all, macro_by_region,
                   db_path=None):
    if not anthropic:
        raise ImportError("anthropic 패키지를 설치하세요: pip install anthropic")
    if not CLAUDE_API_KEY:
        raise ValueError("CLAUDE_API_KEY를 설정하세요")

    news_kr_text = _format_news(news_kr)
    news_gl_text = _format_news(news_global)

    kr_symbols = {k: v for k, v in prices_all.items() if k in ("KOSPI",)}
    us_symbols = {k: v for k, v in prices_all.items()
                  if k in ("SP500", "NASDAQ", "DOW", "VIX", "DXY", "US10Y")}
    crypto_symbols = {k: v for k, v in prices_all.items() if k in ("BTC", "ETH")}
    commodity_symbols = {k: v for k, v in prices_all.items()
                         if k in ("GOLD", "WTI_OIL")}

    prices_kr_text = _format_prices(kr_symbols)
    prices_us_text = _format_prices({**us_symbols, **commodity_symbols})
    prices_crypto_text = _format_prices(crypto_symbols)

    macro_kr_text = _format_macro(macro_by_region.get("kr", []))
    macro_us_text = _format_macro(macro_by_region.get("us", []))
    macro_gl_text = _format_macro(macro_by_region.get("global", []))

    today = datetime.now()
    next_mon = today + timedelta(days=(7 - today.weekday()))
    next_fri = next_mon + timedelta(days=4)

    prompt = ANALYSIS_PROMPT.format(
        news_kr=news_kr_text,
        news_global=news_gl_text,
        prices_kr=prices_kr_text,
        prices_us=prices_us_text,
        prices_crypto=prices_crypto_text,
        macro_kr=macro_kr_text,
        macro_us=macro_us_text,
        macro_global=macro_gl_text,
        today=today.strftime("%Y-%m-%d"),
        target_start=next_mon.strftime("%Y-%m-%d"),
        target_end=next_fri.strftime("%Y-%m-%d"),
    )

    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    prediction = json.loads(raw_text)

    ihash = _input_hash(news_kr_text, news_gl_text,
                        prices_kr_text, prices_us_text, macro_kr_text)
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO predictions "
            "(created_at,target_date,prediction_json,model,input_hash) "
            "VALUES (?,?,?,?,?)",
            (today.isoformat(), next_fri.strftime("%Y-%m-%d"),
             json.dumps(prediction, ensure_ascii=False),
             CLAUDE_MODEL, ihash),
        )

    return prediction


def get_latest_prediction(db_path=None):
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM predictions ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if row:
        result = dict(row)
        result["prediction_json"] = json.loads(result["prediction_json"])
        return result
    return None
