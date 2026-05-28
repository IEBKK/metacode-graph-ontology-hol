"""거시지표 수집기 — ECOS (한국) + FRED (미국) + 글로벌"""
import requests
from datetime import datetime, timedelta
from market_prediction.config import ECOS_API_KEY, FRED_API_KEY
from market_prediction.utils.db import get_db

# --- 한국 (ECOS) ---

ECOS_BASE = "https://ecos.bok.or.kr/api/StatisticSearch"

KR_INDICATORS = {
    "USD_KRW": {"stat_code": "731Y001", "item_code": "0000001", "cycle": "D"},
    "KR_BASE_RATE": {"stat_code": "722Y001", "item_code": "0101000", "cycle": "M"},
    "KR_CPI": {"stat_code": "901Y009", "item_code": "0", "cycle": "M"},
}


def fetch_ecos_indicator(name, stat_code, item_code, cycle="D",
                          start_date=None, end_date=None):
    if not ECOS_API_KEY:
        print(f"[거시] ECOS_API_KEY 미설정 — {name} 건너뜀")
        return []

    end_date = end_date or datetime.now().strftime("%Y%m%d")
    if cycle == "D":
        start_date = start_date or (
            datetime.now().replace(day=1).strftime("%Y%m%d")
        )
    else:
        start_date = start_date or (
            datetime.now().replace(month=max(1, datetime.now().month - 3),
                                   day=1).strftime("%Y%m%d")
        )

    url = (
        f"{ECOS_BASE}/{ECOS_API_KEY}/json/kr/1/30/"
        f"{stat_code}/{cycle}/{start_date}/{end_date}/{item_code}"
    )

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("StatisticSearch", {}).get("row", [])
        results = []
        for row in rows:
            results.append({
                "indicator": name,
                "date": row.get("TIME", ""),
                "value": float(row.get("DATA_VALUE", 0)),
                "unit": row.get("UNIT_NAME", ""),
                "region": "KR",
            })
        return results
    except Exception as exc:
        print(f"[거시] {name} 수집 실패: {exc}")
        return []


def fetch_kr_macro():
    all_data = []
    for name, params in KR_INDICATORS.items():
        rows = fetch_ecos_indicator(name, **params)
        all_data.extend(rows)
    return all_data


# --- 미국 (FRED) ---

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

US_INDICATORS = {
    "US_FED_RATE": "FEDFUNDS",
    "US_CPI": "CPIAUCSL",
    "US_UNEMPLOYMENT": "UNRATE",
    "US_10Y_YIELD": "DGS10",
    "US_2Y_YIELD": "DGS2",
    "US_GDP_GROWTH": "A191RL1Q225SBEA",
    "US_PCE": "PCEPI",
    "US_INITIAL_CLAIMS": "ICSA",
}


def fetch_fred_indicator(name, series_id, limit=10):
    if not FRED_API_KEY:
        print(f"[거시] FRED_API_KEY 미설정 — {name} 건너뜀")
        return []

    try:
        params = {
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        }
        resp = requests.get(FRED_BASE, params=params, timeout=15)
        resp.raise_for_status()
        observations = resp.json().get("observations", [])

        results = []
        for obs in observations:
            val = obs.get("value", ".")
            if val == ".":
                continue
            results.append({
                "indicator": name,
                "date": obs["date"],
                "value": float(val),
                "unit": "",
                "region": "US",
            })
        return results
    except Exception as exc:
        print(f"[거시] {name} (FRED) 수집 실패: {exc}")
        return []


def fetch_us_macro():
    all_data = []
    for name, series_id in US_INDICATORS.items():
        rows = fetch_fred_indicator(name, series_id)
        all_data.extend(rows)
    return all_data


# --- 글로벌 간이 지표 (API 키 불필요) ---

def fetch_fear_greed_index():
    """CNN Fear & Greed 대용 — crypto fear/greed (무료)"""
    try:
        resp = requests.get(
            "https://api.alternative.me/fng/?limit=7", timeout=10
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        results = []
        for d in data:
            results.append({
                "indicator": "CRYPTO_FEAR_GREED",
                "date": datetime.fromtimestamp(int(d["timestamp"])).strftime("%Y-%m-%d"),
                "value": float(d["value"]),
                "unit": d["value_classification"],
                "region": "GLOBAL",
            })
        return results
    except Exception as exc:
        print(f"[거시] Fear&Greed 수집 실패: {exc}")
        return []


# --- 통합 ---

def fetch_all_macro():
    kr = fetch_kr_macro()
    us = fetch_us_macro()
    gl = fetch_fear_greed_index()
    print(f"[거시] 한국 {len(kr)}건, 미국 {len(us)}건, 글로벌 {len(gl)}건")
    return kr + us + gl


def save_macro(records, db_path=None):
    now = datetime.now().isoformat()
    saved = 0
    with get_db(db_path) as conn:
        for r in records:
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO macro "
                    "(indicator,date,value,unit,fetched_at) "
                    "VALUES (?,?,?,?,?)",
                    (r["indicator"], r["date"], r["value"],
                     r["unit"], now),
                )
                saved += 1
            except Exception as exc:
                print(f"[거시 저장] {exc}")
    return saved


def get_recent_macro(region=None, db_path=None):
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT indicator, date, value, unit FROM macro "
            "ORDER BY date DESC LIMIT 60"
        ).fetchall()
    results = [dict(r) for r in rows]
    if region:
        kr_names = set(KR_INDICATORS.keys())
        us_names = set(US_INDICATORS.keys())
        if region == "KR":
            results = [r for r in results if r["indicator"] in kr_names]
        elif region == "US":
            results = [r for r in results if r["indicator"] in us_names]
    return results


def get_macro_by_region(db_path=None):
    """한국/미국/글로벌로 분류해서 반환"""
    all_data = get_recent_macro(db_path=db_path)
    kr_names = set(KR_INDICATORS.keys())
    us_names = set(US_INDICATORS.keys())
    return {
        "kr": [d for d in all_data if d["indicator"] in kr_names],
        "us": [d for d in all_data if d["indicator"] in us_names],
        "global": [d for d in all_data
                    if d["indicator"] not in kr_names and d["indicator"] not in us_names],
    }


if __name__ == "__main__":
    from market_prediction.utils.db import init_db
    init_db()
    data = fetch_all_macro()
    n = save_macro(data)
    print(f"거시지표 {n}건 저장")
