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
# 데이터 조회 (벡터화에 필요한 필드만)
# ───────────────────────────────
def fetch_vehicles(limit: int = 50000) -> List[Dict[str, Any]]:
    sql = text("""
        SELECT
            vehicle_id,
            price,
            model_year,
            distance,
            COALESCE(total_accident_cnt, 0) as total_accident_cnt,
            car_type,
            fuel_type,
            transmission
        FROM vehicles v
        LEFT JOIN insurance_history ih
               ON ih.vehicle_id = v.vehicle_id
        LIMIT :lim
    """)
    with db_engine.begin() as conn:
        rows = conn.execute(sql, {"lim": limit}).mappings().all()
    return [dict(r) for r in rows]

# ───────────────────────────────
# 정규화 함수
# ───────────────────────────────
def normalize_price(price, min_p=5_000_000, max_p=100_000_000):
    return min(1.0, max(0.0, (price - min_p) / (max_p - min_p)))

def normalize_year(year, min_y=2005, max_y=2025):
    return (year - min_y) / (max_y - min_y)

def normalize_mileage(mileage, max_m=200_000):
    return 1 - min(1.0, mileage / max_m)

def normalize_accident(cnt):
    return 1 - min(1.0, cnt / 10)

# 범주형(차종, 연료, 변속기) → 원핫 인코딩 매핑
CAR_TYPES = ["경차", "소형", "준중형", "중형", "대형", "스포츠카", "SUV", "RV", "승합", "트럭"]
FUEL_TYPES = ["가솔린", "디젤", "하이브리드", "전기"]
TRANSMISSIONS = ["자동", "수동"]

def one_hot(value, categories):
    vec = [0.0] * len(categories)
    if value in categories:
        vec[categories.index(value)] = 1.0
    return vec

# ───────────────────────────────
# 벡터 변환
# ───────────────────────────────
def vehicle_to_vector(v: Dict[str, Any]) -> np.ndarray:
    return np.array([
        normalize_price(v.get("price") or 0),
        normalize_year(v.get("model_year") or 2005),
        normalize_mileage(v.get("distance") or 0),
        normalize_accident(v.get("total_accident_cnt") or 0),
        *one_hot(v.get("car_type"), CAR_TYPES),
        *one_hot(v.get("fuel_type"), FUEL_TYPES),
        *one_hot(v.get("transmission"), TRANSMISSIONS),
    ], dtype=np.float32)

def user_to_vector(user: Dict[str, Any]) -> np.ndarray:
    return np.array([[
        normalize_price(user.get("price") or 0),
        normalize_year(user.get("year") or 2005),
        normalize_mileage(user.get("mileage") or 0),
        normalize_accident(user.get("accident") or 0),
        *one_hot(user.get("car_type"), CAR_TYPES),
        *one_hot(user.get("fuel_type"), FUEL_TYPES),
        *one_hot(user.get("transmission"), TRANSMISSIONS),
    ]], dtype=np.float32)

# ───────────────────────────────
# 추천 함수 (FAISS 검색)
# ───────────────────────────────
def get_top_recommendations(user_conditions: Dict[str, Any], top_n: int = 5):
    vehicles = fetch_vehicles()  # 5만개만 불러오기 (필요시 전체)
    vectors = np.array([vehicle_to_vector(v) for v in vehicles], dtype=np.float32)

    d = vectors.shape[1]
    index = faiss.IndexFlatL2(d)
    index.add(vectors)

    user_vec = user_to_vector(user_conditions)
    D, I = index.search(user_vec, top_n)

    results = []
    for idx in I[0]:
        results.append(vehicles[idx])
    return results

# ───────────────────────────────
# 실행 예시
# ───────────────────────────────
if __name__ == "__main__":
    sample_user = {
        "price": 25000000,
        "year": 2019,
        "mileage": 60000,
        "accident": 1,
        "car_type": "SUV",
        "fuel_type": "가솔린",
        "transmission": "자동",
    }
    recs = get_top_recommendations(sample_user, 10)
    for r in recs:
        print(r)
