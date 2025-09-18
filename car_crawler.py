import re,json,time,random,requests,os
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
from connection import session_scope, Engine
from model import Vehicle, Base


KB_HOST = "https://www.kbchachacha.com"
DETAIL_URL = f"{KB_HOST}/public/car/detail.kbc"
MAKER_URL = f"{KB_HOST}/public/search/carMaker.json?page=1&sort=-orderDate"
API_RECENT_URL = f"{KB_HOST}/public/car/common/recent/car/list.json"
OPTION_LAYER_URL = f"{KB_HOST}/public/layer/car/option/list.kbc"
OPTION_MASTER_URL = f"{KB_HOST}/public/car/option/code/list.json"

#세션 생성
def build_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=5,
        connect=3,
        read=3,
        backoff_factor=0.7,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept-Language": "ko-KR,ko;q=0.9",
        }
    )
    return s

#DB에서 이미 크롤링된 carSeq들을 가져옵니다.
def get_existing_car_seqs() -> set:

    with session_scope() as session:
        result = session.query(Vehicle.carseq).filter(Vehicle.platform == "kb_chachacha").all()
        return {str(row[0]) for row in result}


#한 페이지에서 carSeq들을 추출합니다.
def get_car_seqs_from_page(page_num: int, session: Optional[requests.Session] = None) -> List[str]:
    
    s = session or build_session()
    url = f"https://www.kbchachacha.com/public/search/list.empty?page={page_num}&sort=-orderDate"
    
    try:
        res = s.get(url, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # .area 클래스에서 data-car-seq 추출
            areas = soup.select('.area')
            page_car_seqs = []
            
            for area in areas:
                car_seq = area.get('data-car-seq')
                if car_seq:
                    page_car_seqs.append(car_seq)
            
            print(f"페이지 {page_num}: {len(page_car_seqs)}개 carSeq 발견")
            return page_car_seqs
        else:
            print(f"페이지 {page_num}: HTTP {res.status_code}")
            return []
    except Exception as e:
        print(f"페이지 {page_num} 오류: {e}")
        return []

#전체 페이지에서 get_car_seqs_from_page을 이용해서 carSeq들을 추출합니다.
def crawl_car_seqs_from_pages(max_pages: int = 100, max_cars: int = 10000, delay: float = 1.0) -> List[str]:
    # 기존 carSeq 제외
    existing_seqs = get_existing_car_seqs()
    print(f" 기존 DB에 저장된 carSeq: {len(existing_seqs)}개")
    
    session = build_session()
    all_car_seqs = []

    print(f" KB차차차 {max_pages}페이지 carSeq 크롤링 시작... (최대 {max_cars}개)")
    
    for page in range(1, max_pages + 1):
        print(f"\n 페이지 {page} 처리 중... (현재 {len(all_car_seqs)}개 수집됨)")

        if len(all_car_seqs) >= max_cars:
            print(f"최대 {max_cars}개의 carSeq를 추출했습니다. 크롤링을 중단합니다.")
            break

        page_car_seqs = get_car_seqs_from_page(page, session)

        if page_car_seqs:
            new_seqs = [seq for seq in page_car_seqs if seq not in existing_seqs]
            remaining = max_cars - len(all_car_seqs)
            if len(new_seqs) > remaining:
                new_seqs = new_seqs[:remaining]
                print(f"최대 개수 제한으로 {remaining}개만 추가")

            all_car_seqs.extend(new_seqs)
            print(f"페이지 {page}: {len(new_seqs)}개 추가 (총 {len(all_car_seqs)}개)")
        else:
            print(f"페이지 {page}: carSeq 없음 크롤링 중단")
            break
        
        time.sleep(delay)

    # 중복 제거
    unique_car_seqs = list(set(all_car_seqs))
    
    print(f"\n=== carSeq 크롤링 완료 ===")
    print(f"총 수집된 carSeq: {len(all_car_seqs)}개")
    print(f"중복 제거 후: {len(unique_car_seqs)}개")
    
    return unique_car_seqs

#제조사 정보 수집해서 국산/수입 구분을 위한 매핑을 생성
def get_maker_info(session: Optional[requests.Session] = None) -> Dict[str, Dict[str, Any]]:
    
    s = session or build_session()
    try:
        r = s.get(MAKER_URL, timeout=10)
        if r.status_code != 200:
            print(f"❌ 제조사 정보 수집 실패: HTTP {r.status_code}")
            return {}
        data = r.json()
        maker_info: Dict[str, Dict[str, Any]] = {}
        for maker in data.get("result", {}).get("국산", []):
            maker_info[maker["makerCode"]] = {
                "makerName": maker.get("makerName", ""),
                "countryCode": maker.get("countryCode", ""),
                "count": maker.get("count", 0),
            }
        for maker in data.get("result", {}).get("수입", []):
            maker_info[maker["makerCode"]] = {
                "makerName": maker.get("makerName", ""),
                "countryCode": maker.get("countryCode", ""),
                "count": maker.get("count", 0),
            }
        print(f"✅ 제조사 정보 수집 완료: 총 {len(maker_info)}개 제조사")
        return maker_info
    except Exception as e:
        print(f"❌ 제조사 정보 수집 오류: {e}")
        return {}

# api를 통해 차량 기본 정보를 수집합니다.
def get_car_info_via_api(car_seqs: List[str], session: Optional[requests.Session] = None) -> List[Dict[str, Any]]:
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
            "Host": "www.kbchachacha.com",
        }
        
        try:
            r = s.post(API_RECENT_URL, data=payload, headers=headers, timeout=10)
            if r.status_code != 200:
                print(f"❌ API 오류: {r.status_code}")
                continue
                
            # 응답 내용 확인
            print(f"API 응답 길이: {len(r.text)} 문자")
            if len(r.text) < 100:
                print(f"응답 내용: {r.text}")
                
            data = r.json()
            batch_results = data.get("list", [])
            all_results.extend(batch_results)
            
            print(f"배치 {i//batch_size + 1}: {len(batch_results)}개 수집")
            
            # 배치 간 대기
            time.sleep(0.5)
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON 파싱 오류 (배치 {i//batch_size + 1}): {e}")
            print(f"응답 내용: {r.text[:500]}...")
            continue
        except Exception as e:
            print(f"❌ API 요청 실패 (배치 {i//batch_size + 1}): {e}")
            continue
    
    return all_results


# HTML에서 상세 정보를 파싱합니다. (연료/변속기/차종/색상/이미지/신차가격)
def get_car_detail_from_html(car_seq: str, session: Optional[requests.Session] = None) -> Dict[str, Any]:
    s = session or build_session()
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Host": "www.kbchachacha.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    }
    try:
        r = s.get(DETAIL_URL, params={"carSeq": car_seq}, headers=headers, timeout=15)
        if r.status_code != 200:
            print(f"❌ HTML 요청 실패: {r.status_code}")
            return {}
        # 이미지 로딩 대기
        time.sleep(2) 

        soup = BeautifulSoup(r.text, "html.parser")

        # 기본정보 표 파싱
        kv: Dict[str, str] = {}
        for tr in soup.select(".detail-info-table tbody tr"):
            tds = tr.select("th,td")
            for i in range(0, len(tds), 2):
                k = tds[i].get_text(strip=True)
                v = tds[i + 1].get_text(strip=True) if i + 1 < len(tds) else ""
                kv[k] = v

        # 이미지 1장만 추출 (갤러리 → 썸네일 → og:image)
        def _clean_img(u: str) -> str:
            if not u:
                return ""
            # 제거할 쿼리 파라미터 (?width= 등)
            return u.split("?")[0]
        
        image_url: Optional[str] = None

        # 방법 1: og:image 메타태그 (가장 안정적)
        og = soup.select_one('meta[property="og:image"]')
        if og and og.get("content"):
            image_url = _clean_img(og["content"])
            print(f"   ��️ og:image로 이미지 발견: {image_url}")

        # 방법 2: slide-img 이미지 (제공해주신 HTML 구조)
        if not image_url:
            img_el = soup.select_one(".slide-img img[src]")
            if img_el and img_el.get("src"):
                image_url = _clean_img(img_el["src"])
                print(f"   🖼️ slide-img 이미지 발견: {image_url}")
        # 방법 3: 메인 갤러리 이미지
        if not image_url:
            img_el = soup.select_one("#btnCarPhotoView img[src]")
            if img_el and img_el.get("src"):
                image_url = _clean_img(img_el["src"])
                print(f"  ️ 갤러리 이미지 발견: {image_url}")


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
        }
    except Exception as e:
        print(f"❌ HTML 파싱 오류 (carSeq: {car_seq}): {e}")
        return {}


#옵션 정보 수집
def get_car_options_from_html(car_seq: str, session: Optional[requests.Session] = None) -> List[Dict[str, Any]]:
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
        print(f"❌ 옵션 파싱 오류 (carSeq: {car_seq}): {e}")
        return []

# DB 테이블 구조에 맞는 차량 레코드를 생성
def create_vehicle_record(api_data: Dict[str, Any], html_data: Dict[str, Any],  maker_info: Dict[str, Dict[str, Any]], session: Optional[requests.Session] = None) -> Dict[str, Any]:
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
        "OriginPrice": html_data.get("newcar_price", None), 
        "SellType": sell_type,
        "Location": api_data.get("cityName", ""),
        "DetailURL": f"{DETAIL_URL}?carSeq={car_seq}",
        "Photo": html_data.get("image_url", ""),
    }
    return record


def crawl_complete_car_info(car_seqs: List[str], delay: float = 1.5) -> List[Dict[str, Any]]:
    print(f"차량 정보 크롤링 시작 (총 {len(car_seqs)}대)")
    session = build_session()

    print("제조사 정보 수집 중...")
    maker_info = get_maker_info(session=session)

    print("API를 통한 기본 정보 수집 중...")
    api_data_list = get_car_info_via_api(car_seqs, session=session)
    if not api_data_list:
        print(" API 데이터 수집 실패")
        return []
    print(f"API 데이터 수집 완료: {len(api_data_list)}대")

    by_seq = {str(item.get("carSeq", "")): item for item in api_data_list}

    complete_records: List[Dict[str, Any]] = []
    for i, seq in enumerate(car_seqs, 1):
        api_data = by_seq.get(str(seq), {})
        print(f"\n📄 {i}/{len(car_seqs)} - carSeq: {seq} 처리 중...")

        html_data = get_car_detail_from_html(str(seq), session=session)
        

        record = create_vehicle_record(api_data, html_data,  maker_info, session=session)
        complete_records.append(record)

        print(
            f"   ✅ 완료: {record['Manufacturer']} {record['Model']} {record['Generation']} | "
            f"💰 {record['Price']}만원, 🚗 {record['Distance']:,}km, 🖼️ {'OK' if record['Photo'] else 'NO PHOTO'}"
        )

        if i < len(car_seqs):
            time.sleep(delay + random.uniform(0.2, 0.8))

    print(f"\n🎉 크롤링 완료! 총 {len(complete_records)}대의 완전한 정보 수집")
    return complete_records


def save_car_info_to_db(records: List[Dict[str, Any]]) -> None:
    if not records:
        print("저장할 레코드가 없습니다.")
        return

    with session_scope() as session:

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
            
            vehicle = Vehicle(**vehicle_data)
            session.merge(vehicle)  # UPSERT 기능
        
        print(f"✅ DB 저장 완료: {len(records)}건")

# 대량 데이터를 배치 단위로 나누어 크롤링합니다.
def crawl_in_batches(batch_size: int = 10000, max_pages_per_batch: int = 50, delay: float = 1.0):
    batch_num = 1
    
    while True:
        print(f"\n🔄 배치 {batch_num} 시작...")
        
        # carSeq 수집
        car_seqs = crawl_car_seqs_from_pages(
            max_pages=max_pages_per_batch, 
            max_cars=batch_size, 
            delay=delay
        )
        
        if not car_seqs:
            print("✅ 더 이상 크롤링할 데이터가 없습니다.")
            break
        
        # 상세 정보 크롤링
        records = crawl_complete_car_info(car_seqs, delay=1.5)
        
        #DB 저장
        try:
            save_car_info_to_db(records)
            print(f"✅ 배치 {batch_num} DB 저장 완료: {len(records)}건")
        except Exception as e:
            print(f"❌ 배치 {batch_num} DB 저장 실패: {e}")
        
        batch_num += 1
        
        # 배치 간 대기 (서버 부하 방지)
        print(f"⏳ 다음 배치까지 30초 대기...")
        time.sleep(30)



if __name__ == "__main__":
    # 페이지에서 carSeq 수집
    all_car_seqs = crawl_car_seqs_from_pages(max_pages=2, max_cars=80, delay=2)
    
    if all_car_seqs:
        # 상세 정보 크롤링
        records = crawl_complete_car_info(all_car_seqs, delay=1.5)
        
        # DataFrame 확인
        df = pd.DataFrame(records)
        print("\n📊 데이터프레임 미리보기:")
        print(df.head())
        print(f"\nShape: {df.shape}")
        
        # DB 저장 (항상 실행)
        try:
            save_car_info_to_db(records)
        except Exception as e:
            print(f"❌ DB 저장 실패: {e}")
    else:
        print("❌ carSeq 수집 실패")



