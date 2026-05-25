"""가격 수집기 — KRX + 빗썸 + 미국 시장 (yfinance/Yahoo)"""
import requests
from datetime import datetime, timedelta
from market_prediction.config import BITHUMB_API_URL
from market_prediction.utils.db import get_db

try:
    from pykrx import stock as krx
except ImportError:
    krx = None

try:
    import yfinance as yf
except ImportError:
    yf = None


# --- 한국 시장 ---

def fetch_kospi_ohlcv(days=7):
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


# --- 암호화폐 ---

def fetch_bithumb_ticker(coin="BTC"):
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


# --- 미국 시장 (yfinance) ---

US_SYMBOLS = {
    "^GSPC": "SP500",
    "^IXIC": "NASDAQ",
    "^DJI": "DOW",
    "^VIX": "VIX",
    "DX-Y.NYB": "DXY",
    "GC=F": "GOLD",
    "CL=F": "WTI_OIL",
    "^TNX": "US10Y",
}


def fetch_us_market(days=7):
    if not yf:
        return _fetch_us_market_fallback(days)

    records = []
    end = datetime.now()
    start = end - timedelta(days=days + 5)

    for ticker, symbol in US_SYMBOLS.items():
        try:
            data = yf.download(ticker, start=start, end=end,
                               progress=False, auto_adjust=True)
            if data.empty:
                continue
            for date, row in data.tail(days).iterrows():
                records.append({
                    "market": "US",
                    "symbol": symbol,
                    "date": date.strftime("%Y-%m-%d"),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row.get("Volume", 0)),
                })
        except Exception as exc:
            print(f"[가격] {symbol} 수집 실패: {exc}")

    return records


def _fetch_us_market_fallback(days=7):
    """yfinance 없을 때 Yahoo Finance chart API 직접 호출"""
    records = []
    for ticker, symbol in US_SYMBOLS.items():
        try:
            url = (
                f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
                f"?range={days + 3}d&interval=1d"
            )
            resp = requests.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0"
            })
            resp.raise_for_status()
            result = resp.json()["chart"]["result"][0]
            timestamps = result["timestamp"]
            quotes = result["indicators"]["quote"][0]

            for i in range(max(0, len(timestamps) - days), len(timestamps)):
                records.append({
                    "market": "US",
                    "symbol": symbol,
                    "date": datetime.fromtimestamp(timestamps[i]).strftime("%Y-%m-%d"),
                    "open": float(quotes["open"][i] or 0),
                    "high": float(quotes["high"][i] or 0),
                    "low": float(quotes["low"][i] or 0),
                    "close": float(quotes["close"][i] or 0),
                    "volume": float(quotes.get("volume", [0] * len(timestamps))[i] or 0),
                })
        except Exception as exc:
            print(f"[가격] {symbol} 폴백 수집 실패: {exc}")

    return records


# --- 저장/조회 ---

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


def get_all_recent_prices(days=7, db_path=None):
    """모든 심볼의 최근 가격을 딕셔너리로 반환"""
    symbols = ["KOSPI", "BTC", "ETH", "SP500", "NASDAQ", "DOW",
               "VIX", "DXY", "GOLD", "WTI_OIL", "US10Y"]
    result = {}
    for sym in symbols:
        prices = get_recent_prices(sym, days, db_path)
        if prices:
            result[sym] = prices
    return result


if __name__ == "__main__":
    from market_prediction.utils.db import init_db
    init_db()

    kospi = fetch_kospi_ohlcv()
    btc = fetch_bithumb_candlestick("BTC")
    us = fetch_us_market()
    n = save_prices(kospi + btc + us)
    print(f"가격 {n}건 저장 (한국 {len(kospi)}, 암호화폐 {len(btc)}, 미국 {len(us)})")
