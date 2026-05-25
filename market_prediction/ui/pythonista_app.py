"""
Pythonista 3 네이티브 UI — iPad mini 전용
이 파일은 Pythonista 앱 내에서 직접 실행합니다.
일반 Python 환경에서는 html_report.py를 사용하세요.
"""

try:
    import ui
    import webbrowser
    PYTHONISTA = True
except ImportError:
    PYTHONISTA = False

import os
import sys
import json
import tempfile


def show_report_in_webview(html_content):
    """Pythonista WebView로 HTML 리포트 표시"""
    if not PYTHONISTA:
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w")
        tmp.write(html_content)
        tmp.close()
        print(f"리포트 저장: {tmp.name}")
        return

    wv = ui.WebView()
    wv.name = "시장 예측 리포트"
    wv.load_html(html_content)
    wv.present("fullscreen")


def run_full_pipeline():
    """전체 파이프라인 실행: 수집 → 분석 → UI 표시"""
    from market_prediction.utils.db import init_db
    from market_prediction.collectors.news import fetch_news, save_news, get_recent_headlines
    from market_prediction.collectors.price import (
        fetch_kospi_ohlcv, fetch_bithumb_candlestick,
        save_prices, get_recent_prices,
    )
    from market_prediction.collectors.macro import fetch_all_macro, save_macro, get_recent_macro
    from market_prediction.analysis.predictor import run_prediction
    from market_prediction.ui.html_report import generate_report

    print("DB 초기화...")
    init_db()

    print("뉴스 수집 중...")
    news = fetch_news()
    save_news(news)
    headlines = get_recent_headlines()

    print("가격 수집 중...")
    kospi = fetch_kospi_ohlcv()
    btc = fetch_bithumb_candlestick("BTC")
    save_prices(kospi + btc)
    prices_kospi = get_recent_prices("KOSPI")
    prices_btc = get_recent_prices("BTC")

    print("거시지표 수집 중...")
    macro = fetch_all_macro()
    save_macro(macro)
    macro_data = get_recent_macro()

    print("AI 분석 중... (Claude API 호출)")
    prediction = run_prediction(headlines, prices_kospi, prices_btc, macro_data)

    print("리포트 생성 중...")
    html = generate_report(prediction, output_path="report.html")

    print("완료!")
    show_report_in_webview(html)
    return prediction


if __name__ == "__main__":
    run_full_pipeline()
