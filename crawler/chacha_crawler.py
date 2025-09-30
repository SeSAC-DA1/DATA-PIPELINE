import re, json, time, requests, sys, os
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# DB 관련
from db.connection import session_scope
from db.model import (
    Vehicle, OptionMaster, VehicleOption, Inspection,
    create_tables_if_not_exist, check_database_status
)

# 옵션 매핑
from crawler.option_mapping import (
    initialize_global_options, convert_platform_options_to_global
)

# Selenium 관련
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# =============================================================================
# 상수 및 설정
# =============================================================================
KB_HOST = "https://www.kbchachacha.com"
DETAIL_URL = f"{KB_HOST}/public/car/detail.kbc"
MAKER_URL = f"{KB_HOST}/public/search/carMaker.json?page=1&sort=-orderDate"
API_RECENT_URL = f"{KB_HOST}/public/car/common/recent/car/list.json"
OPTION_LAYER_URL = f"{KB_HOST}/public/layer/car/option/list.kbc"
OPTION_MASTER_URL = f"{KB_HOST}/public/car/option/code/list.json"

# =============================================================================
# 1. 세션 관리 및 유틸리티
# =============================================================================

def get_cookies_from_selenium(car_seq: str) -> str:
    """셀레니움으로 쿠키 자동 획득"""
    options = Options()
    options.add_argument('--headless=new')
    driver = webdriver.Chrome(options=options)

    try:
        detail_url = f"{DETAIL_URL}?carSeq={car_seq}"
        driver.get(detail_url)
        
        print(f"[챌린지 통과] carSeq: {car_seq}")
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CLASS_NAME, "detail-info-table"))
            )
            print("[챌린지 통과 완료]")
        except:
            print("[챌린지 통과 시간 초과, 쿠키는 획득]")
        
        cookies = driver.get_cookies()
        cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        
        print(f"[새 쿠키 획득 완료] {len(cookies)}개")
        return cookie_string
        
    finally:
        driver.quit()

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
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "ko,ko-KR;q=0.9,en-US;q=0.8,en;q=0.7",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://www.kbchachacha.com/",
    })

    # 워밍업
    try:
        s.get("https://www.kbchachacha.com/public/search/main.kbc", timeout=10)
        time.sleep(0.5)
        s.get(f"{KB_HOST}/public/search/list.empty?page=1&sort=-orderDate", timeout=10)
    except Exception:
        pass
    return s

def get_existing_car_seqs() -> set:
    """DB에서 이미 크롤링된 carSeq들을 가져옵니다."""
    with session_scope() as session:
        result = session.query(Vehicle.carseq).filter(Vehicle.platform == "kb_chachacha").all()
        return {str(row[0]) for row in result}

# =============================================================================
# 2. 데이터 수집 (API, HTML 파싱)
# =============================================================================

def get_total_car_count(session: Optional[requests.Session] = None) -> int:
    """전체 차량 수를 가져옵니다."""
    s = session or build_session()
    url = "https://www.kbchachacha.com/public/common/top/data/search.json"
    try:
        response = s.post(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("carCount", 0)
        return 0
    except Exception as e:
        print(f"[전체 차량 수 조회 오류] {e}")
        return 0

def get_maker_info(session: Optional[requests.Session] = None) -> List[Dict[str, Any]]:
    """제조사 정보를 수집합니다."""
    s = session or build_session()
    try:
        r = s.get(MAKER_URL, timeout=10)
        if r.status_code != 200:
            print(f"[제조사 정보 수집 실패] HTTP {r.status_code}")
            return []
        
        data = r.json()
        makers = []
        
        # 국산차
        for maker in data.get("result", {}).get("국산", []):
            if maker["count"] > 0:
                makers.append({
                    "makerCode": maker["makerCode"],
                    "makerName": maker["makerName"],
                    "count": maker["count"],
                    "countryCode": maker["countryCode"]
                })
        
        # 수입차
        for maker in data.get("result", {}).get("수입", []):
            if maker["count"] > 0:
                makers.append({
                    "makerCode": maker["makerCode"],
                    "makerName": maker["makerName"],
                    "count": maker["count"],
                    "countryCode": maker["countryCode"]
                })
        
        makers = sorted(makers, key=lambda x: x["count"], reverse=True)
        print(f"[제조사 정보 수집 완료] 총 {len(makers)}개 제조사")
        return makers
            
    except Exception as e:
        print(f"[제조사 정보 수집 오류] {e}")
        return []

def get_classes_for_maker(maker_code: str, session: Optional[requests.Session] = None) -> List[Dict[str, Any]]:
    """특정 제조사의 클래스별 차량 수를 가져옵니다."""
    s = session or build_session()
    url = f"https://www.kbchachacha.com/public/search/carClass.json?page=1&sort=-orderDate&makerCode={maker_code}"
    try:
        response = s.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            classes = []
            
            for class_info in data.get("result", {}).get("code", []):
                class_code = class_info["classCode"]
                class_name = class_info["className"]
                
                count = data.get("result", {}).get("sale", {}).get(class_code, 0)
                
                if count > 0:
                    classes.append({
                        "classCode": class_code,
                        "className": class_name,
                        "count": count,
                        "pages_needed": (count + 39) // 40
                    })
            
            return sorted(classes, key=lambda x: x["count"], reverse=True)
        return []
    except Exception as e:
        print(f"[클래스 정보 조회 오류] {e}")
        return []

def get_car_info_via_api(car_seqs: List[str], session: Optional[requests.Session] = None) -> List[Dict[str, Any]]:
    """API를 통해 차량 기본 정보를 수집합니다."""
    s = session or build_session()
    batch_size = 30
    all_results = []
    
    for i in range(0, len(car_seqs), batch_size):
        batch_seqs = car_seqs[i:i + batch_size]
        
        payload = {
            "gotoPage": 1,
            "pageSize": 30,
            "carSeqVal": ",".join(batch_seqs),
        }
        headers = {
            "Accept": "*/*",
            "Referer": f"{KB_HOST}/public/search/main.kbc",
        }
        
        try:
            r = s.post(API_RECENT_URL, data=payload, headers=headers, timeout=10)
            if r.status_code != 200:
                print(f"[API 오류] {r.status_code}")
                continue
                
            data = r.json()
            batch_results = data.get("list", [])
            all_results.extend(batch_results)
            
            print(f"[배치 {i//batch_size + 1}] {len(batch_results)}개 수집")
            time.sleep(0.2)
            
        except json.JSONDecodeError as e:
            print(f"[JSON 파싱 오류] 배치 {i//batch_size + 1}: {e}")
            continue
        except Exception as e:
            print(f"[API 요청 실패] 배치 {i//batch_size + 1}: {e}")
            continue
    
    return all_results

# =============================================================================
# 3. 페이지 크롤링 (carSeq 수집)
# =============================================================================

def get_car_seqs_from_page(page_num: int, maker_code: str = None, class_code: str = None, session: Optional[requests.Session] = None) -> List[str]:
    """페이지에서 carSeq들을 추출합니다."""
    s = session or build_session()
    
    url = f"https://www.kbchachacha.com/public/search/list.empty?page={page_num}&sort=-orderDate"
    if maker_code:
        url += f"&makerCode={maker_code}"
    if class_code:
        url += f"&classCode={class_code}"
    
    try:
        res = s.get(url, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            page_car_seqs = []
            
            # 우선순위 1: .area 클래스의 data-car-seq 속성
            area_elements = soup.select('.area[data-car-seq]')
            for area in area_elements:
                car_seq = area.get('data-car-seq')
                if car_seq:
                    page_car_seqs.append(car_seq)
            
            # 우선순위 2: 간편정보 섹션에서 href 속성
            if not page_car_seqs:
                car_links = soup.select('.simpleInfo__list a[href*="carSeq="]')
                for link in car_links:
                    href = link.get('href', '')
                    match = re.search(r'carSeq=(\d+)', href)
                    if match:
                        car_seq = match.group(1)
                        page_car_seqs.append(car_seq)
            
            # 우선순위 3: 광고대기 섹션
            if not page_car_seqs:
                dealer_links = soup.select('.dealer-name[data-car-seq]')
                for link in dealer_links:
                    car_seq = link.get('data-car-seq')
                    if car_seq:
                        page_car_seqs.append(car_seq)
                
                history_links = soup.select('.history[data-car-seq]')
                for link in history_links:
                    car_seq = link.get('data-car-seq')
                    if car_seq:
                        page_car_seqs.append(car_seq)
            
            return list(set(page_car_seqs))
        else:
            return []
    except Exception as e:
        return []

def crawl_car_seqs(maker_code: str = None, maker_name: str = None, class_code: str = None, class_name: str = None, max_pages: int = 250, session: Optional[requests.Session] = None) -> List[str]:
    """통합 크롤링 함수"""
    existing_seqs = get_existing_car_seqs()
    s = session or build_session()
    all_car_seqs = []
    
    display_name = ""
    if maker_name and class_name:
        display_name = f"{maker_name} {class_name}"
    elif maker_name:
        display_name = maker_name
    else:
        display_name = "전체"
    
    print(f"  [{display_name}] 크롤링 시작...")
    
    for page in range(1, max_pages + 1):
        page_car_seqs = get_car_seqs_from_page(page, maker_code, class_code, s)
        
        if not page_car_seqs:
            print(f"  [{display_name}] 페이지 {page}에서 데이터 없음 - 크롤링 완료")
            break
            
        new_seqs = [seq for seq in page_car_seqs if seq not in existing_seqs]
        all_car_seqs.extend(new_seqs)
        
        if page % 50 == 0:
            print(f"  [{display_name}] 페이지 {page}: 총 {len(all_car_seqs)}개 수집")
        
        time.sleep(0.2)
    
    return list(set(all_car_seqs))

# =============================================================================
# 4. 상세 정보 크롤링 (HTML 파싱, 옵션 추출)
# =============================================================================

def get_car_detail_from_html(car_seq: str, session: Optional[requests.Session] = None) -> tuple[Dict[str, Any], requests.Session]:
    """HTML에서 상세 정보를 파싱합니다."""
    s = session or build_session()
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Referer": "https://www.kbchachacha.com/public/search/main.kbc",
    }
    try:
        r = s.get(DETAIL_URL, params={"carSeq": car_seq}, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        # 기본정보 표 파싱
        kv: Dict[str, str] = {}
        for tr in soup.select(".detail-info-table tbody tr"):
            tds = tr.select("th,td")
            for i in range(0, len(tds), 2):
                k = tds[i].get_text(strip=True)
                v = tds[i + 1].get_text(strip=True) if i + 1 < len(tds) else ""
                kv[k] = v
        
        # 이미지 URL 추출
        def _pick_first_image_from_jsonld(soup):
            for tag in soup.select('script[type="application/ld+json"]'):
                try:
                    data = json.loads(tag.get_text(strip=True) or "{}")
                except Exception:
                    continue
                candidates = data if isinstance(data, list) else [data]
                for obj in candidates:
                    if obj.get("@type") == "Product":
                        imgs = obj.get("image")
                        if isinstance(imgs, list) and imgs:
                            return imgs[0].split("?")[0]
                        if isinstance(imgs, str) and imgs:
                            return imgs.split("?")[0]
            return None

        def _pick_first_image_url(soup):
            u = _pick_first_image_from_jsonld(soup)
            if u: return u
            og = soup.select_one('meta[property="og:image"]')
            if og and og.get("content"):
                return og["content"].split("?")[0]
            img_el = soup.select_one(".slide-img img[src]") or soup.select_one("#btnCarPhotoView img[src]")
            if img_el and img_el.get("src"):
                return img_el["src"].split("?")[0]
            return None

        image_url = _pick_first_image_url(soup)
        
        # 이미지 URL이 없으면 셀레니움으로 쿠키 갱신
        if not image_url:
            print(f"[쿠키 갱신] carSeq={car_seq} - image_url 없음, 셀레니움으로 새 쿠키 획득 중...")
            
            try:
                new_cookie_string = get_cookies_from_selenium(car_seq)
                s.cookies.clear()
                
                for cookie in new_cookie_string.split('; '):
                    if '=' in cookie:
                        name, value = cookie.split('=', 1)
                        s.cookies.set(name.strip(), value.strip(), domain='.kbchachacha.com')
                
                print(f"[재시도] carSeq={car_seq} - 새 쿠키로 상세페이지 재요청...")
                r = s.get(DETAIL_URL, params={"carSeq": car_seq}, headers=headers, timeout=15)
                soup = BeautifulSoup(r.text, "html.parser")
                image_url = _pick_first_image_url(soup)
                
                if image_url:
                    print(f"[쿠키 갱신 성공] carSeq={car_seq} - image_url 획득")
                else:
                    print(f"[쿠키 갱신 실패] carSeq={car_seq} - 여전히 image_url 없음")
                    
            except Exception as e:
                print(f"[쿠키 갱신 오류] carSeq={car_seq}: {e}")

        # 신차가격 파싱
        scripts_text = "\n".join(s.get_text() for s in soup.find_all("script"))
        newcar_price: Optional[int] = None
        m = re.search(r"var\s+newcarPrice\s*=\s*['\"](\d+)['\"]", scripts_text)
        if m:
            base = int(m.group(1))
            newcar_price = int(base * 1.1)

        # 배기량 파싱 (cc 단위로 변환)
        displacement_str = kv.get("배기량", "") or kv.get("엔진", "")
        displacement = 0
        if displacement_str:
            # "1.6L", "1600cc", "1,600cc" 등의 형태를 처리
            displacement_match = re.search(r'(\d+(?:,\d+)*)\s*(?:cc|L)', displacement_str)
            if displacement_match:
                displacement_value = displacement_match.group(1).replace(',', '')
                displacement = int(displacement_value)
                # L 단위인 경우 cc로 변환 (예: 1.6L -> 1600cc)
                if 'L' in displacement_str and displacement < 1000:
                    displacement = int(displacement * 1000)

        return {
            "fuel": kv.get("연료", ""),
            "transmission": kv.get("변속기", ""),
            "class": kv.get("차종", ""),
            "color": kv.get("색상", ""),
            "displacement": displacement,
            "image_url": image_url or "",
            "newcar_price": newcar_price,
        }, s
    except Exception as e:
        print(f"[HTML 파싱 오류] carSeq: {car_seq}: {e}")
        return {}, s

def get_car_options_from_html(car_seq: str, s: requests.Session) -> List[Dict[str, Any]]:
    """차량 옵션 코드만 추출"""
    try:
        headers = {
            "Accept": "text/html, */*;q=0.1",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{DETAIL_URL}?carSeq={car_seq}",
            "Accept-Language": "ko-KR,ko;q=0.9",
        }
        payload = {
            "layerId": "layerCarOptionView",
            "carSeq": car_seq,
        }

        resp = s.post(OPTION_LAYER_URL, data=payload, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"[옵션 요청 실패] carSeq: {car_seq} - HTTP {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        hidden = soup.select_one("input#carOption")
        
        if not hidden or not hidden.has_attr("value"):
            print(f"[옵션 없음] carSeq: {car_seq} - 옵션 정보가 없습니다")
            return []
        
        codes = [c for c in hidden["value"].split(",") if c]
        
        if not codes:
            print(f"[옵션 없음] carSeq: {car_seq} - 옵션 코드가 비어있습니다")
            return []
        
        print(f"[옵션 발견] carSeq: {car_seq} - {len(codes)}개 옵션")
        return [{"code": c} for c in codes]

    except Exception as e:
        print(f"[옵션 파싱 오류] carSeq: {car_seq}: {e}")
        return []

# =============================================================================
# 5. 데이터 변환 및 저장
# =============================================================================

def create_vehicle_record(api_data: Dict[str, Any], html_data: Dict[str, Any], maker_info: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """DB 테이블 구조에 맞는 차량 레코드를 생성"""
    car_seq = api_data.get("carSeq", "")
    maker_code = api_data.get("makerCode", "")
    country_code = maker_info.get(maker_code, {}).get("countryCode", "알수없음")

    price = api_data.get("sellAmt", 0)
    owner_yn = api_data.get("ownerYn", "Y")
    sell_type = "리스" if owner_yn == "N" else "일반"

    record = {
        "vehicle_id": None,
        "vehicle_no": api_data.get("carNo", ""),
        "car_seq": car_seq,
        "platform": "kb_chachacha",
        "origin": country_code,
        "car_type": html_data.get("class", "기타"),
        "manufacturer": api_data.get("makerName", ""),
        "model": api_data.get("className", ""),
        "generation": api_data.get("carName", ""),
        "trim": api_data.get("gradeName", ""),
        "fuel_type": html_data.get("fuel", ""),
        "transmission": html_data.get("transmission", ""),
        "displacement": html_data.get("displacement", 0),
        "color_name": html_data.get("color", "") or api_data.get("color", ""),
        "model_year": api_data.get("yymm", ""),
        "first_registration_date": api_data.get("regiDay", ""),
        "distance": api_data.get("km", 0),
        "price": price,
        "origin_price": html_data.get("newcar_price", 0),
        "sell_type": sell_type,
        "location": api_data.get("cityName", ""),
        "detail_url": f"{DETAIL_URL}?carSeq={car_seq}",
        "photo": html_data.get("image_url", ""),
    }
    return record

def save_vehicle_options_batch(vehicles_options: List[Dict], platform: str = 'kb_chachacha') -> int:
    """차량 옵션들을 배치로 처리하여 DB에 저장 (최적화된 벌크 인서트)"""
    if not vehicles_options:
        return 0
    
    with session_scope() as session:
        try:
            # 1. 모든 옵션 마스터를 한 번에 조회 (N+1 쿼리 문제 해결)
            option_masters = {opt.option_code: opt.option_id for opt in session.query(OptionMaster).all()}
            
            # 2. 기존 VehicleOption들을 한 번에 조회
            existing_pairs = set()
            for vo in session.query(VehicleOption.vehicle_id, VehicleOption.option_id).all():
                existing_pairs.add((vo.vehicle_id, vo.option_id))
            
            # 3. 벌크 인서트용 데이터 준비
            bulk_data = []
            
            for vehicle_data in vehicles_options:
                vehicle_id = vehicle_data['vehicle_id']
                options = vehicle_data['options']
                
                if not options:
                    continue
                
                # 플랫폼별 옵션 코드 추출 및 공통 옵션 코드로 변환
                platform_codes = [option['code'] for option in options]
                global_codes = convert_platform_options_to_global(platform_codes, platform)
                
                # 중복 제거된 옵션만 추가
                for option_code in global_codes:
                    option_id = option_masters.get(option_code)
                    if option_id and (vehicle_id, option_id) not in existing_pairs:
                        bulk_data.append({
                            'vehicle_id': vehicle_id,
                            'option_id': option_id
                        })
                        existing_pairs.add((vehicle_id, option_id))  # 중복 방지
            
            # 4. 벌크 인서트 실행
            if bulk_data:
                session.bulk_insert_mappings(VehicleOption, bulk_data)
                return len(bulk_data)
            
            return 0
            
        except Exception as e:
            print(f"[배치 옵션 저장 오류]: {e}")
            import traceback
            print(f"[DEBUG] 상세 오류: {traceback.format_exc()}")
            return 0

def save_car_info_to_db(records: List[Dict[str, Any]]) -> None:
    """차량 정보와 공통 옵션 정보를 100대씩 배치로 DB에 저장합니다."""
    if not records:
        print("저장할 레코드가 없습니다.")
        return

    BATCH_SIZE = 100
    total_records = len(records)
    total_saved = 0
    total_skipped = 0
    total_options_saved = 0
    
    print(f"[배치 저장 시작] 총 {total_records}건을 {BATCH_SIZE}개씩 배치로 저장")
    
    # 기존 차량번호를 한 번에 조회 (최적화)
    with session_scope() as session:
        existing_vehiclenos = {row[0] for row in session.query(Vehicle.vehicleno).all() if row[0]}
        print(f"[기존 DB] 저장된 차량번호: {len(existing_vehiclenos)}개")
    
    # 배치별로 처리
    for i in range(0, total_records, BATCH_SIZE):
        batch_records = records[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total_records + BATCH_SIZE - 1) // BATCH_SIZE
        
        print(f"[배치 {batch_num}/{total_batches}] {len(batch_records)}건 처리 중...")
        
        try:
            saved, skipped, options_saved = save_car_info_batch(batch_records, existing_vehiclenos)
            total_saved += saved
            total_skipped += skipped
            total_options_saved += options_saved
            
            print(f"[배치 {batch_num} 완료] 저장: {saved}건, 건너뜀: {skipped}건, 옵션: {options_saved}개")
            
        except Exception as e:
            print(f"[배치 {batch_num} 실패] {e}")
            # 개별 저장으로 fallback
            for record in batch_records:
                try:
                    saved, skipped, options_saved = save_car_info_batch([record], existing_vehiclenos)
                    total_saved += saved
                    total_skipped += skipped
                    total_options_saved += options_saved
                except Exception as individual_error:
                    print(f"[개별 저장 실패] carseq: {record.get('car_seq', 'unknown')}: {individual_error}")
                    total_skipped += 1
    
    print(f"[전체 저장 완료] 차량: {total_saved}건 저장, {total_skipped}건 건너뜀, 공통 옵션: {total_options_saved}개 저장")

def save_car_info_batch(batch_records: List[Dict[str, Any]], existing_vehiclenos: set) -> tuple[int, int, int]:
    """차량 정보 배치를 DB에 저장합니다."""
    if not batch_records:
        return 0, 0, 0
    
    with session_scope() as session:
        # 1. 중복 제거 및 데이터 준비
        vehicle_bulk_data = []
        vehicles_options = []
        skipped_count = 0
        
        for record in batch_records:
            vehicle_data = {
                'carseq': int(record.get('car_seq', 0)),
                'vehicleno': record.get('vehicle_no'),
                'platform': record.get('platform'),
                'origin': record.get('origin'),
                'cartype': record.get('car_type'),
                'manufacturer': record.get('manufacturer'),
                'model': record.get('model'),
                'generation': record.get('generation'),
                'trim': record.get('trim'),
                'fueltype': record.get('fuel_type'),
                'transmission': record.get('transmission'),
                'colorname': record.get('color_name'),
                'modelyear': int(record.get('model_year', 0)),
                'firstregistrationdate': int(record.get('first_registration_date', 0)),
                'distance': int(record.get('distance', 0)),
                'price': int(record.get('price', 0)),
                'originprice': int(record.get('origin_price', 0)),
                'selltype': record.get('sell_type'),
                'location': record.get('location'),
                'detailurl': record.get('detail_url'),
                'photo': record.get('photo'),
                'has_options': None  
            }
            
            # 중복 체크
            if vehicle_data['vehicleno'] and vehicle_data['vehicleno'] in existing_vehiclenos:
                skipped_count += 1
                continue
            
            vehicle_bulk_data.append(vehicle_data)
            
            # 옵션 정보 수집
            options = record.get('options', [])
            if options:
                vehicles_options.append({
                    'carseq': vehicle_data['carseq'],
                    'options': options
                })
        
        if not vehicle_bulk_data:
            return 0, skipped_count, 0
        
        # 2. 차량 정보 일괄 저장
        session.bulk_insert_mappings(Vehicle, vehicle_bulk_data)
        session.flush()
        
        # 3. 저장된 차량들의 ID 조회
        carseqs = [v['carseq'] for v in vehicle_bulk_data]
        saved_vehicles = session.query(Vehicle).filter(Vehicle.carseq.in_(carseqs)).all()
        vehicle_id_map = {v.carseq: v.vehicleid for v in saved_vehicles}
        
        # 4. has_options 플래그 업데이트
        vehicles_with_options = []
        vehicles_without_options = []
        
        for vehicle_data in vehicle_bulk_data:
            carseq = vehicle_data['carseq']
            vehicle_id = vehicle_id_map.get(carseq)
            
            if vehicle_id:
                # 옵션 유무 확인
                has_options = any(vo['carseq'] == carseq for vo in vehicles_options)
                if has_options:
                    vehicles_with_options.append(vehicle_id)
                else:
                    vehicles_without_options.append(vehicle_id)
        
        # has_options 플래그 일괄 업데이트
        if vehicles_with_options:
            session.query(Vehicle).filter(
                Vehicle.vehicleid.in_(vehicles_with_options)
            ).update({Vehicle.has_options: True}, synchronize_session=False)
        
        if vehicles_without_options:
            session.query(Vehicle).filter(
                Vehicle.vehicleid.in_(vehicles_without_options)
            ).update({Vehicle.has_options: False}, synchronize_session=False)
        
        # 5. 옵션 정보 일괄 저장
        options_saved_count = 0
        if vehicles_options:
            # vehicle_id 매핑 추가
            for vo in vehicles_options:
                carseq = vo['carseq']
                vehicle_id = vehicle_id_map.get(carseq)
                if vehicle_id:
                    vo['vehicle_id'] = vehicle_id
            
            # 옵션 저장
            options_saved_count = save_vehicle_options_batch(vehicles_options)
        
        # 6. 기존 차량번호 목록 업데이트
        for vehicle_data in vehicle_bulk_data:
            if vehicle_data['vehicleno']:
                existing_vehiclenos.add(vehicle_data['vehicleno'])
        
        return len(vehicle_bulk_data), skipped_count, options_saved_count

# =============================================================================
# 6. 통합 크롤링 (차량 정보 + 옵션)
# =============================================================================

def crawl_complete_car_info(car_seqs: List[str], delay: float = 1.0, session: Optional[requests.Session] = None) -> List[Dict[str, Any]]:
    """차량 정보 + 옵션 정보를 크롤링합니다."""
    print(f"[차량 정보 크롤링 시작] 총 {len(car_seqs)}대")
    s = session or build_session()

    print("[제조사 정보 수집 중...]")
    makers = get_maker_info(session=s)
    maker_info = {maker["makerCode"]: maker for maker in makers}

    print("[API를 통한 기본 정보 수집 중...]")
    api_data_list = get_car_info_via_api(car_seqs, session=s)
    if not api_data_list:
        print("[API 데이터 수집 실패]")
        return []
    print(f"[API 데이터 수집 완료] {len(api_data_list)}대")

    by_seq = {str(item.get("carSeq", "")): item for item in api_data_list}
    complete_records: List[Dict[str, Any]] = []

    for i, seq in enumerate(car_seqs, 1):
        api_data = by_seq.get(str(seq), {})
        print(f"\n[{i}/{len(car_seqs)}] carSeq: {seq} 처리 중...")

        html_data, s = get_car_detail_from_html(str(seq), session=s)
        options = get_car_options_from_html(str(seq), s)
        
        record = create_vehicle_record(api_data, html_data, maker_info)
        record['options'] = options
        complete_records.append(record)

        print(
            f"   [완료] {record['manufacturer']} {record['model']} {record['generation']} | "
            f"가격: {record['price']}만원, 주행거리: {record['distance']:,}km, "
            f"이미지: {'OK' if record['photo'] else 'NO PHOTO'}, 옵션: {len(options)}개"
        )

        if i < len(car_seqs):
            time.sleep(delay)

    print(f"\n[크롤링 완료] 총 {len(complete_records)}대의 완전한 정보 수집")
    return complete_records

# =============================================================================
# 7. 옵션 전용 크롤링 (기존 차량 대상)
# =============================================================================

def crawl_options_for_existing_vehicles(batch_size: int = 50, delay: float = 0.5):
    """옵션 상태가 미확인인 차량들의 옵션 정보만 크롤링"""
    
    with session_scope() as db_session:
        # 옵션 상태가 미확인인 차량들만 조회
        vehicles_without_options = db_session.query(Vehicle).filter(
            Vehicle.platform == 'kb_chachacha',
            Vehicle.has_options.is_(None)  
        ).all()
        
        print(f"[옵션 크롤링 대상] {len(vehicles_without_options)}대")
        
        if not vehicles_without_options:
            print("[옵션 크롤링 완료] 모든 차량의 옵션 정보가 이미 있습니다.")
            return
    
    total_processed = 0
    requests_session = build_session()  # requests 세션
    
    for i in range(0, len(vehicles_without_options), batch_size):
        batch = vehicles_without_options[i:i + batch_size]
        processed = crawl_options_batch(batch, requests_session, delay)
        total_processed += processed
        
        print(f"[옵션 크롤링 진행] {i + len(batch)}/{len(vehicles_without_options)} 완료 (이번 배치: {processed}대)")
        time.sleep(1)
    
    print(f"[옵션 크롤링 완료] 총 {total_processed}대 처리")

def crawl_options_batch(vehicles: List[Vehicle], requests_session: requests.Session, delay: float = 0.5) -> int:
    """차량 배치의 옵션 정보 크롤링 (배치 처리 방식)"""
    processed_count = 0
    vehicles_options = []  # 배치 데이터 수집
    vehicles_with_options = []  # 옵션이 있는 차량들
    vehicles_without_options = []  # 옵션이 없는 차량들
    
    # 1단계: 모든 차량의 옵션 크롤링
    for vehicle in vehicles:
        try:
            options = get_car_options_from_html(str(vehicle.carseq), requests_session)
            
            if options:  # 옵션이 있는 경우
                vehicles_options.append({
                    'vehicle_id': vehicle.vehicleid,
                    'options': options
                })
                vehicles_with_options.append(vehicle.vehicleid)
                processed_count += 1
            else:  # 옵션이 없는 경우
                vehicles_without_options.append(vehicle.vehicleid)
            
        except Exception as e:
            print(f"[옵션 크롤링 실패] carseq: {vehicle.carseq}: {e}")
        
        time.sleep(delay)
    
    # 2단계: 배치로 DB 저장
    if vehicles_options:
        total_saved = save_vehicle_options_batch(vehicles_options)
        print(f"[배치 저장 완료] {len(vehicles_options)}대 차량, {total_saved}개 옵션 저장")
    
    # 3단계: has_options 플래그 업데이트
    with session_scope() as session:
        # 옵션이 있는 차량들
        if vehicles_with_options:
            session.query(Vehicle).filter(
                Vehicle.vehicleid.in_(vehicles_with_options)
            ).update({Vehicle.has_options: True}, synchronize_session=False)
        
        # 옵션이 없는 차량들
        if vehicles_without_options:
            session.query(Vehicle).filter(
                Vehicle.vehicleid.in_(vehicles_without_options)
            ).update({Vehicle.has_options: False}, synchronize_session=False)
        
        session.commit()
        print(f"[플래그 업데이트] 옵션 있음: {len(vehicles_with_options)}대, 옵션 없음: {len(vehicles_without_options)}대")
    
    return processed_count

# =============================================================================
# 8. 메인 크롤링 전략 (제조사별, 클래스별)
# =============================================================================

def crawl_kb_chachacha():
    """스마트 크롤링 전략"""
    total_processed = 0
    session = build_session()
    
    print("[전체 차량 수 확인 중...]")
    total_count = get_total_car_count(session)
    print(f"전체 차량 수: {total_count:,}대")
    
    print("[제조사별 정보 수집 중...]")
    makers = get_maker_info(session)
    
    for maker in makers:
        maker_code = maker["makerCode"]
        maker_name = maker["makerName"]
        maker_count = maker["count"]
        
        print(f"\n[{maker_name}] {maker_count:,}대 크롤링 시작...")
        
        if maker_count > 10000:
            print(f"[{maker_name}] 10,000대 초과 - 클래스별 세분화 크롤링")
            
            classes = get_classes_for_maker(maker_code, session)
            
            for class_info in classes:
                class_code = class_info["classCode"]
                class_name = class_info["className"]
                class_count = class_info["count"]
                pages_needed = class_info["pages_needed"]
                
                print(f"  - [{class_name}] {class_count:,}대 ({pages_needed}페이지)")
                
                if pages_needed > 250:
                    print(f"    경고: {class_name}은 250페이지 초과! 차량명별 세분화 필요")
                
                car_seqs = crawl_car_seqs(maker_code, maker_name, class_code, class_name, session=session)
                
                if car_seqs:
                    print(f"    [{class_name}] carSeq 수집 완료: {len(car_seqs)}개")
                    
                    print(f"    [{class_name}] 상세 정보 크롤링 시작...")
                    records = crawl_complete_car_info(car_seqs, delay=1.0, session=session)
                    
                    if records:
                        print(f" [{class_name}] DB 저장 시작...")
                        save_car_info_to_db(records)
                        total_processed += len(records)
                        print(f"    {class_name} 완료: {len(records)}건 저장")
                    else:
                        print(f"    {class_name} 상세 정보 크롤링 실패")
                else:
                    print(f"    {class_name} carSeq 수집 실패")
        else:
            print(f"[{maker_name}] 10,000대 이하 - 제조사별 크롤링")
            
            car_seqs = crawl_car_seqs(maker_code, maker_name, session=session)
            
            if car_seqs:
                print(f"  [{maker_name}] carSeq 수집 완료: {len(car_seqs)}개")
                
                print(f"  [{maker_name}] 상세 정보 크롤링 시작...")
                records = crawl_complete_car_info(car_seqs, delay=1.0, session=session)
                
                if records:
                    print(f"  [{maker_name}] DB 저장 시작...")
                    save_car_info_to_db(records)
                    total_processed += len(records)
                    print(f"{maker_name} 완료: {len(records)}건 저장")
                else:
                    print(f"{maker_name} 상세 정보 크롤링 실패")
            else:
                print(f"{maker_name} carSeq 수집 실패")
    
    print(f"\n[전체 크롤링 완료] 총 {total_processed:,}건 처리됨")
    return total_processed

# =============================================================================
# 9. 통계 및 유틸리티
# =============================================================================

def check_vehicles_without_options() -> int:
    """옵션 상태가 미확인인 차량 수를 확인합니다."""
    with session_scope() as session:
        count = session.query(Vehicle).filter(
            Vehicle.platform == 'kb_chachacha',
            Vehicle.has_options.is_(None)  # 옵션 상태가 미확인인 차량
        ).count()
        return count

def get_vehicles_without_options_details() -> List[Dict[str, Any]]:
    """옵션 상태가 미확인인 차량들의 상세 정보를 반환합니다."""
    with session_scope() as session:
        vehicles = session.query(Vehicle).filter(
            Vehicle.platform == 'kb_chachacha',
            Vehicle.has_options.is_(None)  # 옵션 상태가 미확인인 차량
        ).limit(10).all()  # 샘플로 10개만 조회
        
        result = []
        for vehicle in vehicles:
            result.append({
                'carseq': vehicle.carseq,
                'manufacturer': vehicle.manufacturer,
                'model': vehicle.model,
                'generation': vehicle.generation,
                'price': vehicle.price,
                'year': vehicle.modelyear
            })
        return result

def crawl_options_only():
    """옵션 크롤링만 실행"""
    print("[옵션 크롤링 시작]")
    
    print("[옵션 사전 초기화]")
    initialize_global_options()
    
    print("[기존 차량 옵션 크롤링]")
    crawl_options_for_existing_vehicles(batch_size=100, delay=0.5)
    
    print("[옵션 크롤링 완료]")

# =============================================================================
# 10. 메인 실행 함수
# =============================================================================

def crawl_kb_chachacha_with_options():
    """옵션 크롤링을 먼저 실행한 후 통합 크롤링을 실행합니다."""
    print("[KB차차차 통합 크롤링 시작]")
    
    # 1. DB 테이블 생성 확인
    create_tables_if_not_exist()
    
    # 2. DB 상태 확인
    db_status = check_database_status()
    if not db_status:
        print("[DB 연결 실패] 데이터베이스 연결을 확인해주세요.")
        return
    
    # 3. 옵션 상태 미확인 차량 확인
    vehicles_without_options = check_vehicles_without_options()
    print(f"[옵션 상태 확인] 옵션 상태 미확인 차량: {vehicles_without_options:,}대")
    
    # 옵션 상태 미확인 차량들의 샘플 정보 표시
    if vehicles_without_options > 0:
        sample_vehicles = get_vehicles_without_options_details()
        print(f"[옵션 상태 미확인 차량 샘플] (최대 10대):")
        for vehicle in sample_vehicles:
            print(f"  - {vehicle['manufacturer']} {vehicle['model']} {vehicle['generation']} "
                  f"(carSeq: {vehicle['carseq']}, 가격: {vehicle['price']}만원, 연식: {vehicle['year']})")
    
    # 4. 옵션 상태 미확인 차량이 있으면 옵션 크롤링 먼저 실행
    if vehicles_without_options > 0:
        print(f"[옵션 크롤링 필요] {vehicles_without_options:,}대의 옵션 정보를 먼저 크롤링합니다.")
        crawl_options_only()
        
        # 옵션 크롤링 후 다시 확인
        remaining = check_vehicles_without_options()
        print(f"[옵션 크롤링 완료] 남은 차량: {remaining:,}대")
    else:
        print("[옵션 크롤링 불필요] 모든 차량의 옵션 상태가 이미 확인되었습니다.")
    
    # 5. 통합 크롤링 실행 (새로운 차량들)
    print("[통합 크롤링 시작]")
    total_processed = crawl_kb_chachacha()
    
    if total_processed > 0:
        print(f"[전체 크롤링 성공] 총 {total_processed:,}건 처리 완료")
    else:
        print("[크롤링 완료] 새로운 차량이 없습니다.")

# =============================================================================
# 메인 실행
# =============================================================================

def convert_chacha_inspection_to_record(html_content: str, vehicle_id: int) -> Optional[Dict]:
    """차차차 검사 HTML을 Inspection 레코드로 변환"""
    try:
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 기본 정보 추출
        def get_text_by_selector(selector: str) -> str:
            element = soup.select_one(selector)
            return element.get_text(strip=True) if element else ""
        
        def get_checked_radio(prefix: str, suffix: str = "") -> str:
            """체크된 라디오 버튼 값 반환"""
            for i in range(1, 10):  # 최대 9개까지 확인
                selector = f"#{prefix}_{i}_1"
                if suffix:
                    selector = f"#{prefix}_{suffix}_{i}_1"
                element = soup.select_one(selector)
                if element and element.get('checked'):
                    return element.get('value', str(i))
            return ""
        
        def get_emission_values() -> tuple:
            """배출가스 값 추출"""
            co_element = soup.select_one('.ar')
            if co_element:
                text = co_element.get_text(strip=True)
                parts = text.split(', ')
                co = parts[0] if len(parts) > 0 else ""
                hc = parts[1] if len(parts) > 1 else ""
                smoke = parts[2] if len(parts) > 2 else ""
                return co, hc, smoke
            return "", "", ""
        
        def get_mileage() -> int:
            """주행거리 추출"""
            km_element = soup.select_one('.km')
            if km_element:
                km_text = km_element.get_text(strip=True).replace(',', '').replace('Km', '')
                try:
                    return int(km_text)
                except:
                    pass
            return 0
        
        def get_price() -> int:
            """최종 가격 추출"""
            price_elements = soup.select('.price_wrap .price')
            if price_elements:
                price_text = ''.join([elem.get_text(strip=True) for elem in price_elements])
                try:
                    return int(price_text) * 10000  # 만원 단위
                except:
                    pass
            return 0
        
        # 기본 정보 추출
        inspection_no = get_text_by_selector('.num')
        
        # 검사유효기간 추출
        validity_text = get_text_by_selector('th:contains("검사유효기간") + td')
        if ' ~ ' in validity_text:
            validity_parts = validity_text.split(' ~ ')
            inspection_valid_start = validity_parts[0] if len(validity_parts) > 0 else ""
            inspection_valid_end = validity_parts[1] if len(validity_parts) > 1 else ""
        else:
            inspection_valid_start = ""
            inspection_valid_end = ""
        
        # 보증유형
        guaranty_type = "자가보증" if soup.select_one('input[value="자가보증"]:checked') else "보험사보증"
        
        # 주행거리
        mileage = get_mileage()
        
        # 배출가스
        emission_co, emission_hc, emission_smoke = get_emission_values()
        
        # 차량 상태 정보
        accident_history = bool(soup.select_one('input[value="있음"]:checked') and '사고이력' in str(soup))
        simple_repair = bool(soup.select_one('input[value="있음"]:checked') and '단순수리' in str(soup))
        tuning = bool(soup.select_one('#bc_3_2:checked'))  # 튜닝 있음
        tuning_legal = bool(soup.select_one('#bc_31_1:checked'))  # 적법 튜닝
        special_history = bool(soup.select_one('#bc_4_2:checked'))  # 특별이력 있음
        flood_damage = bool(soup.select_one('#bc_41_1:checked'))  # 침수
        fire_damage = bool(soup.select_one('#bc_41_2:checked'))  # 화재
        usage_change = bool(soup.select_one('#bc_5_2:checked'))  # 용도변경 있음
        rental_usage = bool(soup.select_one('#bc_51_1:checked'))  # 렌트
        business_usage = bool(soup.select_one('#bc_51_3:checked'))  # 영업용
        recall_target = bool(soup.select_one('#bc_81_1:checked'))  # 리콜 대상
        recall_completed = bool(soup.select_one('#bc_82_1:checked'))  # 리콜 이행
        
        # 색상 타입
        color_type = "무채색" if soup.select_one('#bc_61_1:checked') else "유채색"
        
        # 주요옵션
        main_options = bool(soup.select_one('#bc_7_2:checked'))
        sunroof = bool(soup.select_one('#bc_71_1:checked'))
        navigation = bool(soup.select_one('#bc_71_2:checked'))
        
        # 세부 검사 결과 추출 함수
        def get_checkbox_value(prefix: str, suffix: str = "") -> str:
            """체크박스 값 반환"""
            for i in range(1, 10):
                selector = f"#{prefix}_{i}_1"
                if suffix:
                    selector = f"#{prefix}_{suffix}_{i}_1"
                element = soup.select_one(selector)
                if element and element.get('checked'):
                    return element.get('value', '1')
            return ""
        
        # 자기진단
        engine_self_diagnosis = get_checkbox_value("dc_11")
        transmission_self_diagnosis = get_checkbox_value("dc_12")
        
        # 원동기 세부검사
        engine_idle_state = get_checkbox_value("dc_21")
        oil_leak_cylinder_cover = get_checkbox_value("dc_221")
        oil_leak_cylinder_head = get_checkbox_value("dc_222")
        oil_leak_cylinder_block = get_checkbox_value("dc_223")
        oil_level = get_checkbox_value("dc_23")
        coolant_leak_cylinder_head = get_checkbox_value("dc_231")
        coolant_leak_water_pump = get_checkbox_value("dc_232")
        coolant_leak_radiator = get_checkbox_value("dc_233")
        coolant_level = get_checkbox_value("dc_234")
        common_rail = get_checkbox_value("dc_24")
        
        # 변속기 세부검사
        at_oil_leak = get_checkbox_value("dc_311")
        at_oil_level = get_checkbox_value("dc_312")
        at_idle_state = get_checkbox_value("dc_313")
        mt_oil_leak = get_checkbox_value("dc_321")
        mt_gear_shifting = get_checkbox_value("dc_322")
        mt_oil_level = get_checkbox_value("dc_323")
        mt_idle_state = get_checkbox_value("dc_324")
        
        # 동력전달 세부검사
        clutch_assembly = get_checkbox_value("dc_41")
        cv_joint = get_checkbox_value("dc_42")
        drive_shaft_bearing = get_checkbox_value("dc_43")
        differential_gear = get_checkbox_value("dc_44")
        
        # 조향 세부검사
        power_steering_oil_leak = get_checkbox_value("dc_51")
        steering_pump = get_checkbox_value("dc_522")
        steering_gear = get_checkbox_value("dc_521")
        steering_joint = get_checkbox_value("dc_524")
        power_high_pressure_hose = get_checkbox_value("dc_525")
        tie_rod_end_ball_joint = get_checkbox_value("dc_523")
        
        # 제동 세부검사
        brake_master_cylinder_oil_leak = get_checkbox_value("dc_61")
        brake_oil_leak = get_checkbox_value("dc_62")
        brake_booster_state = get_checkbox_value("dc_63")
        
        # 전기 세부검사
        generator_output = get_checkbox_value("dc_71")
        starter_motor = get_checkbox_value("dc_72")
        wiper_motor = get_checkbox_value("dc_73")
        interior_fan_motor = get_checkbox_value("dc_74")
        radiator_fan_motor = get_checkbox_value("dc_75")
        window_motor = get_checkbox_value("dc_76")
        
        # 고전원전기장치
        charger_insulation = get_checkbox_value("dc_91")
        drive_battery_isolation = get_checkbox_value("dc_92")
        high_voltage_wiring = get_checkbox_value("dc_93")
        
        # 연료
        fuel_leak = get_checkbox_value("dc_81")
        
        # 수리필요 항목
        exterior_condition = get_checkbox_value("eac_1")
        interior_condition = get_checkbox_value("eac_2")
        gloss_condition = get_checkbox_value("eac_3")
        room_cleaning = get_checkbox_value("eac_4")
        wheel_condition = get_checkbox_value("eac_5")
        tire_condition = get_checkbox_value("eac_6")
        glass_condition = get_checkbox_value("eac_7")
        
        # 기본품목
        basic_items_status = get_checkbox_value("eac_8")
        user_manual = bool(soup.select_one('#eac_83_1:checked'))
        safety_triangle = bool(soup.select_one('#eac_84_1:checked'))
        jack = bool(soup.select_one('#eac_83_1:checked'))
        spanner = bool(soup.select_one('#eac_83_1:checked'))
        
        # 검사자 정보
        inspector_name = get_text_by_selector('.name2')
        inspection_agency = get_text_by_selector('.name1')
        
        # 특기사항
        special_notes = get_text_by_selector('.wrap')
        
        # 최종 가격
        final_price = get_price()
        
        # 검사일 (서명란에서 추출)
        inspection_date = ""
        date_element = soup.find(string=lambda text: text and "년" in text and "월" in text and "일" in text)
        if date_element:
            inspection_date = date_element.strip()
        
        result = {
            "vehicle_id": vehicle_id,
            "platform": "chacha",
            
            # === 검사 식별 정보 ===
            "inspection_no": inspection_no,
            "inspection_date": inspection_date,
            "inspection_valid_start": inspection_valid_start,
            "inspection_valid_end": inspection_valid_end,
            
            # === 검사 관련 기본 정보 ===
            "guaranty_type": guaranty_type,
            "mileage": mileage,
            
            # 차량 상태 정보
            "accident_history": accident_history,
            "simple_repair": simple_repair,
            "tuning": tuning,
            "tuning_legal": tuning_legal,
            "special_history": special_history,
            "flood_damage": flood_damage,
            "fire_damage": fire_damage,
            "usage_change": usage_change,
            "rental_usage": rental_usage,
            "business_usage": business_usage,
            "color_type": color_type,
            "main_options": main_options,
            "sunroof": sunroof,
            "navigation": navigation,
            "recall_target": recall_target,
            "recall_completed": recall_completed,
            
            # 검사 상세 정보
            "emission_co": emission_co,
            "emission_hc": emission_hc,
            "emission_smoke": emission_smoke,
            
            # 검사자/발급 정보
            "inspector_name": inspector_name,
            "inspection_agency": inspection_agency,
            "final_price": final_price,
            "special_notes": special_notes,
            
            # 플랫폼별 원본 데이터
            "raw_data": {"html_content": html_content[:5000]},  # HTML 내용 일부만 저장
            
            # 세부 검사 결과
            "engine_self_diagnosis": engine_self_diagnosis,
            "transmission_self_diagnosis": transmission_self_diagnosis,
            "engine_idle_state": engine_idle_state,
            "oil_leak_cylinder_cover": oil_leak_cylinder_cover,
            "oil_leak_cylinder_head": oil_leak_cylinder_head,
            "oil_leak_cylinder_block": oil_leak_cylinder_block,
            "oil_level": oil_level,
            "coolant_leak_cylinder_head": coolant_leak_cylinder_head,
            "coolant_leak_water_pump": coolant_leak_water_pump,
            "coolant_leak_radiator": coolant_leak_radiator,
            "coolant_level": coolant_level,
            "common_rail": common_rail,
            "at_oil_leak": at_oil_leak,
            "at_oil_level": at_oil_level,
            "at_idle_state": at_idle_state,
            "mt_oil_leak": mt_oil_leak,
            "mt_gear_shifting": mt_gear_shifting,
            "mt_oil_level": mt_oil_level,
            "mt_idle_state": mt_idle_state,
            "clutch_assembly": clutch_assembly,
            "cv_joint": cv_joint,
            "drive_shaft_bearing": drive_shaft_bearing,
            "differential_gear": differential_gear,
            "power_steering_oil_leak": power_steering_oil_leak,
            "steering_pump": steering_pump,
            "steering_gear": steering_gear,
            "steering_joint": steering_joint,
            "power_high_pressure_hose": power_high_pressure_hose,
            "tie_rod_end_ball_joint": tie_rod_end_ball_joint,
            "brake_master_cylinder_oil_leak": brake_master_cylinder_oil_leak,
            "brake_oil_leak": brake_oil_leak,
            "brake_booster_state": brake_booster_state,
            "generator_output": generator_output,
            "starter_motor": starter_motor,
            "wiper_motor": wiper_motor,
            "interior_fan_motor": interior_fan_motor,
            "radiator_fan_motor": radiator_fan_motor,
            "window_motor": window_motor,
            "charger_insulation": charger_insulation,
            "drive_battery_isolation": drive_battery_isolation,
            "high_voltage_wiring": high_voltage_wiring,
            "fuel_leak": fuel_leak,
            "exterior_condition": exterior_condition,
            "interior_condition": interior_condition,
            "gloss_condition": gloss_condition,
            "room_cleaning": room_cleaning,
            "wheel_condition": wheel_condition,
            "tire_condition": tire_condition,
            "glass_condition": glass_condition,
            "basic_items_status": basic_items_status,
            "user_manual": user_manual,
            "safety_triangle": safety_triangle,
            "jack": jack,
            "spanner": spanner
        }
        
        return result
    except Exception as e:
        print(f"  [차차차 검사 데이터 변환 오류] {e}")
        return None

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
                Inspection.platform == 'chacha'
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

if __name__ == "__main__":
    print("KB 차차차 크롤러 시작")
    try:
        crawl_kb_chachacha_with_options()
    except Exception as e:
        print(f"크롤러 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()