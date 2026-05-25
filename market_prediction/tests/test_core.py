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
    "scenarios": [
        {
            "name": "상승",
            "probability": 0.45,
            "drivers": ["반도체 수출 호조", "외국인 순매수 전환"],
            "kospi_range": [2650, 2720],
            "btc_krw_range": [135000000, 142000000],
        },
        {
            "name": "횡보",
            "probability": 0.35,
            "drivers": ["미중 관세 불확실성", "금통위 대기"],
            "kospi_range": [2600, 2680],
            "btc_krw_range": [130000000, 138000000],
        },
        {
            "name": "하락",
            "probability": 0.20,
            "drivers": ["글로벌 경기 둔화 우려"],
            "kospi_range": [2550, 2620],
            "btc_krw_range": [125000000, 133000000],
        },
    ],
    "key_events": ["한국은행 금통위 (5/29)", "미국 PCE 발표 (5/30)"],
    "macro_outlook": {
        "usd_krw_direction": "횡보",
        "rate_outlook": "동결 전망",
    },
    "confidence": 0.55,
    "caveats": ["뉴스 데이터 제한적", "암호화폐 변동성 예측 한계"],
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
            {"source": "test", "title": "테스트 뉴스 2",
             "summary": "요약2", "published": "2025-01-02", "link": "http://b"},
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

    def test_price_save_and_retrieve(self):
        records = [
            {"market": "KRX", "symbol": "KOSPI", "date": "2025-01-01",
             "open": 2600, "high": 2650, "low": 2580, "close": 2640,
             "volume": 1000000},
        ]
        n = save_prices(records, self.db_path)
        self.assertEqual(n, 1)

        prices = get_recent_prices("KOSPI", db_path=self.db_path)
        self.assertEqual(len(prices), 1)
        self.assertEqual(prices[0]["close"], 2640)

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
    def test_report_generation(self):
        html = generate_report(SAMPLE_PREDICTION)
        self.assertIn("시장 예측 리포트", html)
        self.assertIn("상승", html)
        self.assertIn("하락", html)
        self.assertIn("횡보", html)
        self.assertIn("45%", html)
        self.assertIn("투자 권유가 아닙니다", html)

    def test_report_file_output(self):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            generate_report(SAMPLE_PREDICTION, output_path=path)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertGreater(len(content), 1000)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
