import os, re, time
from pathlib import Path
from dotenv import load_dotenv
import pymysql
import requests
from requests.adapters import HTTPAdapter, Retry

# ===== 경로 & 환경 =====
if '__file__' in globals():
    REPO_ROOT = Path(__file__).resolve().parent.parent
else:
    REPO_ROOT = Path.cwd().parent

ENV_PATH = REPO_ROOT.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH); load_dotenv()

host = os.getenv('DB_HOST')
port = int(os.getenv('DB_PORT'))
user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
db_name = os.getenv('DB_NAME')

# ===== DB 연결 =====
conn = pymysql.connect(
    host=host, port=port, user=user, password=password,
    db=db_name, charset='utf8mb4', autocommit=False
)
cur = conn.cursor()

# ===== 테이블 자동 생성 로직(스크립트 실행 시 테이블이 없으면 자동으로 생성) =====
create_sql = """
CREATE TABLE IF NOT EXISTS vehicles_info (
    vehicleId INT PRIMARY KEY,
    vehicleNo VARCHAR(20),
    FOREIGN KEY (vehicleId) REFERENCES vehicles(vehicleId)
);
"""
cur.execute(create_sql)

# 이미 저장된 것은 제외하고 대상만 추출
cur.execute("""
    SELECT v.vehicleId
    FROM vehicles v
    LEFT JOIN vehicles_info i ON i.vehicleId = v.vehicleId
    WHERE i.vehicleId IS NULL OR i.vehicleNo IS NULL
""")
vehicle_ids = [row[0] for row in cur.fetchall()]
print(f"[INFO] 수집 대상 vehicleId: {len(vehicle_ids):,}건")

# ===== HTTP 세션 =====
s = requests.Session()
s.trust_env = False  # OS 프록시 환경변수 무시(407 방지)
retries = Retry(
    total=1,                      
    backoff_factor=0.2,
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://fem.encar.com/",
    "Origin": "https://fem.encar.com",
    "Connection": "keep-alive",
})

RE_VEH_NO = re.compile(r'"vehicleNo"\s*:\s*"([^"]+)"', re.S)

# ===== 배치 UPSERT =====
UPSERT_SQL = """
INSERT INTO vehicles_info (vehicleId, vehicleNo)
VALUES (%s, %s)
ON DUPLICATE KEY UPDATE vehicleNo = VALUES(vehicleNo)
"""

rows_to_upsert = []
BATCH = 500

for i, vid in enumerate(vehicle_ids, 1):
    url = f"https://fem.encar.com/cars/detail/{vid}?pageid=dc_carsearch&listAdvType=pic&carid={vid}&view_type=normal"
    vehicle_no = None

    try:
        resp = s.get(url, timeout=6)
        if resp.ok:
            m = RE_VEH_NO.search(resp.text)
            if m:
                vehicle_no = m.group(1)
    except requests.RequestException:
        # 재시도는 세션 어댑터에서 1회 처리, 여기선 그냥 패스
        pass

    rows_to_upsert.append((vid, vehicle_no))

    if i % BATCH == 0:
        cur.executemany(UPSERT_SQL, rows_to_upsert)
        conn.commit()
        print(f"[DB] upsert {len(rows_to_upsert):,}건 커밋 (누적 {i:,}/{len(vehicle_ids):,})")
        rows_to_upsert.clear()
        time.sleep(0.05)  # 0.1로 잡긴했는데 느리면 0.05로 수정

# 잔여분 flush
if rows_to_upsert:
    cur.executemany(UPSERT_SQL, rows_to_upsert)
    conn.commit()
    print(f"[DB] 잔여 {len(rows_to_upsert):,}건 커밋")

cur.close()
conn.close()
print(f"[DONE] vehicles_info 업데이트 완료 (대상 {len(vehicle_ids):,}건)")
