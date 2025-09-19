import os
from typing import List, Dict
import pymysql
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path)

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
    'charset': 'utf8mb4'
}

def fetch_vehicles_from_db() -> List[Dict]:
    """vehicles 테이블과 JOIN으로 차량 기본+정보+점검+보험 데이터 조회"""
    conn = pymysql.connect(**DB_CONFIG)
    sql = """
        SELECT
            v.*, -- vehicles 테이블의 모든 컬럼
            vi.WarrantyType, vi.Tuning, vi.ChangeUsage, vi.Recall, vi.RecallStatus, vi.AccidentHistory, vi.SimpleRepair,
            vin.vehicleNo AS insurance_vehicleNo, vin.OwnerChangeCnt, vin.MyAccidentCnt, vin.MyAccidentCost,
            vin.OtherAccidentCnt, vin.OtherAccidentCost, vin.isDisclosed,
            vinfo.vehicleNo
        FROM
            vehicles v
        LEFT JOIN
            vehicles_inspect vi ON v.vehicleId = vi.vehicleId
        LEFT JOIN
            vehicles_insurance vin ON v.vehicleId = vin.vehicleId
        LEFT JOIN
            vehicles_info vinfo ON v.vehicleId = vinfo.vehicleId
        LIMIT 1000;
    """
    with conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql)
            results = cursor.fetchall()
    return results

def calculate_score(vehicle: Dict, user_conditions: Dict) -> float:
    score = 0.0
    price = user_conditions.get('Price')
    weight_price = user_conditions.get('Weight_Price', 0)
    if price and vehicle['Price'] <= int(price): score += weight_price

    # 주행거리 (Mileage): 최대 주행거리 이하일 때 점수 부여
    year = user_conditions.get('Year')
    weight_year = user_conditions.get('Weight_Year', 0)
    if year and vehicle['Year'] >= int(year): score += weight_year

    # 주행거리 (Mileage): 최대 주행거리 이하일 때 점수 부여
    mileage = user_conditions.get('Mileage')
    weight_mileage = user_conditions.get('Weight_Mileage', 0)
    if mileage and vehicle['Mileage'] <= int(mileage): score += weight_mileage

    # 차종 (Category): 일치할 경우 점수 부여
    category = user_conditions.get('Category')
    weight_category = user_conditions.get('Weight_Category', 0)
    if category and category.lower() == (vehicle['Category'] or '').lower(): score += weight_category

    # 연료 (FuelType)
    fuel_type = user_conditions.get('FuelType')
    weight_fueltype = user_conditions.get('Weight_FuelType', 0)
    if fuel_type and fuel_type.lower() == (vehicle['FuelType'] or '').lower(): score += weight_fueltype

    # 변속기 (Transmission)
    transmission = user_conditions.get('Transmission')
    weight_transmission = user_conditions.get('Weight_Transmission', 0)
    if transmission and transmission.lower() == (vehicle['Transmission'] or '').lower(): score += weight_transmission

    # 사고 이력 (AccidentHistory) - Yes/No or 무관
    accident_history = user_conditions.get('AccidentHistory')
    weight_accident = user_conditions.get('Weight_AccidentHistory', 0)
    if accident_history:
        if accident_history.lower() == (vehicle.get('AccidentHistory') or '').lower():
            score += weight_accident

    # 보험 공개여부 (isDisclosed) - 0/1 or 무관
    is_disclosed = user_conditions.get('isDisclosed')
    weight_disclosed = user_conditions.get('Weight_isDisclosed', 0)
    if is_disclosed is not None and vehicle.get('isDisclosed') is not None:
        if int(is_disclosed) == int(vehicle['isDisclosed']): score += weight_disclosed

    return score

def get_top_recommendations(user_conditions: Dict, top_n: int = 5) -> List[Dict]:
    vehicles = fetch_vehicles_from_db()
    scored_vehicles = []
    for v in vehicles:
        total_score = calculate_score(v, user_conditions)
        v['score'] = total_score
        scored_vehicles.append(v)
    scored_vehicles.sort(key=lambda x: x['score'], reverse=True)
    return scored_vehicles[:top_n]
