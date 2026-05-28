"""백테스트 모듈 — 글로벌 예측 정확도 자동 평가"""
import json
from datetime import datetime
from market_prediction.utils.db import get_db


def score_prediction(prediction_id, actual_kospi_close, actual_btc_close,
                     db_path=None, actual_sp500_close=None):
    """저장된 예측과 실제 결과를 비교해 점수 산출"""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM predictions WHERE id=?", (prediction_id,)
        ).fetchone()

    if not row:
        return None

    pred = json.loads(row["prediction_json"])

    kr_scenarios = pred.get("korea", {}).get("scenarios", [])
    if not kr_scenarios:
        kr_scenarios = pred.get("scenarios", [])

    us_scenarios = pred.get("us", {}).get("scenarios", [])

    crypto = pred.get("crypto", {})
    btc_range = crypto.get("btc_krw_range", [0, 0])

    score = 0.0

    if kr_scenarios:
        best_kr = max(kr_scenarios, key=lambda s: s["probability"])
        kospi_range = best_kr.get("kospi_range", [0, 0])
        kospi_in_range = kospi_range[0] <= actual_kospi_close <= kospi_range[1]

        if kospi_in_range:
            score += 0.25

        highest_kr = best_kr["name"]
        if highest_kr == "상승" and actual_kospi_close > kospi_range[0]:
            score += 0.1
        elif highest_kr == "하락" and actual_kospi_close < kospi_range[1]:
            score += 0.1
        elif highest_kr == "횡보":
            score += 0.05
    else:
        kospi_in_range = False
        highest_kr = "-"

    if us_scenarios and actual_sp500_close:
        best_us = max(us_scenarios, key=lambda s: s["probability"])
        sp500_range = best_us.get("sp500_range", [0, 0])
        sp500_in_range = sp500_range[0] <= actual_sp500_close <= sp500_range[1]
        if sp500_in_range:
            score += 0.2
        highest_us = best_us["name"]
    else:
        sp500_in_range = None
        highest_us = "-"

    btc_in_range = btc_range[0] <= actual_btc_close <= btc_range[1] if btc_range[0] else False
    if btc_in_range:
        score += 0.2

    confidence = pred.get("confidence", 0.5)
    if score >= 0.4 and confidence >= 0.5:
        score += 0.15
    elif score < 0.3 and confidence < 0.4:
        score += 0.1

    actual = {
        "kospi_close": actual_kospi_close,
        "btc_close": actual_btc_close,
        "sp500_close": actual_sp500_close,
        "kospi_in_range": kospi_in_range,
        "btc_in_range": btc_in_range,
        "sp500_in_range": sp500_in_range,
        "best_kr_scenario": highest_kr,
        "best_us_scenario": highest_us,
    }

    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO prediction_scores "
            "(prediction_id,scored_at,actual_json,accuracy_score,notes) "
            "VALUES (?,?,?,?,?)",
            (prediction_id, datetime.now().isoformat(),
             json.dumps(actual, ensure_ascii=False),
             round(score, 3),
             f"KR:{highest_kr} US:{highest_us} KOSPI적중:{kospi_in_range}"),
        )

    return {"score": round(score, 3), "details": actual}


def get_score_history(limit=10, db_path=None):
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT ps.*, p.target_date, p.model "
            "FROM prediction_scores ps "
            "JOIN predictions p ON ps.prediction_id = p.id "
            "ORDER BY ps.scored_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def average_accuracy(limit=10, db_path=None):
    history = get_score_history(limit, db_path)
    if not history:
        return 0.0
    return sum(h["accuracy_score"] for h in history) / len(history)
