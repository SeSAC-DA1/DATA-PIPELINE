import os, re, time, json
import pandas as pd
import requests
from requests.adapters import HTTPAdapter, Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

# 프로젝트 루트 경로 추가
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import session_scope
from db.model import Vehicle, OptionMaster, VehicleOption, create_tables_if_not_exist, check_database_status
from crawler.option_mapping import initialize_global_options, convert_platform_options_to_global

# =============================================================================
# 상수 및 설정
# =============================================================================

# 새로운 Encar API 엔드포인트 (general 사용)
BASE_URL = "https://api.encar.com/search/car/list/general"
DETAIL_URL = "https://fem.encar.com/cars/detail"
READSIDE_URL = "https://api.encar.com/v1/readside/vehicle"

# 엔카 API 파라미터
DEFAULT_PARAMS = {
    "count": "true",
    "q": "(And.Hidden.N._.CarType.Y.)",
    "inav": "|Metadata|Sort"
}

# =============================================================================
# 유틸리티 함수들
# =============================================================================

def build_session() -> requests.Session:
    """세션 생성 및 설정"""
    s = requests.Session()
    retries = Retry(
        total=5, connect=3, read=3, backoff_factor=0.7,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko,ko-KR;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.encar.com/",
    })
    return s

def to_int_safe(x):
    """안전한 정수 변환"""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return 0
    if isinstance(x, (int, float)):
        try:
            return int(x)
        except Exception:
            return 0
    if isinstance(x, str):
        m = re.findall(r"\d+", x.replace(",", ""))
        return int("".join(m)) if m else 0
    return 0

def parse_year(x) -> int:
    """문자열에서 연식(YYYY) 추출"""
    if x is None:
        return 0
    if isinstance(x, (int, float)) and not pd.isna(x):
        try:
            return int(x)
        except Exception:
            return 0
    s = str(x)
    m = re.search(r"(\d{4})", s)
    return int(m.group(1)) if m else 0

def convert_encar_data_to_vehicle_record(encar_data: Dict[str, Any], vehicle_no: Optional[str] = None, additional_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """엔카 API 응답을 DB 테이블 구조에 맞는 차량 레코드로 변환"""
    
    # 연식 처리 (Year 필드에서)
    year = encar_data.get("Year", 0)
    if isinstance(year, float):
        year = int(year)
    
    # 최초등록일 처리 (FormYear 필드에서)
    form_year = encar_data.get("FormYear", "")
    first_reg_date = 0
    if form_year and form_year.isdigit():
        first_reg_date = int(form_year)
    
    # 주행거리 처리 (Mileage 필드에서)
    mileage = encar_data.get("Mileage", 0)
    if isinstance(mileage, float):
        mileage = int(mileage)
    
    # 가격 처리 (Price 필드에서)
    price = encar_data.get("Price", 0)
    if isinstance(price, float):
        price = int(price)
    
    # 이미지 URL 처리
    photo = encar_data.get("Photo", "")
    if photo and not photo.startswith("http"):
        photo = f"https://www.encar.com{photo}"
    
    # 상세 URL 생성
    car_id = encar_data.get("Id", "")
    detail_url = f"{DETAIL_URL}/{car_id}?pageid=dc_carsearch&listAdvType=pic&carid={car_id}&view_type=normal" if car_id else ""
    
    # 추가 정보 처리
    origin_price = 0
    color_name = ""
    if additional_info:
        origin_price = additional_info.get("origin_price", 0) or 0
        color_name = additional_info.get("color_name", "") or ""
    
    record = {
        "VehicleId": None,
        "VehicleNo": vehicle_no,  # 상세 페이지에서 추출한 차량번호
        "CarSeq": car_id,
        "Platform": "encar",
        "Origin": "국산",  # 기본값, 필요시 추가 로직
        "CarType": "기타",  # 기본값, 필요시 추가 로직
        "Manufacturer": encar_data.get("Manufacturer", ""),
        "Model": encar_data.get("Model", ""),
        "Generation": encar_data.get("Badge", ""),
        "Trim": encar_data.get("BadgeDetail", ""),
        "FuelType": encar_data.get("FuelType", ""),
        "Transmission": encar_data.get("Transmission", ""),
        "ColorName": color_name,  # Readside API에서 추출한 색상
        "ModelYear": year,
        "FirstRegistrationDate": first_reg_date,
        "Distance": mileage,
        "Price": price,
        "OriginPrice": origin_price,  # Readside API에서 추출한 출시가
        "SellType": encar_data.get("SellType", "일반"),
        "Location": encar_data.get("OfficeCityState", ""),
        "DetailURL": detail_url,
        "Photo": photo,
    }
    return record

def get_encar_car_list(session: Optional[requests.Session] = None, page: int = 0, page_size: int = 20) -> Dict[str, Any]:
    """엔카 API에서 차량 목록을 가져옵니다."""
    s = session or build_session()
    
    params = DEFAULT_PARAMS.copy()
    # 페이지네이션 파라미터 추가
    params["page"] = page
    params["size"] = page_size
    
    try:
        response = s.get(BASE_URL, params=params, timeout=15)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"[엔카 API 오류] HTTP {response.status_code}")
            return {"Count": 0, "SearchResults": []}
    except Exception as e:
        print(f"[엔카 API 요청 실패]: {e}")
        return {"Count": 0, "SearchResults": []}

def get_encar_vehicle_no(car_seq: str, session: Optional[requests.Session] = None) -> Optional[str]:
    """엔카 상세 페이지에서 차량번호를 추출합니다."""
    s = session or build_session()
    
    # 상세 페이지 URL
    detail_url = f"{DETAIL_URL}/{car_seq}?pageid=dc_carsearch&listAdvType=pic&carid={car_seq}&view_type=normal"
    
    try:
        response = s.get(detail_url, timeout=15)
        if response.status_code == 200:
            # HTML에서 vehicleNo 추출
            pattern = r'"vehicleNo"\s*:\s*"([^"]+)"'
            match = re.search(pattern, response.text)
            if match:
                return match.group(1)
        return None
    except Exception as e:
        print(f"[차량번호 추출 실패] carSeq: {car_seq}: {e}")
        return None

def get_encar_additional_info(car_seq: str, session: Optional[requests.Session] = None) -> Dict[str, Any]:
    """엔카 Readside API에서 추가 정보를 가져옵니다."""
    s = session or build_session()
    
    # Readside API URL
    readside_url = f"{READSIDE_URL}/{car_seq}?include=CATEGORY,SPEC"
    
    try:
        response = s.get(readside_url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            origin_price = data.get("category", {}).get("originPrice")
            color_name = data.get("spec", {}).get("colorName")
            
            # OriginPrice 정수 변환
            if isinstance(origin_price, str):
                try:
                    origin_price = int(origin_price.replace(",", "").strip())
                except:
                    origin_price = None
            
            return {
                "origin_price": origin_price,
                "color_name": color_name.strip()[:50] if color_name else None
            }
        return {"origin_price": None, "color_name": None}
    except Exception as e:
        print(f"[추가 정보 조회 실패] carSeq: {car_seq}: {e}")
        return {"origin_price": None, "color_name": None}

def get_encar_car_options(car_id: str, session: Optional[requests.Session] = None) -> List[Dict[str, Any]]:
    """엔카에서 특정 차량의 옵션 정보를 가져옵니다."""
    # 현재는 옵션 정보를 제공하지 않음
    return []

def save_encar_vehicles_to_db(vehicles_data: List[Dict[str, Any]]) -> int:
    """엔카 차량 데이터를 DB에 저장합니다."""
    if not vehicles_data:
        return 0
    
    with session_scope() as session:
        # 기존 차량 ID들을 한 번에 조회 (최적화)
        existing_car_seqs = {row[0] for row in session.query(Vehicle.carseq).filter(Vehicle.platform == "encar").all()}
        print(f"[기존 DB] 저장된 엔카 차량 ID: {len(existing_car_seqs)}개")
        
        # 세션 롤백 상태 초기화
        try:
            session.rollback()
        except:
            pass
        
        saved_count = 0
        skipped_count = 0
        options_saved_count = 0
        
        for vehicle_data in vehicles_data:
            car_seq = vehicle_data.get('CarSeq', '')
            
            if car_seq in existing_car_seqs:
                skipped_count += 1
                continue
            
            try:
                vehicle = Vehicle(
                    carseq=car_seq,
                    vehicleno=vehicle_data.get('VehicleNo'),  # 실제 차량번호 또는 None
                    platform=vehicle_data.get('Platform', 'encar'),
                    origin=vehicle_data.get('Origin', ''),
                    cartype=vehicle_data.get('CarType', ''),
                    manufacturer=vehicle_data.get('Manufacturer', ''),
                    model=vehicle_data.get('Model', ''),
                    generation=vehicle_data.get('Generation', ''),
                    trim=vehicle_data.get('Trim', ''),
                    fueltype=vehicle_data.get('FuelType', ''),
                    transmission=vehicle_data.get('Transmission', ''),
                    colorname=vehicle_data.get('ColorName', ''),
                    modelyear=int(vehicle_data.get('ModelYear', 0)),
                    firstregistrationdate=int(vehicle_data.get('FirstRegistrationDate', 0)),
                    distance=int(vehicle_data.get('Distance', 0)),
                    price=int(vehicle_data.get('Price', 0)),
                    originprice=int(vehicle_data.get('OriginPrice', 0)),
                    selltype=vehicle_data.get('SellType', ''),
                    location=vehicle_data.get('Location', ''),
                    detailurl=vehicle_data.get('DetailURL', ''),
                    photo=vehicle_data.get('Photo', '')
                )
                
                session.add(vehicle)
                session.flush()
                saved_count += 1
                existing_car_seqs.add(car_seq)
                
                # 옵션 정보 저장
                options = vehicle_data.get('options', [])
                if options and vehicle.vehicleid:
                    options_saved = save_vehicle_options_single(vehicle.vehicleid, options, session, 'encar')
                    options_saved_count += options_saved
                    
            except Exception as e:
                print(f"[저장 실패] carseq: {car_seq}: {e}")
                session.rollback()  # 개별 실패 시 롤백
                skipped_count += 1
        
        print(f"[DB 저장 완료] 차량: {saved_count}건 저장, {skipped_count}건 건너뜀, 공통 옵션: {options_saved_count}개 저장")
        return saved_count

def save_vehicle_options_single(vehicle_id: int, options: List[Dict[str, Any]], session, platform: str = 'encar') -> int:
    """개별 차량 옵션을 DB에 저장 (기존 세션 사용, 최적화됨)"""
    if not options:
        return 0
    
    try:
        # 플랫폼별 옵션 코드 추출 및 공통 옵션 코드로 변환
        platform_codes = [option.get('option_code', '') for option in options if option.get('option_code')]
        global_codes = convert_platform_options_to_global(platform_codes, platform)
        
        if not global_codes:
            return 0
        
        # 옵션 마스터를 한 번에 조회
        option_masters = {opt.option_code: opt.option_id for opt in 
                         session.query(OptionMaster).filter(OptionMaster.option_code.in_(global_codes)).all()}
        
        # 기존 VehicleOption들을 한 번에 조회
        existing_option_ids = {vo.option_id for vo in 
                              session.query(VehicleOption.option_id).filter(VehicleOption.vehicle_id == vehicle_id).all()}
        
        # 저장할 옵션들 준비
        saved_count = 0
        for option_code in global_codes:
            option_id = option_masters.get(option_code)
            if option_id and option_id not in existing_option_ids:
                vehicle_option = VehicleOption(vehicle_id=vehicle_id, option_id=option_id)
                session.add(vehicle_option)
                existing_option_ids.add(option_id)  # 중복 방지
                saved_count += 1
        
        return saved_count
        
    except Exception as e:
        print(f"[개별 옵션 저장 오류] vehicle_id: {vehicle_id}: {e}")
        return 0

def crawl_encar_with_options(max_pages: int = 100, page_size: int = 20, delay: float = 1.0):
    """엔카 차량 정보와 옵션을 크롤링합니다."""
    print("[엔카 크롤링 시작]")
    
    # 1. DB 테이블 생성 확인
    create_tables_if_not_exist()
    
    # 2. DB 상태 확인
    db_status = check_database_status()
    if not db_status:
        print("[DB 연결 실패] 데이터베이스 연결을 확인해주세요.")
        return
    
    # 3. 옵션 사전 초기화
    print("[옵션 사전 초기화]")
    initialize_global_options()
    
    # 4. 세션 생성
    session = build_session()
    
    total_processed = 0
    
    for page in range(max_pages):
        print(f"\n[페이지 {page + 1}/{max_pages}] 크롤링 중...")
        
        # API에서 차량 목록 가져오기
        api_response = get_encar_car_list(session, page, page_size)
        
        if not api_response.get("SearchResults"):
            print(f"[페이지 {page + 1}] 데이터 없음 - 크롤링 완료")
            break

        vehicles_data = []
        
        for encar_data in api_response["SearchResults"]:
            car_seq = encar_data.get("Id", "")
            
            # 1. 차량번호 추출
            vehicle_no = get_encar_vehicle_no(car_seq, session)
            
            # 2. 추가 정보 수집 (출시가, 색상)
            additional_info = get_encar_additional_info(car_seq, session)
            
            # 3. 차량 데이터 변환
            vehicle_record = convert_encar_data_to_vehicle_record(encar_data, vehicle_no, additional_info)
            
            # 4. 옵션 정보 가져오기 (현재는 빈 리스트)
            car_id = encar_data.get("Id", "")
            options = get_encar_car_options(car_id, session)
            vehicle_record['options'] = options
            
            vehicles_data.append(vehicle_record)
            
            print(f"  [완료] {vehicle_record['Manufacturer']} {vehicle_record['Model']} {vehicle_record['Generation']} | "
                  f"가격: {vehicle_record['Price']}만원, 주행거리: {vehicle_record['Distance']:,}km, "
                  f"차량번호: {'OK' if vehicle_record['VehicleNo'] else 'NO'}, "
                  f"출시가: {vehicle_record['OriginPrice']}만원, 색상: {vehicle_record['ColorName'] or 'N/A'}, "
                  f"이미지: {'OK' if vehicle_record['Photo'] else 'NO PHOTO'}, 옵션: {len(options)}개")
        
        # DB에 저장
        if vehicles_data:
            saved_count = save_encar_vehicles_to_db(vehicles_data)
            total_processed += saved_count
            print(f"[페이지 {page + 1}] {saved_count}건 저장 완료")
        
        # 딜레이
        if page < max_pages - 1:
            time.sleep(delay)
    
    print(f"\n[엔카 크롤링 완료] 총 {total_processed}건 처리됨")

# =============================================================================
# 메인 실행
# =============================================================================

if __name__ == "__main__":
    # 엔카 크롤링 실행
    crawl_encar_with_options(max_pages=10, page_size=20, delay=1.0)