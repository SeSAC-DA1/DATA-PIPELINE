import os, re, time
import requests
import pandas as pd
from pathlib import Path
from requests.adapters import HTTPAdapter, Retry
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from dotenv import load_dotenv

# ===== 경로 =====
if '__file__' in globals():
    REPO_ROOT = Path(__file__).resolve().parent.parent   # data-pipeline/
else:
    REPO_ROOT = Path.cwd().parent

DB_DIR      = REPO_ROOT.parent / "db" # BACKEND/db
SCHEMA_SQL  = DB_DIR / "carfin_tables.sql"
BASE_URL    = "https://api.encar.com/search/car/list/premium"

# ===== .env 로드 (루트 BACKEND/.env) =====
ENV_PATH = REPO_ROOT.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)     # 우선 루트 .env 시도
load_dotenv()                         # 그 외 현재 작업 디렉토리도 fallback 로드

# ===== 카테고리 매핑(영→한) =====
ENG2KOR = {
    "light car": "경차",
    "compact car": "소형차",
    "small car": "소형차",   
    "semi-medium car": "준중형차",
    "medium car": "중형차",
    "large car": "대형차",
    "sports car": "스포츠카",
    "suv": "SUV",
}
def norm_cat_for_dsl(name: str) -> str:
    return ENG2KOR.get(str(name).strip().lower(), name)

# ===== 시장 설정 =====
MARKET = {
    "korean":  {"car_type": "Y", "referer": "https://www.encar.com/dc/dc_carsearchlist.do", "pageid": "dc_carsearch"},
    "foreign": {"car_type": "N", "referer": "https://www.encar.com/fc/fc_carsearchlist.do", "pageid": "fc_carsearch"},
}

# ===== HTTP =====
def make_session(referer: str) -> requests.Session:
    s = requests.Session()
    s.trust_env = False      # ← OS/터미널의 PROXY 환경변수 무시
    s.proxies = {}           # ← 세션 프록시 비우기
    
    retries = Retry(total=5, backoff_factor=1.2, status_forcelist=[429,500,502,503,504], allowed_methods=["GET"])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.headers.update({
        "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/140.0.0.0 Safari/537.36"),
        "accept": "application/json, text/plain, */*",
        "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "origin": "https://www.encar.com",
        "referer": referer,
    })
    return s

def get_json(s: requests.Session, params: dict):
    r = s.get(BASE_URL, params=params, timeout=15)
    r.raise_for_status()
    if "application/json" not in r.headers.get("Content-Type","").lower():
        raise ValueError(f"Non-JSON: {r.url}")
    return r.json()

# ===== DSL =====
def build_action_from_categories(categories, car_type="Y"):
    names = [str(c).strip() for c in categories if c and str(c).strip()]
    names = list(dict.fromkeys(names))
    if not names:
        return f"(And.Hidden.N._.(C.CarType.{car_type}.))"
    joined = "Category." + "._.Category.".join(names) + "."
    return f"(And.Hidden.N._.(C.CarType.{car_type}._.(Or.{joined})))"

def get_total_count(s, action, sort="ModifiedDate"):
    j = get_json(s, {"count":"true", "q":action, "sr":f"|{sort}|0|1"})
    return int(j.get("Count", 0) or 0)

# ===== 유틸 =====
def make_detail_url(cid: int, pageid: str) -> str:
    # URL 생성 시에만 문자열로 변환
    return f"https://fem.encar.com/cars/detail/{cid}?pageid={pageid}&listAdvType=pic&carid={cid}&view_type=normal"

def to_int_safe(x):
    if x is None or (isinstance(x, float) and pd.isna(x)): return None
    if isinstance(x, (int, float)):
        try: return int(x)
        except: return None
    if isinstance(x, str):
        m = re.findall(r"\d+", x.replace(",", ""))
        return int("".join(m)) if m else None
    return None

def extract_photo(row: pd.Series):
    if isinstance(row.get("Photo"), str) and row.get("Photo"): return row["Photo"]
    photos = row.get("Photos")
    if isinstance(photos, list) and photos:
        first = photos[0]
        if isinstance(first, dict):
            for k in ("url","Url","uri","Uri","imageUrl","ImageUrl"):
                if k in first and first[k]:
                    return first[k]
        elif isinstance(first, str):
            return first
    return None

# ===== PostgreSQL =====
def make_postgresql_engine():
    # Backend .env 파일의 DATABASE_URL 사용
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return create_engine(database_url, pool_pre_ping=True, future=True)
    
    # 개별 환경변수로 구성 (fallback)
    host = os.getenv("DB_HOST", "carfin-db.cbkayiqs4div.ap-northeast-2.rds.amazonaws.com")
    port = os.getenv("DB_PORT", "5432")
    user = os.getenv("DB_USER", "carfin_admin")
    pwd = os.getenv("DB_PASSWORD", "carfin_secure_password_2025")
    db = os.getenv("DB_NAME", "carfin")

    url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"
    return create_engine(url, pool_pre_ping=True, future=True)

def ensure_schema(engine):
    if SCHEMA_SQL.exists():
        sql = SCHEMA_SQL.read_text(encoding="utf-8")
        with engine.begin() as con:
            for stmt in [s for s in sql.split(";") if s.strip()]:
                con.exec_driver_sql(stmt)

def upsert_df(engine, df: pd.DataFrame, table_name: str):
    meta = MetaData()
    meta.reflect(bind=engine, only=[table_name])
    table = Table(table_name, meta, autoload_with=engine)
    recs = df.to_dict(orient="records")
    if not recs: return
    
    stmt = postgresql_insert(table).values(recs)
    
    # PostgreSQL UPSERT (ON CONFLICT DO UPDATE)
    update_dict = {c.name: stmt.excluded[c.name] for c in table.columns if c.name not in ["id", "created_at"]}
    if update_dict:
        stmt = stmt.on_conflict_do_update(
            index_elements=[table.primary_key.columns.values()[0]],
            set_=update_dict
        )
    else:
        # 업데이트할 컬럼이 없으면 NOTHING
        stmt = stmt.on_conflict_do_nothing()
    
    with engine.begin() as conn:
        conn.execute(stmt)

# API 모델과 일치하는 컬럼 매핑
WANTED = ["external_id","source","make","model","year","mileage","price","details"]

def shape_rows(df_raw: pd.DataFrame, pageid: str, category_fallback: str, market_key: str) -> pd.DataFrame:
    id_col = next((c for c in ["Id","id","carId","carid"] if c in df_raw.columns), None)
    if id_col is None:
        raise KeyError("Id column not found in SearchResults")
    df = pd.DataFrame()
    
    # API 모델에 맞춰 컬럼명 변경
    df["external_id"] = df_raw[id_col].apply(to_int_safe)  # 외부 사이트 ID
    df["source"] = f"encar_{market_key}"  # 데이터 출처
    df["make"] = df_raw.get("Manufacturer")  # 제조사
    df["model"] = df_raw.get("Model")  # 모델명
    df["year"] = df_raw.get("Year").apply(to_int_safe) if "Year" in df_raw else None
    df["mileage"] = df_raw.get("Mileage").apply(to_int_safe) if "Mileage" in df_raw else None
    df["price"] = df_raw.get("Price").apply(to_int_safe) if "Price" in df_raw else None
    
    # details에 모든 추가 정보 저장 (JSONB)
    details = {}
    details["market"] = market_key
    details["category"] = (df_raw["Category"].iloc[0] if "Category" in df_raw.columns and len(df_raw) > 0
                          else df_raw.get("CategoryName", category_fallback))
    details["badge"] = df_raw.get("Badge").iloc[0] if "Badge" in df_raw and len(df_raw) > 0 else None
    details["badge_detail"] = df_raw.get("BadgeDetail").iloc[0] if "BadgeDetail" in df_raw and len(df_raw) > 0 else None
    details["transmission"] = df_raw.get("Transmission").iloc[0] if "Transmission" in df_raw and len(df_raw) > 0 else None
    details["fuel_type"] = df_raw.get("FuelType").iloc[0] if "FuelType" in df_raw and len(df_raw) > 0 else None
    details["sell_type"] = df_raw.get("SellType").iloc[0] if "SellType" in df_raw and len(df_raw) > 0 else None
    details["office_city_state"] = df_raw.get("OfficeCityState").iloc[0] if "OfficeCityState" in df_raw and len(df_raw) > 0 else None
    details["detail_url"] = df["external_id"].map(lambda x: make_detail_url(x, pageid) if pd.notna(x) else None).iloc[0] if len(df) > 0 else None
    details["photo"] = extract_photo(df_raw.iloc[0]) if len(df_raw) > 0 else None
    
    # details를 각 행에 동일하게 적용
    df["details"] = [details] * len(df)

    # 데이터 타입 설정
    for c in ["source","make","model"]:
        df[c] = df[c].astype("string")
    for c in ["external_id","year","mileage","price"]:
        df[c] = df[c].astype("Int64")
    
    return df[WANTED]

# ===== 크롤링 → UPSERT =====
def crawl_market_to_postgresql(market_key: str, categories_en, sort="ModifiedDate", limit=50, sleep_sec=0.6):
    conf = MARKET[market_key]
    s = make_session(conf["referer"])
    cats_kor = [norm_cat_for_dsl(c) for c in categories_en]
    action = build_action_from_categories(cats_kor, car_type=conf["car_type"])
    total = get_total_count(s, action, sort)
    if total == 0:
        print(f"[{market_key}] 결과 0"); return

    engine = make_postgresql_engine()
    ensure_schema(engine)

    saved = 0
    for offset in range(0, total, limit):
        params = {"count":"false", "q":action, "sr":f"|{sort}|{offset}|{limit}"}
        data = get_json(s, params)
        rows = data.get("SearchResults", [])
        if not rows:
            break
        raw = pd.json_normalize(rows, max_level=1)
        cat_fallback = ", ".join(categories_en)
        shaped = shape_rows(raw, pageid=conf["pageid"], category_fallback=cat_fallback, market_key=market_key)
        upsert_df(engine, shaped, "vehicles")
        saved += len(shaped)
        time.sleep(sleep_sec)
    print(f"[{market_key}] {saved:,}건 UPSERT 완료 → vehicles")

def main():
    categories_en = ["light car", "compact car", "semi-medium car", "medium car", "large car", "SUV"]
    crawl_market_to_postgresql("korean",  categories_en, sort="ModifiedDate", limit=50)
    crawl_market_to_postgresql("foreign", categories_en, sort="ModifiedDate", limit=50)

if __name__ == "__main__":
    main()
