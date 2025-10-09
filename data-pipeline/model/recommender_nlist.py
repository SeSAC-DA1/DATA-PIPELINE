import os
import numpy as np
import faiss
from typing import List, Dict, Any
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# -------------------------------
# DB 연결
# -------------------------------
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path)

db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT", "5432")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_name = os.getenv("DB_NAME")
db_connection_str = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
db_engine = create_engine(db_connection_str, pool_pre_ping=True)

# -------------------------------
# 데이터 조회 (보험 이력 + origin_price 추가)
# -------------------------------
def fetch_vehicles() -> List[Dict[str, Any]]:
    sql = text("""
        SELECT
            v.vehicle_id,
            v.manufacturer,
            v.model,
            v.price,                    -- 만원
            v.origin_price,             -- 만원(신차가)
            v.model_year,
            v.distance,
            v.car_type,
            v.fuel_type,
            v.transmission,
            COALESCE(ih.total_accident_cnt, 0)  AS total_accident_cnt,
            COALESCE(ih.my_accident_cost, 0)    AS my_accident_cost,     -- 원(₩)
            COALESCE(ih.other_accident_cost, 0) AS other_accident_cost   -- 만원(가정)
        FROM vehicles v
        LEFT JOIN insurance_history ih
               ON ih.vehicle_id = v.vehicle_id
        WHERE v.sell_type = '일반'
          AND v.price IS NOT NULL
          AND v.price <> 9999
    """)
    with db_engine.begin() as conn:
        rows = conn.execute(sql).mappings().all()
    return [dict(r) for r in rows]

# -------------------------------
# 정규화/인코딩
# -------------------------------
def normalize_price(price, min_p=500, max_p=20000):  # 단위: '만원'
    if price is None:
        return 0.0
    lo, hi = (min_p, max_p) if min_p <= max_p else (max_p, min_p)
    if hi == lo:
        return 0.0
    x = (price - lo) / (hi - lo)
    return float(min(1.0, max(0.0, x)))

def normalize_mileage(mileage, max_m=200_000):
    return 1 - min(1.0, (mileage or 0) / max_m)

def normalize_accident(cnt):
    return 1 - min(1.0, (cnt or 0) / 10)

CAR_TYPES = ["경차","소형","준중형","중형","대형","스포츠카","SUV","RV","승합","트럭"]
FUEL_TYPES = ["가솔린","디젤","하이브리드","전기"]
TRANSMISSIONS = ["자동","수동"]

def one_hot(value, categories):
    vec = [0.0] * len(categories)
    if value in categories:
        vec[categories.index(value)] = 1.0
    return vec

# -------------------------------
# 보험 손상비율 → 스코어 (신차가 기준)
# -------------------------------
# 단위 변환: my_accident_cost는 '원', other_accident_cost는 '만원'으로 가정
MY_COST_TO_MANWON = 1.0 / 10000.0   # 원 → 만원
OTHER_COST_TO_MANWON = 1.0          # 이미 만원(필요 시 1/10000.0로 변경)

def to_manwon(v, factor=1.0):
    return (v or 0) * factor

def damage_ratio_to_score(total_cost_manwon: float, origin_price_manwon: float) -> float:
    """
    total_cost / origin_price 비율을 0~1 스코어로 변환.
    <10%: 1.0 / 10~20%: 1.0→0.5 / >20%: 0.5→0.0 (선형감쇠)
    """
    if not origin_price_manwon or origin_price_manwon <= 0:
        return 0.5  # 정보 없음은 중립
    ratio = total_cost_manwon / origin_price_manwon
    if ratio <= 0.10:
        return 1.0
    if ratio <= 0.20:
        return 1.0 - 0.5 * ((ratio - 0.10) / 0.10)
    # 20% 초과: 0.5 → 0.0 (약 50% 이상이면 사실상 0)
    return max(0.0, 0.5 * (1.0 - (ratio - 0.20) / 0.30))

# -------------------------------
# 가중치
# -------------------------------
WEIGHTS = {
    "price":        0.25,
    "mileage":      0.18,
    "accident":     0.07,   # 단순 '건수' 영향은 낮게
    "damage_score": 0.25,   # 신차가 대비 수리비 비율 스코어
    "car_type":     0.20,
    "fuel_type":    0.03,
    "transmission": 0.02,
}

def vehicle_to_vector(v: Dict[str, Any]) -> np.ndarray:
    # 원→만원 변환 후 합산
    my_cost_mw    = to_manwon(v.get("my_accident_cost"),    MY_COST_TO_MANWON)
    other_cost_mw = to_manwon(v.get("other_accident_cost"), OTHER_COST_TO_MANWON)
    total_cost_mw = my_cost_mw + other_cost_mw

    dmg_score = damage_ratio_to_score(total_cost_mw, v.get("origin_price") or 0)

    comps = [
        normalize_price(v.get("price")) * WEIGHTS["price"],
        normalize_mileage(v.get("distance")) * WEIGHTS["mileage"],
        normalize_accident(v.get("total_accident_cnt")) * WEIGHTS["accident"],
        dmg_score * WEIGHTS["damage_score"],
    ]
    comps.extend([c * WEIGHTS["car_type"] for c in one_hot(v.get("car_type"), CAR_TYPES)])
    comps.extend([c * WEIGHTS["fuel_type"] for c in one_hot(v.get("fuel_type"), FUEL_TYPES)])
    comps.extend([c * WEIGHTS["transmission"] for c in one_hot(v.get("transmission"), TRANSMISSIONS)])
    return np.array(comps, dtype=np.float32)

def user_to_vector(user: Dict[str, Any]) -> np.ndarray:
    # 사용자는 "손상 적을수록 좋다" 가정: damage_score=1.0
    comps = [
        normalize_price(user.get("price")) * WEIGHTS["price"],
        normalize_mileage(user.get("mileage")) * WEIGHTS["mileage"],
        normalize_accident(user.get("accident")) * WEIGHTS["accident"],
        1.0 * WEIGHTS["damage_score"],
    ]
    comps.extend([c * WEIGHTS["car_type"] for c in one_hot(user.get("car_type"), CAR_TYPES)])
    comps.extend([c * WEIGHTS["fuel_type"] for c in one_hot(user.get("fuel_type"), FUEL_TYPES)])
    comps.extend([c * WEIGHTS["transmission"] for c in one_hot(user.get("transmission"), TRANSMISSIONS)])
    return np.array([comps], dtype=np.float32)

# -------------------------------
# 인덱스 (코사인 + nlist 자동)
# -------------------------------
INDEX_CACHE = {"index": None, "X": None, "rows": None, "label": ""}

def build_or_get_index(vehicles):
    if INDEX_CACHE["index"] is not None and INDEX_CACHE["rows"] is vehicles:
        return INDEX_CACHE["index"], INDEX_CACHE["X"], INDEX_CACHE["rows"]

    X = np.vstack([vehicle_to_vector(v) for v in vehicles]).astype(np.float32)
    faiss.normalize_L2(X)

    d, n = X.shape[1], len(vehicles)
    if n >= 80000:
        nlist_guess = max(1024, n // 64)
        nlist_cap   = max(1024, n // 39)
        nlist = int(min(nlist_guess, nlist_cap))
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
            index.add(X)
            label = "HNSW32 (IP)"
    else:
        index = faiss.IndexFlatIP(d); index.add(X)
        label = "FlatIP (exact cosine)"

    INDEX_CACHE.update({"index": index, "X": X, "rows": vehicles, "label": label})
    print(f"[FAISS] Using index: {label}; n={n}, d={d}")
    return index, X, vehicles

# -------------------------------
# 추천
# -------------------------------
def get_top_recommendations(user_conditions: Dict[str, Any], top_n: int = 5):
    vehicles = fetch_vehicles()
    if not vehicles:
        return []

    index, X, rows = build_or_get_index(vehicles)

    q = user_to_vector(user_conditions).astype(np.float32)
    faiss.normalize_L2(q)
    D, I = index.search(q, top_n)

    results = []
    for rank, (idx, score) in enumerate(zip(I[0], D[0]), 1):
        item = dict(rows[idx])
        item["_rank"] = rank
        item["_score"] = float(score)  # 코사인: 클수록 좋음

        # 출력용 비율도 동일 기준(만원/만원)으로 계산
        my_cost_mw    = to_manwon(item.get("my_accident_cost"), MY_COST_TO_MANWON)
        other_cost_mw = to_manwon(item.get("other_accident_cost"), OTHER_COST_TO_MANWON)
        total_cost_mw = my_cost_mw + other_cost_mw
        origin_mw  = item.get("origin_price") or 1
        item["_damage_ratio"] = round(total_cost_mw / origin_mw, 4)

        results.append(item)
    return results

# ───────────────────────────────
# 실행 예시
# ───────────────────────────────
if __name__ == "__main__":
    personas = {
        "사회 초년생": {"price": 2000, "mileage": 80000, "accident": 1, "car_type": "경차", "fuel_type": "가솔린", "transmission": "자동"},
        "CEO": {"price": 9000, "mileage": 20000, "accident": 0, "car_type": "대형", "fuel_type": "가솔린", "transmission": "자동"},
        "레저/캠핑족": {"price": 4000, "mileage": 50000, "accident": 0, "car_type": "SUV", "fuel_type": "디젤",   "transmission": "자동"},
    }
    selected = "사회 초년생"
    recs = get_top_recommendations(personas[selected], 10)
    for r in recs:
        print(
            r["_rank"], round(r["_score"], 4), f"비율={r['_damage_ratio']}",
            r["manufacturer"], r["model"], r["price"], r["origin_price"], r["total_accident_cnt"]
        )
