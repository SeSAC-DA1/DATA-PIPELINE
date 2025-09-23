import os, re, html, time, math, requests, pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter, Retry
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.exc import OperationalError
from time import sleep

# -------------------- 공통 설정 --------------------
TABLE = "hyundai_segment_purchases"  
PAGE_SIZE_HYUNDAI = 100
PAGE_SIZE_CASPER = 100
SLEEP_SECONDS  = 0.6
MAX_PAGES_CASPER = 4

URL_HYUNDAI = "https://www.hyundai.com/wsvc/kr/front/purchaseReview.selectPurchaseReview.do"
HDR_HYUNDAI = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer": "https://www.hyundai.com/kr/ko/purchase-event/vehicles-review",
}

URL_CASPER = "https://casper.hyundai.com/gw/wp/product/v2/product/epilogues"
HDR_CASPER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json, text/plain, */*",
}

gender_map    = {"M": "남성", "F": "여성"}
car_type_keys = ["E", "N", "P", "R", "S"]  # 현대 구매후기 carType

# -------------------- 분류용 모델 원본 리스트 --------------------
compact_models = ["아반떼", "아반떼 Hybrid", "아반떼 N", "아이오닉 5", "더 뉴 아이오닉 5", "아이오닉 5 N"]
midsize_models = ["쏘나타 디 엣지", "쏘나타 디 엣지 Hybrid", "아이오닉 6"]
large_models   = ["그랜저", "그랜저 Hybrid"]
suv_models = ["베뉴","코나","코나 Hybrid","코나 Electric","넥쏘","디 올뉴 넥쏘","더 뉴 투싼","더 뉴 투싼 Hybrid",
              "싼타페","싼타페 Hybrid","팰리세이드","디 올 뉴 팰리세이드","디 올 뉴 팰리세이드 Hybrid","아이오닉 9"]
van_models   = ["스타리아 라운지","스타리아 라운지 Hybrid","스타리아","스타리아 Hybrid","스타리아 킨더"]
truck_models = ["포터 II Electric", "포터 II Electric 특장차", "ST1","포터 2 일렉트릭", "포터2 일렉트릭", "포터 2 일렉트릭 특장차", "포터2 일렉트릭 특장차"]

# -------------------- 공통 유틸 --------------------
def load_env():
    root = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    env_path = root.parent / ".env"
    load_dotenv(dotenv_path=env_path); load_dotenv()

def make_session(headers, method="GET"):
    s = requests.Session()
    s.headers.update(headers)
    retries = Retry(total=5, backoff_factor=0.8,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=[method])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s

def make_engine():
    url = os.getenv("DB_URL")
    if not url:
        host = os.getenv("DB_HOST","127.0.0.1")
        port = os.getenv("DB_PORT","3306")
        user = os.getenv("DB_USER")
        pwd  = os.getenv("DB_PASSWORD")
        db   = os.getenv("DB_NAME")
        url = (f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db}"
               "?charset=utf8mb4&connect_timeout=10&read_timeout=30&write_timeout=30")
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800,
                         pool_size=5, max_overflow=5, future=True)

def reflect_table(engine, table_name, retries=3):
    meta = MetaData()
    for a in range(retries):
        try:
            meta.reflect(bind=engine, only=[table_name])
            return Table(table_name, meta, autoload_with=engine)
        except OperationalError as e:
            if a == retries - 1:
                raise
            print(f"[DB] reflect 재시도 {a+1}/{retries} ... {e}")
            engine.dispose(); sleep(2)

def upsert_df(engine, df_all: pd.DataFrame, table_name: str, chunk_size=1000):
    if df_all.empty:
        return
    table = reflect_table(engine, table_name)
    keep = [c.name for c in table.columns if c.name in df_all.columns]
    df = df_all[keep].copy()
    n = len(df)
    chunks = math.ceil(n / chunk_size)
    for i in range(chunks):
        part = df.iloc[i*chunk_size:(i+1)*chunk_size]
        stmt = mysql_insert(table).values(part.to_dict(orient="records"))
        upd = {c.name: stmt.inserted[c.name]
               for c in table.columns
               if c.name in part.columns and c.name.lower() not in {"id"}}
        stmt = stmt.on_duplicate_key_update(**upd)
        for a in range(3):
            try:
                with engine.begin() as conn:
                    conn.execute(stmt)
                break
            except OperationalError as e:
                if a == 2:
                    raise
                print(f"[DB] chunk 재시도 {a+1}/3 ... {e}")
                engine.dispose(); sleep(2)
        print(f"[DB] 업서트 진행 {i+1}/{chunks} (누적 {min((i+1)*len(part), n)}/{n})")

def clean_text(text: str) -> str:
    if not text:
        return ""
    t = str(text)
    for _ in range(3):
        t2 = html.unescape(t)
        if t2 == t:
            break
        t = t2
    t = re.sub(r"<\s*br\s*/?>", " ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"[\r\n]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

# 이름 표준화(다른 테이블 매칭용; 표기 통일)
def normalize_car_name(x: str) -> str:
    x = (x or "")
    x = x.replace("더 뉴 아이오닉 5", "더 뉴 아이오닉5").replace("아이오닉 5", "아이오닉5").replace("아이오닉 6", "아이오닉6")
    x = x.replace("아반떼 Hybrid", "아반떼 하이브리드").replace("쏘나타 디 엣지 Hybrid", "쏘나타 디 엣지 하이브리드")
    x = x.replace("그랜저 Hybrid", "그랜저 하이브리드").replace("코나 Hybrid", "코나 하이브리드").replace("코나 Electric", "코나 일렉트릭")
    x = x.replace("더 뉴 투싼 Hybrid", "더 뉴 투싼 하이브리드").replace("싼타페 Hybrid", "싼타페 하이브리드")
    x = x.replace("디 올 뉴 팰리세이드 Hybrid", "디 올 뉴 팰리세이드 하이브리드")
    x = x.replace("스타리아 라운지 Hybrid", "스타리아 라운지 하이브리드").replace("스타리아 Hybrid", "스타리아 하이브리드")
    x = x.replace("포터 II Electric", "포터2 일렉트릭").replace("포터 II Electric 특장차", "포터2 일렉트릭 특장차")
    return x

# ---- 비교용 정규화(공백/하이픈 제거, 소문자) ----
def _norm(s: str) -> str:
    return re.sub(r'[\s\-]+', '', s or '').lower()

# 분류 리스트 정규화 버전
compact_models_norm = list(map(_norm, compact_models))
midsize_models_norm = list(map(_norm, midsize_models))
large_models_norm = list(map(_norm, large_models))
suv_models_norm = list(map(_norm, suv_models))
van_models_norm = list(map(_norm, van_models))
truck_models_norm = list(map(_norm, truck_models))

def classify_car_type(name: str) -> str:
    n = _norm(name)
    if any(m in n for m in compact_models_norm): return "준중형"
    if any(m in n for m in midsize_models_norm): return "중형"
    if any(m in n for m in large_models_norm): return "대형"
    if any(m in n for m in suv_models_norm): return "SUV"
    if any(m in n for m in van_models_norm): return "승합"
    if any(m in n for m in truck_models_norm): return "트럭"
    return ""

# -------------------- 현대 구매후기 수집 --------------------
def fetch_page_hyundai(session, car_type_key: str, page_no: int):
    payload = {"carType": car_type_key, "pageNo": page_no,
               "rowCount": PAGE_SIZE_HYUNDAI, "sortKey": "rating"}
    r = session.post(URL_HYUNDAI, data=payload, timeout=20)
    r.raise_for_status()
    return r.json()

def extract_total_hyundai(j):
    for k in ("totalCount", "totalCnt", "total", "recordsTotal", "count"):
        v = j.get(k)
        if isinstance(v, int):
            return v
    if isinstance(j.get("data"), list) and len(j["data"]) < PAGE_SIZE_HYUNDAI:
        return len(j["data"])
    return None

def collect_hyundai(engine):
    s = make_session(HDR_HYUNDAI, method="POST")
    rows_total = 0
    print("[HYUNDAI] 수집 시작")

    for key in car_type_keys:
        j1 = fetch_page_hyundai(s, key, 1)
        total = extract_total_hyundai(j1)
        total_pages = math.ceil(total / PAGE_SIZE_HYUNDAI) if total else None

        page = 1
        while True:
            j = j1 if page == 1 else fetch_page_hyundai(s, key, page)
            data = j.get("data") or []
            n = len(data)
            if n == 0:
                break

            # 분류는 원문으로, 저장용 모델명만 표준화
            rows = []
            for r in data:
                raw_name = r.get("carName", "")
                rows.append({
                    "Id": r.get("reviewId"),
                    "CarType": classify_car_type(raw_name), # <- 원문으로 분류
                    "Manufacturer": "현대",
                    "Model": normalize_car_name(raw_name),  # <- 저장/매칭용 표준화
                    "Age": r.get("age"),
                    "Gender": gender_map.get(r.get("gender"), r.get("gender")),
                    "Satisfaction": float(r.get("carScore") or 0),
                    "Review": clean_text(r.get("review", "")),
                })
            df = pd.DataFrame(rows)

            upsert_df(engine, df, TABLE, chunk_size=1000)
            rows_total += n

            if total_pages:
                print(f"[HYUNDAI:{key}] {page}/{total_pages} 페이지: {n}건 (누적 {rows_total}/{total})")
                if page >= total_pages:
                    break
            else:
                print(f"[HYUNDAI:{key}] {page} 페이지: {n}건 (누적 {rows_total})")

            page += 1
            time.sleep(SLEEP_SECONDS)

    print(f"[HYUNDAI] 수집/적재 완료 누적: {rows_total}건")

# -------------------- 캐스퍼 수집 --------------------
def fetch_page_casper(session, page_no: int):
    params = {
        "siteTypeCode": "W",
        "carCode": ['AX01', 'AX02'],  # 캐스퍼
        "enginCode": "", "trimCode": "",
        "orderType": "2", "pageNo": page_no,
        "pageSize": PAGE_SIZE_CASPER, "screenCode": "B",
    }
    r = session.get(URL_CASPER, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

def extract_total_casper(j):
    d = j.get("data") or {}
    for k in ("totalCount", "total", "recordsTotal", "count"):
        v = d.get(k)
        if isinstance(v, int):
            return v
    lst = d.get("list") or []
    return None if len(lst) == PAGE_SIZE_CASPER else len(lst)

def collect_casper(engine, max_pages=MAX_PAGES_CASPER):
    s = make_session(HDR_CASPER, method="GET")
    print("[CASPER] 수집 시작")
    first = fetch_page_casper(s, 1)
    total = extract_total_casper(first)
    print(f"[CASPER] 총 {total if total else '?'}건 (최대 {max_pages if max_pages else '∞'} 페이지)")

    grand = 0
    page = 1
    while True:
        if max_pages and page > max_pages:
            break
        j = first if page == 1 else fetch_page_casper(s, page)
        data = (j.get("data") or {}).get("list") or []
        n = len(data)
        if n == 0:
            if page == 1:
                print("[CASPER] 데이터 없음")
            break

        df = pd.DataFrame([{
            "Id": it.get("epilogueNumber"),
            "CarType": "경차",
            "Manufacturer": "현대",
            "Model": it.get("carName"),
            "Age": it.get("customerAgeSectionCode"),
            "Gender": it.get("customerGenderName"),
            "Satisfaction": float(it.get("satisfactionScore") or 0),
            "Review": clean_text(it.get("epilogueContents")),
        } for it in data])

        upsert_df(engine, df, TABLE, chunk_size=1000)
        grand += n
        denom = f"/{total}" if total else ""
        suffix = f"/{max_pages}" if max_pages else ""
        print(f"[CASPER] {page}{suffix} 페이지: {n}건 (누적 {grand}{denom})")

        page += 1
        time.sleep(SLEEP_SECONDS)

    print(f"[CASPER] 수집/적재 완료 누적: {grand}건")

def main():
    load_env()
    engine = make_engine()
    reflect_table(engine, TABLE)
    collect_hyundai(engine)
    collect_casper(engine)

if __name__ == "__main__":
    main()