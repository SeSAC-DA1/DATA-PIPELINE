import os, re, time
import pandas as pd
import requests
from requests.adapters import HTTPAdapter, Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
from connection import session_scope
from model import Vehicle

# =============================================================================
# 상수 및 설정
# =============================================================================

BASE_URL = "https://api.encar.com/search/car/list/premium"
KOR_CATEGORIES = ["경차", "소형차", "준중형차", "중형차", "대형차", "스포츠카", "SUV", "RV", "승합차", "화물차"]

MARKET_CONFIG = {
    "korean": {
        "car_type": "Y",
        "referer": "https://www.encar.com/dc/dc_carsearchlist.do",
        "pageid": "dc_carsearch",
    },
    "foreign": {
        "car_type": "N",
        "referer": "https://www.encar.com/fc/fc_carsearchlist.do",
        "pageid": "fc_carsearch",
    },
}

WANTED_COLS = [
    "CarSeq", "VehicleNo", "Platform", "Origin", "CarType", "Manufacturer", "Model", 
    "Generation", "Trim", "FuelType", "Transmission", "ColorName", "ModelYear", 
    "FirstRegistrationDate", "Distance", "Price", "OriginPrice", "SellType", 
    "Location", "DetailURL", "Photo"
]

# =============================================================================
# 유틸리티 함수들
# =============================================================================

def to_int_safe(x):
    """안전한 정수 변환"""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    if isinstance(x, (int, float)):
        try:
            return int(x)
        except Exception:
            return None
    if isinstance(x, str):
        m = re.findall(r"\d+", x.replace(",", ""))
        return int("".join(m)) if m else None
    return None

def parse_year(x) -> int | None:
    """문자열에서 연식(YYYY) 추출"""
    if x is None:
        return None
    if isinstance(x, (int, float)) and not pd.isna(x):
        try:
            return int(x)
        except Exception:
            return None
    s = str(x)
    m = re.search(r"(\d{4})", s)
    return int(m.group(1)) if m else None

def parse_yyyymmdd(x) -> int | None:
    """문자열에서 YYYYMMDD 추출"""
    if not x:
        return None
    s = re.sub(r"\D", "", str(x))
    if len(s) >= 8:
        s = s[:8]
        try:
            return int(s)
        except Exception:
            return None
    return None

def make_detail_url(cid: int, pageid: str) -> str:
    """상세 URL 생성"""
    return f"https://fem.encar.com/cars/detail/{cid}?pageid={pageid}&listAdvType=pic&carid={cid}&view_type=normal"

def extract_photo(row: pd.Series):
    """사진 URL 추출"""
    if isinstance(row.get("Photo"), str) and row.get("Photo"):
        return row["Photo"]
    photos = row.get("Photos")
    if isinstance(photos, list) and photos:
        first = photos[0]
        if isinstance(first, dict):
            for k in ("url", "Url", "uri", "Uri", "imageUrl", "ImageUrl"):
                if k in first and first[k]:
                    return first[k]
        elif isinstance(first, str):
            return first
    return None

# =============================================================================
# HTTP 세션 관리
# =============================================================================

def make_session(referer: str) -> requests.Session:
    """기본 세션 생성"""
    s = requests.Session()
    s.trust_env = False
    retries = Retry(
        total=5,
        backoff_factor=1.2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.headers.update({
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "accept": "application/json, text/plain, */*",
        "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "origin": "https://www.encar.com",
        "referer": referer,
    })
    return s

def make_readside_session() -> requests.Session:
    """Readside API 세션 생성"""
    s = requests.Session()
    s.trust_env = False
    retries = Retry(
        total=3, 
        backoff_factor=0.4, 
        status_forcelist=[429, 500, 502, 503, 504], 
        allowed_methods=["GET"]
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://fem.encar.com",
        "Referer": "https://fem.encar.com/",
    })
    bearer = (os.getenv("ENCAR_BEARER") or "").strip()
    if bearer:
        s.headers["Authorization"] = f"Bearer {bearer}"
    return s

def get_json(s: requests.Session, params: dict):
    """JSON 응답 가져오기"""
    r = s.get(BASE_URL, params=params, timeout=15)
    r.raise_for_status()
    if "application/json" not in r.headers.get("Content-Type", "").lower():
        raise ValueError(f"Non-JSON: {r.url}")
    return r.json()

# =============================================================================
# 검색 및 필터링
# =============================================================================

def build_action_from_categories(categories, car_type="Y"):
    """카테고리로 검색 액션 생성"""
    names = [str(c).strip() for c in categories if c and str(c).strip()]
    names = list(dict.fromkeys(names))  # 중복 제거
    if not names:
        return f"(And.Hidden.N._.(C.CarType.{car_type}.))"
    joined = "Category." + "._.Category.".join(names) + "."
    return f"(And.Hidden.N._.(C.CarType.{car_type}._.(Or.{joined})))"

def get_total_count(s, action, sort="ModifiedDate"):
    """전체 개수 조회"""
    j = get_json(s, {"count": "true", "q": action, "sr": f"|{sort}|0|1"})
    return int(j.get("Count", 0) or 0)

# =============================================================================
# 데이터 정제 및 변환
# =============================================================================

def shape_rows(df_raw: pd.DataFrame, pageid: str, category_fallback: str, market_key: str) -> pd.DataFrame:
    """원시 데이터를 표준 형식으로 변환"""
    id_col = next((c for c in ["vehicleId", "VehicleId", "id", "Id", "carId", "carid"] if c in df_raw.columns), None)
    if id_col is None:
        raise KeyError("vehicleId-like column not found in SearchResults")

    df = pd.DataFrame()
    
    # 기본 정보
    df["CarSeq"] = df_raw[id_col].apply(to_int_safe).astype("Int64")
    df["Platform"] = pd.Series(["encar"] * len(df_raw), dtype="string")
    df["Origin"] = pd.Series(["국산" if market_key == "korean" else "수입"] * len(df_raw), dtype="string")

    # 차종
    if "Category" in df_raw.columns and df_raw["Category"].notna().any():
        df["CarType"] = df_raw["Category"].astype("string")
    elif "CategoryName" in df_raw.columns and df_raw["CategoryName"].notna().any():
        df["CarType"] = df_raw["CategoryName"].astype("string")
    else:
        df["CarType"] = pd.Series([category_fallback] * len(df_raw), dtype="string")

    # 차량 정보
    df["Manufacturer"] = df_raw.get("Manufacturer").astype("string") if "Manufacturer" in df_raw else pd.Series(dtype="string")
    df["Model"] = df_raw.get("Model").astype("string") if "Model" in df_raw else pd.Series(dtype="string")
    df["Generation"] = df_raw.get("Badge").astype("string") if "Badge" in df_raw else pd.Series(dtype="string")
    df["Trim"] = df_raw.get("BadgeDetail").astype("string") if "BadgeDetail" in df_raw else pd.Series(dtype="string")
    df["FuelType"] = df_raw.get("FuelType").astype("string") if "FuelType" in df_raw else pd.Series(dtype="string")
    df["Transmission"] = df_raw.get("Transmission").astype("string") if "Transmission" in df_raw else pd.Series(dtype="string")
    df["ModelYear"] = df_raw.get("FormYear").apply(to_int_safe).astype("Int64") if "FormYear" in df_raw else pd.Series(dtype="Int64")
    df["Distance"] = df_raw.get("Mileage").apply(to_int_safe).astype("Int64") if "Mileage" in df_raw else pd.Series(dtype="Int64")
    df["Price"] = df_raw.get("Price").apply(to_int_safe).astype("Int64") if "Price" in df_raw else pd.Series(dtype="Int64")
    df["SellType"] = df_raw.get("SellType").astype("string") if "SellType" in df_raw else pd.Series(dtype="string")
    df["Location"] = df_raw.get("OfficeCityState").astype("string") if "OfficeCityState" in df_raw else pd.Series(dtype="string")
    df["DetailURL"] = df["CarSeq"].map(lambda x: make_detail_url(x, pageid) if pd.notna(x) else None).astype("string")
    df["Photo"] = df_raw.apply(extract_photo, axis=1).astype("string")

    # 보강 예정 필드 초기화
    df["VehicleNo"] = pd.Series([None] * len(df), dtype="string")
    df["OriginPrice"] = pd.Series([None] * len(df), dtype="Int64")
    df["ColorName"] = pd.Series([None] * len(df), dtype="string")
    df["FirstRegistrationDate"] = pd.Series([None] * len(df), dtype="Int64")

    return df[WANTED_COLS]

# =============================================================================
# 상세 정보 수집
# =============================================================================

def fetch_vehicle_no(url: str, session: requests.Session) -> str | None:
    """차량번호 수집"""
    RE_VEH_NO = re.compile(r'"vehicleNo"\s*:\s*"([^"]+)"', re.S)
    try:
        resp = session.get(url, timeout=6)
        if resp.ok:
            m = RE_VEH_NO.search(resp.text)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None

def fetch_readside_detail(s: requests.Session, car_seq: int):
    """Readside API에서 상세 정보 수집"""
    url = f"https://api.encar.com/v1/readside/vehicle/{car_seq}?include=CATEGORY,SPEC"
    try:
        r = s.get(url, timeout=8)
        if not r.ok:
            return None, None
        j = r.json()
        op = j.get("category", {}).get("originPrice")
        cn = j.get("spec", {}).get("colorName")
        if isinstance(op, str):
            try:
                op = int(op.replace(",", "").strip())
            except Exception:
                op = None
        if isinstance(cn, str):
            cn = cn.strip()[:50]
        return op, cn
    except Exception:
        return None, None

def fetch_open_record_detail(s: requests.Session, car_seq: int, vehicle_no: str):
    """Open Record API에서 최초등록일 수집"""
    if not vehicle_no:
        return None
    url = f"https://api.encar.com/v1/readside/record/vehicle/{car_seq}/open"
    try:
        r = s.get(url, params={"vehicleNo": vehicle_no}, timeout=8)
        if not r.ok:
            return None
        j = r.json()
        first = parse_yyyymmdd(j.get("firstDate"))
        return first
    except Exception:
        return None

# =============================================================================
# 데이터 보강 함수들
# =============================================================================

def attach_vehicle_no(df: pd.DataFrame, max_workers=6, throttle_sec=0.0):
    """차량번호 추가"""
    if df.empty or "DetailURL" not in df.columns:
        return df
    
    s = requests.Session()
    s.trust_env = False
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Referer": "https://fem.encar.com/",
        "Origin": "https://fem.encar.com",
    })
    
    results = [None] * len(df)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fetch_vehicle_no, url, s): i for i, url in enumerate(df["DetailURL"].tolist())}
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                results[i] = fut.result()
            except Exception:
                results[i] = None
            if throttle_sec > 0:
                time.sleep(throttle_sec)
    
    out = df.copy()
    out["VehicleNo"] = pd.Series(results, index=out.index, dtype="string")
    return out

def enrich_with_readside(df: pd.DataFrame, max_workers=8, throttle_sec=0.0) -> pd.DataFrame:
    """Readside API로 출시가/색상 보강"""
    if df.empty or "CarSeq" not in df.columns:
        return df
    
    s = make_readside_session()
    ids = df["CarSeq"].dropna().astype(int).tolist()

    res_op = [None] * len(df)
    res_cn = [None] * len(df)
    id2idx = {}
    for i, eid in enumerate(df["CarSeq"].tolist()):
        if pd.isna(eid):
            continue
        id2idx.setdefault(int(eid), []).append(i)

    def _job(eid):
        op, cn = fetch_readside_detail(s, int(eid))
        if throttle_sec > 0:
            time.sleep(throttle_sec)
        return eid, op, cn

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_job, eid): eid for eid in ids}
        for fut in as_completed(futures):
            eid, op, cn = fut.result()
            for idx in id2idx.get(int(eid), []):
                res_op[idx] = op
                res_cn[idx] = cn

    out = df.copy()
    out["OriginPrice"] = pd.Series(res_op, index=out.index, dtype="Int64")
    out["ColorName"] = pd.Series(res_cn, index=out.index, dtype="string")
    return out

def enrich_with_open_record(df: pd.DataFrame, max_workers=8, throttle_sec=0.0) -> pd.DataFrame:
    """Open Record API로 최초등록일 보강"""
    if df.empty or "CarSeq" not in df.columns or "VehicleNo" not in df.columns:
        return df

    s = make_readside_session()
    carseq_list = df["CarSeq"].tolist()
    vehno_list = df["VehicleNo"].tolist()

    res_f = [None] * len(df)

    def _job(idx, cs, vn):
        if pd.isna(cs) or (not isinstance(vn, str)) or (not vn.strip()):
            return idx, None
        f = fetch_open_record_detail(s, int(cs), vn.strip())
        if throttle_sec > 0:
            time.sleep(throttle_sec)
        return idx, f

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_job, idx, carseq_list[idx], vehno_list[idx]): idx for idx in range(len(df))}
        for fut in as_completed(futures):
            idx, f = fut.result()
            res_f[idx] = f

    out = df.copy()
    out["FirstRegistrationDate"] = pd.Series(res_f, index=out.index, dtype="Int64")
    return out

# =============================================================================
# DB 관리
# =============================================================================

def save_vehicles_to_db(vehicles_data: list):
    """차량 데이터를 DB에 저장"""
    if not vehicles_data:
        return
    
    with session_scope() as session:
        saved_count = 0
        skipped_count = 0
        
        for data in vehicles_data:
            try:
                # Vehicle 객체 생성
                vehicle = Vehicle(
                    carseq=data.get('CarSeq'),
                    vehicleno=data.get('VehicleNo'),
                    platform=data.get('Platform', 'encar'),
                    origin=data.get('Origin'),
                    cartype=data.get('CarType'),
                    manufacturer=data.get('Manufacturer'),
                    model=data.get('Model'),
                    generation=data.get('Generation'),
                    trim=data.get('Trim'),
                    fueltype=data.get('FuelType'),
                    transmission=data.get('Transmission'),
                    colorname=data.get('ColorName'),
                    modelyear=data.get('ModelYear'),
                    firstregistrationdate=data.get('FirstRegistrationDate'),
                    distance=data.get('Distance'),
                    price=data.get('Price'),
                    originprice=data.get('OriginPrice'),
                    selltype=data.get('SellType'),
                    location=data.get('Location'),
                    detailurl=data.get('DetailURL'),
                    photo=data.get('Photo')
                )
                
                # 중복 체크 후 저장
                existing = session.query(Vehicle).filter(
                    Vehicle.carseq == data.get('CarSeq')
                ).first()
                
                if not existing:
                    session.add(vehicle)
                    saved_count += 1
                else:
                    skipped_count += 1
                    
            except Exception as e:
                print(f"[저장 실패] CarSeq: {data.get('CarSeq')}: {e}")
                skipped_count += 1
        
        print(f"[DB 저장 완료] {saved_count}건 저장, {skipped_count}건 건너뜀")

def get_existing_car_seqs() -> set:
    """DB에서 이미 크롤링된 carSeq들을 가져옵니다."""
    with session_scope() as session:
        result = session.query(Vehicle.carseq).filter(Vehicle.platform == "encar").all()
        return {int(row[0]) for row in result if row[0] is not None}

# =============================================================================
# 메인 크롤링 함수
# =============================================================================

def crawl_market_to_db(
    market_key: str,
    categories,
    sort="ModifiedDate",
    page_size=50,
    sleep_sec=0.6,
    fetch_vehicle_no=True,
    vehno_workers=6,
    vehno_throttle=0.0,
    fetch_detail=True,
    detail_workers=8,
    detail_throttle=0.0,
    resume_from_db=True,
    stop_after_consecutive_seen=2,
):
    """마켓별 크롤링 및 DB 저장"""
    conf = MARKET_CONFIG[market_key]
    s = make_session(conf["referer"])

    # 기존 CarSeq 로드
    existing_ids = set()
    if resume_from_db:
        try:
            existing_ids = get_existing_car_seqs()
            print(f"[resume] existing CarSeq loaded: {len(existing_ids):,}")
        except Exception as e:
            print(f"[resume] load existing ids failed: {e}")

    total_saved = 0
    for cat in categories:
        action = build_action_from_categories([cat], car_type=conf["car_type"])
        total = get_total_count(s, action, sort)
        print(f"[{market_key}] '{cat}' 대상 {total:,}건")

        saved = 0
        consecutive_seen_pages = 0

        for offset in range(0, total, page_size):
            params = {"count": "false", "q": action, "sr": f"|{sort}|{offset}|{page_size}"}
            data = get_json(s, params)
            rows = data.get("SearchResults", [])
            if not rows:
                break

            raw = pd.json_normalize(rows, max_level=1)
            shaped = shape_rows(raw, pageid=conf["pageid"], category_fallback=cat, market_key=market_key)

            # 이어받기: 기존 CarSeq 스킵
            if resume_from_db and not shaped.empty:
                shaped = shaped[~shaped["CarSeq"].isna()].copy()
                shaped["CarSeq"] = shaped["CarSeq"].astype(int)
                shaped.drop_duplicates(subset=["CarSeq"], inplace=True)

                before = len(shaped)
                shaped = shaped[~shaped["CarSeq"].isin(existing_ids)]
                after = len(shaped)

                if after == 0:
                    consecutive_seen_pages += 1
                else:
                    consecutive_seen_pages = 0

                if consecutive_seen_pages >= stop_after_consecutive_seen:
                    print(f"[{market_key}] '{cat}' 오래된 구간 감지 → 조기 종료 (offset={offset})")
                    break

            if shaped.empty:
                time.sleep(sleep_sec)
                continue

            # 데이터 보강
            if fetch_vehicle_no:
                shaped = attach_vehicle_no(shaped, max_workers=vehno_workers, throttle_sec=vehno_throttle)

            shaped = enrich_with_open_record(shaped, max_workers=detail_workers, throttle_sec=detail_throttle)

            if fetch_detail:
                shaped = enrich_with_readside(shaped, max_workers=detail_workers, throttle_sec=detail_throttle)

            # DB 저장
            vehicles_data = shaped.to_dict('records')
            save_vehicles_to_db(vehicles_data)
            saved += len(shaped)

            # 기존 ID 업데이트
            if resume_from_db:
                existing_ids.update(shaped["CarSeq"].dropna().astype(int).tolist())

            time.sleep(sleep_sec)

        print(f"[{market_key}] '{cat}' 저장 완료: {saved:,}건")
        total_saved += saved

    print(f"[{market_key}] 총 {total_saved:,}건 저장 완료 → vehicles")

# =============================================================================
# 실행 부분
# =============================================================================

def main():
    """메인 실행 함수"""
    # 국산차 크롤링
    crawl_market_to_db(
        "korean",
        KOR_CATEGORIES,
        sort="ModifiedDate",
        page_size=50,
        sleep_sec=0.6,
        fetch_vehicle_no=True,
        vehno_workers=6,
        vehno_throttle=0.0,
        fetch_detail=True,
        detail_workers=8,
        detail_throttle=0.0,
        resume_from_db=True,
        stop_after_consecutive_seen=1,
    )
    
    # 수입차 크롤링
    crawl_market_to_db(
        "foreign",
        KOR_CATEGORIES,
        sort="ModifiedDate",
        page_size=50,
        sleep_sec=0.6,
        fetch_vehicle_no=True,
        vehno_workers=6,
        vehno_throttle=0.0,
        fetch_detail=True,
        detail_workers=8,
        detail_throttle=0.0,
        resume_from_db=True,
        stop_after_consecutive_seen=1,
    )

if __name__ == "__main__":
    main()