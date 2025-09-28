import os, re, time, random, json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
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
DETAIL_API_URL = "https://api.encar.com/v1/readside/vehicle"
INSPECTION_API_URL = "https://api.encar.com/v1/readside/inspection/vehicle"
DETAIL_PAGE_URL = "https://fem.encar.com/cars/detail"

# =============================================================================
# 유틸리티 함수
# =============================================================================
def _sleep_with_jitter(base_delay: float = 0.5, jitter_range: float = 0.3) -> None:
    jitter = random.uniform(-jitter_range, jitter_range)
    time.sleep(max(0.1, base_delay + jitter))

def build_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(total=5, connect=3, read=3, backoff_factor=0.7, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries, pool_connections=50, pool_maxsize=50)
    s.mount("https://", adapter)

    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "ko,ko-KR;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Origin": "https://www.encar.com",
        "Referer": "https://www.encar.com/",
        "Priority": "u=1, i",
        "Sec-Ch-Ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site"
    })
    return s

# =============================================================================
# API 호출 함수
# =============================================================================
def get_encar_api_data(url: str, session: requests.Session, params: Optional[Dict] = None) -> Optional[Dict]:
    try:
        response = session.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        # 404는 흔한 경우이므로 간단히 None 반환
        if e.response and e.response.status_code == 404:
            print(f"[API 정보 없음] URL: {url}, HTTP 404")
        else:
            print(f"[API 호출 오류] URL: {url}, 오류: {e}")
        return None

def get_car_list(session: requests.Session, q_filter: str, page: int, page_size: int) -> List[Dict]:
    start = page * page_size
    params = {"q": q_filter, "sr": f"|ModifiedDate|{start}|{page_size}"}
    data = get_encar_api_data(BASE_URL, session, params=params)
    return data.get("SearchResults", []) if data else []

def fetch_vehicle_details(list_car_id: str, session: requests.Session) -> Optional[Dict]:
    """차량의 모든 상세 정보를 가져옵니다."""
    complete_info = get_encar_api_data(f"{DETAIL_API_URL}/{list_car_id}?include=CATEGORY,SPEC,OPTIONS,PHOTOS", session)
    if not complete_info: return None
    
    real_vehicle_id = complete_info.get("vehicleId")
    if not real_vehicle_id: return None

    inspection_info = get_encar_api_data(f"{INSPECTION_API_URL}/{real_vehicle_id}", session)
    if not inspection_info: return None
    
    return {"complete_info": complete_info, "inspection_info": inspection_info}

def get_encar_total_count(session: requests.Session) -> int:
    """전체 차량 수를 조회합니다."""
    try:
        params = {"count": "true", "q": "(And.Hidden.N._.CarType.Y.)", "inav": "|Metadata|Sort"}
        data = get_encar_api_data(BASE_URL, session, params=params)
        if data:
            count = data.get("Count", 0)
            print(f"[전체 차량 수] {count:,}대")
            return count
        else:
            print("[전체 차량 수 조회 실패]")
            return 0
    except Exception as e:
        print(f"[전체 차량 수 조회 오류] {e}")
        return 0

def get_encar_brand_count(session: requests.Session, brand: str) -> int:
    """특정 브랜드의 차량 수를 조회합니다."""
    try:
        params = {"count": "true", "q": f"(And.Hidden.N._.(C.CarType.Y._.Manufacturer.{brand}.))", "inav": "|Metadata|Sort"}
        data = get_encar_api_data(BASE_URL, session, params=params)
        if data:
            count = data.get("Count", 0)
            print(f"[{brand} 브랜드 차량 수] {count:,}대")
            return count
        else:
            print(f"[{brand} 브랜드 차량 수 조회 실패]")
            return 0
    except Exception as e:
        print(f"[{brand} 브랜드 차량 수 조회 오류] {e}")
        return 0

def get_encar_modelgroup_count(session: requests.Session, brand: str, modelgroup: str) -> int:
    """특정 모델그룹의 차량 수를 조회합니다."""
    try:
        params = {"count": "true", "q": f"(And.Hidden.N._.(C.CarType.Y._.(C.Manufacturer.{brand}._.ModelGroup.{modelgroup}.)))", "inav": "|Metadata|Sort"}
        data = get_encar_api_data(BASE_URL, session, params=params)
        if data:
            count = data.get("Count", 0)
            print(f"[{brand} {modelgroup} 모델그룹 차량 수] {count:,}대")
            return count
        else:
            print(f"[{brand} {modelgroup} 모델그룹 차량 수 조회 실패]")
            return 0
    except Exception as e:
        print(f"[{brand} {modelgroup} 모델그룹 차량 수 조회 오류] {e}")
        return 0

def get_encar_car_list(session: requests.Session, page: int, page_size: int, brand: str = None, modelgroup: str = None) -> Dict:
    """차량 목록을 조회합니다."""
    try:
        start = page * page_size
        
        # 필터 조건 구성
        if brand and modelgroup:
            q_filter = f"(And.Hidden.N._.(C.CarType.Y._.(C.Manufacturer.{brand}._.ModelGroup.{modelgroup}.)))"
        elif brand:
            q_filter = f"(And.Hidden.N._.(C.CarType.Y._.Manufacturer.{brand}.))"
        else:
            q_filter = "(And.Hidden.N._.CarType.Y.)"
        
        params = {"q": q_filter, "sr": f"|ModifiedDate|{start}|{page_size}"}
        data = get_encar_api_data(BASE_URL, session, params=params)
        
        if data:
            return {
                "SearchResults": data.get("SearchResults", []),
                "Count": data.get("Count", 0)
            }
        else:
            return {"SearchResults": [], "Count": 0}
    except Exception as e:
        print(f"[차량 목록 조회 오류] {e}")
        return {"SearchResults": [], "Count": 0}

def get_encar_brands(session: requests.Session) -> List[str]:
    """브랜드 목록을 조회합니다."""
    try:
        params = {"count": "true", "q": "(And.Hidden.N._.CarType.Y.)", "inav": "|Metadata|Sort"}
        data = get_encar_api_data(BASE_URL, session, params=params)
        if not data: return []
        
        try:
            brand_facets = data['iNav']['Nodes'][1]['Facets'][0]['Refinements']['Nodes'][0]['Facets']
            brands = [f['Value'] for f in brand_facets if f.get("Count", 0) > 0]
            print(f"[브랜드 목록] {len(brands)}개 브랜드 발견")
            return brands
        except (KeyError, IndexError):
            print("[브랜드 파싱 실패]")
            return []
    except Exception as e:
        print(f"[브랜드 목록 조회 오류] {e}")
        return []

def get_encar_modelgroups_by_brand(brand: str, session: requests.Session) -> List[str]:
    """특정 브랜드의 모델그룹 목록을 조회합니다."""
    try:
        params = {"count": "true", "q": f"(And.Hidden.N._.(C.CarType.Y._.Manufacturer.{brand}.))", "inav": "|Metadata|Sort"}
        data = get_encar_api_data(BASE_URL, session, params=params)
        if not data: return []
        
        try:
            brand_facet = next((f for f in data['iNav']['Nodes'][1]['Facets'][0]['Refinements']['Nodes'][0]['Facets'] if f['Value'] == brand), None)
            if not brand_facet: return []
            modelgroup_facets = brand_facet['Refinements']['Nodes'][0]['Facets']
            modelgroups = [f['Value'] for f in modelgroup_facets if f.get("Count", 0) > 0]
            print(f"[{brand} 모델그룹 추출] {len(modelgroups)}개 발견")
            return modelgroups
        except (KeyError, IndexError, StopIteration):
            print(f"[{brand} 모델그룹 파싱 실패]")
            return []
    except Exception as e:
        print(f"[{brand} 모델그룹 조회 오류] {e}")
        return []

# =============================================================================
# 데이터 변환 및 저장
# =============================================================================
def convert_to_vehicle_record(encar_data: Dict, details: Dict) -> Optional[Dict]:
    try:
        complete_info = details["complete_info"]
        inspection_info = details["inspection_info"]
        real_vehicle_id = str(complete_info["vehicleId"])
        
        spec = complete_info.get("spec", {})
        category = complete_info.get("category", {})
        inspection_master = inspection_info.get("master", {}).get("detail", {})
        first_reg_date_str = str(inspection_master.get("firstRegistrationDate", "0")).replace("-", "")
        
        return {
            "VehicleNo": complete_info.get("vehicleNo"),
            "CarSeq": real_vehicle_id,
            "Platform": "encar",
            "Origin": "국산",
            "CarType": spec.get("bodyName"),
            "Manufacturer": category.get("manufacturerName"),
            "Model": category.get("modelName"),
            "Generation": category.get("modelGroupName"),
            "Trim": category.get("gradeName"),
            "FuelType": spec.get("fuelName"),
            "Transmission": spec.get("transmissionName"),
            "Displacement": int(spec.get("displacement") or 0),
            "ColorName": spec.get("colorName"),
            "ModelYear": int(category.get("formYear") or 0),
            "FirstRegistrationDate": int(first_reg_date_str) if first_reg_date_str.isdigit() else 0,
            "Distance": int(spec.get("mileage") or 0),
            "Price": int(encar_data.get("Price") or 0),
            "OriginPrice": int(category.get("originPrice") or 0),
            "SellType": encar_data.get("SellType"),
            "Location": encar_data.get("OfficeCityState"),
            "DetailURL": f"{DETAIL_PAGE_URL}/{real_vehicle_id}",
            "Photo": f"https://ci.encar.com{encar_data['Photo']}" if encar_data.get("Photo") and encar_data['Photo'].startswith('/carpicture') else encar_data.get("Photo"),
            "options": complete_info.get("options", {}).get("standard", [])
        }
    except (KeyError, TypeError) as e:
        print(f"  [데이터 변환 오류] 필수 키 누락: {e}")
        return None

def save_data_to_db(records: List[Dict]):
    if not records: return 0
    with session_scope() as session:
        try:
            vehicle_mappings = [{k: v for k, v in rec.items() if k != 'options'} for rec in records]
            session.bulk_insert_mappings(Vehicle, vehicle_mappings)
            
            vehicle_map = {v.carseq: v.vehicleid for v in session.query(Vehicle.vehicleid, Vehicle.carseq).filter(Vehicle.carseq.in_([rec['CarSeq'] for rec in records]))}
            all_option_codes = {code for rec in records for code in rec.get('options', [])}
            option_master_map = {opt.option_code: opt.option_id for opt in session.query(OptionMaster).filter(OptionMaster.option_code.in_(all_option_codes))}

            options_to_save = []
            for rec in records:
                vehicle_id = vehicle_map.get(rec['CarSeq'])
                if vehicle_id:
                    global_codes = convert_platform_options_to_global(rec.get('options', []), 'encar')
                    for code in global_codes:
                        option_id = option_master_map.get(code)
                        if option_id:
                            options_to_save.append({'vehicle_id': vehicle_id, 'option_id': option_id})
            
            if options_to_save:
                session.bulk_insert_mappings(VehicleOption, options_to_save)
            
            print(f"  [DB 저장] {len(records)}대 차량, {len(options_to_save)}개 옵션 저장 완료")
            return len(records)
        except Exception as e:
            print(f"  [DB 배치 저장 오류] {e}")
            session.rollback()
            return 0

# =============================================================================
# 크롤링 로직
#==============================================================================
def crawl_encar_modelgroup(brand: str, modelgroup: str, session: requests.Session, existing_data: Dict[str, set], max_pages: int = 1000, page_size: int = 50):
    """특정 모델그룹 크롤링 (선-필터링 및 병렬 처리, 최종 중복 제거 적용)"""
    print(f"\n[모델그룹 크롤링 시작] {brand} {modelgroup}")
    
    total_processed_for_modelgroup = 0
    
    for page in range(max_pages):
        q_filter = f"(And.Hidden.N._.(C.CarType.Y._.(C.Manufacturer.{brand}._.ModelGroup.{modelgroup}.)))"
        car_list = get_car_list(session, q_filter, page, page_size)
        
        if not car_list:
            print(f"  [{brand} {modelgroup} - 페이지 {page + 1}] 데이터 없음. 완료.")
            break
        
        new_cars_to_process = [car for car in car_list if car.get("Id") and str(car["Id"]) not in existing_data['list_ids']]
        
        skipped_count = len(car_list) - len(new_cars_to_process)
        print(f"  [{brand} {modelgroup} - 페이지 {page + 1}] {len(car_list)}대 중 {skipped_count}대 중복(목록ID), {len(new_cars_to_process)}대 신규 처리 시작...")
        
        if not new_cars_to_process:
            _sleep_with_jitter(0.2, 0.1)
            continue

        processed_records = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_car = {executor.submit(fetch_vehicle_details, car["Id"], session): car for car in new_cars_to_process}
            
            for future in as_completed(future_to_car):
                encar_data = future_to_car[future]
                try:
                    details = future.result()
                    if details:
                        record = convert_to_vehicle_record(encar_data, details)
                        if record:
                            processed_records.append(record)
                except Exception as e:
                    print(f"  [병렬 처리 오류] Car ID {encar_data.get('Id', 'N/A')}: {e}")

        # 병렬 처리 후, DB 저장 전에 배치 내/외부의 모든 중복을 최종 제거
        final_records_to_save = []
        seen_in_batch = set()

        for record in processed_records:
            car_seq = record['CarSeq']
            vehicle_no = record['VehicleNo']
            
            # DB에 이미 있는 데이터인지 최종 확인
            if car_seq in existing_data['car_seqs'] or (vehicle_no and vehicle_no in existing_data['vehicle_nos']):
                continue

            # 현재 처리중인 배치 내에서 중복인지 확인 (차량번호 기준)
            if vehicle_no and vehicle_no in seen_in_batch:
                continue

            # 모든 중복 체크를 통과한 경우에만 최종 목록에 추가
            final_records_to_save.append(record)
            if vehicle_no:
                seen_in_batch.add(vehicle_no)
        
        print(f"  [최종 필터링] {len(processed_records)}건 → {len(final_records_to_save)}건 (중복 제거)")

        if final_records_to_save:
            saved_count = save_data_to_db(final_records_to_save)
            total_processed_for_modelgroup += saved_count
            
            # 새로 저장된 정보를 기존 데이터 세트에 실시간으로 추가
            for rec in final_records_to_save:
                original_id = next((car['Id'] for car in new_cars_to_process if str(car.get("Id")) == rec["CarSeq"]), rec["CarSeq"])
                existing_data['list_ids'].add(original_id)
                existing_data['car_seqs'].add(rec['CarSeq'])
                if rec['VehicleNo']:
                    existing_data['vehicle_nos'].add(rec['VehicleNo'])
        
        _sleep_with_jitter(1.0, 0.5)
        
    return total_processed_for_modelgroup

def crawl_encar_with_options(max_pages_per_modelgroup: int = 1000, page_size: int = 50):
    """엔카 크롤러 메인 함수"""
    print("[엔카 크롤링 시작]")
    
    create_tables_if_not_exist()
    if not check_database_status(): return
    initialize_global_options()
    
    session = build_session()
    
    total_count_data = get_encar_api_data(BASE_URL, session, params={"count": "true", "q": "(And.Hidden.N._.CarType.Y.)"})
    print(f"[전체 차량 수] {total_count_data.get('Count', 0):,}대")
    
    with session_scope() as db_session:
        # DB의 carseq를 문자열(str)로 조회해야 api에서 주는 데이터가 str이라 중복체크할때 문제 없음
        existing_car_seqs = {str(r[0]) for r in db_session.query(Vehicle.carseq).filter(Vehicle.platform == 'encar').all() if r[0]}
        existing_vehicle_nos = {r[0] for r in db_session.query(Vehicle.vehicleno).filter(Vehicle.vehicleno.isnot(None)).all()}
    
    #  목록 ID(list_ids)도 중복 체크 대상에 포함/ list_ids는 같은 차량이 다른 광고 id로 올라와서 추적해야 할때 사용
    existing_data = {'car_seqs': existing_car_seqs, 'vehicle_nos': existing_vehicle_nos, 'list_ids': set(existing_car_seqs)}
    print(f"[DB 확인] 기존 엔카 차량 {len(existing_data['car_seqs']):,}대, 차량번호 {len(existing_data['vehicle_nos']):,}대")
    
    major_brands = get_encar_brands(session)
    if not major_brands:
        print("[브랜드 목록 조회 실패] 크롤링 종료.")
        return

    for brand in major_brands:
        print(f"\n{'='*50}\n[브랜드 처리 시작] {brand}")
        modelgroups = get_encar_modelgroups_by_brand(brand, session)
        if not modelgroups:
            print(f"  [{brand}] 모델그룹 없음. 건너뜁니다.")
            continue
            
        for modelgroup in modelgroups:
            modelgroup_count_data = get_encar_api_data(BASE_URL, session, params={"count": "true", "q": f"(And.Hidden.N._.(C.CarType.Y._.(C.Manufacturer.{brand}._.ModelGroup.{modelgroup}.)))"})
            modelgroup_count = modelgroup_count_data.get("Count", 0) if modelgroup_count_data else 0
            
            if modelgroup_count > 0:
                required_pages = (modelgroup_count + page_size - 1) // page_size
                crawl_encar_modelgroup(brand, modelgroup, session, existing_data, required_pages, page_size)

    print(f"\n[엔카 크롤링 최종 완료] 현재 DB의 엔카 차량: {len(existing_data['car_seqs']):,}대")

# =============================================================================
# 메인 실행
# =============================================================================
if __name__ == "__main__":
    crawl_encar_with_options()