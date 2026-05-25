#!/usr/bin/env python3
"""
글로벌 시장 예측 파이프라인 — 한국 + 미국 + 국제

사용법:
  python -m market_prediction.run_pipeline          # 전체 실행
  python -m market_prediction.run_pipeline --collect  # 수집만
  python -m market_prediction.run_pipeline --predict  # 분석만 (캐시 데이터 사용)
  python -m market_prediction.run_pipeline --score 1 --kospi 2700 --sp500 5400 --btc 140000000
"""
import argparse
import json
import sys
from datetime import datetime

from market_prediction.utils.db import init_db
from market_prediction.collectors.news import (
    fetch_news_kr, fetch_news_global, save_news,
    get_recent_headlines, get_headlines_by_source_type,
)
from market_prediction.collectors.price import (
    fetch_kospi_ohlcv, fetch_bithumb_candlestick, fetch_us_market,
    save_prices, get_all_recent_prices,
)
from market_prediction.collectors.macro import (
    fetch_all_macro, save_macro, get_macro_by_region,
)
from market_prediction.analysis.predictor import run_prediction, get_latest_prediction
from market_prediction.analysis.backtest import score_prediction, average_accuracy
from market_prediction.ui.html_report import generate_report


def collect():
    print(f"[{datetime.now():%H:%M}] === 데이터 수집 시작 ===")

    print("  한국 뉴스 수집...")
    kr_news = fetch_news_kr()
    print("  글로벌 뉴스 수집...")
    gl_news = fetch_news_global()
    n_news = save_news(kr_news + gl_news)
    print(f"  뉴스: KR {len(kr_news)} + Global {len(gl_news)} = 저장 {n_news}건")

    print("  한국 가격 수집...")
    kospi = fetch_kospi_ohlcv()
    print("  암호화폐 수집...")
    btc = fetch_bithumb_candlestick("BTC")
    eth = fetch_bithumb_candlestick("ETH")
    print("  미국 시장 수집...")
    us = fetch_us_market()
    n_price = save_prices(kospi + btc + eth + us)
    print(f"  가격: KR {len(kospi)}, Crypto {len(btc)+len(eth)}, US {len(us)} = 저장 {n_price}건")

    print("  거시지표 수집 (한국+미국+글로벌)...")
    macro = fetch_all_macro()
    n_macro = save_macro(macro)
    print(f"  거시: {n_macro}건")

    total = n_news + n_price + n_macro
    print(f"  총 {total}건 수집 완료")
    return total


def predict():
    print(f"[{datetime.now():%H:%M}] === AI 글로벌 분석 시작 ===")

    news_by_type = get_headlines_by_source_type()
    prices_all = get_all_recent_prices()
    macro_by_region = get_macro_by_region()

    if not any(news_by_type.values()) and not prices_all:
        print("  데이터가 없습니다. --collect를 먼저 실행하세요.")
        return None

    print(f"  입력: 뉴스 KR={len(news_by_type.get('kr',[]))} "
          f"Global={len(news_by_type.get('global',[]))}, "
          f"가격 {len(prices_all)}개 심볼")

    prediction = run_prediction(
        news_kr=news_by_type.get("kr", []),
        news_global=news_by_type.get("global", []),
        prices_all=prices_all,
        macro_by_region=macro_by_region,
    )

    report_path = f"report_{datetime.now():%Y%m%d_%H%M}.html"
    generate_report(prediction, output_path=report_path)
    print(f"  리포트 저장: {report_path}")

    print("\n=== 예측 요약 ===")
    kr = prediction.get("korea", {})
    us = prediction.get("us", {})
    print("  [한국 KOSPI]")
    for s in kr.get("scenarios", []):
        print(f"    {s['name']}: {s['probability']*100:.0f}%  "
              f"범위 {s.get('kospi_range', [])}")
    print(f"    원/달러: {kr.get('usd_krw_direction', '-')}")

    print("  [미국 S&P500]")
    for s in us.get("scenarios", []):
        print(f"    {s['name']}: {s['probability']*100:.0f}%  "
              f"Range {s.get('sp500_range', [])}")
    print(f"    Fed: {us.get('fed_outlook', '-')} | VIX: {us.get('vix_level', '-')}")

    crypto = prediction.get("crypto", {})
    print(f"  [BTC] {crypto.get('btc_scenario', '-')}")

    print(f"\n  신뢰도: {prediction.get('confidence', 0)*100:.0f}%")
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
    parser = argparse.ArgumentParser(description="글로벌 시장 예측 파이프라인")
    parser.add_argument("--collect", action="store_true", help="데이터 수집만")
    parser.add_argument("--predict", action="store_true", help="AI 분석만")
    parser.add_argument("--score", type=int, help="예측 채점 (prediction_id)")
    parser.add_argument("--kospi", type=float, help="실제 KOSPI 종가")
    parser.add_argument("--btc", type=float, help="실제 BTC 종가")
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
