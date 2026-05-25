"""Claude API 기반 시장 예측 엔진"""
import json
import hashlib
from datetime import datetime, timedelta
from market_prediction.config import CLAUDE_API_KEY, CLAUDE_MODEL
from market_prediction.utils.db import get_db

try:
    import anthropic
except ImportError:
    anthropic = None

SYSTEM_PROMPT = """당신은 한국 금융시장을 분석하는 전문 애널리스트입니다.
데이터에 기반한 냉정하고 객관적인 분석을 제공합니다.
확실하지 않은 것은 확실하지 않다고 명시합니다.
절대 투자 권유를 하지 않으며, 시나리오 기반 확률 분석만 제공합니다."""

ANALYSIS_PROMPT = """아래 데이터를 기반으로 다음 주 한국 금융시장을 분석하세요.

[최근 뉴스 헤드라인]
{news}

[최근 가격 데이터 (OHLCV)]
{prices}

[거시경제 지표]
{macro}

다음 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만:
{{
  "analysis_date": "{today}",
  "target_period": "{target_start} ~ {target_end}",
  "scenarios": [
    {{
      "name": "상승",
      "probability": 0.0,
      "drivers": ["근거1", "근거2"],
      "kospi_range": [0, 0],
      "btc_krw_range": [0, 0]
    }},
    {{
      "name": "횡보",
      "probability": 0.0,
      "drivers": ["근거1", "근거2"],
      "kospi_range": [0, 0],
      "btc_krw_range": [0, 0]
    }},
    {{
      "name": "하락",
      "probability": 0.0,
      "drivers": ["근거1", "근거2"],
      "kospi_range": [0, 0],
      "btc_krw_range": [0, 0]
    }}
  ],
  "key_events": ["다음주 주목할 이벤트 1", "이벤트 2"],
  "macro_outlook": {{
    "usd_krw_direction": "상승/하락/횡보",
    "rate_outlook": "동결/인상/인하 전망"
  }},
  "confidence": 0.0,
  "caveats": ["모델 한계 1", "불확실성 요인 2"]
}}

규칙:
- scenarios의 probability 합 = 1.0
- confidence는 데이터 충분성과 시장 불확실성을 반영 (0.0~1.0)
- caveats에는 이 분석의 한계를 솔직히 기술
- 근거는 제공된 데이터에서만 도출"""


def _format_news(headlines):
    lines = []
    for h in headlines[:30]:
        lines.append(f"- [{h.get('source','')}] {h['title']}")
    return "\n".join(lines) if lines else "(뉴스 데이터 없음)"


def _format_prices(prices):
    lines = []
    for p in prices:
        lines.append(
            f"  {p['date']}: O={p['open']} H={p['high']} "
            f"L={p['low']} C={p['close']} V={p['volume']}"
        )
    return "\n".join(lines) if lines else "(가격 데이터 없음)"


def _format_macro(macro_data):
    lines = []
    for m in macro_data:
        lines.append(f"  {m['indicator']} ({m['date']}): {m['value']} {m.get('unit','')}")
    return "\n".join(lines) if lines else "(거시지표 데이터 없음)"


def _input_hash(news_text, prices_text, macro_text):
    combined = f"{news_text}{prices_text}{macro_text}"
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def run_prediction(headlines, prices_kospi, prices_btc, macro_data,
                   db_path=None):
    if not anthropic:
        raise ImportError("anthropic 패키지를 설치하세요: pip install anthropic")
    if not CLAUDE_API_KEY:
        raise ValueError("CLAUDE_API_KEY를 설정하세요")

    news_text = _format_news(headlines)
    prices_text = "KOSPI:\n" + _format_prices(prices_kospi)
    prices_text += "\nBTC/KRW:\n" + _format_prices(prices_btc)
    macro_text = _format_macro(macro_data)

    today = datetime.now()
    next_mon = today + timedelta(days=(7 - today.weekday()))
    next_fri = next_mon + timedelta(days=4)

    prompt = ANALYSIS_PROMPT.format(
        news=news_text,
        prices=prices_text,
        macro=macro_text,
        today=today.strftime("%Y-%m-%d"),
        target_start=next_mon.strftime("%Y-%m-%d"),
        target_end=next_fri.strftime("%Y-%m-%d"),
    )

    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=3000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    prediction = json.loads(raw_text)

    ihash = _input_hash(news_text, prices_text, macro_text)
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
