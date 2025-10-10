import os
import numpy as np
import faiss
from typing import List, Dict, Any, Sequence
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# --------------------------------
# .env & DB 연결
# --------------------------------
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env") if '__file__' in globals() else ".env"
load_dotenv(dotenv_path)

db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT", "5432")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_name = os.getenv("DB_NAME")
db_connection_str = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
db_engine = create_engine(db_connection_str, pool_pre_ping=True)

# --------------------------------
# 포맷터
# --------------------------------
def fmt_km(x) -> str:
    try:
        return f"{int(x):,} km"
    except Exception:
        return "-"

def fmt_year(y) -> str:
    return str(y) if y else "-"

# --------------------------------
# 데이터 조회
# --------------------------------
def fetch_vehicles() -> List[Dict[str, Any]]:
    sql = text("""
        WITH latest_ins AS (
            SELECT DISTINCT ON (i.vehicle_id)
                i.inspection_id,
                i.vehicle_id,
                i.guaranty_type,
                i.accident_history,
                i.tuning_exist,
                i.recall_applicable,
                i.recall_fulfilled,
                i.inspected_at
            FROM inspections i
            WHERE i.guaranty_type = 'INSURANCE'
              AND COALESCE(i.accident_history, FALSE) = FALSE
              AND COALESCE(i.tuning_exist,   FALSE) = FALSE
              AND NOT (COALESCE(i.recall_applicable, FALSE) = TRUE AND i.recall_fulfilled IS NULL)
            ORDER BY i.vehicle_id, i.inspected_at DESC NULLS LAST, i.inspection_id DESC
        )
        SELECT
            v.vehicle_id,
            v.manufacturer,
            v.model,
            v.price,
            v.origin_price,
            v.model_year,
            v.distance,
            v.car_type,
            v.fuel_type,
            v.transmission,
            v.detail_url,
            v.photo,
            v.color_name,
            COALESCE(ih.total_accident_cnt, 0)  AS total_accident_cnt,
            COALESCE(ih.my_accident_cost, 0)    AS my_accident_cost,
            COALESCE(ih.other_accident_cost, 0) AS other_accident_cost,
            ARRAY_REMOVE(ARRAY_AGG(DISTINCT om.option_name ORDER BY om.option_name), NULL) AS options,
            li.guaranty_type,
            li.accident_history,
            li.tuning_exist,
            li.recall_applicable,
            li.recall_fulfilled
        FROM vehicles v
        JOIN latest_ins li ON li.vehicle_id = v.vehicle_id
        LEFT JOIN insurance_history ih ON ih.vehicle_id = v.vehicle_id
        LEFT JOIN vehicle_options vo  ON vo.vehicle_id = v.vehicle_id
        LEFT JOIN option_masters om   ON om.option_master_id = vo.option_master_id
        WHERE v.sell_type = '일반'
          AND v.price IS NOT NULL
          AND v.price <> 9999
        GROUP BY
            v.vehicle_id, v.manufacturer, v.model, v.price, v.origin_price, v.model_year, v.distance, v.car_type,
            v.fuel_type, v.transmission, v.detail_url, v.photo, v.color_name,
            ih.total_accident_cnt, ih.my_accident_cost, ih.other_accident_cost,
            li.guaranty_type, li.accident_history, li.tuning_exist, li.recall_applicable, li.recall_fulfilled
    """)
    with db_engine.begin() as conn:
        rows = conn.execute(sql).mappings().all()
    return [dict(r) for r in rows]

# --------------------------------
# 스코어링/벡터화 유틸
# --------------------------------
def normalize_price(price, min_p=500, max_p=20000):
    if price is None:
        return 0.0
    lo, hi = (min_p, max_p) if min_p <= max_p else (max_p, min_p)
    if hi == lo:
        return 0.0
    x = (price - lo) / (hi - lo)
    return float(min(1.0, max(0.0, x)))

# (기존 직선형 주행거리 함수는 더 이상 사용하지 않지만 남겨둠)
def normalize_mileage(mileage, max_m=200_000):
    return 1 - min(1.0, (mileage or 0) / max_m)

def normalize_accident(cnt):
    return 1 - min(1.0, (cnt or 0) / 10)

def normalize_color_name(color: str) -> float:

    popular_colors = {c.lower() for c in ["흰색", "검정색", "은색", "쥐색", "은회색"]}
    normalized_color = str(color or "").strip().lower()
    if normalized_color in popular_colors:
        return 1.0
    return 0.5

def _norm(s: Any) -> str:
    return str(s or "").strip().lower()

def _match_ratio(desired: Sequence[str], actual: Sequence[str]) -> float:
    if not desired:
        return 0.0
    desired_l = {_norm(x) for x in (desired or []) if x}
    actual_l = {_norm(x) for x in (actual or []) if x}
    if not desired_l:
        return 0.0
    inter = desired_l.intersection(actual_l)
    return len(inter) / len(desired_l)

def match_options(desired: Sequence[str], actual: Sequence[str]):
    wanted = {_norm(x) for x in (desired or []) if x}
    have = {_norm(x) for x in (actual or []) if x}
    hits = sorted(list(wanted.intersection(have)))
    return len(hits), hits

CAR_TYPES = ["경차","소형","준중형","중형","대형","스포츠카","SUV","RV","승합","트럭"]
FUEL_TYPES = ["가솔린","디젤","하이브리드","전기"]
TRANSMISSIONS = ["자동","수동"]

def one_hot(value, categories):
    vec = [0.0] * len(categories)
    if value in categories:
        vec[categories.index(value)] = 1.0
    return vec

MY_COST_TO_MANWON = 1.0 / 10000.0
OTHER_COST_TO_MANWON = 1.0

def to_manwon(v, factor=1.0):
    return (v or 0) * factor

def damage_ratio_to_score(total_cost_manwon: float, origin_price_manwon: float) -> float:
    if not origin_price_manwon or origin_price_manwon <= 0:
        return 0.5
    ratio = total_cost_manwon / origin_price_manwon
    if ratio <= 0.10:
        return 1.0
    if ratio <= 0.20:
        return 1.0 - 0.5 * ((ratio - 0.10) / 0.10)
    return max(0.0, 0.5 * (1.0 - (ratio - 0.20) / 0.30))

# -------------------------------
# 가중치
# -------------------------------
WEIGHTS = {
    "price":        0.25,
    "mileage":      0.18,   
    "accident":     0.07,
    "damage_score": 0.25,
    "car_type":     0.15,
    "color_name":   0.05,
    "options":      0.05,
}

def adjust_weights(user_preference: Dict[str, float]) -> Dict[str, float]:
    base_weights = WEIGHTS.copy()
    for key, multiplier in user_preference.items():
        if key in base_weights:
            base_weights[key] *= multiplier
    current_total = sum(base_weights.values())
    if current_total > 0:
        normalized_weights = {k: v / current_total for k, v in base_weights.items()}
        return normalized_weights
    return WEIGHTS

# -------------------------------
# 보증 구간 기반 주행거리 점수
# 3년/6만km, 5년/10만km 기준으로 스윗스팟을 5천~6만km,
# 6만~10만은 완만 감점, 10만 이후는 빠른 감점
# -------------------------------
MILEAGE_BANDS = [
    (0,       5_000,   0.90, 0.95),
    (5_000,   60_000,  0.95, 1.00),   
    (60_000,  100_000, 1.00, 0.85),   
    (100_000, 150_000, 0.85, 0.55),
    (150_000, 300_000, 0.55, 0.25),
]

def mileage_warranty_score(mileage: int, bands=MILEAGE_BANDS) -> float:
    m = int(mileage or 0)
    for lo, hi, s_lo, s_hi in bands:
        if m <= hi:
            t = 0.0 if hi == lo else (m - lo) / (hi - lo)
            return float(s_lo + t * (s_hi - s_lo))
    return float(bands[-1][3])

# -------------------------------
# 벡터화
# -------------------------------
def vehicle_to_vector(v: Dict[str, Any], weights: Dict[str, float]) -> np.ndarray:
    my_cost_mw = to_manwon(v.get("my_accident_cost"), MY_COST_TO_MANWON)
    other_cost_mw = to_manwon(v.get("other_accident_cost"), OTHER_COST_TO_MANWON)
    total_cost_mw = my_cost_mw + other_cost_mw
    dmg_score = damage_ratio_to_score(total_cost_mw, v.get("origin_price") or 0)

    desired_options = ["선루프(일반)","선루프(파노라마)","에어백(운전석)","후방 카메라","후측방 경보 시스템",
                       "통풍시트(운전석)","열선시트(앞좌석)","내비게이션","블루투스","하이패스","열선 스티어링 휠"]
    option_score = _match_ratio(desired_options, v.get("options", []))

    mileage_util = mileage_warranty_score(v.get("distance"))

    comps = [
        normalize_price(v.get("price")) * weights["price"],
        mileage_util * weights["mileage"],  # ← 보증구간 기반 점수 적용
        normalize_accident(v.get("total_accident_cnt")) * weights["accident"],
        dmg_score * weights["damage_score"],
        normalize_color_name(v.get("color_name")) * weights["color_name"],
        option_score * weights["options"],
    ]
    comps.extend([c * weights["car_type"] for c in one_hot(v.get("car_type"), CAR_TYPES)])
    return np.array(comps, dtype=np.float32)

def user_to_vector(user: Dict[str, Any], weights: Dict[str, float]) -> np.ndarray:
    option_score = 1.0

    # 사용자가 mileage 선호를 제공하지 않으면 스윗스팟 중립값으로 0.9 사용
    if user.get("mileage") is None:
        mileage_util = 0.9
    else:
        mileage_util = mileage_warranty_score(user.get("mileage"))

    comps = [
        normalize_price(user.get("price")) * weights["price"],
        mileage_util * weights["mileage"],  # ← 보증구간 기반 점수 적용
        normalize_accident(user.get("accident")) * weights["accident"],
        1.0 * weights["damage_score"],
        1.0 * weights["color_name"],
        option_score * weights["options"],
    ]
    comps.extend([c * weights["car_type"] for c in one_hot(user.get("car_type"), CAR_TYPES)])
    return np.array([comps], dtype=np.float32)

# -------------------------------
# 인덱스 구성/조회
# -------------------------------
INDEX_CACHE = {"index": None, "X": None, "rows": None, "label": "", "weights_label": ""}

def build_or_get_index(vehicles, final_weights):
    if INDEX_CACHE["index"] is not None and INDEX_CACHE["rows"] is vehicles and INDEX_CACHE["weights_label"] == str(final_weights):
        return INDEX_CACHE["index"], INDEX_CACHE["X"], INDEX_CACHE["rows"]

    X = np.vstack([vehicle_to_vector(v, final_weights) for v in vehicles]).astype(np.float32)
    faiss.normalize_L2(X)
    d, n = X.shape[1], len(vehicles)

    if n >= 80000:
        nlist = int(min(max(1024, n // 64), max(1024, n // 39)))
        descs = [f"IVF{nlist}_HNSW32,Flat", f"IVF{nlist},Flat"]
        index, label = None, ""
        for desc in descs:
            try:
                index = faiss.index_factory(d, desc, faiss.METRIC_INNER_PRODUCT)
                index.train(X); index.add(X); index.nprobe = 48
                label = f"{desc} (IP); nlist={nlist}, nprobe={index.nprobe}"
                break
            except Exception:
                index = None
        if index is None:
            index = faiss.IndexHNSWFlat(d, 32, faiss.METRIC_INNER_PRODUCT)
            index.add(X); label = "HNSW32 (IP)"
    else:
        index = faiss.IndexFlatIP(d); index.add(X); label = "FlatIP (exact cosine)"

    INDEX_CACHE.update({"index": index, "X": X, "rows": vehicles, "label": label, "weights_label": str(final_weights)})
    print(f"[FAISS] Using index: {label}; n={n}, d={d}")
    return index, X, vehicles

# -------------------------------
# 추천
# -------------------------------
def get_top_recommendations(user_conditions: Dict[str, Any], user_preferences: Dict[str, float] = None,
                            top_n: int = 5, desired_options: Sequence[str] = None):
    vehicles = fetch_vehicles()
    if not vehicles:
        return []

    final_weights = adjust_weights(user_preferences) if user_preferences else WEIGHTS
    index, _, rows = build_or_get_index(vehicles, final_weights)

    q = user_to_vector(user_conditions, final_weights).astype(np.float32)
    faiss.normalize_L2(q)
    D, I = index.search(q, top_n)

    results = []
    for rank, (idx, score) in enumerate(zip(I[0], D[0]), 1):
        item = dict(rows[idx])
        item["_rank"] = rank
        item["_score"] = float(score)

        my_cost_mw = to_manwon(item.get("my_accident_cost"), MY_COST_TO_MANWON)
        other_cost_mw = to_manwon(item.get("other_accident_cost"), OTHER_COST_TO_MANWON)
        total_cost_mw = my_cost_mw + other_cost_mw
        origin_mw = item.get("origin_price") or 0
        item["_damage_ratio"] = (round(total_cost_mw / origin_mw, 4) if origin_mw > 0 else None)

        price_mw = item.get("price") or 0
        item["_residual_ratio"] = (round(price_mw / origin_mw, 4) if origin_mw > 0 else None)

        cnt, hits = match_options(desired_options or [], item.get("options", []))
        item["_desired_option_count"] = cnt
        item["_desired_option_hits"] = hits

        results.append(item)
    return results

# -------------------------------
# 실행 예시
# -------------------------------
if __name__ == "__main__":
    personas = {
        "사회 초년생": {"price": 1500, "accident": 0, "car_type": "준중형차", "fuel_type": "가솔린", "transmission": "자동"},
        "CEO": {"price": 9000, "accident": 0, "car_type": "대형차", "color_name":"검정색", "fuel_type": "가솔린", "transmission": "자동"},
        "레저/캠핑족": {"price": 4000, "accident": 0, "car_type": "SUV", "fuel_type": "디젤", "transmission": "자동"},
    }

    DESIRED_OPTIONS = ["선루프(일반)","선루프(파노라마)","에어백(운전석)","후방 카메라","후측방 경보 시스템",
                       "통풍시트(운전석)","열선시트(앞좌석)","내비게이션","블루투스","하이패스","열선 스티어링 휠"]
    selected = "사회 초년생"

    # CASE 1: 기본 추천
    print(f"--- CASE 1: {selected} 기본 추천 ---")
    recs = get_top_recommendations(personas[selected], top_n=5, desired_options=DESIRED_OPTIONS)
    for r in recs:
        rv = "-" if r.get("_residual_ratio") is None else f"{r['_residual_ratio']*100:.1f}% ({r['_residual_ratio']:.3f})"
        print(
            f"순위: {r['_rank']:2} | 점수: {r['_score']:.4f} | 제조사: {r['manufacturer']} | 모델: {r['model']} "
            f"| 가격(만원): {r['price']} | 연식: {fmt_year(r.get('model_year'))} | 주행거리: {fmt_km(r.get('distance'))} "
            f"| 사고건수: {r['total_accident_cnt']} | 잔존가치: {rv}"
        )
        print(f"옵션일치: {r['_desired_option_count']}/{len(DESIRED_OPTIONS)} | 히트: {', '.join(r['_desired_option_hits']) if r['_desired_option_hits'] else '-'}")
        print(f"URL: {r.get('detail_url')}")
        print(f"사진: {r.get('photo')}")
        print("-" * 20)

    print("\n" + "="*50 + "\n")

    # CASE 2: 재정렬 (안전/사고 이력 중요)
    print(f"--- CASE 2: {selected} 재정렬 (안전/사고 이력 중요) ---")
    recs_reranked = get_top_recommendations(
        personas[selected],
        user_preferences={"accident": 1.5, "damage_score": 1.5, "price": 0.8},
        top_n=5,
        desired_options=DESIRED_OPTIONS
    )
    for r in recs_reranked:
        rv = "-" if r.get("_residual_ratio") is None else f"{r['_residual_ratio']*100:.1f}% ({r['_residual_ratio']:.3f})"
        print(
            f"순위: {r['_rank']:2} | 점수: {r['_score']:.4f} | 제조사: {r['manufacturer']} | 모델: {r['model']} "
            f"| 가격(만원): {r['price']} | 연식: {fmt_year(r.get('model_year'))} | 주행거리: {fmt_km(r.get('distance'))} "
            f"| 사고건수: {r['total_accident_cnt']} | 잔존가치: {rv}"
        )
        print(f"옵션일치: {r['_desired_option_count']}/{len(DESIRED_OPTIONS)} | 히트: {', '.join(r['_desired_option_hits']) if r['_desired_option_hits'] else '-'}")
        print(f"URL: {r.get('detail_url')}")
        print(f"사진: {r.get('photo')}")
        print("-" * 20)
