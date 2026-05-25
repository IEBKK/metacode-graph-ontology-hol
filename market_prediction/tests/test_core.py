"""오프라인 단위 테스트 — API 호출 없이 DB/포맷/리포트 검증"""
import json
import os
import tempfile
import unittest
from datetime import datetime

from market_prediction.utils.db import init_db, get_db
from market_prediction.collectors.news import save_news, get_recent_headlines
from market_prediction.collectors.price import save_prices, get_recent_prices
from market_prediction.analysis.backtest import score_prediction, average_accuracy
from market_prediction.ui.html_report import generate_report


SAMPLE_PREDICTION = {
    "analysis_date": "2025-05-25",
    "target_period": "2025-05-26 ~ 2025-05-30",
    "korea": {
        "scenarios": [
            {
                "name": "상승", "probability": 0.45,
                "drivers": ["반도체 수출 호조", "외국인 순매수 전환"],
                "kospi_range": [2650, 2720],
            },
            {
                "name": "횡보", "probability": 0.35,
                "drivers": ["미중 관세 불확실성"],
                "kospi_range": [2600, 2680],
            },
            {
                "name": "하락", "probability": 0.20,
                "drivers": ["글로벌 경기 둔화 우려"],
                "kospi_range": [2550, 2620],
            },
        ],
        "usd_krw_direction": "횡보",
        "kr_rate_outlook": "동결",
    },
    "us": {
        "scenarios": [
            {
                "name": "Bullish", "probability": 0.40,
                "drivers": ["Strong earnings", "AI momentum"],
                "sp500_range": [5350, 5450],
            },
            {
                "name": "Neutral", "probability": 0.35,
                "drivers": ["Mixed economic data"],
                "sp500_range": [5250, 5380],
            },
            {
                "name": "Bearish", "probability": 0.25,
                "drivers": ["Rate uncertainty", "Geopolitical tension"],
                "sp500_range": [5150, 5280],
            },
        ],
        "fed_outlook": "hold",
        "dxy_direction": "flat",
        "vix_level": "moderate",
    },
    "crypto": {
        "btc_scenario": "bullish",
        "btc_krw_range": [135000000, 142000000],
        "drivers": ["Institutional inflows", "ETF momentum"],
    },
    "cross_market": {
        "us_to_kr_impact": "미국 금리 동결 기대감이 한국 외국인 자금 유입에 긍정적",
        "global_risk_factors": ["미중 무역 갈등", "중동 지정학 리스크", "일본 엔화 약세"],
        "correlation_notes": "S&P500과 KOSPI 상관계수 0.7 이상 유지 중",
    },
    "key_events": [
        {"date": "5/27", "event": "US Consumer Confidence", "market": "US", "impact": "medium"},
        {"date": "5/28", "event": "NVIDIA Earnings", "market": "US", "impact": "high"},
        {"date": "5/29", "event": "한국은행 금통위", "market": "KR", "impact": "high"},
        {"date": "5/30", "event": "US PCE Data", "market": "US", "impact": "high"},
    ],
    "commodities": {
        "oil_direction": "flat",
        "gold_direction": "up",
        "notes": "금은 안전자산 수요로 강세, 유가는 OPEC 감산 vs 수요 둔화로 횡보",
    },
    "confidence": 0.55,
    "caveats": [
        "뉴스 데이터 제한적",
        "US-KR market hours gap may cause delayed reactions",
        "암호화폐 변동성 예측 한계",
    ],
}


class TestDB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        init_db(self.db_path)

    def tearDown(self):
        os.unlink(self.db_path)

    def test_news_save_and_retrieve(self):
        items = [
            {"source": "test", "title": "테스트 뉴스 1",
             "summary": "요약", "published": "2025-01-01", "link": "http://a"},
            {"source": "reuters", "title": "Fed holds rates steady",
             "summary": "summary", "published": "2025-01-01", "link": "http://b"},
        ]
        n = save_news(items, self.db_path)
        self.assertEqual(n, 2)
        headlines = get_recent_headlines(db_path=self.db_path)
        self.assertEqual(len(headlines), 2)

    def test_news_dedup(self):
        items = [
            {"source": "test", "title": "중복 테스트",
             "summary": "", "published": "", "link": "http://dup"},
        ]
        save_news(items, self.db_path)
        save_news(items, self.db_path)
        headlines = get_recent_headlines(db_path=self.db_path)
        self.assertEqual(len(headlines), 1)

    def test_price_save_kr_and_us(self):
        records = [
            {"market": "KRX", "symbol": "KOSPI", "date": "2025-01-01",
             "open": 2600, "high": 2650, "low": 2580, "close": 2640, "volume": 1000000},
            {"market": "US", "symbol": "SP500", "date": "2025-01-01",
             "open": 5300, "high": 5380, "low": 5280, "close": 5350, "volume": 3000000000},
            {"market": "US", "symbol": "NASDAQ", "date": "2025-01-01",
             "open": 16800, "high": 16950, "low": 16750, "close": 16900, "volume": 5000000000},
        ]
        n = save_prices(records, self.db_path)
        self.assertEqual(n, 3)
        kospi = get_recent_prices("KOSPI", db_path=self.db_path)
        sp500 = get_recent_prices("SP500", db_path=self.db_path)
        self.assertEqual(len(kospi), 1)
        self.assertEqual(len(sp500), 1)
        self.assertEqual(sp500[0]["close"], 5350)

    def test_prediction_and_scoring(self):
        with get_db(self.db_path) as conn:
            conn.execute(
                "INSERT INTO predictions "
                "(created_at,target_date,prediction_json,model,input_hash) "
                "VALUES (?,?,?,?,?)",
                (datetime.now().isoformat(), "2025-01-10",
                 json.dumps(SAMPLE_PREDICTION), "test", "abc123"),
            )
            pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        result = score_prediction(pid, 2670, 137000000, self.db_path)
        self.assertIsNotNone(result)
        self.assertIn("score", result)
        self.assertGreaterEqual(result["score"], 0.0)
        self.assertLessEqual(result["score"], 1.0)

    def test_average_accuracy_empty(self):
        avg = average_accuracy(db_path=self.db_path)
        self.assertEqual(avg, 0.0)


class TestHTMLReport(unittest.TestCase):
    def test_global_report_generation(self):
        html = generate_report(SAMPLE_PREDICTION)
        self.assertIn("Global Market Forecast", html)
        self.assertIn("한국 시장", html)
        self.assertIn("US Market", html)
        self.assertIn("상승", html)
        self.assertIn("Bullish", html)
        self.assertIn("Bearish", html)
        self.assertIn("Cross-Market", html)
        self.assertIn("NVIDIA", html)
        self.assertIn("투자 권유가 아닙니다", html)
        self.assertIn("not investment advice", html)

    def test_report_file_output(self):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            generate_report(SAMPLE_PREDICTION, output_path=path)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertGreater(len(content), 2000)
        finally:
            os.unlink(path)

    def test_report_confidence_colors(self):
        high_conf = {**SAMPLE_PREDICTION, "confidence": 0.8}
        html_high = generate_report(high_conf)
        self.assertIn("#4caf50", html_high)

        low_conf = {**SAMPLE_PREDICTION, "confidence": 0.2}
        html_low = generate_report(low_conf)
        self.assertIn("#ef5350", html_low)


if __name__ == "__main__":
    unittest.main()
