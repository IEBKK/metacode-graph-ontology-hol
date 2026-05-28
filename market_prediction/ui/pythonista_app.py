"""
Pythonista 3 앱 — iPad mini 전용
전체 파이프라인 실행: 한국+미국+국제 데이터 수집 → Claude 분석 → 리포트
"""

try:
    import ui
    PYTHONISTA = True
except ImportError:
    PYTHONISTA = False

import tempfile


def show_report_in_webview(html_content):
    if not PYTHONISTA:
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w")
        tmp.write(html_content)
        tmp.close()
        print(f"리포트 저장: {tmp.name}")
        return

    wv = ui.WebView()
    wv.name = "Global Market Forecast"
    wv.load_html(html_content)
    wv.present("fullscreen")


def run_full_pipeline():
    from market_prediction.utils.db import init_db
    from market_prediction.collectors.news import (
        fetch_news_kr, fetch_news_global, save_news, get_headlines_by_source_type,
    )
    from market_prediction.collectors.price import (
        fetch_kospi_ohlcv, fetch_bithumb_candlestick, fetch_us_market,
        save_prices, get_all_recent_prices,
    )
    from market_prediction.collectors.macro import (
        fetch_all_macro, save_macro, get_macro_by_region,
    )
    from market_prediction.analysis.predictor import run_prediction
    from market_prediction.ui.html_report import generate_report

    print("DB 초기화...")
    init_db()

    print("한국 뉴스 수집...")
    kr_news = fetch_news_kr()
    print("글로벌 뉴스 수집...")
    gl_news = fetch_news_global()
    save_news(kr_news + gl_news)

    print("한국 가격 수집...")
    kospi = fetch_kospi_ohlcv()
    print("암호화폐 수집...")
    btc = fetch_bithumb_candlestick("BTC")
    eth = fetch_bithumb_candlestick("ETH")
    print("미국 시장 수집...")
    us = fetch_us_market()
    save_prices(kospi + btc + eth + us)

    print("거시지표 수집 (한국+미국+글로벌)...")
    macro = fetch_all_macro()
    save_macro(macro)

    news_by_type = get_headlines_by_source_type()
    prices_all = get_all_recent_prices()
    macro_by_region = get_macro_by_region()

    print("AI 글로벌 분석 중... (Claude API)")
    prediction = run_prediction(
        news_kr=news_by_type.get("kr", []),
        news_global=news_by_type.get("global", []),
        prices_all=prices_all,
        macro_by_region=macro_by_region,
    )

    print("리포트 생성...")
    html = generate_report(prediction, output_path="report.html")

    print("완료!")
    show_report_in_webview(html)
    return prediction


if __name__ == "__main__":
    run_full_pipeline()
