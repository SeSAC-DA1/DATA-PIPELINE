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
from db.model import Vehicle, OptionMaster, VehicleOption, InsuranceHistory, Inspection, InspectionDetail, create_tables_if_not_exist, check_database_status
from crawler.option_mapping import initialize_global_options, convert_platform_options_to_global
from crawler.inspection_mapping import normalize_status, normalize_rank, normalize_damage_types

# =============================================================================
# 상수 및 설정
# =============================================================================
BASE_URL = "https://api.encar.com/search/car/list/general"
DETAIL_API_URL = "https://api.encar.com/v1/readside/vehicle"
INSPECTION_API_URL = "https://api.encar.com/v1/readside/inspection/vehicle"
DETAIL_PAGE_URL = "https://fem.encar.com/cars/detail"
RECORD_API_URL = "https://api.encar.com/v1/readside/record/vehicle"

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
        # 404는 정상적인 경우이므로 출력하지 않음
        if e.response and e.response.status_code != 404:
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
    if not complete_info: 
        return None
    
    real_vehicle_id = complete_info.get("vehicleId")
    vehicle_no = complete_info.get("vehicleNo")
    if not real_vehicle_id or not vehicle_no: 
        return None

    # record_info API 시도
    record_info = get_encar_api_data(f"{RECORD_API_URL}/{real_vehicle_id}/open", session, params={"vehicleNo": vehicle_no})
    
    # record_info가 없으면 차량검사 API 시도
    if not record_info:
        inspection_info = get_encar_api_data(f"{INSPECTION_API_URL}/{real_vehicle_id}", session)
        if inspection_info:
            record_info = {
                "firstDate": inspection_info.get("firstRegistrationDate", "0"),
                "inspectionData": inspection_info
            }
        else:
            # 두 API 모두 실패한 경우에만 출력
            print(f"  [API 실패] carseq: {real_vehicle_id} - record_info와 차량검사 API 모두 실패")
            record_info = {}
    
    return {"complete_info": complete_info, "record_info": record_info}

def get_encar_brands(session: requests.Session, car_type: str = "Y") -> List[str]:
    """브랜드 목록을 조회합니다. car_type: Y(국산), N(수입)"""
    try:
        params = {"count": "true", "q": f"(And.Hidden.N._.CarType.{car_type}.)", "inav": "|Metadata|Sort"}
        data = get_encar_api_data(BASE_URL, session, params=params)
        if not data: 
            return []
        
        brand_facets = data['iNav']['Nodes'][1]['Facets'][0]['Refinements']['Nodes'][0]['Facets']
        brands = [f['Value'] for f in brand_facets if f.get("Count", 0) > 0]
        origin_type = "국산" if car_type == "Y" else "수입"
        print(f"[{origin_type} 브랜드] {len(brands)}개")
        return brands
    except Exception:
        return []

def get_encar_modelgroups_by_brand(brand: str, session: requests.Session, car_type: str = "Y") -> List[str]:
    """특정 브랜드의 모델그룹 목록을 조회합니다. car_type: Y(국산), N(수입)"""
    try:
        params = {"count": "true", "q": f"(And.Hidden.N._.(C.CarType.{car_type}._.Manufacturer.{brand}.))", "inav": "|Metadata|Sort"}
        data = get_encar_api_data(BASE_URL, session, params=params)
        if not data: 
            return []
        
        brand_facet = next((f for f in data['iNav']['Nodes'][1]['Facets'][0]['Refinements']['Nodes'][0]['Facets'] if f['Value'] == brand), None)
        if not brand_facet: 
            return []
        modelgroup_facets = brand_facet['Refinements']['Nodes'][0]['Facets']
        modelgroups = [f['Value'] for f in modelgroup_facets if f.get("Count", 0) > 0]
        return modelgroups
    except Exception:
        return []

# =============================================================================
# 데이터 변환 및 저장
# =============================================================================
def convert_to_vehicle_record(encar_data: Dict, details: Dict, car_type: str = "Y") -> Optional[Dict]:
    try:
        complete_info = details["complete_info"]
        record_info = details["record_info"]
        real_vehicle_id = str(complete_info["vehicleId"])
        
        spec = complete_info.get("spec", {})
        category = complete_info.get("category", {})
        
        # firstDate 처리
        first_date = record_info.get("firstDate", "0")
        if not first_date or first_date == "0":
            inspection_data = record_info.get("inspectionData", {})
            first_date = inspection_data.get("firstRegistrationDate", "0")
        
        first_reg_date_str = str(first_date).replace("-", "")
        
        # 옵션 데이터 수집
        options_data = complete_info.get("options", {})
        standard_options = options_data.get("standard", [])
        
        result = {
            "vehicleno": complete_info.get("vehicleNo"),
            "carseq": int(real_vehicle_id),
            "platform": "encar",
            "origin": "국산" if car_type == "Y" else "수입",
            "cartype": spec.get("bodyName"),
            "manufacturer": category.get("manufacturerName"),
            "model": category.get("modelName"),
            "generation": category.get("modelGroupName"),
            "trim": category.get("gradeName"),
            "fueltype": spec.get("fuelName"),
            "transmission": spec.get("transmissionName"),
            "displacement": int(spec.get("displacement") or 0),
            "colorname": spec.get("colorName"),
            "modelyear": int(category.get("formYear") or 0),
            "firstregistrationdate": int(first_reg_date_str) if first_reg_date_str.isdigit() else 0,
            "distance": int(spec.get("mileage") or 0),
            "price": int(encar_data.get("Price") or 0),
            "originprice": int(category.get("originPrice") or 0),
            "selltype": encar_data.get("SellType"),
            "location": encar_data.get("OfficeCityState"),
            "detailurl": f"{DETAIL_PAGE_URL}/{real_vehicle_id}",
            "photo": f"https://ci.encar.com{encar_data['Photo']}" if encar_data.get("Photo") and encar_data['Photo'].startswith('/carpicture') else encar_data.get("Photo"),
            "options": standard_options,
            "record_info": record_info  # 보험 이력 정보 추가
        }
        
        return result
    except (KeyError, TypeError):
        return None

def convert_to_insurance_record(record_info: Dict, vehicle_id: int) -> Optional[Dict]:
    """엔카 record_info를 InsuranceHistory 레코드로 변환"""
    try:
        # 미가입 기간 처리
        not_join_periods = []
        for i in range(1, 6):
            period = record_info.get(f'notJoinDate{i}')
            if period:
                not_join_periods.append(period)
        not_join_periods_str = ', '.join(not_join_periods) if not_join_periods else None
        
        result = {
            "vehicle_id": vehicle_id,
            "platform": "encar",
            
            # 사고 이력 요약
            "my_accident_cnt": record_info.get("myAccidentCnt", 0),
            "other_accident_cnt": record_info.get("otherAccidentCnt", 0),
            "my_accident_cost": record_info.get("myAccidentCost", 0),
            "other_accident_cost": record_info.get("otherAccidentCost", 0),
            "total_accident_cnt": record_info.get("accidentCnt", 0),
            
            # 특수 사고 이력
            "total_loss_cnt": record_info.get("totalLossCnt", 0),
            "total_loss_date": record_info.get("totalLossDate"),
            "robber_cnt": record_info.get("robberCnt", 0),
            "robber_date": record_info.get("robberDate"),
            "flood_total_loss_cnt": record_info.get("floodTotalLossCnt", 0),
            "flood_part_loss_cnt": record_info.get("floodPartLossCnt", 0),
            "flood_date": record_info.get("floodDate"),
            
            # 기타 이력
            "owner_change_cnt": record_info.get("ownerChangeCnt", 0),
            "car_no_change_cnt": record_info.get("carNoChangeCnt", 0),
            
            # 특수 용도 이력
            "government": record_info.get("government", 0),
            "business": record_info.get("business", 0),
            "rental": 0,  # 엔카에서는 rental 정보가 없음
            "loan": record_info.get("loan", 0),
            
            # 미가입 기간
            "not_join_periods": not_join_periods_str
        }
        
        return result
    except (KeyError, TypeError):
        return None

def convert_to_inspection_record(inspection_data: Dict, vehicle_id: int) -> Optional[Dict]:
    """엔카 검사 API 응답을 Inspection/Item/Panel 레코드로 변환"""
    try:
        master = inspection_data.get("master", {})
        detail = master.get("detail", {})
        
        # 1) Inspection 요약
        inspection = {
            "vehicle_id": vehicle_id,
            "platform": "encar",
            "accident_history": master.get("accdient"),  # API 오타 필드명
            "simple_repair": master.get("simpleRepair"),
            "waterlog": detail.get("waterlog"),
            "fire_history": None,
            "recall_target": detail.get("recall"),
            "tuning_illegal": detail.get("tuning"),
            "outer_1": 0,
            "outer_2": 0,
            "struct_a": 0,
            "struct_b": 0,
            "struct_c": 0,
            "images": None
        }
        
        # 2) InspectionItem 파싱
        items = _parse_inspection_items(inspection_data.get('inners', []), vehicle_id)
        
        # 3) InspectionPanel 파싱
        panels = _parse_inspection_panels(inspection_data.get('outers', []), vehicle_id)
        
        # 외판/골격 카운트 계산
        for panel in panels:
            rank = panel['rank']
            if rank == '1': inspection['outer_1'] += 1
            elif rank == '2': inspection['outer_2'] += 1
            elif rank == 'A': inspection['struct_a'] += 1
            elif rank == 'B': inspection['struct_b'] += 1
            elif rank == 'C': inspection['struct_c'] += 1
        
        # 이미지 처리
        images = inspection_data.get('images', [])
        if images:
            image_urls = [img.get('path', '') for img in images if img.get('path')]
            inspection['images'] = ','.join(image_urls[:10])  # 최대 10개
        
        return {
            "inspection": inspection,
            "items": items,
            "panels": panels
        }
    except Exception as e:
        print(f"  [검사 데이터 변환 오류] {e}")
        return None

def _parse_inspection_items(inners_data: List[Dict], vehicle_id: int) -> List[Dict]:
    """inners 데이터에서 검사 항목 추출"""
    items = []
    
    def extract_items(children, group_name):
        for child in children:
            child_type = child.get('type', {})
            status_type = child.get('statusType', {})
            
            item_name = child_type.get('title', '')
            status_code = status_type.get('code', '')
            status_text = status_type.get('title', '')
            
            # 상태가 있는 항목만 저장
            if status_code and item_name:
                # 양호 여부 판단 (코드 1=양호, 그 외=불량/문제)
                is_good = (status_code == '1')
                
                items.append({
                    "vehicle_id": vehicle_id,
                    "group_name": group_name,
                    "item_name": item_name,
                    "status_code": status_code,
                    "status_text": status_text,
                    "is_good": is_good
                })
            
            # 재귀 처리
            if child.get('children'):
                extract_items(child['children'], group_name)
    
    for inner in inners_data:
        inner_type = inner.get('type', {})
        group_name = inner_type.get('title', '기타')
        
        if inner.get('children'):
            extract_items(inner['children'], group_name)
    
    return items

def _parse_inspection_panels(outers_data: List[Dict], vehicle_id: int) -> List[Dict]:
    """outers 데이터에서 외판/골격 손상 추출"""
    panels = []
    
    for outer in outers_data:
        outer_type = outer.get('type', {})
        part_code = outer_type.get('code', '')
        part_title = outer_type.get('title', '')
        
        # 랭크 추출 및 변환
        attributes = outer.get('attributes', [])
        rank = None
        if 'RANK_ONE' in attributes: 
            rank = 'OUTER_1'
        elif 'RANK_TWO' in attributes: 
            rank = 'OUTER_2'
        elif 'RANK_A' in attributes: 
            rank = 'STRUCT_A'
        elif 'RANK_B' in attributes: 
            rank = 'STRUCT_B'
        elif 'RANK_C' in attributes: 
            rank = 'STRUCT_C'
        
        # 손상 유형 추출
        status_types = outer.get('statusTypes', [])
        exchanged = False
        welded = False
        scratched = False
        uneven = False
        corroded = False
        damaged = False
        
        for st in status_types:
            code = st.get('code', '')
            if code == 'X': exchanged = True
            elif code == 'W': welded = True
            elif code == 'A': scratched = True
            elif code == 'U': uneven = True
            elif code == 'C': corroded = True
            elif code == 'T': damaged = True
        
        # 손상이 있는 부위만 저장
        if rank and (exchanged or welded or scratched or uneven or corroded or damaged):
            panels.append({
                "vehicle_id": vehicle_id,
                "part_code": part_code,
                "part_title": part_title,
                "rank": rank,
                "exchanged": exchanged,
                "welded": welded,
                "scratched": scratched,
                "uneven": uneven,
                "corroded": corroded,
                "damaged": damaged
            })
    
    return panels

def save_inspection_to_db(inspection_records: List[Dict]):
    """검사 이력을 DB에 저장 (Inspection + Items + Panels)"""
    if not inspection_records:
        print(f"  [검사 이력 저장] 저장할 레코드가 없음")
        return 0
    
    try:
        with session_scope() as session:
            saved_count = 0
            
            for record in inspection_records:
                vehicle_id = record['inspection']['vehicle_id']
                
                # 기존 검사 이력 확인
                existing = session.query(Inspection).filter(
                    Inspection.vehicle_id == vehicle_id,
                    Inspection.platform == 'encar'
                ).first()
                
                if existing:
                    # 기존 데이터 삭제 (관련 items, panels도 cascade로 삭제됨)
                    session.delete(existing)
                    session.flush()
                
                # 1) Inspection 저장
                inspection_obj = Inspection(**record['inspection'])
                session.add(inspection_obj)
                session.flush()
                
                # 2) InspectionItem 저장
                if record['items']:
                    for item_data in record['items']:
                        session.add(InspectionItem(**item_data))
                
                # 3) InspectionPanel 저장
                if record['panels']:
                    for panel_data in record['panels']:
                        session.add(InspectionPanel(**panel_data))
                
                saved_count += 1
            
            print(f"  [검사 이력 저장] {saved_count}건 저장 완료")
            print(f"  [검사 항목] {sum(len(r['items']) for r in inspection_records)}개 항목 저장")
            print(f"  [외판/골격] {sum(len(r['panels']) for r in inspection_records)}개 부위 저장")
            
            return saved_count
    except Exception as e:
        print(f"  [검사 이력 저장 오류] {e}")
        import traceback
        traceback.print_exc()
        return 0

def _old_save_inspection_to_db(inspection_records: List[Dict]):
    """[LEGACY] 이전 방식의 검사 이력 저장 함수"""
    if not inspection_records:
        print(f"  [검사 이력 저장] 저장할 레코드가 없음")
        return 0
    
    try:
        with session_scope() as session:
            # 기존 레코드들을 한 번에 조회
            vehicle_ids = [rec['vehicle_id'] for rec in inspection_records]
            print(f"  [검사 이력 저장] 기존 레코드 확인 중... (vehicle_ids: {len(vehicle_ids)}개)")
            
            existing_records = session.query(Inspection).filter(
                Inspection.vehicle_id.in_(vehicle_ids),
                Inspection.platform == 'encar'
            ).all()
            
            existing_keys = {(r.vehicle_id, r.platform) for r in existing_records}
            print(f"  [검사 이력 저장] 기존 레코드: {len(existing_keys)}건")
            
            # 신규 레코드만 필터링
            new_records = []
            for record in inspection_records:
                key = (record['vehicle_id'], record['platform'])
                if key not in existing_keys:
                    new_records.append(Inspection(**record))
            
            print(f"  [검사 이력 저장] 신규 레코드: {len(new_records)}건")
            
            # 신규 레코드만 배치 삽입
            if new_records:
                session.bulk_save_objects(new_records)
                print(f"  [검사 이력 저장] {len(new_records)}건 신규 저장 완료")
            else:
                print(f"  [검사 이력 저장] 모든 레코드가 이미 존재함")
            
            return len(new_records)
    except Exception as e:
        print(f"  [검사 이력 저장 오류] {e}")
        return 0

def save_data_to_db(records: List[Dict]):
    if not records: 
        return 0
    
    with session_scope() as session:
        try:
            # 차량 정보 저장 (has_options 포함)
            vehicle_mappings = []
            for rec in records:
                vehicle_data = {k: v for k, v in rec.items() if k != 'options'}
                # has_options 설정: 옵션이 있으면 True, 없으면 False
                platform_options = rec.get('options', [])
                global_codes = convert_platform_options_to_global(platform_options, 'encar')
                vehicle_data['has_options'] = len(global_codes) > 0
                vehicle_mappings.append(vehicle_data)
            
            session.bulk_insert_mappings(Vehicle, vehicle_mappings)
            
            # 저장된 차량 ID 매핑
            vehicle_map = {v.car_seq: v.vehicle_id for v in session.query(Vehicle.vehicle_id, Vehicle.car_seq).filter(Vehicle.car_seq.in_([rec['carseq'] for rec in records]))}
            
            print(f"  [차량 저장] {len(records)}대 저장 완료")
            
            # 옵션 처리
            options_to_save = []
            for rec in records:
                vehicle_id = vehicle_map.get(rec['carseq'])
                if vehicle_id:
                    platform_options = rec.get('options', [])
                    global_codes = convert_platform_options_to_global(platform_options, 'encar')
                    
                    # OptionMaster에서 option_id 찾기
                    for code in global_codes:
                        option = session.query(OptionMaster).filter(OptionMaster.option_code == code).first()
                        if option:
                            options_to_save.append({'vehicle_id': vehicle_id, 'option_id': option.option_id})
            
            # 옵션 저장
            if options_to_save:
                session.bulk_insert_mappings(VehicleOption, options_to_save)
                print(f"  [옵션 저장] {len(options_to_save)}개 옵션 저장 완료")
            
            return len(records)
        except Exception as e:
            print(f"  [DB 저장 오류] {e}")
            session.rollback()
            return 0

def save_insurance_to_db(insurance_records: List[Dict]):
    """보험 이력을 DB에 저장 (기존 있으면 스킵, 없으면 삽입)"""
    if not insurance_records:
        print(f"  [보험 이력 저장] 저장할 레코드가 없음")
        return 0
    
    try:
        with session_scope() as session:
            # 기존 레코드들을 한 번에 조회
            vehicle_ids = [rec['vehicle_id'] for rec in insurance_records]
            print(f"  [보험 이력 저장] 기존 레코드 확인 중... (vehicle_ids: {len(vehicle_ids)}개)")
            
            existing_records = session.query(InsuranceHistory).filter(
                InsuranceHistory.vehicle_id.in_(vehicle_ids),
                InsuranceHistory.platform == 'encar'
            ).all()
            
            existing_keys = {(r.vehicle_id, r.platform) for r in existing_records}
            print(f"  [보험 이력 저장] 기존 레코드: {len(existing_keys)}건")
            
            # 신규 레코드만 필터링
            new_records = []
            for record in insurance_records:
                key = (record['vehicle_id'], record['platform'])
                if key not in existing_keys:
                    new_records.append(InsuranceHistory(**record))
            
            print(f"  [보험 이력 저장] 신규 레코드: {len(new_records)}건")
            
            # 신규 레코드만 배치 삽입
            if new_records:
                session.bulk_save_objects(new_records)
                print(f"  [보험 이력 저장] {len(new_records)}건 신규 저장 완료")
            else:
                print(f"  [보험 이력 저장] 모든 레코드가 이미 존재함")
            
            return len(new_records)
    except Exception as e:
        print(f"  [보험 이력 저장 오류] {e}")
        return 0

def save_inspection_to_db(inspection_records: List[Dict]):
    """검사 이력을 DB에 저장 (기존 있으면 스킵, 없으면 삽입)"""
    if not inspection_records:
        print(f"  [검사 이력 저장] 저장할 레코드가 없음")
        return 0
    
    try:
        with session_scope() as session:
            # 기존 레코드들을 한 번에 조회
            vehicle_ids = [rec['vehicle_id'] for rec in inspection_records]
            print(f"  [검사 이력 저장] 기존 레코드 확인 중... (vehicle_ids: {len(vehicle_ids)}개)")
            
            existing_records = session.query(Inspection).filter(
                Inspection.vehicle_id.in_(vehicle_ids),
                Inspection.platform == 'encar'
            ).all()
            
            existing_keys = {(r.vehicle_id, r.platform) for r in existing_records}
            print(f"  [검사 이력 저장] 기존 레코드: {len(existing_keys)}건")
            
            # 신규 레코드만 필터링
            new_records = []
            for record in inspection_records:
                key = (record['vehicle_id'], record['platform'])
                if key not in existing_keys:
                    new_records.append(Inspection(**record))
            
            print(f"  [검사 이력 저장] 신규 레코드: {len(new_records)}건")
            
            # 신규 레코드만 배치 삽입
            if new_records:
                session.bulk_save_objects(new_records)
                print(f"  [검사 이력 저장] {len(new_records)}건 신규 저장 완료")
            else:
                print(f"  [검사 이력 저장] 모든 레코드가 이미 존재함")
            
            return len(new_records)
    except Exception as e:
        print(f"  [검사 이력 저장 오류] {e}")
        return 0

# =============================================================================
# 크롤링 로직
# =============================================================================
def crawl_encar_model(brand: str, model: str, session: requests.Session, existing_data: Dict[str, set], max_pages: int = 1000, page_size: int = 50, car_type: str = "Y"):
    """특정 모델그룹 크롤링"""
    print(f"\n[{brand} {model}] 크롤링 시작")
    
    total_processed = 0
    
    for page in range(max_pages):
        q_filter = f"(And.Hidden.N._.(C.CarType.{car_type}._.(C.Manufacturer.{brand}._.ModelGroup.{model}.)))"
        car_list = get_car_list(session, q_filter, page, page_size)
        
        if not car_list:
            print(f"  [완료] 더 이상 데이터 없음")
            break
        
        # 중복 제거
        new_cars = [car for car in car_list if car.get("Id") and str(car["Id"]) not in existing_data['car_seqs']]
        print(f"  [페이지 {page + 1}] {len(car_list)}대 중 {len(new_cars)}대 신규")
        
        if not new_cars:
            _sleep_with_jitter(0.2, 0.1)
            continue

        # 병렬 처리로 차량 상세 정보 수집
        processed_records = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_car = {executor.submit(fetch_vehicle_details, car["Id"], session): car for car in new_cars}
            
            for future in as_completed(future_to_car):
                encar_data = future_to_car[future]
                try:
                    details = future.result()
                    if details:
                        record = convert_to_vehicle_record(encar_data, details, car_type)
                        if record:
                            processed_records.append(record)
                
                except Exception as e:
                    car_id = encar_data.get('Id', 'N/A')
                    print(f"  [처리 오류] Car ID {car_id}: {type(e).__name__}: {e}")
                    # 에러 발생한 차량은 로그에 기록하되 크롤링은 계속 진행

        # 최종 중복 제거
        final_records = []
        seen_in_batch = set()
        for record in processed_records:
            car_seq = str(record['carseq'])
            vehicle_no = record['vehicleno']
            
            if (car_seq in existing_data['car_seqs'] or 
                (vehicle_no and vehicle_no in existing_data['vehicle_nos']) or
                (vehicle_no and vehicle_no in seen_in_batch)):
                continue
            
            final_records.append(record)
            if vehicle_no:
                seen_in_batch.add(vehicle_no)

        # DB 저장
        if final_records:
            saved_count = save_data_to_db(final_records)
            total_processed += saved_count
            print(f"  [저장 완료] {len(final_records)}건 → {saved_count}건 저장")
            
            # 저장 성공한 경우에만 기존 데이터에 추가
            if saved_count > 0:
                # 보험 이력 및 검사 이력 저장 (배치 처리)
                car_seqs = [rec['carseq'] for rec in final_records if rec.get('record_info')]
                print(f"  [보험/검사 이력 처리] record_info가 있는 차량: {len(car_seqs)}대")
                
                if car_seqs:
                    with session_scope() as db_session:
                        # 한 번에 모든 Vehicle ID 조회
                        vehicles = db_session.query(Vehicle).filter(Vehicle.car_seq.in_(car_seqs)).all()
                        vehicle_map = {v.car_seq: v.vehicle_id for v in vehicles}
                        print(f"  [보험/검사 이력 처리] Vehicle ID 조회 완료: {len(vehicle_map)}대")
                        
                        # 보험 이력 변환
                        insurance_records = []
                        inspection_records = []
                        
                        for rec in final_records:
                            if rec.get('record_info') and rec['carseq'] in vehicle_map:
                                vehicle_id = vehicle_map[rec['carseq']]
                                
                                # 보험 이력 변환
                                insurance_record = convert_to_insurance_record(rec['record_info'], vehicle_id)
                                if insurance_record:
                                    insurance_records.append(insurance_record)
                                
                                # 검사 데이터가 있는 경우 검사 이력 변환
                                inspection_data = rec['record_info'].get('inspectionData')
                                if inspection_data:
                                    inspection_record = convert_to_inspection_record(inspection_data, vehicle_id)
                                    if inspection_record:
                                        inspection_records.append(inspection_record)
                        
                        print(f"  [보험 이력 처리] 변환된 보험 이력: {len(insurance_records)}건")
                        if insurance_records:
                            save_insurance_to_db(insurance_records)
                        else:
                            print(f"  [보험 이력 처리] 저장할 보험 이력이 없음")
                        
                        print(f"  [검사 이력 처리] 변환된 검사 이력: {len(inspection_records)}건")
                        if inspection_records:
                            save_inspection_to_db(inspection_records)
                        else:
                            print(f"  [검사 이력 처리] 저장할 검사 이력이 없음")
                else:
                    print(f"  [보험/검사 이력 처리] record_info가 있는 차량이 없음")
            
            # 저장 성공한 레코드만 기존 데이터에 추가
            for rec in final_records:
                existing_data['car_seqs'].add(str(rec['carseq']))
                if rec['vehicleno']:
                    existing_data['vehicle_nos'].add(rec['vehicleno'])
        
        _sleep_with_jitter(1.0, 0.5)
        
    return total_processed

def crawl_encar_daily(max_pages_per_modelgroup: int = 1000, page_size: int = 50):
    """일반 크롤링 함수 (평일용) - 새 데이터만 수집"""
    print("[일반 크롤링 시작] - 새 데이터 수집")
    
    create_tables_if_not_exist()
    if not check_database_status(): 
        return
    initialize_global_options()
    
    session = build_session()
    
    # 기존 데이터 조회 (한 번만)
    with session_scope() as db_session:
        existing_car_seqs = {str(r[0]) for r in db_session.query(Vehicle.car_seq).filter(Vehicle.platform == 'encar').all() if r[0]}
        existing_vehicle_nos = {r[0] for r in db_session.query(Vehicle.vehicle_no).filter(Vehicle.vehicle_no.isnot(None)).all()}
    
    existing_data = {
        'car_seqs': existing_car_seqs, 
        'vehicle_nos': existing_vehicle_nos
    }
    print(f"[DB 확인] 기존 차량 {len(existing_data['car_seqs']):,}대")
    
    # 국산차와 수입차를 순차적으로 처리하는 루프
    for car_type, origin_name in [("Y", "국산"), ("N", "수입")]:
        print(f"\n{'='*50}\n[{origin_name} 크롤링 시작]")
        
        # 전체 차량 수 조회
        total_count_data = get_encar_api_data(BASE_URL, session, params={"count": "true", "q": f"(And.Hidden.N._.CarType.{car_type}.)"})
        print(f"[전체 {origin_name} 수] {total_count_data.get('Count', 0):,}대")
        
        # 해당 타입의 브랜드 목록 조회
        major_brands = get_encar_brands(session, car_type)
        if not major_brands:
            print(f"[{origin_name}] 브랜드 목록 조회 실패. 건너뜁니다.")
            continue

        for brand in major_brands:
            print(f"\n--- [브랜드] {brand} ---")
            modelgroups = get_encar_modelgroups_by_brand(brand, session, car_type)
            if not modelgroups:
                continue
            
            for modelgroup in modelgroups:
                # 모델그룹별 차량 수 확인
                count_data = get_encar_api_data(BASE_URL, session, params={"count": "true", "q": f"(And.Hidden.N._.(C.CarType.{car_type}._.(C.Manufacturer.{brand}._.ModelGroup.{modelgroup}.)))"})
                modelgroup_count = count_data.get("Count", 0) if count_data else 0
                
                if modelgroup_count > 0:
                    required_pages = (modelgroup_count + page_size - 1) // page_size
                    crawl_encar_model(brand, modelgroup, session, existing_data, required_pages, page_size, car_type)

    print(f"\n[일반 크롤링 완료] 현재 DB의 엔카 차량: {len(existing_data['car_seqs']):,}대")

def cleanup_deleted_vehicles_weekly(batch_size: int = 50):
    """주기적 정리 함수 (주말용) - 삭제된 차량 정리"""
    print("[주기적 정리 시작] - 삭제된 차량 정리")
    
    total_deleted = 0
    
    with session_scope() as session:
        # 전체 엔카 차량 수 확인
        total_vehicles = session.query(Vehicle).filter(Vehicle.platform == 'encar').count()
        print(f"[전체 엔카 차량] {total_vehicles:,}대 검사 예정")
        
        offset = 0
        while True:
            # DB에 있는 모든 엔카 차량을 배치 단위로 조회
            vehicles_to_check = session.query(Vehicle).filter(
                Vehicle.platform == 'encar'
            ).offset(offset).limit(batch_size).all()
            
            if not vehicles_to_check:
                break
            
            print(f"[삭제된 차량 확인] {len(vehicles_to_check)}대 차량 확인 중...")
            
            with requests.Session() as http_session:
                http_session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                deleted_count = 0
                for vehicle in vehicles_to_check:
                    # 차량 상세정보 조회
                    detail_info = get_encar_api_data(
                        f"{DETAIL_API_URL}/{vehicle.car_seq}?include=OPTIONS", 
                        http_session
                    )
                    
                    if not detail_info:
                        try:
                            # 삭제/판매된 차량은 DB에서 완전히 삭제 (데드락 방지를 위해 순서 변경)
                            # 1. 먼저 VehicleOption 삭제
                            session.query(VehicleOption).filter(VehicleOption.vehicle_id == vehicle.vehicle_id).delete()
                            # 2. 그 다음 InsuranceHistory 삭제
                            session.query(InsuranceHistory).filter(InsuranceHistory.vehicle_id == vehicle.vehicle_id).delete()
                            # 3. 그 다음 Inspection 삭제
                            session.query(Inspection).filter(Inspection.vehicle_id == vehicle.vehicle_id).delete()
                            # 4. 그 다음 Vehicle 삭제
                            session.query(Vehicle).filter(Vehicle.vehicle_id == vehicle.vehicle_id).delete()
                            # 5. 즉시 커밋하여 데드락 방지
                            session.commit()
                            deleted_count += 1
                            print(f"  [삭제] CarSeq: {vehicle.car_seq}")
                        except Exception as e:
                            session.rollback()
                            print(f"  [삭제 실패] CarSeq: {vehicle.car_seq}, 오류: {e}")
                            continue
                
                total_deleted += deleted_count
                print(f"[배치 완료] {deleted_count}대 차량 삭제 (진행률: {offset + len(vehicles_to_check)}/{total_vehicles})")
                
                # 다음 배치를 위해 offset 증가
                offset += batch_size
    
    print(f"[주기적 정리 완료] 총 {total_deleted}대 차량 삭제")

def crawl_encar_weekly():
    """주간 정리 함수 (주말용) - 정리만"""
    print("[주간 정리 시작] - 삭제된 차량 정리 + 옵션 누락 차량 크롤링 + 보험 이력 누락 차량 크롤링 + 검사 이력 누락 차량 크롤링")
    
    # 1단계: 삭제된 차량 정리
    print("\n" + "=" * 50)
    print("1단계: 삭제된 차량 정리")
    print("=" * 50)
    cleanup_deleted_vehicles_weekly(batch_size=50)
    
    # 2단계: 옵션 누락 차량 크롤링
    print("\n" + "=" * 50)
    print("2단계: 옵션 누락 차량 크롤링")
    print("=" * 50)
    crawl_missing_options()
    
    # 3단계: 보험 이력 누락 차량 크롤링
    print("\n" + "=" * 50)
    print("3단계: 보험 이력 누락 차량 크롤링")
    print("=" * 50)
    crawl_missing_insurance()
    
    # 4단계: 검사 이력 누락 차량 크롤링
    print("\n" + "=" * 50)
    print("4단계: 검사 이력 누락 차량 크롤링")
    print("=" * 50)
    crawl_missing_inspection()
    
    print("\n[주간 정리 완료]")

# =============================================================================
# 옵션정보만 크롤링
# =============================================================================
def update_has_options_from_existing_data():
    """기존 vehicle_options 테이블 데이터를 기반으로 has_options를 업데이트합니다."""
    with session_scope() as session:
        # vehicle_options 테이블에 데이터가 있는 차량들의 has_options를 True로 업데이트
        vehicles_with_options = session.query(VehicleOption.vehicle_id).distinct().subquery()
        
        updated_count = session.query(Vehicle).filter(
            Vehicle.platform == 'encar',
            Vehicle.vehicle_id.in_(session.query(vehicles_with_options.c.vehicle_id))
        ).update({'has_options': True}, synchronize_session=False)
        
        print(f"[has_options 업데이트] {updated_count}대 차량을 True로 업데이트")

def get_vehicles_without_options():
    """옵션이 없는 차량들을 조회합니다."""
    with session_scope() as session:
        # has_options가 NULL인 차량들만 조회 (아직 옵션 확인을 하지 않은 차량)
        vehicles_without_options = session.query(Vehicle).filter(
            Vehicle.platform == 'encar',
            Vehicle.has_options.is_(None)
        ).all()
        
        # 디버깅: 전체 상태 확인
        total_encar = session.query(Vehicle).filter(Vehicle.platform == 'encar').count()
        null_options = session.query(Vehicle).filter(Vehicle.platform == 'encar', Vehicle.has_options.is_(None)).count()
        false_options = session.query(Vehicle).filter(Vehicle.platform == 'encar', Vehicle.has_options == False).count()
        true_options = session.query(Vehicle).filter(Vehicle.platform == 'encar', Vehicle.has_options == True).count()
        
        print(f"[디버깅] 엔카 차량 총 {total_encar}대:")
        print(f"  - has_options = NULL: {null_options}대")
        print(f"  - has_options = False: {false_options}대") 
        print(f"  - has_options = True: {true_options}대")
        print(f"[옵션 누락 차량] {len(vehicles_without_options)}대 발견")
        
        return vehicles_without_options

def get_vehicles_without_insurance():
    """보험 이력이 누락된 차량들을 조회합니다."""
    with session_scope() as session:
        # 보험 이력이 없는 엔카 차량들 조회
        vehicles = session.query(Vehicle).outerjoin(InsuranceHistory, 
            (Vehicle.vehicle_id == InsuranceHistory.vehicle_id) & 
            (InsuranceHistory.platform == 'encar')
        ).filter(
            Vehicle.platform == 'encar',
            InsuranceHistory.vehicle_id.is_(None)
        ).all()
        return vehicles

def get_vehicles_without_inspection():
    """검사 이력이 누락된 차량들을 조회합니다."""
    with session_scope() as session:
        # 검사 이력이 없는 엔카 차량들 조회
        vehicles = session.query(Vehicle).outerjoin(Inspection, 
            (Vehicle.vehicle_id == Inspection.vehicle_id) & 
            (Inspection.platform == 'encar')
        ).filter(
            Vehicle.platform == 'encar',
            Inspection.vehicle_id.is_(None)
        ).all()
        return vehicles

def crawl_missing_insurance():
    """보험 이력이 누락된 차량들의 보험 이력을 크롤링합니다."""
    print("[보험 이력 크롤링 시작] - 누락된 보험 이력 수집")
    
    # 보험 이력이 누락된 차량들 조회
    vehicles = get_vehicles_without_insurance()
    if not vehicles:
        print("[보험 이력 크롤링] 누락된 보험 이력이 없습니다.")
        return
    
    with session_scope() as session:
        with requests.Session() as http_session:
            http_session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            print(f"[보험 이력 크롤링 시작] {len(vehicles)}대 차량")
            
            for i, vehicle in enumerate(vehicles, 1):
                # 100대마다 commit하여 메모리 효율성 확보
                if i % 100 == 0:
                    session.commit()
                    print(f"  [진행상황] {i}/{len(vehicles)}대 처리 완료, DB 커밋")
                print(f"  [{i}/{len(vehicles)}] CarSeq: {vehicle.car_seq}")
                
                # record_info API 시도
                record_info = get_encar_api_data(
                    f"{RECORD_API_URL}/{vehicle.car_seq}/open", 
                    http_session, 
                    params={"vehicleNo": vehicle.vehicle_no}
                )
                
                if not record_info:
                    # record_info가 없으면 차량검사 API 시도
                    inspection_info = get_encar_api_data(
                        f"{INSPECTION_API_URL}/{vehicle.car_seq}", 
                        http_session
                    )
                    if inspection_info:
                        record_info = {
                            "firstDate": inspection_info.get("firstRegistrationDate", "0"),
                            "inspectionData": inspection_info
                        }
                    else:
                        print(f"    [보험 이력 없음] CarSeq: {vehicle.car_seq}")
                        continue
                
                # 보험 이력 변환
                insurance_record = convert_to_insurance_record(record_info, vehicle.vehicle_id)
                if insurance_record:
                    # 기존 레코드가 있는지 확인
                    existing = session.query(InsuranceHistory).filter(
                        InsuranceHistory.vehicle_id == vehicle.vehicle_id,
                        InsuranceHistory.platform == 'encar'
                    ).first()
                    
                    if not existing:
                        # 신규 레코드 삽입
                        session.add(InsuranceHistory(**insurance_record))
                        print(f"    [보험 이력 저장 완료] CarSeq: {vehicle.car_seq}")
                    else:
                        print(f"    [보험 이력 이미 존재] CarSeq: {vehicle.car_seq}")
                else:
                    print(f"    [보험 이력 변환 실패] CarSeq: {vehicle.car_seq}")
    
    print(f"[보험 이력 크롤링 완료] {len(vehicles)}대 차량 처리")

def crawl_missing_inspection():
    """검사 이력이 누락된 차량들의 검사 이력을 크롤링합니다."""
    print("[검사 이력 크롤링 시작] - 누락된 검사 이력 수집")
    
    # 검사 이력이 누락된 차량들 조회
    vehicles = get_vehicles_without_inspection()
    if not vehicles:
        print("[검사 이력 크롤링] 누락된 검사 이력이 없습니다.")
        return
    
    with session_scope() as session:
        with requests.Session() as http_session:
            http_session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            print(f"[검사 이력 크롤링 시작] {len(vehicles)}대 차량")
            
            for i, vehicle in enumerate(vehicles, 1):
                # 100대마다 commit하여 메모리 효율성 확보
                if i % 100 == 0:
                    session.commit()
                    print(f"  [진행상황] {i}/{len(vehicles)}대 처리 완료, DB 커밋")
                print(f"  [{i}/{len(vehicles)}] CarSeq: {vehicle.car_seq}")
                
                # 검사 API 호출
                inspection_info = get_encar_api_data(
                    f"{INSPECTION_API_URL}/{vehicle.car_seq}", 
                    http_session
                )
                
                if not inspection_info:
                    print(f"    [검사 이력 없음] CarSeq: {vehicle.car_seq}")
                    continue
                
                # 검사 이력 변환
                inspection_record = convert_to_inspection_record(inspection_info, vehicle.vehicle_id)
                if inspection_record:
                    # 기존 레코드가 있는지 확인
                    existing = session.query(Inspection).filter(
                        Inspection.vehicle_id == vehicle.vehicle_id,
                        Inspection.platform == 'encar'
                    ).first()
                    
                    if not existing:
                        # 신규 레코드 삽입
                        session.add(Inspection(**inspection_record))
                        print(f"    [검사 이력 저장 완료] CarSeq: {vehicle.car_seq}")
                    else:
                        print(f"    [검사 이력 이미 존재] CarSeq: {vehicle.car_seq}")
                else:
                    print(f"    [검사 이력 변환 실패] CarSeq: {vehicle.car_seq}")
    
    print(f"[검사 이력 크롤링 완료] {len(vehicles)}대 차량 처리")

def crawl_missing_options():
    """옵션이 누락된 차량들의 옵션정보를 크롤링합니다."""
    # 1단계: 기존 vehicle_options 테이블 데이터를 기반으로 has_options 업데이트
    print("[1단계] 기존 옵션 데이터 기반 has_options 업데이트")
    update_has_options_from_existing_data()
    
    # 2단계: has_options가 NULL인 차량들 조회
    print("\n[2단계] 옵션 누락 차량 조회")
    vehicles = get_vehicles_without_options()
    if not vehicles:
        print("[옵션 크롤링] 누락된 옵션이 없습니다.")
        return
    
    with session_scope() as session:
        with requests.Session() as http_session:
            http_session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            print(f"[옵션 크롤링 시작] {len(vehicles)}대 차량")
            
            for i, vehicle in enumerate(vehicles, 1):
                # 100대마다 commit하여 메모리 효율성 확보
                if i % 100 == 0:
                    session.commit()
                    print(f"  [진행상황] {i}/{len(vehicles)}대 처리 완료, DB 커밋")
                print(f"  [{i}/{len(vehicles)}] CarSeq: {vehicle.car_seq}")
                
                # 차량 상세정보 조회
                detail_info = get_encar_api_data(
                    f"{DETAIL_API_URL}/{vehicle.car_seq}?include=OPTIONS", 
                    http_session
                )
                
                if not detail_info:
                    print(f"    [삭제/판매된 차량] CarSeq: {vehicle.car_seq} - DB에서 삭제")
                    try:
                        # 삭제/판매된 차량은 DB에서 완전히 삭제 (데드락 방지)
                        # 1. 먼저 VehicleOption 삭제
                        session.query(VehicleOption).filter(VehicleOption.vehicle_id == vehicle.vehicle_id).delete()
                        # 2. 그 다음 InsuranceHistory 삭제
                        session.query(InsuranceHistory).filter(InsuranceHistory.vehicle_id == vehicle.vehicle_id).delete()
                        # 3. 그 다음 Inspection 삭제
                        session.query(Inspection).filter(Inspection.vehicle_id == vehicle.vehicle_id).delete()
                        # 4. 그 다음 Vehicle 삭제
                        session.query(Vehicle).filter(Vehicle.vehicle_id == vehicle.vehicle_id).delete()
                        # 5. 즉시 커밋
                        session.commit()
                    except Exception as e:
                        session.rollback()
                        print(f"    [삭제 실패] CarSeq: {vehicle.car_seq}, 오류: {e}")
                    continue
                
                # 옵션 데이터 추출
                options_data = detail_info.get("options", {})
                standard_options = options_data.get("standard", [])
                
                if not standard_options:
                    print(f"    [옵션 없음] CarSeq: {vehicle.car_seq}")
                    # 옵션이 없는 차량은 has_options를 False로 설정
                    session.query(Vehicle).filter(Vehicle.vehicle_id == vehicle.vehicle_id).update({'has_options': False})
                    continue
                
                # 플랫폼 옵션을 글로벌 옵션으로 변환
                global_options = convert_platform_options_to_global(standard_options, 'encar')
                
                if not global_options:
                    print(f"    [변환된 옵션 없음] CarSeq: {vehicle.car_seq}")
                    continue
                
                # 옵션 마스터에서 옵션 ID 조회
                option_masters = session.query(OptionMaster).filter(
                    OptionMaster.option_code.in_(global_options)
                ).all()
                
                option_master_map = {opt.option_code: opt.option_id for opt in option_masters}
                
                # VehicleOption 레코드 생성
                vehicle_options = []
                for global_code in global_options:
                    if global_code in option_master_map:
                        vehicle_options.append({
                            'vehicle_id': vehicle.vehicle_id,
                            'option_id': option_master_map[global_code]
                        })
                
                if vehicle_options:
                    # 새 옵션만 추가
                    try:
                        session.bulk_insert_mappings(VehicleOption, vehicle_options)
                        print(f"    [옵션 저장 완료] CarSeq: {vehicle.car_seq}, 옵션 {len(vehicle_options)}개")
                        # 옵션이 저장된 차량은 has_options를 True로 설정
                        session.query(Vehicle).filter(Vehicle.vehicle_id == vehicle.vehicle_id).update({'has_options': True})
                    except Exception as e:
                        if "duplicate key" in str(e).lower():
                            print(f"    [옵션 중복] CarSeq: {vehicle.car_seq}, 이미 존재하는 옵션들")
                            # 중복 옵션이 있는 차량은 has_options를 True로 설정
                            session.query(Vehicle).filter(Vehicle.vehicle_id == vehicle.vehicle_id).update({'has_options': True})
                        else:
                            print(f"    [옵션 저장 실패] CarSeq: {vehicle.car_seq}, 오류: {type(e).__name__}: {e}")
                    

                else:
                    print(f"    [옵션 없음] CarSeq: {vehicle.car_seq}")
                    # 옵션이 없는 차량은 has_options를 False로 설정
                    session.query(Vehicle).filter(Vehicle.vehicle_id == vehicle.vehicle_id).update({'has_options': False})

# =============================================================================
# 메인 실행
# =============================================================================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='엔카 크롤러')
    parser.add_argument('--mode', choices=['daily', 'weekly'], default='daily',
                       help='크롤링 모드: daily(일반 크롤링), weekly(정리만)')
    parser.add_argument('--page-size', type=int, default=50,
                       help='페이지 크기 (기본값: 50)')
    
    args = parser.parse_args()
    
    if args.mode == 'weekly':
        print("주간 정리 모드 시작")
        crawl_encar_weekly()
    else:
        print("일반 크롤링 모드 시작")
        crawl_encar_daily(page_size=args.page_size)
    
    print("크롤링 완료")