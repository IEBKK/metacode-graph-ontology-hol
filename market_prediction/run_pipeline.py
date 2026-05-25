#!/usr/bin/env python3
"""
주간 예측 파이프라인 — 단독 실행 스크립트
Pythonista에서도, 서버에서도, 로컬에서도 동작.

사용법:
  python -m market_prediction.run_pipeline          # 전체 실행
  python -m market_prediction.run_pipeline --collect  # 수집만
  python -m market_prediction.run_pipeline --predict  # 분석만 (캐시 데이터 사용)
  python -m market_prediction.run_pipeline --score 1  # 예측 ID 1번 채점
"""
import argparse
import json
import sys
from datetime import datetime

from market_prediction.utils.db import init_db
from market_prediction.collectors.news import fetch_news, save_news, get_recent_headlines
from market_prediction.collectors.price import (
    fetch_kospi_ohlcv, fetch_bithumb_candlestick,
    save_prices, get_recent_prices,
)
from market_prediction.collectors.macro import fetch_all_macro, save_macro, get_recent_macro
from market_prediction.analysis.predictor import run_prediction, get_latest_prediction
from market_prediction.analysis.backtest import score_prediction, average_accuracy
from market_prediction.ui.html_report import generate_report


def collect():
    print(f"[{datetime.now():%H:%M}] 데이터 수집 시작")

    news = fetch_news()
    n_news = save_news(news)
    print(f"  뉴스: {n_news}건")

    kospi = fetch_kospi_ohlcv()
    btc = fetch_bithumb_candlestick("BTC")
    eth = fetch_bithumb_candlestick("ETH")
    n_price = save_prices(kospi + btc + eth)
    print(f"  가격: {n_price}건")

    macro = fetch_all_macro()
    n_macro = save_macro(macro)
    print(f"  거시: {n_macro}건")

    return n_news + n_price + n_macro


def predict():
    print(f"[{datetime.now():%H:%M}] AI 분석 시작")

    headlines = get_recent_headlines()
    prices_kospi = get_recent_prices("KOSPI")
    prices_btc = get_recent_prices("BTC")
    macro_data = get_recent_macro()

    if not headlines and not prices_kospi and not prices_btc:
        print("  데이터가 없습니다. --collect를 먼저 실행하세요.")
        return None

    prediction = run_prediction(headlines, prices_kospi, prices_btc, macro_data)

    report_path = f"report_{datetime.now():%Y%m%d_%H%M}.html"
    generate_report(prediction, output_path=report_path)
    print(f"  리포트 저장: {report_path}")

    print("\n=== 예측 요약 ===")
    for s in prediction.get("scenarios", []):
        print(f"  {s['name']}: {s['probability']*100:.0f}%")
    print(f"  신뢰도: {prediction.get('confidence', 0)*100:.0f}%")
    print(f"  주의: {', '.join(prediction.get('caveats', []))}")

    return prediction


def score(prediction_id, kospi_close, btc_close):
    result = score_prediction(prediction_id, kospi_close, btc_close)
    if result:
        print(f"  점수: {result['score']:.1%}")
        avg = average_accuracy()
        print(f"  평균 정확도: {avg:.1%}")
    return result


def main():
    parser = argparse.ArgumentParser(description="시장 예측 파이프라인")
    parser.add_argument("--collect", action="store_true", help="데이터 수집만")
    parser.add_argument("--predict", action="store_true", help="AI 분석만")
    parser.add_argument("--score", type=int, help="예측 채점 (prediction_id)")
    parser.add_argument("--kospi", type=float, help="실제 KOSPI 종가 (채점용)")
    parser.add_argument("--btc", type=float, help="실제 BTC 종가 (채점용)")
    parser.add_argument("--report", action="store_true", help="최신 예측 리포트 재생성")
    args = parser.parse_args()

    init_db()

    if args.score:
        if not args.kospi or not args.btc:
            print("채점에는 --kospi와 --btc가 필요합니다")
            sys.exit(1)
        score(args.score, args.kospi, args.btc)
    elif args.collect:
        collect()
    elif args.predict:
        predict()
    elif args.report:
        latest = get_latest_prediction()
        if latest:
            path = f"report_{datetime.now():%Y%m%d_%H%M}.html"
            generate_report(latest["prediction_json"], output_path=path)
            print(f"리포트 생성: {path}")
        else:
            print("저장된 예측이 없습니다.")
    else:
        collect()
        predict()


if __name__ == "__main__":
    main()
