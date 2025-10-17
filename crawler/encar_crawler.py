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
from crawler.inspection_mapping import (
    normalize_status, normalize_rank, normalize_damage_types,
    map_to_common_inner_code, map_to_common_outer_code, get_common_item_name,
    normalize_guaranty_type
)

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

def _delete_vehicle_cascade(session, vehicle_id: int) -> bool:

    try:
        # FK 순서에 맞게 삭제 (데드락 방지)
        session.query(VehicleOption).filter(VehicleOption.vehicle_id == vehicle_id).delete()
        session.query(InsuranceHistory).filter(InsuranceHistory.vehicle_id == vehicle_id).delete()
        session.query(InspectionDetail).filter(InspectionDetail.inspection_id.in_(
            session.query(Inspection.inspection_id).filter(Inspection.vehicle_id == vehicle_id)
        )).delete(synchronize_session=False)
        session.query(Inspection).filter(Inspection.vehicle_id == vehicle_id).delete()
        session.query(Vehicle).filter(Vehicle.vehicle_id == vehicle_id).delete()
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"    [삭제 실패] vehicle_id: {vehicle_id}, 오류: {e}")
        return False

def build_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(total=5, connect=3, read=3, backoff_factor=0.7, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries, pool_connections=50, pool_maxsize=50)
    s.mount("https://", adapter)

    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko,ko-KR;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Origin": "https://www.encar.com",
        "Referer": "https://www.encar.com/",
        "Priority": "u=0, i",
        "Sec-Ch-Ua": '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Cache-Control": "no-cache"
    })
    return s

# =============================================================================
# API 호출 함수
# =============================================================================
def get_encar_api_data(url: str, session: requests.Session, params: Optional[Dict] = None) -> Optional[Dict]:
    try:
        response = session.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        # 404는 정상적인 경우이므로 출력하지 않음
        if e.response and e.response.status_code not in [404, 429]:
            print(f"[API 호출 오류] URL: {url}, 상태코드: {e.response.status_code if e.response else 'N/A'}, 오류: {e}")
        return None
    except Exception as e:
        print(f"[API 파싱 오류] URL: {url}, 오류: {e}")
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

    # 1. 보험 이력 API (record API)
    insurance_info = get_encar_api_data(f"{RECORD_API_URL}/{real_vehicle_id}/open", session, params={"vehicleNo": vehicle_no})
    
    # 2. 검사 정보 API (inspection API)
    inspection_info = get_encar_api_data(f"{INSPECTION_API_URL}/{real_vehicle_id}", session)
    
    return {
        "complete_info": complete_info,
        "insurance_info": insurance_info,    # 보험 이력 (없으면 None)
        "inspection_info": inspection_info   # 검사 정보 (없으면 None)
    }

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
# 데이터 변환 함수
# =============================================================================
def convert_to_vehicle_record(encar_data: Dict, details: Dict, car_type: str = "Y") -> Optional[Dict]:
    try:
        complete_info = details["complete_info"]
        insurance_info = details.get("insurance_info")
        inspection_info = details.get("inspection_info")
        real_vehicle_id = str(complete_info["vehicleId"])
        
        spec = complete_info.get("spec", {})
        category = complete_info.get("category", {})
        
        # firstDate 처리 (보험 API 우선, 없으면 검사 API)
        first_date = "0"
        if insurance_info:
            first_date = insurance_info.get("firstDate", "0")
        if (not first_date or first_date == "0") and inspection_info:
            first_date = inspection_info.get("firstRegistrationDate", "0")
        
        first_reg_date_str = str(first_date).replace("-", "")
        
        # 옵션 데이터 수집
        options_data = complete_info.get("options", {})
        standard_options = options_data.get("standard", [])
        
        result = {
            "vehicle_no": complete_info.get("vehicleNo"),
            "car_seq": int(real_vehicle_id),
            "platform": "encar",
            "origin": "국산" if car_type == "Y" else "수입",
            "car_type": spec.get("bodyName"),
            "manufacturer": category.get("manufacturerName"),
            "model_group": category.get("modelGroupName"),  # 엔카: modelGroupName → model_group (EV6, 모하비)
            "model": category.get("modelName"),  # 엔카: modelName → model (더 뉴 EV6, 모하비 더 마스터)
            "grade": category.get("gradeName"),  # 엔카: gradeName → grade (롱레인지 2wd, 디젤 3.0 4WD 6인승)
            "trim": category.get("gradeDetailName", ""),  # 엔카: gradeDetailName → trim (어스, 마스터즈 그래비티)
            "fuel_type": spec.get("fuelName"),
            "transmission": spec.get("transmissionName"),
            "displacement": int(spec.get("displacement") or 0),
            "color_name": spec.get("colorName"),
            "model_year": int(category.get("formYear") or 0),
            "first_registration_date": int(first_reg_date_str) if first_reg_date_str.isdigit() else 0,
            "distance": int(spec.get("mileage") or 0),
            "price": int(encar_data.get("Price") or 0),
            "origin_price": int(category.get("originPrice") or 0),
            "sell_type": encar_data.get("SellType"),
            "location": encar_data.get("OfficeCityState"),
            "detail_url": f"{DETAIL_PAGE_URL}/{real_vehicle_id}",
            "photo": f"https://ci.encar.com{encar_data['Photo']}" if encar_data.get("Photo") and encar_data['Photo'].startswith('/carpicture') else encar_data.get("Photo"),
            "has_options": bool(standard_options and len(standard_options) > 0),
            "options": standard_options,
            "insurance_info": insurance_info,    # 보험 이력 (None 가능)
            "inspection_info": inspection_info   # 검사 정보 (None 가능)
        }
        
        return result
    except (KeyError, TypeError):
        return None

def convert_to_insurance_record(insurance_info: Dict, vehicle_id: int) -> Optional[Dict]:
    """엔카 보험 API 응답을 InsuranceHistory 레코드로 변환"""
    try:
        # 미가입 기간 처리
        not_join_periods = []
        for i in range(1, 6):
            period = insurance_info.get(f'notJoinDate{i}')
            if period:
                not_join_periods.append(period)
        
        result = {
            "vehicle_id": vehicle_id,
            "platform": "encar",
            
            # 사고 이력 요약
            "my_accident_cnt": insurance_info.get("myAccidentCnt", 0),
            "other_accident_cnt": insurance_info.get("otherAccidentCnt", 0),
            "my_accident_cost": insurance_info.get("myAccidentCost", 0),
            "other_accident_cost": insurance_info.get("otherAccidentCost", 0),
            "total_accident_cnt": insurance_info.get("accidentCnt", 0),
            
            # 특수 사고 이력
            "total_loss_cnt": insurance_info.get("totalLossCnt", 0),
            "total_loss_date": insurance_info.get("totalLossDate"),
            "robber_cnt": insurance_info.get("robberCnt", 0),
            "robber_date": insurance_info.get("robberDate"),
            "flood_total_loss_cnt": insurance_info.get("floodTotalLossCnt", 0),
            "flood_part_loss_cnt": insurance_info.get("floodPartLossCnt", 0),
            "flood_date": insurance_info.get("floodDate"),
            
            # 기타 이력
            "owner_change_cnt": insurance_info.get("ownerChangeCnt", 0),
            "car_no_change_cnt": insurance_info.get("carNoChangeCnt", 0),
            
            # 특수 용도 이력 (carInfoUse1s: 1=관용, 2=자가용, 3=렌트, 4=영업용)
            "government": insurance_info.get("government", 0),
            "business": 1 if "4" in insurance_info.get("carInfoUse1s", []) else 0,
            "rental": 1 if "3" in insurance_info.get("carInfoUse1s", []) else 0,
            "loan": insurance_info.get("loan", 0),
            
            # 미가입 기간
            "not_join_periods": ', '.join(not_join_periods) if not_join_periods else None
        }
        
        return result
    except (KeyError, TypeError):
        return None

def convert_to_inspection_record(inspection_data: Dict, vehicle_id: int) -> Optional[Dict]:
    """엔카 검사 API 응답을 Inspection/InspectionDetail 레코드로 변환"""
    try:
        # IMAGE 형식 체크 (사진으로만 등록된 검사서는 스킵)
        formats = inspection_data.get("formats", [])
        if "IMAGE" in formats and "TABLE" not in formats:
            print(f"  [검사 이력 스킵] vehicle_id: {vehicle_id}, 이미지 형식 검사서")
            return None
            
        master = inspection_data.get("master", {})
        detail = master.get("detail", {})
        
        # 보증유형 공통화
        guaranty_code = detail.get("guarantyType", {}).get("code")
        guaranty_type = normalize_guaranty_type(guaranty_code)
        
        # 리콜 정보 파싱
        recall_applicable = detail.get("recall")
        recall_fulfill_types = detail.get("recallFullFillTypes", [])
        recall_fulfilled = len(recall_fulfill_types) > 0 if recall_fulfill_types else None
        
        # 이미지 처리 (type: M1=앞면, M2=뒷면)
        images = inspection_data.get('images', [])
        images_dict = {
            img.get('type'): f"https://ci.encar.com{img['path']}" 
            for img in images 
            if img and isinstance(img, dict) and img.get('path')
        }
        
        # 1) Inspection 요약
        inspection = {
            "vehicle_id": vehicle_id,
            "platform": "encar",
            "inspected_at": detail.get("issueDate"),
            "valid_from": detail.get("validityStartDate"),
            "valid_to": detail.get("validityEndDate"),
            "mileage_at_inspect": detail.get("mileage"),
            "accident_history": master.get("accdient"),  
            "simple_repair": master.get("simpleRepair"),
            "waterlog": detail.get("waterlog"),
            "fire_history": None,
            "tuning_exist": detail.get("tuning"),
            "recall_applicable": recall_applicable,
            "recall_fulfilled": recall_fulfilled,
            "engine_check_ok": detail.get("engineCheck") == "Y",
            "trans_check_ok": detail.get("trnsCheck") == "Y",
            "guaranty_type": guaranty_type,
            "image_front": images_dict.get('M1'),
            "image_rear": images_dict.get('M2'),
            "remarks": detail.get("comments")
        }
        
        # 2) InspectionDetail - INNER 파싱 (inspection_id는 저장 시 설정)
        items = _parse_inspection_items(inspection_data.get('inners', []))
        
        # 3) InspectionDetail - OUTER 파싱 (inspection_id는 저장 시 설정)
        panels = _parse_inspection_panels(inspection_data.get('outers', []))
        
        return {
            "inspection": inspection,
            "items": items,
            "panels": panels
        }
    except Exception as e:
        print(f"  [검사 데이터 변환 오류] vehicle_id: {vehicle_id}, 오류: {e}")
        return None

# =============================================================================
# 검사 데이터 파싱 헬퍼
# =============================================================================
def _parse_inspection_items(inners_data: List[Dict]) -> List[Dict]:
    """inners 데이터에서 검사 항목을 InspectionDetail(INNER) 레코드로 변환"""
    items = []
    
    def extract_items(children, group_code, group_title):
        for child in children:
            child_type = child.get('type') or {}
            status_type = child.get('statusType') or {}
            
            item_code = child_type.get('code', '')
            item_title = child_type.get('title', '')
            status_code = status_type.get('code', '')
            status_text = status_type.get('title', '')
            
            # 상태가 있는 항목만 저장
            if status_code and item_title:
                # 플랫폼 코드 → 공통 코드 변환
                common_code = map_to_common_inner_code(item_code, 'encar')
                common_title = get_common_item_name(common_code, 'INNER')
                
                # 상태 정규화
                normalized = normalize_status(status_code, status_text)
                
                item = {
                    "detail_type": "INNER",
                    "group_code": group_code,
                    "group_title": group_title,
                    "item_code": common_code,  # 공통 코드 사용
                    "item_title": common_title,  # 공통 한글명 사용
                    "good_bad": normalized.get('good_bad'),
                    "leak_level": normalized.get('leak_level'),
                    "level_state": normalized.get('level_state'),
                    "rank": None,
                    "exchanged": False,
                    "welded": False,
                    "scratched": False,
                    "uneven": False,
                    "corroded": False,
                    "damaged": False,
                    "note": child.get('description')
                }
                items.append(item)
            
            # 재귀 처리
            if child.get('children'):
                extract_items(child['children'], group_code, group_title)
    
    for inner in inners_data:
        inner_type = inner.get('type') or {}
        group_code = inner_type.get('code', '')
        group_title = inner_type.get('title', '기타')
        
        if inner.get('children'):
            extract_items(inner['children'], group_code, group_title)
    
    return items

def _parse_inspection_panels(outers_data: List[Dict]) -> List[Dict]:
    """outers 데이터에서 외판/골격 손상을 InspectionDetail(OUTER) 레코드로 변환"""
    panels = []
    
    for outer in outers_data:
        outer_type = outer.get('type') or {}
        part_code = outer_type.get('code', '')
        part_title = outer_type.get('title', '')
        
        # 랭크 추출 및 변환
        attributes = outer.get('attributes', [])
        rank = None
        for attr in attributes:
            rank = normalize_rank(attr)
            if rank:
                break
        
        # 손상 유형 추출
        status_types = outer.get('statusTypes', [])
        status_codes = [st.get('code', '') for st in status_types]
        damage_flags = normalize_damage_types(status_codes)
        
        # 손상이 있는 부위만 저장
        if rank and any(damage_flags.values()):
            # 플랫폼 코드 → 공통 코드 변환
            common_code = map_to_common_outer_code(part_code, 'encar')
            common_title = get_common_item_name(common_code, 'OUTER')
            
            # 그룹 코드/이름 추출 (P0: 외판, PA: 골격 등)
            group_code = part_code[:2] if len(part_code) >= 2 else 'P0'
            group_title = '외판' if rank in ['OUTER_1', 'OUTER_2'] else '골격'
            
            panels.append({
                "detail_type": "OUTER",
                "group_code": group_code,
                "group_title": group_title,
                "item_code": common_code,  # 공통 코드 사용
                "item_title": common_title,  # 공통 한글명 사용
                "good_bad": None,
                "leak_level": None,
                "level_state": None,
                "rank": rank,
                "exchanged": damage_flags['exchanged'],
                "welded": damage_flags['welded'],
                "scratched": damage_flags['scratched'],
                "uneven": damage_flags['uneven'],
                "corroded": damage_flags['corroded'],
                "damaged": damage_flags['damaged'],
                "note": None
            })
    
    return panels

# =============================================================================
# DB 저장 함수
# =============================================================================
def save_data_to_db(records: List[Dict]):
    if not records: 
        return 0
    
    with session_scope() as session:
        try:
            # 차량 정보 저장 (has_options 포함)
            vehicle_mappings = []
            for rec in records:
                vehicle_data = {k: v for k, v in rec.items() if k not in ['options', 'insurance_info', 'inspection_info']}
                # has_options 설정: 옵션이 있으면 True, 없으면 False
                platform_options = rec.get('options', [])
                global_codes = convert_platform_options_to_global(platform_options, 'encar')
                vehicle_data['has_options'] = len(global_codes) > 0
                vehicle_mappings.append(vehicle_data)
            
            session.bulk_insert_mappings(Vehicle, vehicle_mappings)
            
            # 저장된 차량 ID 매핑
            vehicle_map = {v.car_seq: v.vehicle_id for v in session.query(Vehicle.vehicle_id, Vehicle.car_seq).filter(Vehicle.car_seq.in_([rec['car_seq'] for rec in records]))}
            
            print(f"  [차량 저장] {len(records)}대 저장 완료")
            
            # 옵션 처리 (N+1 쿼리 방지)
            # 1. 모든 옵션 코드 수집
            all_option_codes = set()
            for rec in records:
                platform_options = rec.get('options', [])
                global_codes = convert_platform_options_to_global(platform_options, 'encar')
                all_option_codes.update(global_codes)
            
            # 2. 한 번의 쿼리로 모든 OptionMaster 조회
            option_masters = session.query(OptionMaster).filter(
                OptionMaster.option_code.in_(all_option_codes)
            ).all() if all_option_codes else []
            option_master_map = {opt.option_code: opt.option_master_id for opt in option_masters}
            
            # 3. 옵션 매핑
            options_to_save = []
            for rec in records:
                vehicle_id = vehicle_map.get(rec['car_seq'])
                if vehicle_id:
                    platform_options = rec.get('options', [])
                    global_codes = convert_platform_options_to_global(platform_options, 'encar')
                    
                    for code in global_codes:
                        option_master_id = option_master_map.get(code)
                        if option_master_id:
                            options_to_save.append({'vehicle_id': vehicle_id, 'option_master_id': option_master_id})
            
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
            existing_records = session.query(InsuranceHistory).filter(
                InsuranceHistory.vehicle_id.in_(vehicle_ids),
                InsuranceHistory.platform == 'encar'
            ).all()
            
            existing_keys = {(r.vehicle_id, r.platform) for r in existing_records}
            
            # 신규 레코드만 필터링
            new_records = []
            for record in insurance_records:
                key = (record['vehicle_id'], record['platform'])
                if key not in existing_keys:
                    new_records.append(InsuranceHistory(**record))
            
            # 신규 레코드만 배치 삽입
            if new_records:
                session.bulk_save_objects(new_records)
                print(f"  [보험 이력] {len(new_records)}건 저장")
            
            return len(new_records)
    except Exception as e:
        print(f"  [보험 이력 저장 오류] {e}")
        return 0

def save_inspection_to_db(inspection_records: List[Dict]):
    """검사 이력을 DB에 저장 (Inspection + InspectionDetails)"""
    if not inspection_records:
        print(f"  [검사 이력 저장] 저장할 레코드가 없음")
        return 0
    
    try:
        with session_scope() as session:
            saved_count = 0
            
            for record in inspection_records:
                vehicle_id = record['inspection']['vehicle_id']
                
                # 기존 검사 이력 확인 및 삭제
                existing = session.query(Inspection).filter(
                    Inspection.vehicle_id == vehicle_id,
                    Inspection.platform == 'encar'
                ).first()
                
                if existing:
                    # 기존 InspectionDetail 삭제
                    session.query(InspectionDetail).filter(
                        InspectionDetail.inspection_id == existing.inspection_id
                    ).delete()
                    session.delete(existing)
                    session.flush()
                
                # 1) Inspection 저장
                inspection_obj = Inspection(**record['inspection'])
                session.add(inspection_obj)
                session.flush()  # inspection_id 생성을 위해 flush
                
                # 2) InspectionDetail (INNER) 저장 - inspection_id 설정
                if record['items']:
                    for item_data in record['items']:
                        item_data['inspection_id'] = inspection_obj.inspection_id
                        session.add(InspectionDetail(**item_data))
                
                # 3) InspectionDetail (OUTER) 저장 - inspection_id 설정
                if record['panels']:
                    for panel_data in record['panels']:
                        panel_data['inspection_id'] = inspection_obj.inspection_id
                        session.add(InspectionDetail(**panel_data))
                
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

# =============================================================================
# 크롤링 로직
# =============================================================================
def crawl_encar_model(brand: str, model: str, session: requests.Session, existing_data: Dict[str, set], max_pages: int = 1000, page_size: int = 50, car_type: str = "Y"):
    """특정 모델그룹 크롤링"""
    print(f"\n[{brand} {model}] 크롤링 시작")
    
    total_processed = 0
    
    for page in range(max_pages):
        print(f"  [페이지 {page + 1}] 조회 중...", end='', flush=True)
        
        q_filter = f"(And.Hidden.N._.(C.CarType.{car_type}._.(C.Manufacturer.{brand}._.ModelGroup.{model}.)))"
        car_list = get_car_list(session, q_filter, page, page_size)
        
        if not car_list:
            print(" → 완료 (더 이상 데이터 없음)")
            break
        
        # 중복 제거
        new_cars = [car for car in car_list if car.get("Id") and str(car["Id"]) not in existing_data['car_seqs']]
        
        if not new_cars:
            print(" → 신규 없음")
            _sleep_with_jitter(0.2, 0.1)
            continue
        
        print()  # 줄바꿈

        processed_records = []

        # 병렬 처리로 차량 상세 정보 수집
        with ThreadPoolExecutor(max_workers=10) as executor:
            # 미래에 완료될 작업의 결과를 담을 컨테이너 Future 객체 생성
            future_to_car = {executor.submit(fetch_vehicle_details, car["Id"], session): car for car in new_cars}
            
            # as_completed은 완료된 작업부터 처리
            for future in as_completed(future_to_car):
                encar_data = future_to_car[future]
                try:
                    # 작업이 완료되면 결과를 반환
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
            car_seq = str(record['car_seq'])
            vehicle_no = record['vehicle_no']
            
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
            
            # 저장된 데이터를 existing_data에 실시간 추가
            for record in final_records:
                existing_data['car_seqs'].add(str(record['car_seq']))
                if record['vehicle_no']:
                    existing_data['vehicle_nos'].add(record['vehicle_no'])
            
            print(f"    → 최종 {len(final_records)}건 신규 → {saved_count}건 저장")
            
            # 저장 성공한 경우에만 기존 데이터에 추가
            if saved_count > 0:
                # 보험 이력 및 검사 이력 저장 (배치 처리)
                car_seqs = [rec['car_seq'] for rec in final_records]
                
                with session_scope() as db_session:
                    # 한 번에 모든 Vehicle ID 조회
                    vehicles = db_session.query(Vehicle).filter(Vehicle.car_seq.in_(car_seqs)).all()
                    vehicle_map = {v.car_seq: v.vehicle_id for v in vehicles}
                    
                    insurance_records = []
                    inspection_records = []
                    
                    for rec in final_records:
                        if rec['car_seq'] not in vehicle_map:
                            continue
                        
                        vehicle_id = vehicle_map[rec['car_seq']]
                        
                        # 보험 이력 변환
                        if rec.get('insurance_info'):
                            insurance_record = convert_to_insurance_record(rec['insurance_info'], vehicle_id)
                            if insurance_record:
                                insurance_records.append(insurance_record)
                        
                        # 검사 이력 변환
                        if rec.get('inspection_info'):
                            inspection_record = convert_to_inspection_record(rec['inspection_info'], vehicle_id)
                            if inspection_record:
                                inspection_records.append(inspection_record)
                    
                    if insurance_records:
                        save_insurance_to_db(insurance_records)
                    
                    if inspection_records:
                        save_inspection_to_db(inspection_records)
            
            # 저장 성공한 레코드만 기존 데이터에 추가
            for rec in final_records:
                existing_data['car_seqs'].add(str(rec['car_seq']))
                if rec['vehicle_no']:
                    existing_data['vehicle_nos'].add(rec['vehicle_no'])
        
        _sleep_with_jitter(1.0, 0.5)
        
    return total_processed

def crawl_encar(max_pages_per_modelgroup: int = 1000, page_size: int = 50, cleanup_first: bool = True):
    """엔카 통합 크롤러 (차량 정보 + 옵션 + 보험이력 + 검사이력)"""
    print("="*80)
    print("엔카 통합 크롤러")
    print("="*80)
    
    create_tables_if_not_exist()
    if not check_database_status(): 
        return
    initialize_global_options()
    
    # 1. 판매된 차량 정리 (선택적)
    if cleanup_first:
        print("\n[1단계] 판매된 차량 정리")
        print("="*80)
        cleanup_sold_vehicles(batch_size=50)
        print()
    
    # 2. 새 차량 크롤링
    print("[2단계] 새 차량 크롤링")
    print("="*80)
    
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
        if total_count_data is None:
            print(f"[전체 {origin_name} 수] 조회 실패 - 건너뜁니다")
        else:
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

    print(f"\n{'='*80}")
    print(f"✅ 엔카 크롤링 완료")
    print(f"{'='*80}")
    print(f"현재 DB의 엔카 차량: {len(existing_data['car_seqs']):,}대")

def cleanup_sold_vehicles(batch_size: int = 50):
    """판매된 차량 정리 (API에서 404 반환 시 DB에서 제거)"""
    print("[판매된 차량 정리 시작]")
    
    total_deleted = 0
    
    with session_scope() as session:
        total_vehicles = session.query(Vehicle).filter(Vehicle.platform == 'encar').count()
        print(f"[대상] DB 엔카 차량 {total_vehicles:,}대")
        
        offset = 0
        while True:
            vehicles_to_check = session.query(Vehicle).filter(
                Vehicle.platform == 'encar'
            ).offset(offset).limit(batch_size).all()
            
            if not vehicles_to_check:
                break
            
            print(f"[확인 중] {offset}~{offset+len(vehicles_to_check)} / {total_vehicles}", end='', flush=True)
            
            with requests.Session() as http_session:
                http_session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                deleted_count = 0
                for vehicle in vehicles_to_check:
                    # 보험이력 API로 판매 여부 확인
                    record_api_url = f"{RECORD_API_URL}/{vehicle.car_seq}/open?vehicleNo={vehicle.vehicle_no}"
                    record_info = get_encar_api_data(record_api_url, http_session)
                    
                    if not record_info:
                        # 보험이력이 없으면 판매된 차량
                        if _delete_vehicle_cascade(session, vehicle.vehicle_id):
                            deleted_count += 1
                
                if deleted_count > 0:
                    print(f" → {deleted_count}대 삭제")
                else:
                    print(f" → 삭제 없음")
                
                total_deleted += deleted_count
                offset += batch_size
    
    print(f"[판매된 차량 정리 완료] 총 {total_deleted:,}대 삭제")


# =============================================================================
# 메인 실행
# =============================================================================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='엔카 통합 크롤러 (차량 정보 + 옵션 + 보험이력 + 검사이력)')
    parser.add_argument('--page-size', type=int, default=50,
                       help='페이지 크기 (기본값: 50)')
    parser.add_argument('--no-cleanup', action='store_true',
                       help='판매된 차량 정리 건너뛰기 (기본: 정리 후 크롤링)')
    
    args = parser.parse_args()
    
    try:
        crawl_encar(page_size=args.page_size, cleanup_first=not args.no_cleanup)
        
        print("\n" + "="*80)
        print("✅ 엔카 크롤러 완료")
        print("="*80)
    except KeyboardInterrupt:
        print("\n\n[중단] 사용자가 크롤링을 중단했습니다.")
    except Exception as e:
        print(f"\n[오류] 크롤러 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()