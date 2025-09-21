import re,json,time,random,requests,os
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlencode
import pandas as pd
from connection import session_scope, Engine
from model import Vehicle, Base
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import gc 

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
# 유틸리티 함수들
# =============================================================================

def get_cookies_from_selenium(car_seq: str):
    """셀레니움으로 쿠키 자동 획득 (상세페이지까지 접근)"""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    options = Options()
    options.add_argument('--headless') #백그라운드 실행
    driver = webdriver.Chrome(options=options) #요새는 셀레니움 매니저가 알아서 해줌.

    try:
        # 상세페이지 직접 접근 (챌린지 발생 지점)
        detail_url = f"https://www.kbchachacha.com/public/car/detail.kbc?carSeq={car_seq}"
        driver.get(detail_url)
        
        # 챌린지 통과 대기 (최대 30초)
        print(f"[챌린지 통과] carSeq: {car_seq}")
        try:
            # 상세페이지 로딩 완료 대기
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CLASS_NAME, "detail-info-table"))
            )
            print("[챌린지 통과 완료]")
        except:
            print("[챌린지 통과 시간 초과, 쿠키는 획득]")
        
        # 쿠키 추출
        cookies = driver.get_cookies()
        cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        
        print(f"[새 쿠키 획득 완료] {len(cookies)}개")
        return cookie_string
        
    finally:
        driver.quit()

def build_session() -> requests.Session:
    """세션 생성 (브라우저 쿠키 사용)"""
    s = requests.Session()
    retries = Retry(
        total=5,connect=3,read=3,backoff_factor=0.7,
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
# 데이터 수집 함수들 (API 호출)
# =============================================================================

def get_total_car_count() -> int:
    """전체 차량 수를 가져옵니다."""
    url = "https://www.kbchachacha.com/public/common/top/data/search.json"
    try:
        response = requests.post(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("carCount", 0)
        return 0
    except Exception as e:
        print(f"[전체 차량 수 조회 오류] {e}")
        return 0

def get_maker_info(session: Optional[requests.Session] = None) -> List[Dict[str, Any]]:
    """제조사 정보를 수집합니다. (정렬된 리스트 형태로 반환)"""
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
                
                # sale 데이터에서 해당 클래스의 차량 수 찾기
                count = data.get("result", {}).get("sale", {}).get(class_code, 0)
                
                if count > 0:
                    classes.append({
                        "classCode": class_code,
                        "className": class_name,
                        "count": count,
                        "pages_needed": (count + 39) // 40  # 40개씩 페이지 계산
                    })
            
            return sorted(classes, key=lambda x: x["count"], reverse=True)
        return []
    except Exception as e:
        print(f"[클래스 정보 조회 오류] {e}")
        return []

def get_car_info_via_api(car_seqs: List[str], session: Optional[requests.Session] = None) -> List[Dict[str, Any]]:
    """api를 통해 차량 기본 정보를 수집합니다."""
    s = session or build_session()
    
    # 한 번에 요청할 carSeq 개수 제한 (30개씩 배치 처리)
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
                
            # 응답 내용 확인
            print(f"API 응답 길이: {len(r.text)} 문자")
            if len(r.text) < 100:
                print(f"응답 내용: {r.text}")
                
            data = r.json()
            batch_results = data.get("list", [])
            all_results.extend(batch_results)
            
            print(f"[배치 {i//batch_size + 1}] {len(batch_results)}개 수집")
            
            # 배치 간 대기
            time.sleep(0.5)
            
        except json.JSONDecodeError as e:
            print(f"[JSON 파싱 오류] 배치 {i//batch_size + 1}: {e}")
            print(f"응답 내용: {r.text[:500]}...")
            continue
        except Exception as e:
            print(f"[API 요청 실패] 배치 {i//batch_size + 1}: {e}")
            continue
    
    return all_results

# =============================================================================
# 페이지 크롤링 함수들 (carSeq 추출)
# =============================================================================

def get_car_seqs_from_page(page_num: int, maker_code: str = None, class_code: str = None, session: Optional[requests.Session] = None) -> List[str]:
    """페이지에서 carSeq들을 추출합니다. (makerCode, classCode 선택적 사용)"""
    s = session or build_session()
    
    # URL 구성
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
            
            # 우선순위 1: 전체 섹션에서 .area 클래스의 data-car-seq 속성으로 carSeq 추출 (가장 일반적)
            area_elements = soup.select('.area[data-car-seq]')
            for area in area_elements:
                car_seq = area.get('data-car-seq')
                if car_seq:
                    page_car_seqs.append(car_seq)
            
            # 우선순위 2: 간편정보 섹션에서 href 속성으로 carSeq 추출
            if not page_car_seqs:  # 전체 섹션에서 찾지 못했을 때만
                car_links = soup.select('.simpleInfo__list a[href*="carSeq="]')
                for link in car_links:
                    href = link.get('href', '')
                    # href에서 carSeq= 뒤의 숫자 추출
                    import re
                    match = re.search(r'carSeq=(\d+)', href)
                    if match:
                        car_seq = match.group(1)
                        page_car_seqs.append(car_seq)
            
            # 우선순위 3: 광고대기 섹션에서 data-car-seq 속성으로 carSeq 추출
            if not page_car_seqs:  # 위 방법들로 찾지 못했을 때만
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
            
            return list(set(page_car_seqs))  # 중복 제거
        else:
            return []
    except Exception as e:
        return []

def crawl_car_seqs(maker_code: str = None, maker_name: str = None, class_code: str = None, class_name: str = None, max_pages: int = 250, session: Optional[requests.Session] = None) -> List[str]:
    """통합 크롤링 함수 (제조사별/클래스별 모두 지원)"""
    existing_seqs = get_existing_car_seqs()
    s = session or build_session()
    all_car_seqs = []
    
    # 표시명 생성
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
        
        if page % 50 == 0:  # 50페이지마다 진행상황 출력
            print(f"  [{display_name}] 페이지 {page}: 총 {len(all_car_seqs)}개 수집")
        
        time.sleep(0.2)
    
    return list(set(all_car_seqs))

# =============================================================================
# 상세 정보 크롤링 함수들
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
        
        # JSON-LD에서 이미지 추출
        def _pick_first_image_from_jsonld(soup):
            for tag in soup.select('script[type="application/ld+json"]'):
                try:
                    data = json.loads(tag.get_text(strip=True) or "{}")
                except Exception:
                    continue
                # 단일 객체 or 배열 모두 대응
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
            # 1) JSON-LD
            u = _pick_first_image_from_jsonld(soup)
            if u: return u
            # 2) og:image
            og = soup.select_one('meta[property="og:image"]')
            if og and og.get("content"):
                return og["content"].split("?")[0]
            # 3) 갤러리 첫 장
            img_el = soup.select_one(".slide-img img[src]") or soup.select_one("#btnCarPhotoView img[src]")
            if img_el and img_el.get("src"):
                return img_el["src"].split("?")[0]
            return None

        image_url = _pick_first_image_url(soup)
        
        # image_url이 없으면 셀레니움으로 쿠키 갱신 후 재시도
        if not image_url:
            print(f"[쿠키 갱신] carSeq={car_seq} - image_url 없음, 셀레니움으로 새 쿠키 획득 중...")
            
            try:
                # 새 쿠키 획득
                new_cookie_string = get_cookies_from_selenium(car_seq)
                
                # 기존 세션에 새 쿠키 적용
                s.cookies.clear()
                
                for cookie in new_cookie_string.split('; '):
                    if '=' in cookie:
                        name, value = cookie.split('=', 1)
                        s.cookies.set(name.strip(), value.strip(), domain='.kbchachacha.com')
                
                # 재시도
                print(f"[재시도] carSeq={car_seq} - 새 쿠키로 상세페이지 재요청...")
                r = s.get(DETAIL_URL, params={"carSeq": car_seq}, headers=headers, timeout=15)
                soup = BeautifulSoup(r.text, "html.parser")
                
                # 다시 이미지 URL 추출
                image_url = _pick_first_image_url(soup)
                
                if image_url:
                    print(f"[쿠키 갱신 성공] carSeq={car_seq} - image_url 획득")
                else:
                    print(f"[쿠키 갱신 실패] carSeq={car_seq} - 여전히 image_url 없음")
                    
            except Exception as e:
                print(f"[쿠키 갱신 오류] carSeq={car_seq}: {e}")

        # 신차가격(newcarPrice) 파싱 (만원 단위, 부가세 10% 반영)
        scripts_text = "\n".join(s.get_text() for s in soup.find_all("script"))
        newcar_price: Optional[int] = None
        m = re.search(r"var\s+newcarPrice\s*=\s*['\"](\d+)['\"]", scripts_text)
        if m:
            base = int(m.group(1))
            newcar_price = int(base * 1.1)

        return {
            "fuel": kv.get("연료", ""),
            "transmission": kv.get("변속기", ""),
            "class": kv.get("차종", ""),
            "color": kv.get("색상", ""),
            "image_url": image_url or "",
            "newcar_price": newcar_price,
        }, s
    except Exception as e:
        print(f"[HTML 파싱 오류] carSeq: {car_seq}: {e}")
        return {}, s

def get_car_options_from_html(car_seq: str, session: Optional[requests.Session] = None) -> List[Dict[str, Any]]:
    """옵션 정보 수집"""
    s = session or build_session()
    base_headers = {"Accept-Language": "ko-KR,ko;q=0.9"}
    try:
        # 상세로 세션 확보
        s.get(DETAIL_URL, params={"carSeq": car_seq}, headers=base_headers, timeout=15)
        # 레이어 POST
        layer_headers = {
            **base_headers,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{DETAIL_URL}?carSeq={car_seq}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html, */*;q=0.1",
        }
        layer_res = s.post(OPTION_LAYER_URL, data={"carSeq": car_seq}, headers=layer_headers, timeout=15)
        if layer_res.status_code != 200:
            return []

        soup = BeautifulSoup(layer_res.text, "html.parser")
        hidden = soup.select_one("input#carOption")
        codes = [c for c in (hidden["value"].split(",") if hidden and hidden.has_attr("value") else []) if c]

        # 마스터 POST
        master_headers = {
            **base_headers,
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "x-ajax": "true",
            "Referer": OPTION_LAYER_URL,
        }
        master_res = s.post(OPTION_MASTER_URL, headers=master_headers, timeout=15)
        if master_res.status_code != 200:
            return []
        data = master_res.json()
        master = data["optionList"] if isinstance(data, dict) else data
        code_to_meta = {m["optionCode"]: m for m in master}

        equipped = [code_to_meta[c] for c in codes if c in code_to_meta]
        return [
            {"code": o["optionCode"], "name": o["optionName"], "group": o.get("optionGbnName", "")}
            for o in equipped
        ]
    except Exception as e:
        print(f"[옵션 파싱 오류] carSeq: {car_seq}: {e}")
        return []

# =============================================================================
# 데이터 변환 및 저장 함수들
# =============================================================================

def create_vehicle_record(api_data: Dict[str, Any], html_data: Dict[str, Any],  maker_info: Dict[str, Dict[str, Any]], session: Optional[requests.Session] = None) -> Dict[str, Any]:
    """DB 테이블 구조에 맞는 차량 레코드를 생성"""
    car_seq = api_data.get("carSeq", "")
    maker_code = api_data.get("makerCode", "")
    country_code = maker_info.get(maker_code, {}).get("countryCode", "알수없음")

    price = api_data.get("sellAmt", 0)
    
    # API의 ownerYn으로 리스 여부 판별 (N이면 리스 승계)
    owner_yn = api_data.get("ownerYn", "Y")
    sell_type = "리스" if owner_yn == "N" else "일반"

    record = {
        "VehicleId": None,
        "VehicleNo": api_data.get("carNo", ""),
        "CarSeq": car_seq,
        "Platform": "kb_chachacha",
        "Origin": country_code,
        "CarType": html_data.get("class", "기타"),
        "Manufacturer": api_data.get("makerName", ""),
        "Model": api_data.get("className", ""),
        "Generation": api_data.get("carName", ""),
        "Trim": api_data.get("gradeName", ""),
        "FuelType": html_data.get("fuel", "") ,
        "Transmission": html_data.get("transmission", ""),
        "ColorName": html_data.get("color", "") or api_data.get("color", ""),
        "ModelYear": api_data.get("yymm", ""),
        "FirstRegistrationDate": api_data.get("regiDay", ""),
        "Distance": api_data.get("km", 0),
        "Price": price,
        "OriginPrice": html_data.get("newcar_price", 0), 
        "SellType": sell_type,
        "Location": api_data.get("cityName", ""),
        "DetailURL": f"{DETAIL_URL}?carSeq={car_seq}",
        "Photo": html_data.get("image_url", ""),
    }
    return record

def save_car_info_to_db(records: List[Dict[str, Any]]) -> None:
    """차량 정보를 DB에 저장합니다."""
    if not records:
        print("저장할 레코드가 없습니다.")
        return

    with session_scope() as session:
        # 기존 vehicleno 목록 가져오기
        existing_vehiclenos = set()
        existing_records = session.query(Vehicle.vehicleno).all()
        for row in existing_records:
            if row[0]:  # None이 아닌 경우만
                existing_vehiclenos.add(row[0])
        
        print(f"[기존 DB] 저장된 차량번호: {len(existing_vehiclenos)}개")
        
        saved_count = 0
        skipped_count = 0
        
        for record in records:
            vehicle_data = {
                'carseq': int(record.get('CarSeq', 0)),
                'vehicleno': record.get('VehicleNo'),
                'platform': record.get('Platform'),
                'origin': record.get('Origin'),
                'cartype': record.get('CarType'),
                'manufacturer': record.get('Manufacturer'),
                'model': record.get('Model'),
                'generation': record.get('Generation'),
                'trim': record.get('Trim'),
                'fueltype': record.get('FuelType'),
                'transmission': record.get('Transmission'),
                'colorname': record.get('ColorName'),
                'modelyear': int(record.get('ModelYear', 0)),
                'firstregistrationdate': int(record.get('FirstRegistrationDate', 0)),
                'distance': int(record.get('Distance', 0)) ,
                'price': int(record.get('Price', 0)) ,
                'originprice': int(record.get('OriginPrice', 0)),
                'selltype': record.get('SellType'),
                'location': record.get('Location'),
                'detailurl': record.get('DetailURL'),
                'photo': record.get('Photo')
            }
            
            # vehicleno 중복 체크
            if vehicle_data['vehicleno'] and vehicle_data['vehicleno'] in existing_vehiclenos:
                skipped_count += 1
                continue
            
            try:
                vehicle = Vehicle(**vehicle_data)
                session.merge(vehicle)
                saved_count += 1
                
                # 저장된 vehicleno를 세트에 추가 (동일 배치 내 중복 방지)
                if vehicle_data['vehicleno']:
                    existing_vehiclenos.add(vehicle_data['vehicleno'])
                    
            except Exception as e:
                print(f"[저장 실패] carseq: {vehicle_data['carseq']}: {e}")
                skipped_count += 1
        
        print(f"[DB 저장 완료] {saved_count}건 저장, {skipped_count}건 건너뜀")

def crawl_complete_car_info(car_seqs: List[str], delay: float = 1.5, session: Optional[requests.Session] = None) -> List[Dict[str, Any]]:
    """완전한 차량 정보를 크롤링합니다."""
    print(f"[차량 정보 크롤링 시작] 총 {len(car_seqs)}대")
    s = session or build_session()

    print("[제조사 정보 수집 중...]")
    makers = get_maker_info(session=s)
    
    # makerCode로 빠른 조회를 위한 딕셔너리 생성
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
        
        record = create_vehicle_record(api_data, html_data,  maker_info, session=s)
        complete_records.append(record)

        print(
            f"   [완료] {record['Manufacturer']} {record['Model']} {record['Generation']} | "
            f"가격: {record['Price']}만원, 주행거리: {record['Distance']:,}km, 이미지: {'OK' if record['Photo'] else 'NO PHOTO'}"
        )

        # 기본 딜레이
        if i < len(car_seqs):
            time.sleep(delay)

    print(f"\n[크롤링 완료] 총 {len(complete_records)}대의 완전한 정보 수집")
    return complete_records

# =============================================================================
# 메인 크롤링 전략 함수들
# =============================================================================

def crawl_smart_strategy():
    """스마트 크롤링 전략: 각 제조사/클래스별로 즉시 상세 크롤링 + 저장 완료"""
    total_processed = 0
    session = build_session()
    
    print("[전체 차량 수 확인 중...]")
    total_count = get_total_car_count()
    print(f"전체 차량 수: {total_count:,}대")
    
    print("[제조사별 정보 수집 중...]")
    makers = get_maker_info(session)
    
    for maker in makers:
        maker_code = maker["makerCode"]
        maker_name = maker["makerName"]
        maker_count = maker["count"]
        
        print(f"\n[{maker_name}] {maker_count:,}대 크롤링 시작...")
        
        # 10,000대 이상인 경우 클래스별 세분화
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
                    print(f"    ⚠️ {class_name}은 250페이지 초과! 차량명별 세분화 필요")
                    # 아직 차량명 별 세분화 필요가 없어서 구현 안함.
                
                # 1. carSeq 수집
                car_seqs = crawl_car_seqs(maker_code, maker_name, class_code, class_name, session=session)
                
                if car_seqs:
                    print(f"    [{class_name}] carSeq 수집 완료: {len(car_seqs)}개")
                    
                    # 2. 상세 정보 크롤링
                    print(f"    [{class_name}] 상세 정보 크롤링 시작...")
                    records = crawl_complete_car_info(car_seqs, delay=1.5, session=session)
                    
                    # 3. DB 저장
                    if records:
                        print(f"    [{class_name}] DB 저장 시작...")
                        save_car_info_to_db(records)
                        total_processed += len(records)
                        print(f"    ✅ {class_name} 완료: {len(records)}건 저장")
                    else:
                        print(f"    ❌ {class_name} 상세 정보 크롤링 실패")
                else:
                    print(f"    ❌ {class_name} carSeq 수집 실패")
        else:
            print(f"[{maker_name}] 10,000대 이하 - 제조사별 크롤링")
            
            # 1. carSeq 수집
            car_seqs = crawl_car_seqs(maker_code, maker_name, session=session)
            
            if car_seqs:
                print(f"  [{maker_name}] carSeq 수집 완료: {len(car_seqs)}개")
                
                # 2. 상세 정보 크롤링
                print(f"  [{maker_name}] 상세 정보 크롤링 시작...")
                records = crawl_complete_car_info(car_seqs, delay=1.5, session=session)
                
                # 3. DB 저장
                if records:
                    print(f"  [{maker_name}] DB 저장 시작...")
                    save_car_info_to_db(records)
                    total_processed += len(records)
                    print(f"✅ {maker_name} 완료: {len(records)}건 저장")
                else:
                    print(f"❌ {maker_name} 상세 정보 크롤링 실패")
            else:
                print(f"❌ {maker_name} carSeq 수집 실패")
    
    print(f"\n[전체 크롤링 완료] 총 {total_processed:,}건 처리됨")
    return total_processed

# =============================================================================
# 실행 부분
# =============================================================================

if __name__ == "__main__":
    # 스마트 크롤링 전략 실행 (각 제조사/클래스별로 즉시 처리)
    print("[크롤링 시작]")
    total_processed = crawl_smart_strategy()
    
    if total_processed > 0:
        print(f"[전체 크롤링 성공] 총 {total_processed:,}건 처리 완료")
    else:
        print("[크롤링 실패] 처리된 데이터가 없습니다.")