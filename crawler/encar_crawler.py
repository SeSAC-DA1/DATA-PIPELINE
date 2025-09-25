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

BASE_URL = "https://api.encar.com/search/car/list/general"
DETAIL_URL = "https://fem.encar.com/cars/detail"

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
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "ko,ko-KR;q=0.9,en-US;q=0.8,en;q=0.7",
        "origin": "https://www.encar.com",
        "referer": "https://www.encar.com/",
        "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    })
    return s

def to_int_safe(x):
    """안전한 정수 변환"""
    if x is None:
        return 0
    if isinstance(x, (int, float)):
        return int(x)
    if isinstance(x, str):
        try:
            return int(float(x))
        except:
            return 0
    return 0

def parse_year(x) -> int:
    """연도 파싱"""
    if x is None:
        return 0
    s = str(x)
    m = re.search(r"(\d{4})", s)
    return int(m.group(1)) if m else 0

# =============================================================================
# 데이터 변환 함수들
# =============================================================================

def convert_encar_data_to_vehicle_record(encar_data: Dict[str, Any], detail_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """엔카 API 응답을 DB 테이블 구조에 맞는 차량 레코드로 변환"""
    
    # 연식 처리 (Year 필드에서)
    year = encar_data.get("Year", 0)
    if isinstance(year, float):
        year = int(year)
    
    # 차량 ID
    car_id = encar_data.get("Id", "")
    
    # 이미지 URL 처리
    photo = encar_data.get("Photo", "")
    if photo and not photo.startswith("http"):
        photo = f"https://ci.encar.com/carpicture{photo}"
    
    # 상세 정보에서 추출한 데이터
    vehicle_no = ""
    transmission = ""
    color_name = ""
    origin_price = 0
    cartype = "기타"  # 기본값
    
    if detail_info:
        vehicle_no = detail_info.get("vehicle_no", "") or ""
        transmission = detail_info.get("transmission", "") or ""
        color_name = detail_info.get("color_name", "") or ""
        origin_price = detail_info.get("origin_price", 0) or 0
        body_name = detail_info.get("body_name", "") or ""
        
        # bodyName을 cartype으로 사용
        if body_name:
            cartype = body_name
    
    record = {
        "VehicleId": None,
        "VehicleNo": vehicle_no,  # 상세 페이지에서 추출한 차량번호
        "CarSeq": car_id,
        "Platform": "encar",
        "Origin": "국산",  # 기본값, 필요시 추가 로직
        "CarType": cartype,
        "Manufacturer": encar_data.get("Manufacturer", ""),
        "Model": encar_data.get("Model", ""),
        "Generation": encar_data.get("Grade", ""),
        "Trim": encar_data.get("GradeDetail", ""),
        "FuelType": encar_data.get("FuelType", ""),
        "Transmission": transmission,  # 상세 페이지에서 추출
        "ColorName": color_name,  # 상세 페이지에서 추출
        "ModelYear": year,
        "FirstRegistrationDate": year,  # 연식과 동일하게 설정
        "Distance": to_int_safe(encar_data.get("Mileage", 0)),
        "Price": to_int_safe(encar_data.get("Price", 0)),
        "OriginPrice": origin_price,  # 상세 페이지에서 추출
        "SellType": "일반",  # 기본값
        "Location": encar_data.get("Location", ""),
        "DetailURL": f"{DETAIL_URL}/{car_id}?pageid=dc_carsearch&listAdvType=pic&carid={car_id}&view_type=normal",
        "Photo": photo
    }
    
    return record

# =============================================================================
# API 호출 함수들
# =============================================================================

def get_encar_total_count(session: Optional[requests.Session] = None) -> int:
    """전체 국산차 차량 수를 확인합니다."""
    s = session or build_session()
    
    params = {
        "count": "true",
        "q": "(And.Hidden.N._.CarType.Y.)",
        "inav": "|Metadata|Sort"
    }
    
    try:
        response = s.get(BASE_URL, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return data.get("Count", 0)
        else:
            print(f"[전체 차량 수 조회 오류] HTTP {response.status_code}")
            return 0
    except Exception as e:
        print(f"[전체 차량 수 조회 실패]: {e}")
        return 0

def get_encar_brand_count(brand: str, session: Optional[requests.Session] = None) -> int:
    """특정 브랜드의 차량 수를 확인합니다."""
    s = session or build_session()
    
    params = {
        "count": "true",
        "q": f"(And.Hidden.N._.(C.CarType.Y._.Manufacturer.{brand}.))",
        "inav": "|Metadata|Sort"
    }
    
    try:
        response = s.get(BASE_URL, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return data.get("Count", 0)
        else:
            print(f"[브랜드 차량 수 조회 오류] {brand}: HTTP {response.status_code}")
            return 0
    except Exception as e:
        print(f"[브랜드 차량 수 조회 실패] {brand}: {e}")
        return 0

def get_encar_modelgroup_count(brand: str, modelgroup: str, session: Optional[requests.Session] = None) -> int:
    """특정 브랜드의 특정 모델그룹 차량 수를 확인합니다."""
    s = session or build_session()
    
    params = {
        "count": "true",
        "q": f"(And.Hidden.N._.(C.CarType.Y._.(C.Manufacturer.{brand}._.ModelGroup.{modelgroup}.)))",
        "inav": "|Metadata|Sort"
    }
    
    try:
        response = s.get(BASE_URL, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return data.get("Count", 0)
        else:
            print(f"[모델그룹 차량 수 조회 오류] {brand} {modelgroup}: HTTP {response.status_code}")
            return 0
    except Exception as e:
        print(f"[모델그룹 차량 수 조회 실패] {brand} {modelgroup}: {e}")
        return 0

def get_encar_car_list(session: Optional[requests.Session] = None, page: int = 0, page_size: int = 20, brand: Optional[str] = None, model: Optional[str] = None, modelgroup: Optional[str] = None) -> Dict[str, Any]:
    """엔카 API에서 차량 목록을 가져옵니다."""
    s = session or build_session()
    
    # 기본 파라미터 (count와 inav 제거 - 실제 데이터 요청용)
    params = {
        "q": "(And.Hidden.N._.CarType.Y.)"
    }
    
    # 브랜드별/모델별/모델그룹별 필터링
    if brand and modelgroup:
        params["q"] = f"(And.Hidden.N._.(C.CarType.Y._.(C.Manufacturer.{brand}._.ModelGroup.{modelgroup}.)))"
        # 페이지네이션을 sr 파라미터로 설정
        start = page * page_size
        params["sr"] = f"|ModifiedDate|{start}|{page_size}"
    elif brand and model:
        params["q"] = f"(And.Hidden.N._.(C.CarType.Y._.Manufacturer.{brand}._.Model.{model}.))"
        # 페이지네이션을 sr 파라미터로 설정
        start = page * page_size
        params["sr"] = f"|ModifiedDate|{start}|{page_size}"
    elif brand:
        params["q"] = f"(And.Hidden.N._.(C.CarType.Y._.Manufacturer.{brand}.))"
        # 페이지네이션을 sr 파라미터로 설정
        start = page * page_size
        params["sr"] = f"|ModifiedDate|{start}|{page_size}"
    
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

def get_encar_detail_info(car_seq: str, session: Optional[requests.Session] = None) -> Dict[str, Any]:
    """엔카 상세 페이지에서 추가 정보를 추출합니다."""
    s = session or build_session()
    
    # 상세 페이지 URL
    detail_url = f"{DETAIL_URL}/{car_seq}?pageid=dc_carsearch&listAdvType=pic&carid={car_seq}&view_type=normal"
    
    try:
        response = s.get(detail_url, timeout=15)
        if response.status_code == 200:
            # __PRELOADED_STATE__에서 정보 추출
            pattern = r'__PRELOADED_STATE__\s*=\s*({.*?});'
            match = re.search(pattern, response.text, re.DOTALL)
            if match:
                try:
                    import json
                    preloaded_state = json.loads(match.group(1))
                    cars_base = preloaded_state.get("cars", {}).get("base", {})
                    
                    # 필요한 정보들 추출
                    options_data = cars_base.get("options", {})
                    standard_options = options_data.get("standard", [])
                    choice_options = options_data.get("choice", [])
                    etc_options = options_data.get("etc", [])
                    tuning_options = options_data.get("tuning", [])
                    
                    # 디버깅: 옵션 데이터 확인
                    if standard_options or choice_options or etc_options or tuning_options:
                        print(f"[상세페이지 옵션 발견] carSeq: {car_seq}, standard: {len(standard_options)}개, choice: {len(choice_options)}개, etc: {len(etc_options)}개, tuning: {len(tuning_options)}개")
                    
                    detail_info = {
                        "vehicle_no": cars_base.get("vehicleNo"),
                        "transmission": cars_base.get("spec", {}).get("transmissionName"),
                        "color_name": cars_base.get("spec", {}).get("colorName"),
                        "origin_price": cars_base.get("category", {}).get("originPrice"),
                        "body_name": cars_base.get("spec", {}).get("bodyName"),
                        "standard_options": standard_options,
                        "choice_options": choice_options,
                        "etc_options": etc_options,
                        "tuning_options": tuning_options
                    }
                    
                    return detail_info
                except json.JSONDecodeError as e:
                    print(f"[JSON 파싱 실패] carSeq: {car_seq}: {e}")
                    pass
            
            # 기존 방식도 시도 (fallback) - vehicleNo만
            pattern = r'"vehicleNo"\s*:\s*"([^"]+)"'
            match = re.search(pattern, response.text)
            if match:
                return {"vehicle_no": match.group(1)}
        
        return {}
    except Exception as e:
        print(f"[상세 정보 추출 실패] carSeq: {car_seq}: {e}")
        return {}

def get_encar_brands(session: Optional[requests.Session] = None) -> List[str]:
    """엔카에서 사용 가능한 브랜드 목록을 가져옵니다."""
    s = session or build_session()
    
    params = {
        "count": "true",
        "q": "(And.Hidden.N._.CarType.Y.)",
        "inav": "|Metadata|Sort"
    }
    
    try:
        response = s.get(BASE_URL, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            brands = []
            
            # iNav.Nodes[1].Facets[0].Refinements.Nodes[0].Facets에서 브랜드 정보 추출
            inav = data.get("iNav", {})
            nodes = inav.get("Nodes", [])
            
            if len(nodes) > 1:
                node1 = nodes[1]
                facets1 = node1.get("Facets", [])
                
                if len(facets1) > 0:
                    facet1 = facets1[0]  # "Y" 값의 facet
                    refinements = facet1.get("Refinements", {})
                    refinement_nodes = refinements.get("Nodes", [])
                    
                    if len(refinement_nodes) > 0:
                        facets2 = refinement_nodes[0].get("Facets", [])
                        
                        for facet in facets2:
                            brand_name = facet.get("Value", "")
                            brand_count = facet.get("Count", 0)
                            
                            if brand_name and brand_count > 0:
                                brands.append(brand_name)
            
            print(f"[브랜드 목록] {len(brands)}개 브랜드: {', '.join(brands)}")
            return brands
        else:
            print(f"[브랜드 조회 오류] HTTP {response.status_code}")
            return []
    except Exception as e:
        print(f"[브랜드 조회 실패]: {e}")
        return []

def get_encar_modelgroups_by_brand(brand: str, session: requests.Session) -> List[str]:
    """특정 브랜드의 모델그룹 목록을 가져옵니다."""
    # 카운트 전용 API로 모델그룹 정보를 추출
    params = {
        "count": "true",
        "q": f"(And.Hidden.N._.(C.CarType.Y._.Manufacturer.{brand}.))",
        "inav": "|Metadata|Sort"
    }
    
    try:
        response = session.get(BASE_URL, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            modelgroups = []
            
            # iNav.Nodes[1].Facets[0].Refinements.Nodes[0].Facets[0].Refinements.Nodes[0].Facets에서 모델그룹 정보 추출
            inav = data.get("iNav", {})
            nodes = inav.get("Nodes", [])
            
            if len(nodes) > 1:
                node1 = nodes[1]
                facets1 = node1.get("Facets", [])
                
                if len(facets1) > 0:
                    facet1 = facets1[0]  # "Y" 값의 facet
                    refinements1 = facet1.get("Refinements", {})
                    refinement_nodes1 = refinements1.get("Nodes", [])
                    
                    if len(refinement_nodes1) > 0:
                        ref_node1 = refinement_nodes1[0]
                        facets2 = ref_node1.get("Facets", [])
                        
                        if len(facets2) > 0:
                            facet2 = facets2[0]  # "현대" 브랜드 facet
                            refinements2 = facet2.get("Refinements", {})
                            refinement_nodes2 = refinements2.get("Nodes", [])
                            
                            if len(refinement_nodes2) > 0:
                                ref_node2 = refinement_nodes2[0]
                                facets3 = ref_node2.get("Facets", [])
                                
                                for facet in facets3:
                                    modelgroup_name = facet.get("Value", "")
                                    modelgroup_count = facet.get("Count", 0)
                                    
                                    if modelgroup_name and modelgroup_count > 0:
                                        modelgroups.append(modelgroup_name)
            
            print(f"[{brand} 모델그룹 추출] {len(modelgroups)}개 모델그룹 발견")
            return modelgroups
        else:
            print(f"[모델그룹 조회 오류] {brand}: HTTP {response.status_code}")
            return []
    except Exception as e:
        print(f"[모델그룹 조회 실패] {brand}: {e}")
        return []

# =============================================================================
# DB 저장 함수들
# =============================================================================

def save_encar_vehicles_to_db(vehicles_data: List[Dict[str, Any]]) -> int:
    """엔카 차량 데이터를 DB에 저장합니다."""
    if not vehicles_data:
        return 0
    
    with session_scope() as session:
        # 기존 carseq와 vehicleno 목록을 한 번에 조회
        car_seqs = [vehicle_data.get('CarSeq', '') for vehicle_data in vehicles_data if vehicle_data.get('CarSeq')]
        vehicle_nos = [vehicle_data.get('VehicleNo', '') for vehicle_data in vehicles_data if vehicle_data.get('VehicleNo')]
        
        # 현재 배치의 carseq만 체크 (이미 저장된 것들)
        existing_car_seqs = {str(car_seq) for car_seq in 
                           session.query(Vehicle.carseq).filter(Vehicle.carseq.in_(car_seqs)).all()}
        
        # 전체 DB에서 vehicleno 체크 (모든 기존 차량번호)
        existing_vehicle_nos = {vehicle_no for vehicle_no in 
                              session.query(Vehicle.vehicleno).filter(Vehicle.vehicleno.isnot(None)).all()}
        
        saved_count = 0
        skipped_count = 0
        options_saved_count = 0
        
        for vehicle_data in vehicles_data:
            car_seq = vehicle_data.get('CarSeq', '')
            vehicle_no = vehicle_data.get('VehicleNo', '')
            
            # carseq나 vehicleno가 이미 존재하면 건너뛰기
            if car_seq in existing_car_seqs or vehicle_no in existing_vehicle_nos:
                skipped_count += 1
                continue
            
            try:
                # 기존 차량이 있으면 건너뛰기
                existing_vehicle = session.query(Vehicle).filter(Vehicle.vehicleno == vehicle_no).first()
                
                if existing_vehicle:
                    # 기존 차량이 있으면 건너뛰기
                    skipped_count += 1
                    continue
                
                # 새 차량 생성
                vehicle = Vehicle(
                    carseq=car_seq,
                    vehicleno=vehicle_no,
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
                existing_vehicle_nos.add(vehicle_no)
                
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

# =============================================================================
# 크롤링 함수들
# =============================================================================

def crawl_encar_modelgroup(brand: str, modelgroup: str, session: requests.Session, max_pages: int = 100, page_size: int = 20, delay: float = 1.0) -> int:
    """특정 브랜드의 특정 모델그룹 차량을 크롤링합니다."""
    print(f"\n[모델그룹 크롤링 시작] {brand} {modelgroup}")
    
    total_processed = 0
    
    for page in range(max_pages):
        print(f"\n[{brand} {modelgroup} - 페이지 {page + 1}/{max_pages}] 크롤링 중...")
        
        # API 호출
        api_response = get_encar_car_list(session, page, page_size, brand=brand, modelgroup=modelgroup)
        
        if not api_response.get("SearchResults"):
            print(f"[{brand} {modelgroup} - 페이지 {page + 1}] 데이터 없음 - 크롤링 완료")
            break

        vehicles_data = []
        
        for encar_data in api_response["SearchResults"]:
            car_seq = encar_data.get("Id", "")
            
            # 1. 상세 페이지에서 정보 추출 (차량번호, 변속기, 색상, 출시가, 차량타입, 옵션)
            detail_info = get_encar_detail_info(car_seq, session)
            
            # 2. 차량 데이터 변환
            vehicle_record = convert_encar_data_to_vehicle_record(encar_data, detail_info)
            
            # 3. 옵션 정보 처리 (상세 페이지에서 추출한 옵션 사용)
            standard_options = detail_info.get("standard_options", [])
            choice_options = detail_info.get("choice_options", [])
            etc_options = detail_info.get("etc_options", [])
            tuning_options = detail_info.get("tuning_options", [])
            all_options = standard_options + etc_options + tuning_options
            
            # 디버깅: 옵션 추출 상태 확인
            if standard_options or etc_options or tuning_options:
                print(f"    [옵션 발견] carSeq: {car_seq}, standard: {len(standard_options)}개, etc: {len(etc_options)}개, tuning: {len(tuning_options)}개")
            
            # 옵션을 DB 형식으로 변환
            options = []
            for option_code in all_options:
                options.append({"option_code": option_code})
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
            print(f"[{brand} {modelgroup} - 페이지 {page + 1}] {saved_count}건 저장 완료")
        
        # 딜레이
        if page < max_pages - 1:
            time.sleep(delay)
    
    print(f"\n[{brand} {modelgroup} 크롤링 완료] 총 {total_processed}건 처리됨")
    return total_processed

def crawl_encar_with_options(max_pages: int = 100, page_size: int = 20, delay: float = 1.0, 
                           max_vehicles_per_brand: int = 10000):
    """엔카에서 차량 정보와 옵션을 크롤링합니다."""
    print("[엔카 크롤링 시작]")
    
    # 1. DB 테이블 생성
    print("[DB 테이블 확인 중...]")
    create_tables_if_not_exist()
    print("[DB 테이블 생성 완료] 모든 테이블이 준비되었습니다.")
    
    # 2. DB 상태 확인
    check_database_status()
    
    # 3. 옵션 사전 초기화
    print("[옵션 사전 초기화]")
    initialize_global_options()
    print("[공통 옵션 초기화 완료] 77개 옵션 저장")
    
    # 4. 전체 차량 수 확인
    session = build_session()
    total_count = get_encar_total_count(session)
    print(f"[전체 차량 수] {total_count:,}대")
    
    # 5. 브랜드 목록을 API에서 동적으로 가져오기
    print("[브랜드 목록 조회]")
    major_brands = get_encar_brands(session)
    
    if not major_brands:
        print("[브랜드 목록 조회 실패] 하드코딩된 브랜드 목록을 사용합니다.")
        major_brands = ["현대", "기아", "쉐보레", "르노삼성", "쌍용", "제네시스"]
    
    total_processed = 0
    
    for brand in major_brands:
        print(f"\n{'='*50}")
        print(f"[브랜드 분석] {brand}")
        
        # 브랜드별 차량 수 확인
        brand_count = get_encar_brand_count(brand, session)
        print(f"[{brand} 차량 수] {brand_count:,}대")
        
        if brand_count > max_vehicles_per_brand:
            print(f"[{brand}] {max_vehicles_per_brand:,}대 초과 - 모델그룹별 크롤링 시작")
            
            # 모델그룹 목록 가져오기
            modelgroups = get_encar_modelgroups_by_brand(brand, session)
            print(f"[{brand} 모델그룹 목록] {len(modelgroups)}개 모델그룹: {', '.join(modelgroups[:10])}{'...' if len(modelgroups) > 10 else ''}")
            
            # 각 모델그룹별로 크롤링
            for modelgroup in modelgroups:
                modelgroup_count = get_encar_modelgroup_count(brand, modelgroup, session)
                print(f"[{brand} {modelgroup} 차량 수] {modelgroup_count}대")
                
                if modelgroup_count > 0:
                    processed = crawl_encar_modelgroup(brand, modelgroup, session, max_pages, page_size, delay)
                    total_processed += processed
                    
                    # 딜레이
                    time.sleep(delay)
        else:
            print(f"[{brand}] {max_vehicles_per_brand:,}대 이하 - 브랜드별 직접 크롤링")
            # 브랜드별 직접 크롤링 (구현 필요시 추가)
            pass
    
    print(f"\n[엔카 크롤링 완료] 총 {total_processed:,}건 처리됨")
    return total_processed

# =============================================================================
# 메인 실행
# =============================================================================

if __name__ == "__main__":
    crawl_encar_with_options(max_pages=100, page_size=20, delay=1.0)
