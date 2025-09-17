import re,json,time,random,requests
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd

KB_HOST = "https://www.kbchachacha.com"
DETAIL_URL = f"{KB_HOST}/public/car/detail.kbc"
MAKER_URL = f"{KB_HOST}/public/search/carMaker.json?page=1&sort=-orderDate"
API_RECENT_URL = f"{KB_HOST}/public/car/common/recent/car/list.json"
OPTION_LAYER_URL = f"{KB_HOST}/public/layer/car/option/list.kbc"
OPTION_MASTER_URL = f"{KB_HOST}/public/car/option/code/list.json"

IMG_BASE = "https://img.kbchachacha.com/IMG/carimg/l"


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


def get_car_info_via_api(car_seqs: List[str], session: Optional[requests.Session] = None) -> List[Dict[str, Any]]:
    """API를 통해 차량 기본 정보를 수집합니다."""
    s = session or build_session()
    payload = {
        "gotoPage": 1,
        "pageSize": 30,
        "carSeqVal": ",".join(car_seqs),
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
            return []
        data = r.json()
        return data.get("list", [])
    except Exception as e:
        print(f"❌ API 요청 실패: {e}")
        return []


# HTML에서 상세 정보를 파싱합니다. (연료/변속기/차종/색상/이미지/신차가격)
def get_car_detail_from_html(car_seq: str, session: Optional[requests.Session] = None) -> Dict[str, Any]:
    s = session or build_session()
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": f"{KB_HOST}/public/search/main.kbc",
    }
    try:
        r = s.get(DETAIL_URL, params={"carSeq": car_seq}, headers=headers, timeout=15)
        if r.status_code != 200:
            print(f"❌ HTML 요청 실패: {r.status_code}")
            return {}

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
            # 제거할 쿼리 파라미터 (?width= 등)
            return u.split("?")[0]

        image_url: Optional[str] = None
        img_el = soup.select_one("#btnCarPhotoView img[src]") or soup.select_one("#bx-pager img[src]")
        if img_el and img_el.get("src"):
            image_url = _clean_img(img_el["src"])  # type: ignore
        else:
            og = soup.select_one('meta[property="og:image"]')
            if og and og.get("content"):
                image_url = _clean_img(og["content"])  # type: ignore

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

    record = {
        "VehicleId": None,
        "VehicleNo": api_data.get("carNo", ""),
        "CarSeq": car_seq,
        "Platform": "kbchachacha",
        "Origin": country_code,
        "CarType": html_data.get("class", "기타"),
        "Manufacturer": api_data.get("makerName", ""),
        "Model": api_data.get("className", ""),
        "Generation": api_data.get("carName", ""),
        "Trim": api_data.get("gradeName", ""),
        "FuelType": html_data.get("fuel", "") or api_data.get("gasName", ""),
        "Transmission": html_data.get("transmission", "") or api_data.get("transmission", ""),
        "ColorName": html_data.get("color", "") or api_data.get("color", ""),
        "ModelYear": api_data.get("yymm", ""),
        "FirstRegistrationDate": api_data.get("regiDay", ""),
        "Distance": api_data.get("km", 0),
        "Price": price,
        "OriginPrice": html_data.get("newcar_price", None), 
        "SellType": "일반",
        "Location": api_data.get("cityName", ""),
        "DetailURL": f"{DETAIL_URL}?carSeq={car_seq}",
        "Photo": html_data.get("image_url", ""),
    }
    return record


def crawl_complete_car_info(car_seqs: List[str], delay: float = 1.0) -> List[Dict[str, Any]]:
    """완전한 차량 정보를 크롤링합니다."""
    print(f"🚀 완전한 차량 정보 크롤링 시작 (총 {len(car_seqs)}대)")
    session = build_session()

    print("📋 제조사 정보 수집 중...")
    maker_info = get_maker_info(session=session)

    print("🔍 API를 통한 기본 정보 수집 중...")
    api_data_list = get_car_info_via_api(car_seqs, session=session)
    if not api_data_list:
        print("❌ API 데이터 수집 실패")
        return []
    print(f"✅ API 데이터 수집 완료: {len(api_data_list)}대")

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


if __name__ == "__main__":
    # 예시 실행
    test_car_seqs = ["27490092", "27483488", "27471263"]
    records = crawl_complete_car_info(test_car_seqs, delay=1.5)


    # DataFrame 확인
    df = pd.DataFrame(records)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 200)
    print("\n📊 데이터프레임 미리보기:")
    print(df)
    print(f"\nShape: {df.shape}")



