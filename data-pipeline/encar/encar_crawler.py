import os, re, time
import requests
import pandas as pd
from pathlib import Path
from requests.adapters import HTTPAdapter, Retry
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.dialects.mysql import insert as mysql_insert
from dotenv import load_dotenv

# ===== 경로 =====
if '__file__' in globals():
    REPO_ROOT = Path(__file__).resolve().parent.parent   # 위치: data-pipeline/
else:
    REPO_ROOT = Path.cwd().parent

DB_DIR = REPO_ROOT.parent / "db"  # 위치: BACKEND/db
SCHEMA_SQL = DB_DIR / "carfin_tables.sql"
BASE_URL = "https://api.encar.com/search/car/list/premium"

ENV_PATH = REPO_ROOT.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)
load_dotenv()  # 추가 로드(있으면 덮어씀)

# ===== 카테고리 매핑 =====
ENG2KOR = {
    "light car": "경차",
    "compact car": "소형차",  
    "small car": "소형차",
    "semi-medium car": "준중형차",
    "medium car": "중형차",
    "large car": "대형차",
    "sports car": "스포츠카",
    "suv": "SUV",
    "rv":"RV",
    "van":"승합차",
    "truck":"화물차",
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
    # 프록시 환경변수로 인한 407 회피
    s.trust_env = False
    s.proxies = {}

    retries = Retry(
        total=5, backoff_factor=1.2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
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
    if "application/json" not in r.headers.get("Content-Type", "").lower():
        raise ValueError(f"Non-JSON: {r.url}")
    return r.json()

# ===== DSL =====
def build_action_from_categories(categories, car_type="Y"):
    """엔카 DSL: 주어진 카테고리(한글)의 OR 묶음 + CarType 필터"""
    names = [str(c).strip() for c in categories if c and str(c).strip()]
    names = list(dict.fromkeys(names))
    if not names:
        return f"(And.Hidden.N._.(C.CarType.{car_type}.))"
    joined = "Category." + "._.Category.".join(names) + "."
    return f"(And.Hidden.N._.(C.CarType.{car_type}._.(Or.{joined})))"

def get_total_count(s, action, sort="ModifiedDate"):
    j = get_json(s, {"count": "true", "q": action, "sr": f"|{sort}|0|1"})
    return int(j.get("Count", 0) or 0)

# ===== 유틸 =====
def make_detail_url(cid: int, pageid: str) -> str:
    return f"https://fem.encar.com/cars/detail/{cid}?pageid={pageid}&listAdvType=pic&carid={cid}&view_type=normal"

def to_int_safe(x):
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

def extract_photo(row: pd.Series):
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

# ===== MySQL =====
def make_mysql_engine():
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    user = os.getenv("DB_USER")
    pwd = os.getenv("DB_PASSWORD")
    db = os.getenv("DB_NAME")
    url = f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db}?charset=utf8mb4"
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
    if not recs:
        return
    stmt = mysql_insert(table).values(recs)
    stmt = stmt.on_duplicate_key_update(
        **{c.name: stmt.inserted[c.name] for c in table.columns if c.name != "Id"}
    )
    with engine.begin() as conn:
        conn.execute(stmt)

WANTED = [
    "Id", "Market", "Manufacturer", "Model", "Category", "Badge", "BadgeDetail",
    "Transmission", "FuelType", "Year", "Mileage", "Price",
    "SellType", "OfficeCityState", "detail_url", "Photo"
]

def shape_rows(df_raw: pd.DataFrame, pageid: str, category_fallback: str, market_key: str) -> pd.DataFrame:
    id_col = next((c for c in ["Id", "id", "carId", "carid"] if c in df_raw.columns), None)
    if id_col is None:
        raise KeyError("Id column not found in SearchResults")

    df = pd.DataFrame()
    df["Id"] = df_raw[id_col].apply(to_int_safe) 
    df["Market"] = market_key
    df["Manufacturer"] = df_raw.get("Manufacturer")
    df["Model"] = df_raw.get("Model")

    if "Category" in df_raw.columns and df_raw["Category"].notna().any():
        df["Category"] = df_raw["Category"]
    elif "CategoryName" in df_raw.columns and df_raw["CategoryName"].notna().any():
        df["Category"] = df_raw["CategoryName"]
    else:
        df["Category"] = pd.Series([category_fallback] * len(df_raw), dtype="string")

    df["Badge"] = df_raw.get("Badge")
    df["BadgeDetail"] = df_raw.get("BadgeDetail")
    df["Transmission"] = df_raw.get("Transmission")
    df["FuelType"] = df_raw.get("FuelType")
    df["Year"] = df_raw.get("Year").apply(to_int_safe) if "Year" in df_raw else None
    df["Mileage"] = df_raw.get("Mileage").apply(to_int_safe) if "Mileage" in df_raw else None
    df["Price"] = df_raw.get("Price").apply(to_int_safe) if "Price" in df_raw else None
    df["SellType"] = df_raw.get("SellType")
    df["OfficeCityState"] = df_raw.get("OfficeCityState")
    df["detail_url"] = df["Id"].map(lambda x: make_detail_url(x, pageid) if pd.notna(x) else None)
    df["Photo"] = df_raw.apply(extract_photo, axis=1)

    for c in ["Market", "Manufacturer", "Model", "Category", "Badge", "BadgeDetail",
              "Transmission", "FuelType", "SellType", "OfficeCityState", "detail_url", "Photo"]:
        df[c] = df[c].astype("string")
    for c in ["Id", "Year", "Mileage", "Price"]:
        df[c] = df[c].astype("Int64")

    return df[WANTED]

# ===== 크롤링 → UPSERT =====
def crawl_market_to_mysql(market_key: str, categories_en, sort="ModifiedDate", limit=50, sleep_sec=0.6):
    conf = MARKET[market_key]
    s = make_session(conf["referer"])

    engine = make_mysql_engine()
    ensure_schema(engine)

    total_saved = 0
    for cat_en in categories_en:
        cat_kor = norm_cat_for_dsl(cat_en)
        action = build_action_from_categories([cat_kor], car_type=conf["car_type"])  # 단일 카테고리 DSL
        total = get_total_count(s, action, sort)
        if total == 0:
            print(f"[{market_key}] {cat_en} → 0건 (skip)")
            continue

        saved = 0
        for offset in range(0, total, limit):
            params = {"count": "false", "q": action, "sr": f"|{sort}|{offset}|{limit}"}
            data = get_json(s, params)
            rows = data.get("SearchResults", [])
            if not rows:
                break

            raw = pd.json_normalize(rows, max_level=1)
            shaped = shape_rows(raw, pageid=conf["pageid"], category_fallback=cat_en, market_key=market_key)
            upsert_df(engine, shaped, "vehicles")
            saved += len(shaped)
            time.sleep(sleep_sec)

        print(f"[{market_key}] {cat_en} → {saved:,}건 저장 완료")
        total_saved += saved

    print(f"[{market_key}] 전체 합계: {total_saved:,}건 UPSERT 완료 → vehicles")

def main():
    categories_en = ["light car", "compact car", "semi-medium car", "medium car", "large car", "sports car", "suv", "rv", "van", "truck"]
    crawl_market_to_mysql("korean",  categories_en, sort="ModifiedDate", limit=50)
    crawl_market_to_mysql("foreign", categories_en, sort="ModifiedDate", limit=50)

if __name__ == "__main__":
    main()
