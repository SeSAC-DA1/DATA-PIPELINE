# 🗄️ CarFin PostgreSQL DB 설정 가이드

> **전체 팀원 공용** - CarFin 프로젝트의 PostgreSQL 데이터베이스를 Docker로 설정하고 사용하는 완벽 가이드

---

## 📋 목차

1. [시작하기 전에](#-시작하기-전에)
2. [PostgreSQL 실행 방법](#-postgresql-실행-방법)
3. [데이터베이스 접속 및 확인](#-데이터베이스-접속-및-확인)
4. [백엔드 개발팀용](#-백엔드-개발팀용)
5. [크롤링팀용](#-크롤링팀용)
6. [문제 해결](#-문제-해결)
7. [개발 시 주의사항](#-개발-시-주의사항)

---

## 🚀 시작하기 전에

### 필수 요구사항

- **Docker Desktop** 설치 및 실행 중
- **Git** 설치
- **터미널/CMD** 사용 가능

### 저장소 클론 (처음 한 번만)

```bash
git clone https://github.com/SeSAC-DA1/backend.git
cd backend
```

---

## 🗄️ PostgreSQL 실행 방법

### 방법 1: 전체 환경 실행 (백엔드 개발팀 권장)

```bash
# 모든 서비스(PostgreSQL, Backend) 실행 - 
docker-compose up --build -d
```

### 방법 2: PostgreSQL만 실행 (크롤링팀 권장)

```bash
# PostgreSQL만 실행 (빠르고 가볍게)
docker-compose up postgres -d
```

### 실행 확인

```bash
# 컨테이너 상태 확인
docker-compose ps postgres

# 테이블 자동 생성 확인
docker-compose exec postgres psql -U carfin_admin -d carfin -c "\dt"
```

**성공하면 다음 테이블들이 보입니다:**

| 테이블명 | 용도 | 백엔드팀 | 크롤링팀 |
|----------|------|----------|----------|
| `vehicles` | **차량 매물 정보** | ✅ | ✅ **주요 사용** |
| `users` | 사용자 정보 | ✅ | ❌ |
| `loan_product` | 대출 상품 정보 | ✅ | ⚠️ 필요시 |
| `loan_rates` | 대출 금리 정보 | ✅ | ⚠️ 필요시 |
| `recommendations` | AI 추천 결과 | ✅ | ❌ |
| `matches` | 금융 매칭 결과 | ✅ | ❌ |

---

## 🔍 데이터베이스 접속 및 확인

### 접속 정보

| 항목 | 값 |
|------|-----|
| **호스트** | `localhost` |
| **포트** | `5432` |
| **사용자명** | `carfin_admin` |
| **비밀번호** | `carfin_secure_password_2025` |
| **데이터베이스** | `carfin` |

### PostgreSQL 직접 접속

```bash
# Docker 컨테이너 내에서 접속
docker-compose exec postgres psql -U carfin_admin -d carfin

# 로컬에 PostgreSQL 클라이언트가 있다면
psql -h localhost -p 5432 -U carfin_admin -d carfin
```

### 기본 SQL 명령어

```sql
-- 테이블 목록 확인
\dt

-- 특정 테이블 구조 확인
\d vehicles
\d users

-- 데이터 확인
SELECT * FROM vehicles LIMIT 5;
SELECT COUNT(*) FROM vehicles;
```

---

## 💻 백엔드 개발팀용

### FastAPI에서 DB 연결 확인

```bash
# 백엔드 서버 헬스체크
curl http://localhost:8000/health

# 또는 브라우저에서
# http://localhost:8000/docs
```

### SQLAlchemy 모델 작성 예시

```python
# backend/src/models/vehicles.py
from sqlalchemy import Column, Integer, String, Float, DateTime
from ..database.connection import Base

class Vehicle(Base):
    __tablename__ = "vehicles"
    
    Id = Column(Integer, primary_key=True)
    Manufacturer = Column(String(100))
    Model = Column(String(150))
    Year = Column(Integer)
    Price = Column(Integer)
    # ... 기타 필드들
```

### API 엔드포인트 예시

```python
# backend/src/api/endpoints/vehicles.py
@app.get("/vehicles")
async def get_vehicles(db: AsyncSession = Depends(get_database_session)):
    result = await db.execute(
        select(Vehicle).limit(10)
    )
    vehicles = result.scalars().all()
    return vehicles
```

---

## 🕷️ 크롤링팀용

### Python 필수 라이브러리 설치

```bash
pip install psycopg2-binary sqlalchemy pandas python-dotenv
```

### 환경변수 설정 (.env 파일)

```bash
# 크롤링 스크립트 폴더에 .env 파일 생성
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=carfin
DATABASE_USER=carfin_admin
DATABASE_PASSWORD=carfin_secure_password_2025
```

### vehicles 테이블 구조

```python
# 크롤링 데이터 구조 (Python dict 형태) - **중요: 소문자 필드명 사용**
vehicle_data = {
    'id': 1234567,                    # 엔카 차량 고유 ID (필수)
    'market': '국내차',                # 국내차/외제차
    'manufacturer': '현대',            # 제조사
    'model': '아반떼',                 # 모델명
    'category': '세단',                # 차종
    'badge': 'LX',                    # 트림/등급
    'badgedetail': 'LX 스마트스트림',   # 트림 상세
    'transmission': '자동',            # 변속기
    'fueltype': '가솔린',             # 연료 타입
    'year': 2022,                     # 연식
    'mileage': 25000,                 # 주행거리 (km)
    'price': 1850,                    # 판매가 (만원)
    'selltype': '일반',               # 판매형태
    'officecitystate': '서울특별시',   # 차량 소재지
    'detail_url': 'https://encar.com/detail/1234567',  # 상세 URL
    'photo': 'https://encar.com/photo/1234567.jpg'     # 이미지 URL
}
```

### 완전한 크롤링 스크립트

```python
# encar_crawler.py
import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

class EncarCrawler:
    def __init__(self):
        self.db_engine = create_engine(
            f"postgresql://{os.getenv('DATABASE_USER')}:{os.getenv('DATABASE_PASSWORD')}"
            f"@{os.getenv('DATABASE_HOST')}:{os.getenv('DATABASE_PORT')}"
            f"/{os.getenv('DATABASE_NAME')}"
        )
        
    def save_vehicles(self, vehicle_list):
        """차량 데이터를 DB에 저장"""
        df = pd.DataFrame(vehicle_list)
        df['created_at'] = datetime.now()
        df['updated_at'] = datetime.now()
        
        # 중복 제거 (id 기준)
        df.drop_duplicates(subset=['id'], inplace=True)
        
        # DB 저장
        df.to_sql('vehicles', self.db_engine, if_exists='append', index=False)
        print(f"✅ {len(df)} 건 저장 완료")
        
    def batch_save(self, large_data_list, batch_size=1000):
        """대용량 데이터 배치 저장"""
        total = len(large_data_list)
        for i in range(0, total, batch_size):
            batch = large_data_list[i:i+batch_size]
            self.save_vehicles(batch)
            print(f"📦 진행률: {min(i+batch_size, total)}/{total}")
    
    def get_vehicle_count(self):
        """저장된 차량 수 확인"""
        query = "SELECT COUNT(*) as count FROM vehicles"
        result = pd.read_sql(query, self.db_engine)
        return result['count'].iloc[0]

# 사용 예시
if __name__ == "__main__":
    crawler = EncarCrawler()
    
    # 크롤링 데이터 (실제 크롤링 로직으로 대체)
    sample_data = [
        {
            'id': 1234567,
            'manufacturer': '현대',
            'model': '아반떼',
            'year': 2022,
            'price': 1850,
            # ... 기타 필드들
        }
    ]
    
    crawler.save_vehicles(sample_data)
    print(f"총 저장된 차량: {crawler.get_vehicle_count():,} 대")
```

### 중복 데이터 처리 (UPSERT)

```python
def upsert_vehicles(self, vehicle_list):
    """중복 시 업데이트, 없으면 삽입"""
    import psycopg2
    
    conn = psycopg2.connect(
        host=os.getenv('DATABASE_HOST'),
        database=os.getenv('DATABASE_NAME'),
        user=os.getenv('DATABASE_USER'),
        password=os.getenv('DATABASE_PASSWORD')
    )
    cursor = conn.cursor()
    
    for vehicle in vehicle_list:
        cursor.execute("""
            INSERT INTO vehicles (id, manufacturer, model, year, price, created_at, updated_at)
            VALUES (%(id)s, %(manufacturer)s, %(model)s, %(year)s, %(price)s, NOW(), NOW())
            ON CONFLICT (id) DO UPDATE SET
                price = EXCLUDED.price,
                updated_at = NOW()
        """, vehicle)
    
    conn.commit()
    cursor.close()
    conn.close()
```

---

## 🚨 문제 해결

### 1. PostgreSQL 실행 안됨

```bash
# 로그 확인
docker-compose logs postgres

# 재시작
docker-compose restart postgres

# 완전 초기화
docker-compose down -v && docker-compose up postgres -d
```

### 2. 포트 5432 충돌

```bash
# 포트 사용 확인 (Windows)
netstat -ano | findstr :5432

# 포트 사용 확인 (Mac/Linux)  
lsof -i :5432

# 기존 PostgreSQL 서비스 중지 필요
```

### 3. 테이블이 없다는 오류

```bash
# 볼륨 삭제 후 재시작 (init.sql 자동 실행됨)
docker-compose down -v
docker-compose up postgres -d

# 테이블 확인
docker-compose exec postgres psql -U carfin_admin -d carfin -c "\dt"
```

### 4. Python 연결 오류

```python
# 연결 테스트 코드
import psycopg2

try:
    conn = psycopg2.connect(
        host='localhost', port=5432,
        database='carfin', user='carfin_admin',
        password='carfin_secure_password_2025'
    )
    print('✅ DB 연결 성공!')
    conn.close()
except Exception as e:
    print(f'❌ DB 연결 실패: {e}')
```

---

## ⚠️ 개발 시 주의사항

### 전체 팀 공통 ✅

1. **최신 코드 유지**
   ```bash
   git checkout develop
   git pull origin develop
   ```

2. **스키마 변경 시 팀원 공지**
   - 변경사항을 Slack/Discord에 공유
   - 팀원들이 `docker-compose down -v` 후 재시작하도록 안내

3. **데이터 백업** (중요한 테스트 데이터가 있을 때)
   ```bash
   docker-compose exec postgres pg_dump -U carfin_admin carfin > backup.sql
   ```

### 크롤링팀 전용 ✅

1. **배치 처리** - 1000건씩 나누어 저장
2. **중복 체크** - Id 컬럼으로 중복 제거
3. **에러 핸들링** - try/except로 DB 오류 처리
4. **속도 조절** - `time.sleep()` 으로 서버 부하 방지

### 하지 말 것 ❌

1. **프로덕션 데이터 착각 금지** - 개발용 로컬 DB입니다
2. **무한 크롤링 금지** - 적절한 종료 조건 설정
3. **대량 데이터 한번에 삽입 금지** - 메모리 초과 위험

---

## 📊 데이터 확인 쿼리

```sql
-- 기본 통계
SELECT COUNT(*) as 총차량수 FROM vehicles;
SELECT Manufacturer, COUNT(*) as 차량수 FROM vehicles GROUP BY Manufacturer ORDER BY 차량수 DESC;

-- 최근 크롤링 데이터
SELECT COUNT(*) as 오늘크롤링 FROM vehicles WHERE DATE(created_at) = CURRENT_DATE;

-- 데이터 품질 체크
SELECT COUNT(*) as 전체, COUNT(Price) as 가격있음, COUNT(Year) as 연식있음 FROM vehicles;

-- 중복 데이터 확인
SELECT id, COUNT(*) FROM vehicles GROUP BY id HAVING COUNT(*) > 1;
```

---

## 🎉 성공 확인 체크리스트

- [ ] `docker-compose ps postgres` 에서 Up 상태 확인
- [ ] `\dt` 명령으로 6개 테이블 존재 확인
- [ ] Python에서 DB 연결 성공
- [ ] 샘플 데이터 1건 삽입 성공
- [ ] `SELECT COUNT(*) FROM vehicles` 실행 성공

모든 항목 체크 완료시 환경 구축 성공! 🚀

---

## 📞 도움 요청

- **DB 연결 문제**: 팀 채팅방에 에러 로그 공유
- **스키마 변경 요청**: `db/init.sql` 수정 후 PR 생성
- **성능 최적화**: DB 담당자와 인덱스 최적화 상의

---

*마지막 업데이트: 2025-09-10* 