"""가격 수집기 — KRX(pykrx) + 빗썸 API"""
import requests
from datetime import datetime, timedelta
from market_prediction.config import BITHUMB_API_URL
from market_prediction.utils.db import get_db

try:
    from pykrx import stock as krx
except ImportError:
    krx = None


def fetch_kospi_ohlcv(days=7):
    """pykrx로 KOSPI 지수 OHLCV 수집"""
    if not krx:
        print("[가격] pykrx 미설치 — KOSPI 수집 건너뜀")
        return []

    end = datetime.now()
    start = end - timedelta(days=days + 5)
    fmt = "%Y%m%d"

    try:
        df = krx.get_index_ohlcv(start.strftime(fmt), end.strftime(fmt), "1001")
        records = []
        for date, row in df.tail(days).iterrows():
            records.append({
                "market": "KRX",
                "symbol": "KOSPI",
                "date": date.strftime("%Y-%m-%d"),
                "open": float(row["시가"]),
                "high": float(row["고가"]),
                "low": float(row["저가"]),
                "close": float(row["종가"]),
                "volume": float(row["거래량"]),
            })
        return records
    except Exception as exc:
        print(f"[가격] KOSPI 수집 실패: {exc}")
        return []


def fetch_bithumb_ticker(coin="BTC"):
    """빗썸 Public API — 실시간 시세"""
    try:
        url = f"{BITHUMB_API_URL}/ticker/{coin}_KRW"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return {
            "market": "Bithumb",
            "symbol": coin,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "open": float(data.get("opening_price", 0)),
            "high": float(data.get("max_price", 0)),
            "low": float(data.get("min_price", 0)),
            "close": float(data.get("closing_price", 0)),
            "volume": float(data.get("units_traded_24H", 0)),
        }
    except Exception as exc:
        print(f"[가격] 빗썸 {coin} 수집 실패: {exc}")
        return None


def fetch_bithumb_candlestick(coin="BTC", interval="24h"):
    """빗썸 캔들스틱 API — 최근 7일"""
    try:
        url = f"{BITHUMB_API_URL}/candlestick/{coin}_KRW/{interval}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        raw = resp.json().get("data", [])
        records = []
        for candle in raw[-7:]:
            ts, o, c, h, l, vol = candle
            records.append({
                "market": "Bithumb",
                "symbol": coin,
                "date": datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d"),
                "open": float(o), "high": float(h),
                "low": float(l), "close": float(c),
                "volume": float(vol),
            })
        return records
    except Exception as exc:
        print(f"[가격] 빗썸 캔들 수집 실패: {exc}")
        return []


def save_prices(records, db_path=None):
    now = datetime.now().isoformat()
    saved = 0
    with get_db(db_path) as conn:
        for r in records:
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO prices "
                    "(market,symbol,date,open,high,low,close,volume,fetched_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (r["market"], r["symbol"], r["date"],
                     r["open"], r["high"], r["low"], r["close"],
                     r["volume"], now),
                )
                saved += 1
            except Exception as exc:
                print(f"[가격 저장] {exc}")
    return saved


def get_recent_prices(symbol="KOSPI", days=7, db_path=None):
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT date, open, high, low, close, volume FROM prices "
            "WHERE symbol=? ORDER BY date DESC LIMIT ?",
            (symbol, days),
        ).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    from market_prediction.utils.db import init_db
    init_db()

    kospi = fetch_kospi_ohlcv()
    btc = fetch_bithumb_candlestick("BTC")
    n = save_prices(kospi + btc)
    print(f"가격 {n}건 저장")
