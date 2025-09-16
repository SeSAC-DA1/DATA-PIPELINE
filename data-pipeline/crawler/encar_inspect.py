import os, time
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests
from requests.adapters import HTTPAdapter, Retry
import pymysql
from dotenv import load_dotenv

# ===== 경로 & .env =====
if '__file__' in globals():
    REPO_ROOT = Path(__file__).resolve().parent.parent  # data-pipeline/
else:
    REPO_ROOT = Path.cwd().parent
ENV_PATH = REPO_ROOT.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH); load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')

API_URL = "https://api.encar.com/v1/readside/inspection/vehicle/{vehicle_id}"
ENCAR_BEARER = (os.getenv("ENCAR_BEARER") or "").strip() # ENCAR_BEARER 토큰은 .env에 넣어 사용

# ===== DB =====
def connect_db():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
        db=DB_NAME, charset='utf8mb4', autocommit=False
    )

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS vehicles_inspect (
    vehicleId INT PRIMARY KEY,
    WarrantyType VARCHAR(50)  NULL,
    Tuning       VARCHAR(50)  NULL,
    ChangeUsage  VARCHAR(16)  NULL,
    Recall       VARCHAR(16)  NULL,
    RecallStatus VARCHAR(16)  NULL,
    AccidentHistory VARCHAR(16) NULL,
    SimpleRepair VARCHAR(16)  NULL,
    CONSTRAINT fk_vi_vehicle
      FOREIGN KEY (vehicleId) REFERENCES vehicles(vehicleId)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

UPSERT_SQL = """
INSERT INTO vehicles_inspect
  (vehicleId, WarrantyType, Tuning, ChangeUsage, Recall, RecallStatus, AccidentHistory, SimpleRepair)
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
  WarrantyType=VALUES(WarrantyType),
  Tuning=VALUES(Tuning),
  ChangeUsage=VALUES(ChangeUsage),
  Recall=VALUES(Recall),
  RecallStatus=VALUES(RecallStatus),
  AccidentHistory=VALUES(AccidentHistory),
  SimpleRepair=VALUES(SimpleRepair);
"""

TARGET_BASE = """
SELECT v.vehicleId
FROM vehicles v
{join_clause}
{where_clause}
ORDER BY v.vehicleId
{limit_clause}
"""

# ===== HTTP 세션 =====
def make_session() -> requests.Session:
    if not ENCAR_BEARER:
        raise RuntimeError("ENCAR_BEARER 환경변수가 비어 있습니다. .env에 유효한 토큰을 넣어주세요.")

    s = requests.Session()
    s.trust_env = False       # OS 프록시 무시(407 예방)
    s.proxies = {}

    retries = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=50, pool_maxsize=50)
    s.mount("https://", adapter)
    s.mount("http://", adapter)

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

def _safe_get(obj: dict, keys: list, default=None):
    cur = obj
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur

def parse_inspect_json(j: Dict[str, Any]) -> Dict[str, Optional[str]]:
    if not isinstance(j, dict):
        return {k: None for k in (
            "WarrantyType","Tuning","ChangeUsage","Recall","RecallStatus","AccidentHistory","SimpleRepair"
        )}

    master = j.get("master", {}) or {}
    detail = master.get("detail", {}) if isinstance(master, dict) else {}

    result: Dict[str, Optional[str]] = {}

    # 보증유형
    result["WarrantyType"] = _safe_get(detail, ["guarantyType", "title"])

    # 튜닝
    t = _safe_get(detail, ["tuning"])
    result["Tuning"] = ("있음" if t else "없음") if t is not None else None

    # 용도변경
    u = _safe_get(detail, ["usageChangeTypes"], [])
    result["ChangeUsage"] = "있음" if isinstance(u, list) and len(u) > 0 else ("없음" if isinstance(u, list) else None)

    # 리콜/이행
    r = _safe_get(detail, ["recall"])
    result["Recall"] = ("해당" if r else "해당없음") if r is not None else None

    rf = _safe_get(detail, ["recallFullFillTypes"], [])
    if isinstance(rf, list) and rf:
        titles = [x.get("title") for x in rf if isinstance(x, dict) and x.get("title")]
        result["RecallStatus"] = ", ".join(titles)[:16] if titles else None
    else:
        result["RecallStatus"] = None

    # 사고/단순수리 (주의: accdient 오탈자)
    a = _safe_get(master, ["accdient"])
    result["AccidentHistory"] = ("있음" if a else "없음") if a is not None else None

    s = _safe_get(master, ["simpleRepair"])
    result["SimpleRepair"] = ("있음" if s else "없음") if s is not None else None

    return result

def fetch_one(s: requests.Session, vehicle_id: int) -> Optional[Dict[str, Optional[str]]]:
    url = API_URL.format(vehicle_id=vehicle_id)
    try:
        r = s.get(url, timeout=8)
        if r.status_code == 200:
            try:
                data = r.json()
            except Exception:
                return None
            info = parse_inspect_json(data)
            # 전부 None이면 무의미 → 쓰지 않음
            if all(v is None for v in info.values()):
                return None
            return info

        # 토큰 문제면 즉시 중단 유도
        if r.status_code in (401, 403):
            raise RuntimeError(f"Bearer 토큰 오류(status {r.status_code}). 토큰을 갱신하세요.")

        # 404/기타는 스킵
        return None

    except requests.RequestException:
        return None

# ===== main =====
def main(only_missing: bool = True, limit: Optional[int] = None, offset: int = 0, batch_size: int = 500):
    s = make_session()
    db = connect_db()
    cur = db.cursor()

    # 테이블 보장
    cur.execute(CREATE_SQL)
    db.commit()

    # 대상 vehicleId 목록
    join_clause  = "LEFT JOIN vehicles_inspect i ON i.vehicleId = v.vehicleId" if only_missing else ""
    where_clause = "WHERE i.vehicleId IS NULL" if only_missing else ""
    limit_clause = ""
    params: List[Any] = []
    if limit is not None:
        limit_clause = "LIMIT %s OFFSET %s"
        params.extend([limit, offset])

    sql = TARGET_BASE.format(join_clause=join_clause, where_clause=where_clause, limit_clause=limit_clause)
    cur.execute(sql, params)
    ids = [row[0] for row in cur.fetchall()]
    total = len(ids)
    print(f"[INFO] 성능점검 수집 대상: {total:,}건 (only_missing={only_missing}, limit={limit}, offset={offset})")

    rows: List[tuple] = []
    ok = skipped = 0

    for i, vid in enumerate(ids, 1):
        info = fetch_one(s, vid)
        if info:
            rows.append((
                vid,
                info["WarrantyType"],
                info["Tuning"],
                info["ChangeUsage"],
                info["Recall"],
                info["RecallStatus"],
                info["AccidentHistory"],
                info["SimpleRepair"],
            ))
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
    print(f"[DONE] vehicles_inspect 업데이트 완료 — 성공 {ok}, 스킵 {skipped}, 대상 {total}")

if __name__ == "__main__":
    main(only_missing=True, limit=None, offset=0, batch_size=500)
