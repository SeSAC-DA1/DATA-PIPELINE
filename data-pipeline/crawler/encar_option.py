import os, time
from pathlib import Path
from typing import Optional, Dict, Any, List
import requests
from requests.adapters import HTTPAdapter, Retry
import pymysql
from dotenv import load_dotenv

# ===== 경로 및 .env 설정 =====
if '__file__' in globals():
    REPO_ROOT = Path(__file__).resolve().parent.parent
else:
    REPO_ROOT = Path.cwd().parent
ENV_PATH = REPO_ROOT.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH); load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
ENCAR_BEARER = (os.getenv("ENCAR_BEARER") or "").strip()

# 차량 옵션 API 엔드포인트
API_URL = "https://api.encar.com/v1/readside/vehicle/{vehicleId}?include=ADVERTISEMENT,CATEGORY,CONDITION,CONTACT,MANAGE,OPTIONS,PHOTOS,SPEC,PARTNERSHIP,CENTER,VIEW"

# ===== DB =====
def connect_db():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
        db=DB_NAME, charset='utf8mb4', autocommit=False
    )

# 옵션 정보 저장 테이블 (옵션 컬럼은 optionCd별 동적/longtable로 예시 구현)
CREATE_SQL = """
CREATE TABLE IF NOT EXISTS vehicles_option (
    vehicleId INT PRIMARY KEY,
    colorName VARCHAR(30),
    {} -- option code 컬럼들 예시, 뒤에서 동적으로 생성
    FOREIGN KEY (vehicleId) REFERENCES vehicles(vehicleId)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

OPTIONS_CD_LIST = [
    "001","004","005","006","007","008","014","015","017","019","020","022","024",
    "026","027","030","031","032","033","055","056","057","058","071","072","074","086","096","097"
]

OPTION_COLUMNS = ",\n    ".join([f'`opt_{cdn}` TINYINT(1) DEFAULT 0' for cdn in OPTIONS_CD_LIST])

UPSERT_SQL = f"""
INSERT INTO vehicles_option
(vehicleId, colorName, {", ".join(["opt_" + cd for cd in OPTIONS_CD_LIST])})
VALUES
(%s, %s, {", ".join(['%s']*len(OPTIONS_CD_LIST))})
ON DUPLICATE KEY UPDATE
colorName=VALUES(colorName),
{', '.join([f"opt_{cd}=VALUES(opt_{cd})" for cd in OPTIONS_CD_LIST])};
"""

# ===== HTTP 세션 =====
def make_session() -> requests.Session:
    if not ENCAR_BEARER:
        raise RuntimeError("ENCAR_BEARER 토큰 누락. .env에 넣어주세요.")
    s = requests.Session()
    s.trust_env = False
    s.proxies = {}
    retries = Retry(
        total=2, backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=50, pool_maxsize=50)
    s.mount("https://", adapter); s.mount("http://", adapter)
    s.headers.update({
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/140.0.0.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Authorization": f"Bearer {ENCAR_BEARER}",
        "Origin": "https://fem.encar.com",
        "Referer": "https://fem.encar.com/",
    })
    return s

# ===== 옵션 파싱 =====
def parse_option_json(j: Dict[str, Any]) -> Dict[str, Any]:
    color_name = None
    try:
        color_name = j.get('spec', {}).get('colorName')
    except Exception:
        color_name = None
    option_flag = {f"opt_{cdn}": 0 for cdn in OPTIONS_CD_LIST}
    try:
        standard_list = j.get('options', {}).get('standard', [])
        for cd in standard_list:
            k = f"opt_{cd}"
            if k in option_flag:
                option_flag[k] = 1
    except Exception:
        pass
    return {'colorName': color_name, **option_flag}

def fetch_one(s: requests.Session, vehicle_id: int) -> Optional[Dict[str, Any]]:
    url = API_URL.format(vehicle_id=vehicle_id)
    try:
        r = s.get(url, timeout=8)
        if r.status_code == 200:
            try:
                data = r.json()
            except Exception:
                return None
            info = parse_option_json(data)
            if all((v == 0 or v is None) for k, v in info.items() if k.startswith('opt_')):
                return None
            return info
        if r.status_code in (401, 403):
            raise RuntimeError(f"[{vehicle_id}] 토큰 오류(status:{r.status_code})")
        return None
    except requests.RequestException:
        return None

# ===== main =====
def main(only_missing: bool = True, limit: Optional[int] = None, offset: int = 0, batch_size: int = 500):
    s = make_session()
    db = connect_db(); cur = db.cursor()
    cur.execute(CREATE_SQL.format(OPTION_COLUMNS)); db.commit()
    # 미수집된 vehicleId 목록
    join_clause = "LEFT JOIN vehicles_option o ON o.vehicleId = v.vehicleId" if only_missing else ""
    where_clause = "WHERE o.vehicleId IS NULL" if only_missing else ""
    limit_clause = ""
    params: List[Any] = []
    if limit is not None:
        limit_clause = "LIMIT %s OFFSET %s"
        params.extend([limit, offset])
    sql = f"""
    SELECT v.vehicleId
    FROM vehicles v
    {join_clause}
    {where_clause}
    ORDER BY v.vehicleId
    {limit_clause}
    """
    cur.execute(sql, params)
    ids = [row[0] for row in cur.fetchall()]
    total = len(ids)
    print(f"[INFO] 옵션 수집 대상: {total:,}건 (only_missing={only_missing}, limit={limit}, offset={offset})")

    rows: List[Any] = []
    ok = skipped = 0
    for i, vid in enumerate(ids, 1):
        info = fetch_one(s, vid)
        if info:
            values = [vid, info["colorName"]] + [info[f"opt_{cd}"] for cd in OPTIONS_CD_LIST]
            rows.append(tuple(values))
            ok += 1
        else:
            skipped += 1

        if i % batch_size == 0 and rows:
            cur.executemany(UPSERT_SQL, rows)
            db.commit()
            print(f"[DB] upsert {len(rows):,}건 커밋 (누적 {i:,}/{total:,}, 성공 {ok}, 스킵 {skipped})")
            rows.clear()
        if i % 50 == 0:
            time.sleep(0.05)
    if rows:
        cur.executemany(UPSERT_SQL, rows)
        db.commit()
        print(f"[DB] 잔여 {len(rows):,}건 커밋")
    cur.close(); db.close()
    print(f"[DONE] vehicles_option 업데이트 완료 — 성공 {ok}, 스킵 {skipped}, 대상 {total}")

if __name__ == "__main__":
    main(only_missing=True, limit=None, offset=0, batch_size=500)












import os, time, requests
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

if '__file__' in globals():
    REPO_ROOT = Path(__file__).resolve().parent
else:
    REPO_ROOT = Path.cwd()
load_dotenv(REPO_ROOT.parent / ".env"); load_dotenv()

DB_HOST=os.getenv("DB_HOST"); DB_PORT=os.getenv("DB_PORT","3306")
DB_USER=os.getenv("DB_USER"); DB_PW=os.getenv("DB_PASSWORD")
DB_NAME=os.getenv("DB_NAME"); BEARER=(os.getenv("ENCAR_BEARER") or "").strip()

def engine():
    url=f"mysql+pymysql://{DB_USER}:{DB_PW}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    return create_engine(url, pool_pre_ping=True, future=True)

def ensure_columns(e):
    q = text("""SELECT COLUMN_NAME FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=:db AND TABLE_NAME='vehicles'""")
    with e.begin() as con:
        cols={r[0] for r in con.execute(q, {"db": DB_NAME}).all()}
        if "originPrice" not in cols:
            con.exec_driver_sql("ALTER TABLE vehicles ADD COLUMN originPrice INT NULL")
        if "colorName" not in cols:
            con.exec_driver_sql("ALTER TABLE vehicles ADD COLUMN colorName VARCHAR(30) NULL")

def make_session():
    s=requests.Session()
    s.headers.update({
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Accept":"application/json, text/plain, */*",
        "Origin":"https://fem.encar.com","Referer":"https://fem.encar.com/"
    })
    if BEARER: s.headers["Authorization"]=f"Bearer {BEARER}"
    return s

def fetch_detail(s, encar_id:int):
    url=f"https://api.encar.com/v1/readside/vehicle/{encar_id}?include=CATEGORY,SPEC"
    r=s.get(url, timeout=8)
    if not r.ok: return None, None
    j=r.json()
    op = j.get("category",{}).get("originPrice")
    cn = j.get("spec",{}).get("colorName")
    return op, cn

def targets(e, only_missing=True, limit=None):
    base="SELECT vehicleId, encarId FROM vehicles"
    cond=" WHERE originPrice IS NULL OR colorName IS NULL" if only_missing else ""
    lim=f" LIMIT {int(limit)}" if limit else ""
    with e.begin() as con:
        return con.execute(text(base+cond+lim)).all()

def update_batch(e, rows):
    if not rows: return
    with e.begin() as con:
        con.execute(
            text("UPDATE vehicles SET originPrice=:op, colorName=:cn WHERE vehicleId=:vid"),
            rows
        )

def main(only_missing=True, limit=None, batch=300, sleep=0.05):
    e=engine(); ensure_columns(e)
    s=make_session()
    todo=targets(e, only_missing, limit)
    buf=[]; done=0
    for vid, eid in todo:
        op, cn = fetch_detail(s, int(eid))
        buf.append({"vid": int(vid), "op": op, "cn": cn})
        if len(buf)>=batch:
            update_batch(e, buf); done+=len(buf); buf.clear(); time.sleep(sleep)
    if buf: update_batch(e, buf); done+=len(buf)
    print(f"[DONE] vehicles 업데이트 {done}건")

if __name__=="__main__":
    main(only_missing=True, limit=None, batch=300, sleep=0.05)
