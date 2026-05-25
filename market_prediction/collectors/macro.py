"""거시지표 수집기 — ECOS API (한국은행 경제통계시스템)"""
import requests
from datetime import datetime
from market_prediction.config import ECOS_API_KEY
from market_prediction.utils.db import get_db

ECOS_BASE = "https://ecos.bok.or.kr/api/StatisticSearch"

INDICATORS = {
    "USD_KRW": {"stat_code": "731Y001", "item_code": "0000001", "cycle": "D"},
    "BASE_RATE": {"stat_code": "722Y001", "item_code": "0101000", "cycle": "M"},
    "CPI": {"stat_code": "901Y009", "item_code": "0", "cycle": "M"},
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
            })
        return results
    except Exception as exc:
        print(f"[거시] {name} 수집 실패: {exc}")
        return []


def fetch_all_macro():
    all_data = []
    for name, params in INDICATORS.items():
        rows = fetch_ecos_indicator(name, **params)
        all_data.extend(rows)
    return all_data


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


def get_recent_macro(db_path=None):
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT indicator, date, value, unit FROM macro "
            "ORDER BY date DESC LIMIT 30"
        ).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    from market_prediction.utils.db import init_db
    init_db()
    data = fetch_all_macro()
    n = save_macro(data)
    print(f"거시지표 {n}건 저장")
