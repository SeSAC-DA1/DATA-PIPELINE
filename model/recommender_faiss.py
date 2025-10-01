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
# 데이터 조회 (필터: sell_type=일반, price!=9999)
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
# 정규화 함수
# ───────────────────────────────
def normalize_price(price, min_p=5_000_000, max_p=100_000_000):
    return min(1.0, max(0.0, (price - min_p) / (max_p - min_p)))

def normalize_mileage(mileage, max_m=200_000):
    return 1 - min(1.0, (mileage or 0) / max_m)

def normalize_accident(cnt):
    return 1 - min(1.0, (cnt or 0) / 10)

# 범주형 → 원핫
CAR_TYPES = ["경차", "소형", "준중형", "중형", "대형", "스포츠카", "SUV", "RV", "승합", "트럭"]
FUEL_TYPES = ["가솔린", "디젤", "하이브리드", "전기"]
TRANSMISSIONS = ["자동", "수동"]

def one_hot(value, categories):
    vec = [0.0] * len(categories)
    if value in categories:
        vec[categories.index(value)] = 1.0
    return vec

# ───────────────────────────────
# 가중치 (year 제거)
# ───────────────────────────────
WEIGHTS = {
    "price": 0.3,
    "mileage": 0.2,
    "accident": 0.1,
    "car_type": 0.3,
    "fuel_type": 0.05,
    "transmission": 0.05,
}

# ───────────────────────────────
# 벡터 변환 (year 제외)
# ───────────────────────────────
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
    # year(연식)은 더 이상 사용하지 않음
    comps = [
        normalize_price(user.get("price")) * WEIGHTS["price"],
        normalize_mileage(user.get("mileage")) * WEIGHTS["mileage"],
        normalize_accident(user.get("accident")) * WEIGHTS["accident"],
    ]
    comps.extend([c * WEIGHTS["car_type"] for c in one_hot(user.get("car_type"), CAR_TYPES)])
    comps.extend([c * WEIGHTS["fuel_type"] for c in one_hot(user.get("fuel_type"), FUEL_TYPES)])
    comps.extend([c * WEIGHTS["transmission"] for c in one_hot(user.get("transmission"), TRANSMISSIONS)])
    return np.array([comps], dtype=np.float32)

# ───────────────────────────────
# 추천 (FAISS)
# ───────────────────────────────
def get_top_recommendations(user_conditions: Dict[str, Any], top_n: int = 5):
    vehicles = fetch_vehicles()
    vectors = np.array([vehicle_to_vector(v) for v in vehicles], dtype=np.float32)
    d = vectors.shape[1]
    index = faiss.IndexFlatL2(d)
    index.add(vectors)
    user_vec = user_to_vector(user_conditions)
    D, I = index.search(user_vec, top_n)
    return [vehicles[idx] for idx in I[0]]

if __name__ == "__main__":
    personas = {
        "사회 초년생": {"price": 20000000, "mileage": 80000, "accident": 1, "car_type": "경차", "fuel_type": "가솔린", "transmission": "자동"},
        "CEO": {"price": 90000000, "mileage": 20000, "accident": 0, "car_type": "대형", "fuel_type": "하이브리드", "transmission": "자동"},
        "레저/캠핑족": {"price": 40000000, "mileage": 50000, "accident": 0, "car_type": "SUV", "fuel_type": "디젤", "transmission": "자동"},
    }
    selected_persona = "CEO"
    for r in get_top_recommendations(personas[selected_persona], 10):
        print(r)
