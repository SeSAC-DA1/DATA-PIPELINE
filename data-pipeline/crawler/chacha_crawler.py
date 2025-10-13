import re, json, time, requests, sys, os
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 환경변수 로드
load_dotenv()

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# DB 관련
from db.connection import session_scope
from db.model import (
    Vehicle, OptionMaster, VehicleOption, Inspection, InsuranceHistory,
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
INSURANCE_HISTORY_CHECK_URL = f"{KB_HOST}/public/layer/car/history/info/check.json"
INSURANCE_HISTORY_INFO_URL = f"{KB_HOST}/public/car/layer/member/car/history/info.kbc"

# =============================================================================
# 1. 세션 관리 및 유틸리티
# =============================================================================

def get_cookies_from_selenium(car_seq: str) -> List[Dict[str, Any]]:
    """셀레니움으로 쿠키 자동 획득 (헤드리스 모드)"""
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get(f"{DETAIL_URL}?carSeq={car_seq}")
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CLASS_NAME, "detail-info-table"))
            )
        except:
            pass
        
        cookies = driver.get_cookies()
        print(f"[새 쿠키 획득 완료] {len(cookies)}개")
        return cookies
    finally:
        driver.quit()

def login_with_naver_via_insurance(car_seq: str) -> Optional[webdriver.Chrome]:
    """보험이력 조회 팝업을 통한 네이버 SNS 로그인 (키보드 보안 프로그램 없음)"""
    naver_id = os.getenv('NAVER_ID')
    naver_password = os.getenv('NAVER_PASSWORD')
    
    if not naver_id or not naver_password:
        print("[로그인 오류] .env 파일에 NAVER_ID와 NAVER_PASSWORD를 설정해주세요.")
        return None
    
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    # 자동화 탐지 우회 옵션
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=options)
    
    # WebDriver 속성 숨기기
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        '''
    })
    
    try:
        # 1. 차량 상세 페이지로 이동
        print(f"[SNS 로그인] 차량 상세 페이지 이동 (carSeq={car_seq})...")
        driver.get(f"{DETAIL_URL}?carSeq={car_seq}")
        
        # 챌린지 통과 대기 (로봇 체크 자동 통과)
        print("[SNS 로그인] 챌린지 통과 대기 중...")
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CLASS_NAME, "detail-info-table"))
            )
            print("[SNS 로그인] 챌린지 통과 완료")
        except:
            print("[SNS 로그인] 챌린지 통과 시간 초과, 계속 진행...")
        
        time.sleep(1)
        
        # 2. 보험이력 버튼 클릭 (이때 SNS 로그인 팝업이 자동으로 뜸)
        print("[SNS 로그인] 보험이력 버튼 클릭...")
        try:
            insurance_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "btnCarHistoryView1"))
            )
            print("[SNS 로그인] 보험이력 버튼 발견")
            insurance_btn.click()
            time.sleep(2)
            
        except Exception as e:
            print(f"[SNS 로그인] 보험이력 버튼 클릭 실패: {e}")
            driver.quit()
            return None
        
        # 3. SNS 로그인 팝업에서 네이버 버튼 클릭
        print("[SNS 로그인] SNS 로그인 팝업에서 네이버 버튼 찾는 중...")
        try:
            # 네이버 로그인 버튼 클릭 (정확한 셀렉터)
            naver_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.sns-login__link-naver"))
            )
            print("[SNS 로그인] 네이버 SNS 로그인 버튼 클릭")
            naver_btn.click()
            time.sleep(2)
                
        except Exception as e:
            print(f"[SNS 로그인] 네이버 버튼 찾기 실패: {e}")
            driver.quit()
            return None
        
        # 4. 네이버 로그인 창으로 전환
        print("[SNS 로그인] 네이버 로그인 창 전환...")
        original_window = driver.current_window_handle
        
        # 새 창 대기
        WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > 1)
        
        for window in driver.window_handles:
            if window != original_window:
                driver.switch_to.window(window)
                break
        
        # 5. 네이버 아이디/비밀번호 입력
        print("[SNS 로그인] 네이버 아이디/비밀번호 입력...")
        try:
            id_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "id"))
            )
            
            # JavaScript로 입력
            driver.execute_script(f"document.getElementById('id').value = '{naver_id}';")
            driver.execute_script(f"document.getElementById('pw').value = '{naver_password}';")
            
            # 로그인 버튼 클릭
            print("[SNS 로그인] 네이버 로그인 실행...")
            login_submit = driver.find_element(By.ID, "log.login")
            login_submit.click()
            time.sleep(3)
            
        except Exception as e:
            print(f"[SNS 로그인] 네이버 로그인 실패: {e}")
            driver.quit()
            return None
        
        # 6. 원래 창으로 돌아가기
        driver.switch_to.window(original_window)
        time.sleep(2)
        
        print("[SNS 로그인] ✅ 로그인 성공!")
        return driver
            
    except Exception as e:
        print(f"[SNS 로그인 오류] {e}")
        import traceback
        traceback.print_exc()
        driver.quit()
        return None

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
        result = session.query(Vehicle.car_seq).filter(Vehicle.platform == "kb_chachacha").all()
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

def get_car_detail_from_html(car_seq: str, session: Optional[requests.Session] = None) -> tuple[Dict[str, Any], requests.Session, bool]:
    """HTML에서 상세 정보를 파싱합니다.
    
    Returns:
        (차량 정보, 세션, 쿠키_갱신_여부)
    """
    s = session or build_session()
    cookie_refreshed = False  # 쿠키 갱신 플래그
    
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
                cookies = get_cookies_from_selenium(car_seq)
                
                # 기존 세션 버리고 새 세션 생성
                s = build_session()
                s.cookies.clear()
                
                # 도메인/경로 보존 + www/non-www 양쪽에 set
                for c in cookies:
                    name, value = c['name'], c['value']
                    domain = c.get('domain') or 'kbchachacha.com'
                    path = c.get('path') or '/'
                    
                    # 원본 그대로
                    s.cookies.set(name, value, domain=domain, path=path, 
                                 secure=c.get('secure', False), expires=c.get('expiry'))
                    
                    # www 보정 쿠키도 추가 (KB가 둘 다 쓰는 케이스 방지)
                    if domain.lstrip('.').startswith('kbchachacha.com'):
                        s.cookies.set(name, value, domain='www.kbchachacha.com', path=path, 
                                     secure=c.get('secure', False), expires=c.get('expiry'))
                
                cookie_refreshed = True  # 쿠키 갱신됨 (보험이력 로그인 무효화 필요)
                
                print(f"[재시도] carSeq={car_seq} - 새 세션 및 쿠키로 상세페이지 재요청...")
                r = s.get(DETAIL_URL, params={"carSeq": car_seq}, headers=headers, timeout=15)
                soup = BeautifulSoup(r.text, "html.parser")  # soup 재생성
                
                # kv 테이블도 재파싱
                kv = {}
                for tr in soup.select(".detail-info-table tbody tr"):
                    tds = tr.select("th,td")
                    for i in range(0, len(tds), 2):
                        k = tds[i].get_text(strip=True)
                        v = tds[i + 1].get_text(strip=True) if i + 1 < len(tds) else ""
                        kv[k] = v
                
                image_url = _pick_first_image_url(soup)
                
                if image_url:
                    print(f"[쿠키 갱신 성공] carSeq={car_seq} - image_url 획득 (새 세션 생성)")
                else:
                    print(f"[쿠키 갱신 실패] carSeq={car_seq} - 여전히 image_url 없음")
                    
            except Exception as e:
                print(f"[쿠키 갱신 오류] carSeq={car_seq}: {e}")

        # 신차가격 및 carHistorySeq 파싱 (최종 soup 사용)
        scripts_text = "\n".join(s.get_text() for s in soup.find_all("script"))
        newcar_price: Optional[int] = None
        car_history_seq: Optional[str] = None
        
        m = re.search(r"var\s+newcarPrice\s*=\s*['\"](\d+)['\"]", scripts_text)
        if m:
            base = int(m.group(1))
            newcar_price = int(base * 1.1)
        
        # carHistorySeq 추출 (보험이력용)
        m_history = re.search(r'carHistorySeq["\s:=]+(\d+)', scripts_text)
        if m_history:
            car_history_seq = m_history.group(1)
        else:
            # 디버깅: carHistorySeq가 scripts에 있는지 확인
            if 'carHistorySeq' in scripts_text:
                print(f"[디버깅] 'carHistorySeq' 문자열은 있지만 패턴 매칭 실패")
                # 다른 패턴 시도
                m_alt = re.search(r'carHistorySeq[\'\":\s]*[=:]\s*[\'\"]*(\d+)', scripts_text)
                if m_alt:
                    car_history_seq = m_alt.group(1)
                    print(f"[디버깅] 대체 패턴으로 carHistorySeq 추출: {car_history_seq}")
            else:
                print(f"[디버깅] carSeq={car_seq} - 'carHistorySeq' 문자열 자체가 없음")

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
            "car_history_seq": car_history_seq,  # 보험이력용
        }, s, cookie_refreshed
    except Exception as e:
        print(f"[HTML 파싱 오류] carSeq: {car_seq}: {e}")
        return {}, s, False

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
        "model_group": api_data.get("className", ""),  
        "model": api_data.get("carName", ""),  
        "grade": api_data.get("modelName", ""),  
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

def save_vehicle_options_batch(session, vehicles_options: List[Dict], platform: str = 'kb_chachacha') -> int:
    """차량 옵션들을 배치로 처리하여 DB에 저장
    
    Note: 새 차량만 저장하므로 중복 체크 불필요
    """
    if not vehicles_options:
        return 0
    
    try:
        # 1. 옵션 마스터 조회
        option_masters = {opt.option_code: opt.option_master_id 
                         for opt in session.query(OptionMaster).all()}
        
        # 2. 벌크 인서트 데이터 준비
        bulk_data = []
        for vehicle_data in vehicles_options:
            vehicle_id = vehicle_data['vehicle_id']
            options = vehicle_data['options']
            
            if not options:
                continue
            
            # 플랫폼별 옵션 코드 추출 및 공통 옵션 코드로 변환
            platform_codes = [option['code'] for option in options]
            global_codes = convert_platform_options_to_global(platform_codes, platform)
            
            for option_code in global_codes:
                option_master_id = option_masters.get(option_code)
                if option_master_id:
                    bulk_data.append({
                        'vehicle_id': vehicle_id,
                        'option_master_id': option_master_id
                    })
        
        # 3. 벌크 인서트 실행
        if bulk_data:
            session.bulk_insert_mappings(VehicleOption, bulk_data)
            return len(bulk_data)
        
        return 0
        
    except Exception as e:
        print(f"[옵션 저장 오류]: {e}")
        return 0

def save_car_info_to_db(records: List[Dict[str, Any]]) -> tuple[int, int, int]:
    """차량 정보와 공통 옵션 정보를 100대씩 배치로 DB에 저장합니다.
    
    Returns:
        (저장된 차량 수, 건너뛴 차량 수, 저장된 옵션 수)
    """
    if not records:
        print("[경고] 저장할 레코드가 없습니다.")
        return 0, 0, 0

    BATCH_SIZE = 100
    total_records = len(records)
    total_saved = 0
    total_skipped = 0
    total_options_saved = 0
    
    print(f"[배치 저장 시작] 총 {total_records}건을 {BATCH_SIZE}개씩 배치로 저장")
    print("[참고] vehicle_no 중복 체크는 이미 crawl_complete_car_info에서 완료")
    
    # 배치별로 처리
    for i in range(0, total_records, BATCH_SIZE):
        batch_records = records[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total_records + BATCH_SIZE - 1) // BATCH_SIZE
        
        print(f"[배치 {batch_num}/{total_batches}] {len(batch_records)}건 처리 중...")
        
        try:
            saved, skipped, options_saved = save_car_info_batch(batch_records)
            total_saved += saved
            total_skipped += skipped
            total_options_saved += options_saved
            
            print(f"[배치 {batch_num} 완료] 저장: {saved}건, 건너뜀: {skipped}건, 옵션: {options_saved}개")
            
        except Exception as e:
            print(f"[배치 {batch_num} 실패] {e}")
            # 개별 저장으로 fallback
            for record in batch_records:
                try:
                    saved, skipped, options_saved = save_car_info_batch([record])
                    total_saved += saved
                    total_skipped += skipped
                    total_options_saved += options_saved
                except Exception as individual_error:
                    print(f"[개별 저장 실패] carseq: {record.get('car_seq', 'unknown')}: {individual_error}")
                    total_skipped += 1
    
    print(f"[전체 저장 완료] 차량: {total_saved}건 저장, {total_skipped}건 건너뜀, 공통 옵션: {total_options_saved}개 저장")
    
    return total_saved, total_skipped, total_options_saved

def save_car_info_batch(batch_records: List[Dict[str, Any]]) -> tuple[int, int, int]:
    """차량 정보 배치를 DB에 저장합니다.
    
    Note: vehicle_no 중복 체크는 이미 crawl_complete_car_info에서 완료
    """
    if not batch_records:
        return 0, 0, 0
    
    with session_scope() as session:
        # 1. 차량 데이터 준비
        vehicle_bulk_data = []
        options_by_car_seq = {}  # {car_seq: [option_codes]}
        
        for record in batch_records:
            car_seq = int(record.get('car_seq', 0))
            
            vehicle_data = {
                'car_seq': car_seq,
                'vehicle_no': record.get('vehicle_no'),
                'platform': record.get('platform'),
                'origin': record.get('origin'),
                'car_type': record.get('car_type'),
                'manufacturer': record.get('manufacturer'),
                'model_group': record.get('model_group'),
                'model': record.get('model'),
                'grade': record.get('grade'),
                'trim': record.get('trim'),
                'fuel_type': record.get('fuel_type'),
                'transmission': record.get('transmission'),
                'displacement': int(record.get('displacement', 0)),
                'color_name': record.get('color_name'),
                'model_year': int(record.get('model_year', 0)),
                'first_registration_date': int(record.get('first_registration_date', 0)),
                'distance': int(record.get('distance', 0)),
                'price': int(record.get('price', 0)),
                'origin_price': int(record.get('origin_price', 0)),
                'sell_type': record.get('sell_type'),
                'location': record.get('location'),
                'detail_url': record.get('detail_url'),
                'photo': record.get('photo'),
                'has_options': bool(record.get('options'))  # 옵션 유무 플래그
            }
            vehicle_bulk_data.append(vehicle_data)
            
            # 옵션 정보 저장
            options = record.get('options', [])
            if options:
                options_by_car_seq[car_seq] = options
        
        # 2. 차량 정보 일괄 저장
        vehicle_objects = [Vehicle(**v) for v in vehicle_bulk_data]
        session.bulk_save_objects(vehicle_objects, return_defaults=True)
        session.flush()
        
        # 3. vehicle_id 매핑 생성
        vehicle_id_map = {v.car_seq: v.vehicle_id for v in vehicle_objects}
        
        # 4. 옵션 저장
        options_saved_count = 0
        if options_by_car_seq:
            vehicles_options = []
            for car_seq, options in options_by_car_seq.items():
                vehicle_id = vehicle_id_map.get(car_seq)
                if vehicle_id:
                    vehicles_options.append({
                        'vehicle_id': vehicle_id,
                        'options': options
                    })
            
            if vehicles_options:
                options_saved_count = save_vehicle_options_batch(session, vehicles_options)
        
        # 5. 보험이력 저장
        insurance_saved_count = 0
        for record in batch_records:
            insurance_data = record.get('insurance_data')
            if not insurance_data:
                continue
                
            car_seq = int(record.get('car_seq'))
            vehicle_id = vehicle_id_map.get(car_seq)
            
            if not vehicle_id:
                continue
            
            # 중복 체크
            existing = session.query(InsuranceHistory).filter(
                InsuranceHistory.vehicle_id == vehicle_id,
                InsuranceHistory.platform == insurance_data['platform']
            ).first()
            
            if existing:
                continue
            
            # 보험이력 저장
            insurance_history = InsuranceHistory(
                vehicle_id=vehicle_id,
                platform=insurance_data['platform'],
                my_accident_cnt=insurance_data.get('my_accident_cnt', 0),
                other_accident_cnt=insurance_data.get('other_accident_cnt', 0),
                my_accident_cost=insurance_data.get('my_accident_cost', 0),
                other_accident_cost=insurance_data.get('other_accident_cost', 0),
                total_accident_cnt=insurance_data.get('total_accident_cnt', 0),
                total_loss_cnt=insurance_data.get('total_loss_cnt', 0),
                total_loss_date=insurance_data.get('total_loss_date'),
                robber_cnt=insurance_data.get('robber_cnt', 0),
                robber_date=insurance_data.get('robber_date'),
                flood_total_loss_cnt=insurance_data.get('flood_total_loss_cnt', 0),
                flood_part_loss_cnt=insurance_data.get('flood_part_loss_cnt', 0),
                flood_date=insurance_data.get('flood_date'),
                owner_change_cnt=insurance_data.get('owner_change_cnt', 0),
                car_no_change_cnt=insurance_data.get('car_no_change_cnt', 0),
                government=insurance_data.get('government', 0),
                business=insurance_data.get('business', 0),
                rental=insurance_data.get('rental', 0),
                loan=insurance_data.get('loan', 0),
                not_join_periods=insurance_data.get('not_join_periods')
            )
            session.add(insurance_history)
            insurance_saved_count += 1
        
        if insurance_saved_count > 0:
            print(f"[보험이력] {insurance_saved_count}건 저장")
        
        return len(vehicle_bulk_data), 0, options_saved_count

# =============================================================================
# 6. 통합 크롤링 (차량 정보 + 옵션 + 보험이력)
# =============================================================================

def crawl_complete_car_info(car_seqs: List[str], delay: float = 1.0, session: Optional[requests.Session] = None, crawl_insurance: bool = True) -> List[Dict[str, Any]]:
    """차량별 완전한 정보 크롤링 (기본정보 + 옵션 + 보험이력)"""
    print(f"[차량 정보 크롤링 시작] 총 {len(car_seqs)}대 (보험이력: {'포함' if crawl_insurance else '제외'})")
    s = session or build_session()
    insurance_session_valid = False  # 보험이력 로그인 상태

    print("[제조사 정보 수집 중...]")
    makers = get_maker_info(session=s)
    maker_info = {maker["makerCode"]: maker for maker in makers}

    print("[API를 통한 기본 정보 수집 중...]")
    api_data_list = get_car_info_via_api(car_seqs, session=s)
    if not api_data_list:
        print("[API 데이터 수집 실패]")
        return []
    print(f"[API 데이터 수집 완료] {len(api_data_list)}대")

    # vehicle_no 중복 체크 및 필터링
    print("[중복 차량번호 체크 중...]")
    with session_scope() as db_session:
        existing_vehiclenos = {row[0] for row in db_session.query(Vehicle.vehicle_no).all() if row[0]}
    
    filtered_api_data = []
    skipped_by_vehicleno = 0
    
    for item in api_data_list:
        car_no = item.get("carNo", "")
        if car_no and car_no in existing_vehiclenos:
            skipped_by_vehicleno += 1
        else:
            filtered_api_data.append(item)
    
    if skipped_by_vehicleno > 0:
        print(f"[중복 스킵] 차량번호 중복: {skipped_by_vehicleno}대")
    print(f"[크롤링 대상] {len(filtered_api_data)}대")
    
    if not filtered_api_data:
        print("[모든 차량이 중복] 크롤링할 차량이 없습니다.")
        return []

    by_seq = {str(item.get("carSeq", "")): item for item in filtered_api_data}
    complete_records: List[Dict[str, Any]] = []

    for i, item in enumerate(filtered_api_data, 1):
        seq = str(item.get("carSeq", ""))
        api_data = item
        print(f"\n[{i}/{len(filtered_api_data)}] carSeq: {seq} 처리 중...")

        # 1. HTML 파싱 (carHistorySeq 포함)
        html_data, s, cookie_refreshed = get_car_detail_from_html(str(seq), session=s)
        
        # 쿠키가 갱신되었으면 보험이력 로그인 무효화
        if cookie_refreshed:
            print(f"   [보험이력] 쿠키 갱신됨 - 로그인 상태 무효화")
            insurance_session_valid = False
        
        # 2. 옵션 크롤링
        options = get_car_options_from_html(str(seq), s)
        
        # 3. 차량 레코드 생성
        record = create_vehicle_record(api_data, html_data, maker_info)
        record['options'] = options
        record['insurance_data'] = None  # 보험이력 데이터 저장용
        complete_records.append(record)

        print(
            f"   [차량정보] {record['manufacturer']} {record['model_group']} {record['model']} | "
            f"가격: {record['price']}만원, 주행거리: {record['distance']:,}km, "
            f"이미지: {'OK' if record['photo'] else 'NO PHOTO'}, 옵션: {len(options)}개"
        )
        
        # 4. 보험이력 크롤링 (선택적)
        if crawl_insurance:
            car_history_seq = html_data.get('car_history_seq')
            
            if not car_history_seq:
                print(f"   [보험이력] carHistorySeq를 찾을 수 없음, 스킵")
            else:
                # 보험이력 로그인 체크
                if not insurance_session_valid:
                    print(f"   [보험이력] 네이버 SNS 로그인 중...")
                    try:
                        driver = login_with_naver_via_insurance(str(seq))
                        if driver:
                            # 쿠키 및 UA 추출
                            cookies, user_agent = extract_cookies_and_ua_from_driver(driver)
                            driver.quit()
                            
                            # 새 세션 생성 (기존 세션과 쿠키 충돌 방지)
                            print(f"   [보험이력] 새 세션 생성 중...")
                            s = build_session()
                            
                            # 쿠키 및 UA 적용
                            apply_cookies_to_session(s, cookies, user_agent)
                            
                            # 워밍업 시퀀스 실행
                            if warmup_insurance_session(str(seq), s):
                                insurance_session_valid = True
                                print(f"   [보험이력] 로그인 + 워밍업 성공 ✓")
                            else:
                                print(f"   [보험이력] 워밍업 실패, 보험이력 크롤링 스킵")
                        else:
                            print(f"   [보험이력] 로그인 실패, 보험이력 크롤링 스킵")
                    except Exception as e:
                        print(f"   [보험이력 로그인 오류] {e}")
                
                # 보험이력 크롤링 (수집만, 저장은 나중에)
                if insurance_session_valid:
                    try:
                        insurance_data = get_insurance_history_with_car_history_seq(
                            car_seq=str(seq),
                            car_history_seq=car_history_seq,
                            session=s
                        )
                        
                        if insurance_data:
                            # 레코드에 보험이력 데이터 저장 (DB 저장은 나중에)
                            record['insurance_data'] = insurance_data
                            print(f"   [보험이력] 수집 완료: 사고 {insurance_data['total_accident_cnt']}건")
                        else:
                            # 세션 만료 가능성
                            print(f"   [보험이력] 데이터 없음 (세션 만료 가능성)")
                            insurance_session_valid = False
                            
                    except Exception as e:
                        print(f"   [보험이력 오류] {e}")
                        insurance_session_valid = False

        if i < len(filtered_api_data):
            time.sleep(delay)

    print(f"\n[크롤링 완료] 총 {len(complete_records)}대의 완전한 정보 수집")
    return complete_records

# =============================================================================
# 7. 판매완료 차량 정리
# =============================================================================

def _delete_vehicle_cascade(session, vehicle_id: int) -> bool:
    """차량 및 관련 데이터 cascade 삭제"""
    try:
        # 1. VehicleOption 테이블에서 먼저 삭제 (외래키 제약조건)
        session.query(VehicleOption).filter(VehicleOption.vehicle_id == vehicle_id).delete()
        
        # 2. InsuranceHistory 테이블에서 삭제 (외래키 제약조건)
        session.query(InsuranceHistory).filter(InsuranceHistory.vehicle_id == vehicle_id).delete()
        
        # 3. Vehicle 테이블에서 삭제 (Inspection은 CASCADE로 자동 삭제됨)
        session.query(Vehicle).filter(Vehicle.vehicle_id == vehicle_id).delete()
        
        session.commit()
        return True
    except Exception as e:
        print(f"[삭제 오류] {e}")
        session.rollback()
        return False

def cleanup_sold_vehicles(batch_size: int = 50):
    """판매된 차량 정리 (페이지 접근 시 404 또는 오류 반환 시 DB에서 제거)"""
    print("[판매완료 차량 정리 시작]")
    
    total_deleted = 0
    
    with session_scope() as session:
        total_vehicles = session.query(Vehicle).filter(Vehicle.platform == 'kb_chachacha').count()
        print(f"[대상] DB 차차차 차량 {total_vehicles:,}대")
        
        offset = 0
        s = build_session()
        
        while True:
            vehicles_to_check = session.query(Vehicle).filter(
                Vehicle.platform == 'kb_chachacha'
            ).offset(offset).limit(batch_size).all()
            
            if not vehicles_to_check:
                break
            
            print(f"[확인 중] {offset}~{offset+len(vehicles_to_check)} / {total_vehicles}", end='', flush=True)
            
            deleted_count = 0
            for vehicle in vehicles_to_check:
                try:
                    # 차량 상세 페이지 접근 시도
                    url = f"{DETAIL_URL}?carSeq={vehicle.car_seq}"
                    response = s.get(url, timeout=5)
                    
                    # 404 또는 오류 페이지 확인
                    if response.status_code == 404:
                        is_sold = True
                    else:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        # 판매완료 또는 오류 메시지 확인
                        error_texts = ['판매완료', '존재하지 않는', '삭제된', '찾을 수 없습니다']
                        page_text = soup.get_text()
                        is_sold = any(error_text in page_text for error_text in error_texts)
                    
                    if is_sold:
                        # 판매된 차량 발견
                        print(f"\n  [판매완료] CarSeq: {vehicle.car_seq} - 삭제 중...", end='', flush=True)
                        if _delete_vehicle_cascade(session, vehicle.vehicle_id):
                            deleted_count += 1
                            print(" ✓")
                        else:
                            print(" ✗")
                    
                    time.sleep(0.1)  # 서버 부하 방지
                    
                except Exception as e:
                    print(f"\n  [오류] CarSeq: {vehicle.car_seq} - {e}")
                    continue
            
            if deleted_count > 0:
                print(f" → {deleted_count}대 삭제")
            else:
                print(f" → 삭제 없음")
            
            total_deleted += deleted_count
            offset += batch_size
    
    print(f"[정리 완료] 총 {total_deleted}대 삭제")
    return total_deleted

# =============================================================================
# 8. 메인 크롤링 전략 (제조사별, 클래스별)
# =============================================================================

def crawl_kb_chachacha(cleanup_first: bool = True):
    """KB 차차차 통합 크롤러 (차량 정보 + 옵션 + 보험이력)"""
    
    # 1. DB 초기화
    print("[KB차차차 통합 크롤링 시작]")
    create_tables_if_not_exist()
    
    db_status = check_database_status()
    if not db_status:
        print("[DB 연결 실패] 데이터베이스 연결을 확인해주세요.")
        return 0
    
    # 2. 판매완료 차량 정리 (선택적)
    if cleanup_first:
        print("\n[판매완료 차량 정리]")
        cleanup_sold_vehicles()
        print()
    
    # 3. 크롤링 시작
    total_processed = 0
    session = build_session()
    
    print("\n[전체 차량 수 확인 중...]")
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

def convert_chacha_inspection_to_record(html_content: str, vehicle_id: int) -> Optional[Dict]:
    """차차차 검사 HTML을 Inspection 레코드로 변환"""
    try:
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

# =============================================================================
# 8. 네이버 SNS 로그인
# =============================================================================

def extract_cookies_and_ua_from_driver(driver: webdriver.Chrome) -> tuple[List[Dict[str, Any]], str]:
    """Selenium 드라이버에서 쿠키 및 User-Agent 추출"""
    cookies = driver.get_cookies()
    user_agent = driver.execute_script("return navigator.userAgent")
    print(f"[쿠키 추출] {len(cookies)}개 쿠키 추출 완료")
    print(f"[UA 추출] {user_agent}")
    return cookies, user_agent

def apply_cookies_to_session(session: requests.Session, cookies: List[Dict[str, Any]], user_agent: str = None) -> None:
    """Requests 세션에 쿠키 및 UA 적용 (도메인/경로 정확히 보존)"""
    important_cookies = []
    for cookie in cookies:
        # Selenium 쿠키의 domain/path를 그대로 사용
        session.cookies.set(
            name=cookie['name'],
            value=cookie['value'],
            domain=cookie.get('domain'),  # 그대로 사용
            path=cookie.get('path', '/'),
            secure=cookie.get('secure', False),
            expires=cookie.get('expiry')
        )
        # 중요한 쿠키 확인
        if cookie['name'] in ['JSESSIONID', 'NA_SA', 'NA_SAS', 'NA_CO']:
            important_cookies.append(cookie['name'])
    
    # User-Agent 복제
    if user_agent:
        session.headers.update({"User-Agent": user_agent})
        print(f"[UA 적용] Selenium UA 복제 완료")
    
    print(f"[쿠키 적용] {len(cookies)}개 쿠키 적용 (중요: {', '.join(important_cookies) if important_cookies else '없음'})")

def warmup_insurance_session(car_seq: str, session: requests.Session) -> bool:
    """보험이력 세션 워밍업 (서버 세션 컨텍스트 설정)"""
    try:
        print(f"[워밍업] 보험이력 세션 초기화 중...")
        
        # 1. 메인 페이지 방문
        session.get(f"{KB_HOST}/public/search/main.kbc", timeout=10)
        time.sleep(0.5)
        
        # 2. 차량 상세 페이지 방문 (보험이력 컨텍스트)
        session.get(f"{DETAIL_URL}?carSeq={car_seq}&f=carhistory", timeout=10)
        time.sleep(0.5)
        
        # 3. 보험이력 체크 API 호출 (멤버십/세션 검증)
        check_response = session.post(
            INSURANCE_HISTORY_CHECK_URL,
            data={"carSeq": car_seq},
            headers={
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{DETAIL_URL}?carSeq={car_seq}&f=carhistory"
            },
            timeout=10
        )
        
        if check_response.status_code == 200:
            data = check_response.json()
            if data.get("errCode") == "0":
                print(f"[워밍업] 완료 - 로그인 상태 확인됨 ✓")
                return True
            else:
                print(f"[워밍업] 실패 - errCode: {data.get('errCode')}, errMsg: {data.get('errMsg')}")
                return False
        else:
            print(f"[워밍업] 실패 - HTTP {check_response.status_code}")
            return False
            
    except Exception as e:
        print(f"[워밍업 오류] {e}")
        return False

# =============================================================================
# 9. 보험이력 데이터 추출
# =============================================================================

def get_insurance_history_with_car_history_seq(car_seq: str, car_history_seq: str, session: requests.Session) -> Optional[Dict[str, Any]]:
    """로그인된 세션으로 보험이력 조회 및 파싱"""
    try:
        # POST 데이터 구성
        post_data = {
            "layerId": "layerCarHistoryInfo",
            "carHistorySeq": car_history_seq,
            "refGbn": "331100",
            "refSeq": car_seq
        }
        
        info_response = session.post(
            INSURANCE_HISTORY_INFO_URL,
            data=post_data,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "ko,ko-KR;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "max-age=0",
                "Connection": "keep-alive",
                "Content-Type": "application/x-www-form-urlencoded",
                "Host": "www.kbchachacha.com",
                "Origin": "https://www.kbchachacha.com",
                "Referer": f"{DETAIL_URL}?carSeq={car_seq}&f=carhistory",
                "Sec-Ch-Ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "iframe",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
            },
            timeout=15
        )
        
        if info_response.status_code != 200:
            print(f"[보험이력] HTML 페이지 오류: {info_response.status_code}")
            return None
        
        # HTML 파싱
        soup = BeautifulSoup(info_response.text, 'html.parser')
        
        # 보험이력 데이터 추출 (InsuranceHistory 테이블 구조에 맞춤)
        insurance_data = {
            'car_seq': car_seq,
            'platform': 'kb_chachacha',
            
            # 사고 이력 요약
            'my_accident_cnt': 0,
            'other_accident_cnt': 0,
            'my_accident_cost': 0,
            'other_accident_cost': 0,
            'total_accident_cnt': 0,
            
            # 특수 사고 이력
            'total_loss_cnt': 0,
            'total_loss_date': None,
            'robber_cnt': 0,
            'robber_date': None,
            'flood_total_loss_cnt': 0,
            'flood_part_loss_cnt': 0,
            'flood_date': None,
            
            # 기타 이력
            'owner_change_cnt': 0,
            'car_no_change_cnt': 0,
            
            # 특수 용도 이력
            'government': 0,
            'business': 0,
            'rental': 0,
            'loan': 0,
            
            # 미가입 기간
            'not_join_periods': None,
            
            # 상세 이력 (JSON용)
            'details': []
        }
        
        # 1. 요약 정보 추출 (중고차 사고이력 정보 요약)
        summary_list = soup.find('div', class_='acd-qk-list')
        if summary_list:
            items = summary_list.find_all('li')
            for item in items:
                tit = item.find('span', class_='tit')
                txt = item.find('span', class_='txt')
                
                if not tit or not txt:
                    continue
                
                tit_text = tit.get_text(strip=True)
                txt_text = txt.get_text(strip=True)
                
                # 전손 보험사고
                if '전손' in tit_text:
                    if '있음' in txt_text:
                        insurance_data['total_loss_cnt'] = 1
                        # 날짜 추출 (있을 경우)
                        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', txt_text)
                        if date_match:
                            insurance_data['total_loss_date'] = date_match.group(1)
                
                # 도난 보험사고
                elif '도난' in tit_text:
                    if '있음' in txt_text:
                        insurance_data['robber_cnt'] = 1
                        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', txt_text)
                        if date_match:
                            insurance_data['robber_date'] = date_match.group(1)
                
                # 침수 보험사고
                elif '침수' in tit_text:
                    if '있음' in txt_text:
                        insurance_data['flood_part_loss_cnt'] = 1
                        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', txt_text)
                        if date_match:
                            insurance_data['flood_date'] = date_match.group(1)
                
                # 내차 피해 (예: "2회/866,908원")
                elif '내차 피해' in tit_text or '내차피해' in tit_text:
                    if txt_text and txt_text != '없음':
                        parts = txt_text.split('/')
                        if len(parts) == 2:
                            count_str = parts[0].replace('회', '').strip()
                            if count_str.isdigit():
                                insurance_data['my_accident_cnt'] = int(count_str)
                            
                            amount_str = parts[1].replace(',', '').replace('원', '').strip()
                            if amount_str.isdigit():
                                insurance_data['my_accident_cost'] = int(amount_str)
                
                # 상대차 피해 (예: "1회/497,905원")
                elif '상대차 피해' in tit_text or '상대차피해' in tit_text:
                    if txt_text and txt_text != '없음':
                        parts = txt_text.split('/')
                        if len(parts) == 2:
                            count_str = parts[0].replace('회', '').strip()
                            if count_str.isdigit():
                                insurance_data['other_accident_cnt'] = int(count_str)
                            
                            amount_str = parts[1].replace(',', '').replace('원', '').strip()
                            if amount_str.isdigit():
                                insurance_data['other_accident_cost'] = int(amount_str)
                
                # 소유자 변경 (예: "6회")
                elif '소유자 변경' in tit_text or '소유자변경' in tit_text:
                    count_match = re.search(r'(\d+)\s*회', txt_text)
                    if count_match:
                        insurance_data['owner_change_cnt'] = int(count_match.group(1))
                
                # 차량번호 변경 (예: "2회")
                elif '차량번호 변경' in tit_text or '차량번호변경' in tit_text:
                    count_match = re.search(r'(\d+)\s*회', txt_text)
                    if count_match:
                        insurance_data['car_no_change_cnt'] = int(count_match.group(1))
        
        # 2. 특수 용도 이력 정보 추출
        special_use_list = soup.find('div', class_='acd-qk-list tp02')
        if special_use_list:
            items = special_use_list.find_all('li')
            for item in items:
                tit = item.find('span', class_='tit')
                txt = item.find('span', class_='txt')
                
                if not tit or not txt:
                    continue
                
                tit_text = tit.get_text(strip=True)
                txt_text = txt.get_text(strip=True)
                
                # 대여용도(렌터카)
                if '대여' in tit_text or '렌터카' in tit_text:
                    insurance_data['rental'] = 1 if '있음' in txt_text else 0
                
                # 영업용도
                elif '영업' in tit_text:
                    insurance_data['business'] = 1 if '있음' in txt_text else 0
                
                # 관용용도
                elif '관용' in tit_text:
                    insurance_data['government'] = 1 if '있음' in txt_text else 0
        
        # 3. 미가입 기간 추출
        not_join_box = soup.find('div', class_='box-line')
        if not_join_box:
            date_divs = not_join_box.find_all('div', class_='date')
            if date_divs:
                periods = []
                for date_div in date_divs:
                    period = date_div.get_text(strip=True)
                    if period:
                        # "2019년06월~2020년09월" 형식을 "201906~202009"로 변환
                        period = period.replace('년', '').replace('월', '')
                        periods.append(period)
                
                if periods:
                    insurance_data['not_join_periods'] = ', '.join(periods)
        
        # 총 사고 건수 계산
        insurance_data['total_accident_cnt'] = insurance_data['my_accident_cnt'] + insurance_data['other_accident_cnt']
        
        # 상세 이력 추출 (보험사고이력 상세 정보)
        detail_tables = soup.find_all('table', class_='table-l02')
        
        for table in detail_tables:
            # 날짜 추출
            date_header = table.find('thead').find_all('tr')[0] if table.find('thead') else None
            if not date_header:
                continue
            
            date_th = date_header.find('th')
            if not date_th:
                continue
            
            accident_date = date_th.get_text(strip=True)
            
            # 내차 사고/상대차 사고 데이터 추출
            tbody = table.find('tbody')
            if not tbody:
                continue
            
            rows = tbody.find_all('tr')
            
            my_car_insurance = None
            my_car_other = None
            other_car_insurance = None
            
            for row in rows:
                th = row.find('th')
                td = row.find('td')
                
                if not th or not td:
                    continue
                
                th_text = th.get_text(strip=True)
                td_text = td.get_text(strip=True)
                
                # 금액 추출
                amount_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*원', td_text)
                amount = 0
                if amount_match:
                    amount_str = amount_match.group(1).replace(',', '')
                    amount = int(amount_str)
                
                if '내 차 보험' in th_text and '내 차 사고' in str(table):
                    my_car_insurance = amount
                elif '상대 보험' in th_text and '내 차 사고' in str(table):
                    my_car_other = amount
                elif '내 차 보험' in th_text and '상대 차 사고' in str(table):
                    other_car_insurance = amount
            
            # 상세 이력 추가
            if my_car_insurance or my_car_other or other_car_insurance:
                detail = {
                    'date': accident_date,
                    'my_car_insurance': my_car_insurance if my_car_insurance else 0,
                    'my_car_other': my_car_other if my_car_other else 0,
                    'other_car_insurance': other_car_insurance if other_car_insurance else 0,
                }
                insurance_data['details'].append(detail)
        
        total_cost = insurance_data['my_accident_cost'] + insurance_data['other_accident_cost']
        print(f"[보험이력] 추출 완료:")
        print(f"  - 사고: 내차{insurance_data['my_accident_cnt']}회, 상대차{insurance_data['other_accident_cnt']}회")
        print(f"  - 특수용도: 렌터카{'O' if insurance_data['rental'] else 'X'}, 영업{'O' if insurance_data['business'] else 'X'}")
        print(f"  - 소유자변경: {insurance_data['owner_change_cnt']}회")
        return insurance_data
        
    except Exception as e:
        print(f"[보험이력 오류] carSeq={car_seq}: {e}")
        return None

# =============================================================================
# 10. 보험이력 배치 크롤링 (독립 실행용)
# =============================================================================

def crawl_insurance_history_batch(car_seqs: List[str] = None, limit: int = None) -> List[Dict[str, Any]]:
    """보험이력 배치 크롤링 (테스트 또는 독립 실행용)"""
    
    # car_seqs가 없으면 DB에서 조회
    if not car_seqs:
        with session_scope() as session:
            query = session.query(Vehicle.car_seq).filter(
                Vehicle.platform == 'kb_chachacha'
            )
            
            if limit:
                query = query.limit(limit)
            
            car_seqs = [str(row[0]) for row in query.all()]
    
    if not car_seqs:
        print("[보험이력 크롤링] 크롤링할 차량이 없습니다.")
        return []
    
    print(f"[보험이력 크롤링] 총 {len(car_seqs)}대 크롤링 시작...")
    
    # 1. Selenium으로 로그인하여 쿠키 획득
    print(f"\n[1단계] Selenium으로 로그인하여 쿠키 획득...")
    driver = login_with_naver_via_insurance(car_seqs[0])
    
    if not driver:
        print("[보험이력 크롤링] 로그인 실패")
        return []
    
    try:
        # 쿠키 및 UA 추출
        cookies, user_agent = extract_cookies_and_ua_from_driver(driver)
        driver.quit()
        
        # 2. 새 Requests 세션 생성 및 쿠키 적용
        print(f"\n[2단계] 새 세션 생성 및 쿠키 적용...")
        session = build_session()
        apply_cookies_to_session(session, cookies, user_agent)
        
        # 워밍업 시퀀스
        if not warmup_insurance_session(car_seqs[0], session):
            print("[보험이력 크롤링] 워밍업 실패")
            return []
        
        # 3. 보험이력 크롤링
        print(f"\n[3단계] 보험이력 데이터 크롤링...")
        results = []
        
        for i, car_seq in enumerate(car_seqs, 1):
            print(f"\n[{i}/{len(car_seqs)}] carSeq={car_seq} 처리 중...")
            
            # carHistorySeq 추출
            detail_response = session.get(f"{DETAIL_URL}?carSeq={car_seq}", timeout=15)
            detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
            scripts_text = "\n".join(s.get_text() for s in detail_soup.find_all("script"))
            
            car_history_seq = None
            m_history = re.search(r'carHistorySeq["\s:=]+(\d+)', scripts_text)
            if m_history:
                car_history_seq = m_history.group(1)
            
            if not car_history_seq:
                print(f"  [경고] carHistorySeq를 찾을 수 없음")
                continue
            
            insurance_data = get_insurance_history_with_car_history_seq(car_seq, car_history_seq, session)
            
            if insurance_data:
                results.append(insurance_data)
                print(f"  ✓ 성공: 사고건수={insurance_data['total_accident_cnt']}건")
            else:
                print(f"  ✗ 실패")
            
            # 딜레이
            time.sleep(0.5)
        
        print(f"\n[보험이력 크롤링 완료] 총 {len(results)}건 수집")
        
        # 4. DB에 저장
        if results:
            print(f"\n[4단계] DB에 보험이력 저장...")
            saved_count = save_insurance_history_to_db(results)
            print(f"[DB 저장 완료] {saved_count}건 저장됨")
        
        # 결과를 JSON으로 저장
        output_file = "insurance_history_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"[JSON 저장] {output_file}에 저장 완료")
        
        return results
        
    finally:
        print("[보험이력 크롤링] 완료")

# =============================================================================
# 11. 보험이력 DB 저장
# =============================================================================

def save_insurance_history_to_db(insurance_data_list: List[Dict[str, Any]]) -> int:
    """보험이력 데이터를 DB에 저장 (중복 시 스킵)"""
    saved_count = 0
    
    with session_scope() as db_session:
        for data in insurance_data_list:
            car_seq = data['car_seq']
            platform = data['platform']
            
            # vehicle_id 조회
            vehicle = db_session.query(Vehicle).filter(
                Vehicle.car_seq == car_seq,
                Vehicle.platform == platform
            ).first()
            
            if not vehicle:
                print(f"  [경고] carSeq={car_seq} 차량 정보를 DB에서 찾을 수 없습니다. 스킵합니다.")
                continue
            
            # 이미 보험이력이 있는지 확인
            existing = db_session.query(InsuranceHistory).filter(
                InsuranceHistory.vehicle_id == vehicle.vehicle_id,
                InsuranceHistory.platform == platform
            ).first()
            
            if existing:
                print(f"  [스킵] carSeq={car_seq} (vehicle_id={vehicle.vehicle_id}) 보험이력이 이미 존재합니다.")
                continue
            
            # 새로운 보험이력 레코드 생성
            insurance_history = InsuranceHistory(
                vehicle_id=vehicle.vehicle_id,
                platform=platform,
                
                # 사고 이력 요약
                my_accident_cnt=data.get('my_accident_cnt', 0),
                other_accident_cnt=data.get('other_accident_cnt', 0),
                my_accident_cost=data.get('my_accident_cost', 0),
                other_accident_cost=data.get('other_accident_cost', 0),
                total_accident_cnt=data.get('total_accident_cnt', 0),
                
                # 특수 사고 이력
                total_loss_cnt=data.get('total_loss_cnt', 0),
                total_loss_date=data.get('total_loss_date'),
                robber_cnt=data.get('robber_cnt', 0),
                robber_date=data.get('robber_date'),
                flood_total_loss_cnt=data.get('flood_total_loss_cnt', 0),
                flood_part_loss_cnt=data.get('flood_part_loss_cnt', 0),
                flood_date=data.get('flood_date'),
                
                # 기타 이력
                owner_change_cnt=data.get('owner_change_cnt', 0),
                car_no_change_cnt=data.get('car_no_change_cnt', 0),
                
                # 특수 용도 이력
                government=data.get('government', 0),
                business=data.get('business', 0),
                rental=data.get('rental', 0),
                loan=data.get('loan', 0),
                
                # 미가입 기간
                not_join_periods=data.get('not_join_periods')
            )
            
            db_session.add(insurance_history)
            saved_count += 1
            print(f"  [저장] carSeq={car_seq} (vehicle_id={vehicle.vehicle_id}) 보험이력 저장 완료")
        
        db_session.commit()
    
    return saved_count

# =============================================================================
# 12. 메인 실행
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='KB 차차차 크롤러')
    parser.add_argument('--no-cleanup', action='store_true', help='판매완료 차량 정리 건너뛰기')
    args = parser.parse_args()
    
    print("="*80)
    print("KB 차차차 통합 크롤러 (차량 정보 + 옵션 + 보험이력)")
    print("="*80)
    try:
        total = crawl_kb_chachacha(cleanup_first=not args.no_cleanup)
        print(f"\n{'='*80}")
        print(f"✅ 크롤링 완료: 총 {total:,}건 처리")
        print(f"{'='*80}")
    except KeyboardInterrupt:
        print("\n\n[중단] 사용자가 크롤링을 중단했습니다.")
    except Exception as e:
        print(f"\n[오류] 크롤러 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()