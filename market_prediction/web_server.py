"""
경량 웹 서버 — 지인 베타 배포용
Render/Replit 무료 티어에 올려서 URL만 공유.

사용법:
  python -m market_prediction.web_server
  # http://localhost:8080 접속
"""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

from market_prediction.utils.db import init_db
from market_prediction.analysis.predictor import get_latest_prediction
from market_prediction.analysis.backtest import get_score_history
from market_prediction.ui.html_report import generate_report
from market_prediction.config import DISCLAIMER


class PredictionHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/report":
            self._serve_report()
        elif self.path == "/api/prediction":
            self._serve_json()
        elif self.path == "/api/scores":
            self._serve_scores()
        elif self.path == "/health":
            self._respond(200, "application/json", '{"status":"ok"}')
        else:
            self._respond(404, "text/plain", "Not Found")

    def _serve_report(self):
        latest = get_latest_prediction()
        if latest:
            html = generate_report(latest["prediction_json"])
            self._respond(200, "text/html; charset=utf-8", html)
        else:
            self._respond(200, "text/html; charset=utf-8",
                          "<h1>아직 예측 결과가 없습니다</h1>"
                          "<p>파이프라인을 먼저 실행하세요.</p>")

    def _serve_json(self):
        latest = get_latest_prediction()
        if latest:
            data = {
                "prediction": latest["prediction_json"],
                "created_at": latest["created_at"],
                "model": latest["model"],
                "disclaimer": DISCLAIMER,
            }
            self._respond(200, "application/json",
                          json.dumps(data, ensure_ascii=False))
        else:
            self._respond(404, "application/json",
                          '{"error":"no predictions yet"}')

    def _serve_scores(self):
        scores = get_score_history()
        self._respond(200, "application/json",
                      json.dumps(scores, ensure_ascii=False, default=str))

    def _respond(self, code, content_type, body):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format, *args):
        print(f"[{datetime.now():%H:%M:%S}] {args[0]}")


def run(port=8080):
    init_db()
    server = HTTPServer(("0.0.0.0", port), PredictionHandler)
    print(f"서버 시작: http://localhost:{port}")
    print(f"  리포트: http://localhost:{port}/report")
    print(f"  API:    http://localhost:{port}/api/prediction")
    server.serve_forever()


if __name__ == "__main__":
    run()
