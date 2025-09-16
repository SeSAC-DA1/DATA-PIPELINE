import os, time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

import requests
from requests.adapters import HTTPAdapter, Retry
import pymysql
from dotenv import load_dotenv

# ===== env =====
if '__file__' in globals():
    REPO_ROOT = Path(__file__).resolve().parent.parent
else:
    REPO_ROOT = Path.cwd().parent

ENV_PATH = REPO_ROOT.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH); load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# 보험이력 공개(open) 엔드포인트 (vehicleId + vehicleNo 필요)
API_URL = "https://api.encar.com/v1/readside/record/vehicle/{vehicle_id}/open?vehicleNo={vehicle_no}"
ENCAR_BEARER = os.getenv("ENCAR_BEARER", "").strip() # ENCAR_BEARER 토큰은 .env에 넣어 사용

# ===== DB =====
def connect_db():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
        db=DB_NAME, charset="utf8mb4", autocommit=False
    )

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS vehicles_insurance (
  vehicleId         INT PRIMARY KEY,
  vehicleNo         VARCHAR(20),
  OwnerChangeCnt    INT NULL,
  MyAccidentCnt     INT NULL,
  MyAccidentCost    INT NULL,
  OtherAccidentCnt  INT NULL,
  OtherAccidentCost INT NULL,
  isDisclosed       TINYINT(1) NULL,
  CONSTRAINT fk_vi_ins FOREIGN KEY (vehicleId) REFERENCES vehicles(vehicleId)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

UPSERT_SQL = """
INSERT INTO vehicles_insurance
 (vehicleId, vehicleNo, OwnerChangeCnt, MyAccidentCnt, MyAccidentCost,
  OtherAccidentCnt, OtherAccidentCost, isDisclosed)
VALUES
 (%s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
  vehicleNo=VALUES(vehicleNo),
  OwnerChangeCnt=VALUES(OwnerChangeCnt),
  MyAccidentCnt=VALUES(MyAccidentCnt),
  MyAccidentCost=VALUES(MyAccidentCost),
  OtherAccidentCnt=VALUES(OtherAccidentCnt),
  OtherAccidentCost=VALUES(OtherAccidentCost),
  isDisclosed=VALUES(isDisclosed);
"""

TARGET_SQL = """
SELECT vi.vehicleId, vi.vehicleNo
FROM vehicles_info vi
LEFT JOIN vehicles_insurance ins ON ins.vehicleId = vi.vehicleId
WHERE vi.vehicleNo IS NOT NULL
  AND {cond}
ORDER BY vi.vehicleId
{limit_clause}
"""

# ===== HTTP =====
def make_session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    s.proxies = {}
    retries = Retry(
        total=2, backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"],
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
        "Origin": "https://fem.encar.com",
        "Referer": "https://fem.encar.com/",
    })
    if ENCAR_BEARER:
        s.headers["Authorization"] = f"Bearer {ENCAR_BEARER}"
    return s

# ===== parsing =====
def to_int(v) -> Optional[int]:
    try:
        if v is None: return None
        if isinstance(v, str):
            v = v.replace(",", "").replace("원", "").strip()
        return int(v)
    except Exception:
        return None

def parse_insurance_json(j: Dict[str, Any]) -> Tuple[bool, Dict[str, Optional[int]]]:
    if not isinstance(j, dict):
        return False, {k: None for k in
                       ("OwnerChangeCnt","MyAccidentCnt","MyAccidentCost","OtherAccidentCnt","OtherAccidentCost")}

    fields = {
        "OwnerChangeCnt":   to_int(j.get("ownerChangeCnt")),
        "MyAccidentCnt":    to_int(j.get("myAccidentCnt")),
        "MyAccidentCost":   to_int(j.get("myAccidentCost")),
        "OtherAccidentCnt": to_int(j.get("otherAccidentCnt")),
        "OtherAccidentCost":to_int(j.get("otherAccidentCost")),
    }
    # 공개된 응답이면 핵심 키들이 숫자로 들어옴!
    any_value = any(v is not None for v in fields.values())
    return any_value, fields

# ===== fetch =====
def fetch_one(s: requests.Session, vehicle_id: int, vehicle_no: str) -> Tuple[bool, Dict[str, Optional[int]]]:
    """
    is_disclosed, fields 를 반환.
    200 OK 이면 파싱, 403/404/409 등은 비공개로 처리.
    """
    url = API_URL.format(vehicle_id=vehicle_id, vehicle_no=vehicle_no)
    try:
        r = s.get(url, timeout=8)
        if r.status_code == 200:
            try:
                data = r.json()
            except Exception:
                return False, {k: None for k in
                               ("OwnerChangeCnt","MyAccidentCnt","MyAccidentCost","OtherAccidentCnt","OtherAccidentCost")}
            return parse_insurance_json(data)

        if r.status_code in (401, 403, 404, 409):   # 비공개/권한없음/없음
            return False, {k: None for k in
                           ("OwnerChangeCnt","MyAccidentCnt","MyAccidentCost","OtherAccidentCnt","OtherAccidentCost")}

        # 그 외 상태코드: 일시 오류 -> 비공개처럼 표기만 하고 진행(무한재시도 방지)
        return False, {k: None for k in
                       ("OwnerChangeCnt","MyAccidentCnt","MyAccidentCost","OtherAccidentCnt","OtherAccidentCost")}
    except requests.RequestException:
        return False, {k: None for k in
                       ("OwnerChangeCnt","MyAccidentCnt","MyAccidentCost","OtherAccidentCnt","OtherAccidentCost")}

# ===== main =====
def main(only_missing: bool = True, limit: int | None = None, offset: int = 0, batch_size: int = 400):
    s = make_session()
    db = connect_db(); cur = db.cursor()
    cur.execute(CREATE_SQL); db.commit()

    cond = "ins.vehicleId IS NULL" if only_missing else "1=1"
    limit_clause = ""
    params: List[Any] = []
    if limit is not None:
        limit_clause = "LIMIT %s OFFSET %s"
        params.extend([limit, offset])

    cur.execute(TARGET_SQL.format(cond=cond, limit_clause=limit_clause), params)
    rows = cur.fetchall()
    targets = [(vid, vno) for vid, vno in rows if vno]  # 안전
    total = len(targets)
    print(f"[INFO] 보험이력 대상: {total:,}건 (only_missing={only_missing}, limit={limit}, offset={offset})")

    buf = []
    success = 0
    for i, (vid, vno) in enumerate(targets, 1):
        is_disclosed, fields = fetch_one(s, vid, vno)
        if is_disclosed:
            success += 1

        buf.append((
            vid, vno,
            fields["OwnerChangeCnt"],
            fields["MyAccidentCnt"],
            fields["MyAccidentCost"],
            fields["OtherAccidentCnt"],
            fields["OtherAccidentCost"],
            1 if is_disclosed else 0
        ))

        if i % batch_size == 0:
            cur.executemany(UPSERT_SQL, buf)
            db.commit()
            print(f"[DB] upsert {len(buf):,}건 커밋 (누적 {i:,}/{total:,}, 공개 {success:,})")
            buf.clear()
            time.sleep(0.05)

    if buf:
        cur.executemany(UPSERT_SQL, buf)
        db.commit()
        print(f"[DB] 잔여 {len(buf):,}건 커밋 (공개 {success:,})")

    cur.close(); db.close()
    print("[DONE] vehicles_insurance 업데이트 완료")

if __name__ == "__main__":
    main(only_missing=True, limit=None, offset=0, batch_size=500)
