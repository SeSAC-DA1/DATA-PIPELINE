import os
import numpy as np
import faiss
from typing import List, Dict, Any
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ───────────────────────────────
# DB 연결
# ───────────────────────────────
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path)

db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT", "5432")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_name = os.getenv("DB_NAME")
db_connection_str = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
db_engine = create_engine(db_connection_str, pool_pre_ping=True)

# ───────────────────────────────
# 데이터 조회 
# ───────────────────────────────
def fetch_vehicles() -> List[Dict[str, Any]]:
    sql = text("""
        SELECT
            v.vehicle_id,
            v.manufacturer,
            v.model,
            v.price,
            v.model_year,
            v.distance,
            COALESCE(ih.total_accident_cnt, 0) AS total_accident_cnt,
            v.car_type,
            v.fuel_type,
            v.transmission
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

# ───────────────────────────────
# 정규화/인코딩
# ───────────────────────────────
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

CAR_TYPES = ["경차", "소형", "준중형", "중형", "대형", "스포츠카", "SUV", "RV", "승합", "트럭"]
FUEL_TYPES = ["가솔린", "디젤", "하이브리드", "전기"]
TRANSMISSIONS = ["자동", "수동"]

def one_hot(value, categories):
    vec = [0.0] * len(categories)
    if value in categories:
        vec[categories.index(value)] = 1.0
    return vec

# ───────────────────────────────
# 가중치(연식 제외)
# ───────────────────────────────
WEIGHTS = {
    "price": 0.3,
    "mileage": 0.2,
    "accident": 0.1,
    "car_type": 0.3,
    "fuel_type": 0.05,
    "transmission": 0.05,
}

def vehicle_to_vector(v: Dict[str, Any]) -> np.ndarray:
    comps = [
        normalize_price(v.get("price")) * WEIGHTS["price"],
        normalize_mileage(v.get("distance")) * WEIGHTS["mileage"],
        normalize_accident(v.get("total_accident_cnt")) * WEIGHTS["accident"],
    ]
    comps.extend([c * WEIGHTS["car_type"] for c in one_hot(v.get("car_type"), CAR_TYPES)])
    comps.extend([c * WEIGHTS["fuel_type"] for c in one_hot(v.get("fuel_type"), FUEL_TYPES)])
    comps.extend([c * WEIGHTS["transmission"] for c in one_hot(v.get("transmission"), TRANSMISSIONS)])
    return np.array(comps, dtype=np.float32)

def user_to_vector(user: Dict[str, Any]) -> np.ndarray:
    comps = [
        normalize_price(user.get("price")) * WEIGHTS["price"],
        normalize_mileage(user.get("mileage")) * WEIGHTS["mileage"],
        normalize_accident(user.get("accident")) * WEIGHTS["accident"],
    ]
    comps.extend([c * WEIGHTS["car_type"] for c in one_hot(user.get("car_type"), CAR_TYPES)])
    comps.extend([c * WEIGHTS["fuel_type"] for c in one_hot(user.get("fuel_type"), FUEL_TYPES)])
    comps.extend([c * WEIGHTS["transmission"] for c in one_hot(user.get("transmission"), TRANSMISSIONS)])
    q = np.array([comps], dtype=np.float32)
    return q

# ───────────────────────────────
# 인덱스 캐시 + 코사인 + nlist 자동 튜닝
# ───────────────────────────────
INDEX_CACHE = {"index": None, "X": None, "rows": None, "label": ""}

def build_or_get_index(vehicles):
    if INDEX_CACHE["index"] is not None and INDEX_CACHE["rows"] is vehicles:
        return INDEX_CACHE["index"], INDEX_CACHE["X"], INDEX_CACHE["rows"]

    X = np.vstack([vehicle_to_vector(v) for v in vehicles]).astype(np.float32)
    faiss.normalize_L2(X)  # 코사인용 정규화

    d, n = X.shape[1], len(vehicles)
    label = ""

    if n >= 80000:
        # nlist 자동 산정: ~N/64, 그리고 FAISS 권장(>=39*nlist) 조건 만족하도록 캡
        nlist_guess = max(1024, n // 64)
        nlist_cap   = max(1024, n // 39)        # 부족 경고 방지 상한
        nlist = int(min(nlist_guess, nlist_cap))

        # 1) IVF + HNSW(코스 그라파) 시도
        desc = f"IVF{nlist}_HNSW32,Flat"
        try:
            index = faiss.index_factory(d, desc, faiss.METRIC_INNER_PRODUCT)
            index.train(X)
            index.add(X)
            index.nprobe = 48
            label = f"{desc} (IP); nlist={nlist}, nprobe={index.nprobe}"
        except Exception:
            # 2) IVF(Flat)로 폴백
            try:
                desc = f"IVF{nlist},Flat"
                index = faiss.index_factory(d, desc, faiss.METRIC_INNER_PRODUCT)
                index.train(X)
                index.add(X)
                index.nprobe = 48
                label = f"{desc} (IP); nlist={nlist}, nprobe={index.nprobe}"
            except Exception:
                # 3) 최후: HNSW(정확도↑/구현 호환↑)
                desc = "HNSW32,Flat"
                index = faiss.index_factory(d, desc, faiss.METRIC_INNER_PRODUCT)
                index.add(X)
                label = f"{desc} (IP)"
    else:
        # 소규모는 정확탐색
        index = faiss.IndexFlatIP(d)
        index.add(X)
        label = "FlatIP (exact cosine)"

    INDEX_CACHE.update({"index": index, "X": X, "rows": vehicles, "label": label})
    print(f"[FAISS] Using index: {label}; n={n}, d={d}")
    return index, X, vehicles


# ───────────────────────────────
# 추천
# ───────────────────────────────
def get_top_recommendations(user_conditions: Dict[str, Any], top_n: int = 5):
    vehicles = fetch_vehicles()
    if not vehicles:
        return []

    index, X, rows = build_or_get_index(vehicles)
    q = user_to_vector(user_conditions).astype(np.float32)
    faiss.normalize_L2(q)                    # cosine
    D, I = index.search(q, top_n)

    results = []
    for rank, (idx, score) in enumerate(zip(I[0], D[0]), 1):
        item = dict(rows[idx])
        item["_rank"] = rank
        item["_score"] = float(score)       
        results.append(item)
    return results


# ───────────────────────────────
# 실행 예시
# ───────────────────────────────
if __name__ == "__main__":
    personas = {
        "사회 초년생": {"price": 2000, "mileage": 80000, "accident": 1, "car_type": "경차", "fuel_type": "가솔린", "transmission": "자동"},
        "CEO": {"price": 9000, "mileage": 20000, "accident": 0, "car_type": "대형", "fuel_type": "하이브리드", "transmission": "자동"},
        "레저/캠핑족": {"price": 4000, "mileage": 50000, "accident": 0, "car_type": "SUV", "fuel_type": "디젤", "transmission": "자동"},
    }
    selected_persona = "레저/캠핑족"
    recs = get_top_recommendations(personas[selected_persona], 10)
    for r in recs:
        print(r["_rank"], round(r["_score"], 4),r["car_type"], r["manufacturer"], r["model"], r["price"], r["distance"])
