"""백테스트 모듈 — 예측 정확도 자동 평가"""
import json
from datetime import datetime
from market_prediction.utils.db import get_db


def score_prediction(prediction_id, actual_kospi_close, actual_btc_close,
                     db_path=None):
    """저장된 예측과 실제 결과를 비교해 점수 산출"""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM predictions WHERE id=?", (prediction_id,)
        ).fetchone()

    if not row:
        return None

    pred = json.loads(row["prediction_json"])
    scenarios = pred.get("scenarios", [])

    best_scenario = max(scenarios, key=lambda s: s["probability"])
    kospi_range = best_scenario.get("kospi_range", [0, 0])
    btc_range = best_scenario.get("btc_krw_range", [0, 0])

    kospi_in_range = kospi_range[0] <= actual_kospi_close <= kospi_range[1]
    btc_in_range = btc_range[0] <= actual_btc_close <= btc_range[1]

    direction_scores = []
    for s in scenarios:
        kr = s.get("kospi_range", [0, 0])
        mid = (kr[0] + kr[1]) / 2 if kr[0] and kr[1] else 0
        direction_scores.append({
            "name": s["name"],
            "probability": s["probability"],
            "predicted_mid": mid,
        })

    score = 0.0
    if kospi_in_range:
        score += 0.4
    if btc_in_range:
        score += 0.3

    highest_prob = best_scenario["name"]
    if highest_prob == "상승" and actual_kospi_close > kospi_range[0]:
        score += 0.15
    elif highest_prob == "하락" and actual_kospi_close < kospi_range[1]:
        score += 0.15
    elif highest_prob == "횡보":
        score += 0.1

    confidence = pred.get("confidence", 0.5)
    if score >= 0.5 and confidence >= 0.5:
        score += 0.15
    elif score < 0.5 and confidence < 0.5:
        score += 0.1

    actual = {
        "kospi_close": actual_kospi_close,
        "btc_close": actual_btc_close,
        "kospi_in_range": kospi_in_range,
        "btc_in_range": btc_in_range,
        "best_scenario": highest_prob,
    }

    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO prediction_scores "
            "(prediction_id,scored_at,actual_json,accuracy_score,notes) "
            "VALUES (?,?,?,?,?)",
            (prediction_id, datetime.now().isoformat(),
             json.dumps(actual, ensure_ascii=False),
             round(score, 3),
             f"방향: {highest_prob}, KOSPI범위적중: {kospi_in_range}"),
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
