# 🚗 CarFin: AI 기반 차량 추천 및 금융 매칭 통합 플랫폼

## ✨ 프로젝트 소개

**CarFin**은 사회초년생이 겪는 '어떤 차를 어떻게 살까?'라는 고민을 해결해주는 **원스톱 통합 의사결정 플랫폼**입니다. 사용자의 라이프스타일과 재정 상태를 분석하여 최적의 차량을 추천하고, AI 기반 금융 매칭을 통해 맞춤형 대출 및 보험 상품까지 한 번에 제공하여, 데이터 기반의 투명하고 합리적인 차량 구매 경험을 제공하는 것을 목표로 합니다.

특히, 신용 이력이 부족하여 16~24%대의 고금리 대출에 내몰리는 **사회초년생**들이 겪는 정보 비대칭과 금융 장벽 문제를 해결하는 데 집중합니다.

---

## 📂 프로젝트 구조 (Project Structure)

이 프로젝트는 여러 컴포넌트(API 서버, 데이터 파이프라인 등)를 하나의 저장소에서 관리하는 **모노레포(Monorepo)** 구조를 따릅니다.

```
.
├── backend/          #  FastAPI 기반의 메인 API 서버
├── data-pipeline/    # 데이터 수집 및 처리를 위한 파이프라인
├── db/               # 데이터베이스 초기화 스크립트 및 설정
├── docs/             # 프로젝트 관련 문서
├── docker-compose.yml  # 전체 서비스 실행을 위한 Docker Compose 파일
└── README.md         # 프로젝트 안내 문서
```

각 폴더는 독립적인 애플리케이션으로 구성되어 있으며, 자세한 내용은 각 폴더의 `README.md`를 참고해주세요.

---

## ✨ Git 협업 워크플로우 (Git Workflow)

우리 팀은 `Git-flow` 전략을 기반으로 협업을 진행합니다.

- **`main`**: 🚢 **제품 출시**를 위한 브랜치입니다. 오직 `develop` 브랜치의 내용만 병합(Merge)하며, 직접적인 수정은 절대 금지합니다.
- **`develop`**: ✨ **다음 버전 개발**을 위한 통합 브랜치입니다. 모든 기능 개발은 이 브랜치에서 시작하고, 완료된 기능은 이 브랜치로 다시 병합됩니다.
- **`feature/{기능이름}`**: 📝 **신규 기능 개발**을 위한 브랜치입니다. `develop`에서 생성하며, 개발 완료 후 `develop`으로 PR(Pull Request)을 보냅니다. (예: `feature/login-api`)

### 🤝 협업 절차
1. `develop` 브랜치에서 최신 코드를 `pull` 받습니다.
2. `feature/기능이름` 브랜치를 새로 생성합니다.
3. 기능 개발을 완료하고 자신의 `feature` 브랜치에 커밋합니다.
4. GitHub에서 `develop` 브랜치를 대상으로 **Pull Request(PR)**를 생성합니다.
5. 다른 팀원 1명 이상에게 **코드 리뷰**를 받고 승인(Approve)을 받습니다.
6. PR을 `develop` 브랜치에 병합(Merge)합니다.

---

## 🏁 시작하기 (Getting Started)

프로젝트를 로컬 환경에서 실행하기 위한 절차입니다.

### 1. 저장소 복제
```bash
git clone https://github.com/SeSAC-DA1/backend.git
cd backend
```

### 2. 환경변수 설정
각 컴포넌트의 `.env.example` 파일을 복사하여 `.env` 파일을 생성하고, 자신의 로컬 환경에 맞게 값을 수정합니다.

- `backend/.env.example` -> `backend/.env`
- `data-pipeline/.env.example` -> `data-pipeline/.env`

**`backend/.env` 예시:**
```
DATABASE_URL="postgresql+asyncpg://carfin_admin:carfin_secure_password_2025@localhost:5432/carfin"
# ... 기타 Supabase 키 등
```
> **Note**: `docker-compose` 환경에서는 호스트 이름을 `localhost`가 아닌 Docker Compose 파일에 정의된 서비스 이름(예: `postgres`)으로 설정해야 합니다.

### 3. 서비스 실행
프로젝트 루트 디렉토리에서 아래 명령어를 실행하여 모든 서비스를 한 번에 시작합니다.
```bash
docker-compose up --build
```
- `--build` 옵션은 Docker 이미지를 새로 빌드한 후 컨테이너를 실행합니다. 코드 변경사항이 있을 때 사용합니다.

### 4. API 문서 확인
백엔드 서버가 정상적으로 실행되면, 아래 주소에서 자동으로 생성된 API 문서를 확인할 수 있습니다.
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

---

## 🛠️ 기술 스택 (Technology Stack)

실무 환경과 동일한 기술 스택을 사용하여 확장 가능하고 안정적인 시스템을 구축합니다.

| 역할 | 기술 | 선정한 이유 |
| :--- | :--- | :--- |
| **프론트엔드** | `Next.js`, `React`, `TypeScript` | 사용자에게 빠르고 현대적인 웹 화면을 제공하며, 코드의 안정성을 높입니다. |
| **백엔드** | `FastAPI` (Python), `Uvicorn` | AI 모델의 결과를 전달하고, 데이터를 처리하는 고성능 서버를 빠르게 구축합니다. |
| (서버 & AI) | `Supabase` (Python SDK), `python-dotenv`, `pydantic`, `requests`, `httpx` | Supabase를 통한 인증, 환경 변수 관리, 데이터 유효성 검사, HTTP 통신을 처리합니다. |
| | `psycopg2-binary`, `asyncpg`, `SQLAlchemy`, `Alembic` | PostgreSQL 데이터베이스 연동 및 마이그레이션을 위한 라이브러리입니다. |
| | `scikit-learn`, `pandas`, `numpy` (AI/ML 라이브러리) | 차량 리스크 분석 및 **개인화된 차량 추천 시스템**과 같은 핵심 AI 모델을 개발하는 데 활용됩니다. 특히, **scikit-learn**은 다양한 머신러닝 알고리즘을 제공하여 추천 모델 구축에 적합합니다. |
| **데이터베이스** | `PostgreSQL` | 실무에서 가장 널리 사용되는 관계형 데이터베이스로, 안정성과 확장성이 뛰어납니다. **Docker Compose로 직접 구축하여 완전한 제어권을 확보**합니다. |
| **인증 시스템** | `Supabase Auth` | 구글 소셜 로그인 등 OAuth 인증 기능을 빠르게 구현하기 위해 사용합니다. |
| **인프라** | `Docker`, `docker-compose` | 어디서든 동일한 개발/실행 환경을 보장하고, **PostgreSQL 등 모든 서비스를 컨테이너로 관리**합니다. |
| (개발 환경) | `Poetry` (Python 의존성 관리) | 백엔드(Python)에서 사용하는 수많은 라이브러리들의 버전을 깔끔하게 관리합니다. |
| **테스트** | `pytest`, `pytest-asyncio` | 백엔드 API의 기능 및 비동기 테스트를 위한 프레임워크입니다. |

---

## 🐳 Docker + PostgreSQL 아키텍처

**실무 표준 기술 스택**을 사용하여 확장 가능하고 관리하기 쉬운 시스템을 구축했습니다.

### 🏗️ 서비스 구성
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Database      │
│   (Next.js)     │ ─► │   (FastAPI)     │ ─► │   (PostgreSQL)  │
│   Port: 3000    │    │   Port: 8000    │    │   Port: 5432    │
│   (별도 개발)    │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**현재 구성 (Backend + Database):**
- Backend (FastAPI): `http://localhost:8000`
- Database (PostgreSQL): `localhost:5432`
- Frontend: 별도 개발 예정

### 💪 주요 장점
- **완전한 제어권**: 데이터베이스 설정, 튜닝, 백업을 직접 관리
- **확장성**: 필요에 따라 Read Replica, 샤딩 등 구현 가능
- **비용 효율성**: 오픈소스 기반으로 라이센스 비용 없음
- **포트폴리오 가치**: 실무에서 요구하는 "인프라 구축 및 관리" 경험

---

## 💎 차별점 및 경쟁 우위

기존 서비스들은 차량 정보 제공과 금융 상품 추천을 별개로 다루지만, CarFin은 **'최적 차량 추천 + 맞춤 금융 설계'를 하나의 흐름으로 통합**하여, 특히 금융 정보에 취약한 사용자를 위한 원스톱 솔루션을 제공하는 점에서 명확한 차별점을 가집니다.

---

## 🗄️ 데이터베이스 설계 (Database Schema)

**Docker Compose로 구축한 PostgreSQL 서버**에 아래와 같은 구조로 데이터를 저장합니다. 인증 정보만 Supabase Auth를 사용하고, 모든 비즈니스 데이터는 자체 PostgreSQL에서 관리합니다.

#### 1. `users` - 사용자 정보
> 서비스에 가입한 사용자의 기본 정보와 AI 추천에 필요한 프로필 데이터를 저장합니다.

| 컬럼명 | 데이터 타입 | 설명 |
| :--- | :--- | :--- |
| `id` | `UUID` | 사용자 고유 ID |
| `email` | `text` | 로그인용 이메일 |
| `password` | `text` | 암호화된 비밀번호 |
| `user_profile` | `jsonb` | 사용자의 라이프스타일, 선호도, 예산 등 (JSON 형식) |
| `created_at` | `timestamptz` | 가입일 |

#### 2. `vehicles` - 차량 매물 정보
> 외부 사이트에서 수집한 중고차 매물의 상세 정보와 AI 분석 결과를 저장합니다.

| 컬럼명 | 데이터 타입 | 설명 |
| :--- | :--- | :--- |
| `id` | `UUID` | 차량 매물 고유 ID |
| `source` | `text` | 데이터 출처 (예: '엔카') |
| `make` | `text` | 제조사 |
| `model` | `text` | 모델명 |
| `year` | `integer` | 연식 |
| `mileage` | `integer` | 주행거리 |
| `price` | `integer` | 판매 가격 |
| `details` | `jsonb` | 사고 이력, 정비 기록 등 |
| `risk_score` | `float` | AI가 분석한 차량 리스크 점수 |
| `tco` | `integer` | AI가 분석한 5년 총 소유 비용 |

#### 3. `recommendations` - 개인화 추천 결과
> AI가 각 사용자에게 어떤 차량을 추천했는지 기록합니다.

| 컬럼명 | 데이터 타입 | 설명 |
| :--- | :--- | :--- |
| `id` | `UUID` | 추천 기록 고유 ID |
| `user_id` | `UUID` | 추천 받은 사용자 (users.id) |
| `vehicle_id` | `UUID` | 추천된 차량 (vehicles.id) |
| `score` | `float` | AI 추천 정확도 점수 |
| `created_at` | `timestamptz` | 추천 생성 시각 |

#### 4. `financial_products` - 금융 상품 정보
> 제휴된 캐피탈사의 대출, 보험 상품 정보를 저장합니다.

| 컬럼명 | 데이터 타입 | 설명 |
| :--- | :--- | :--- |
| `id` | `UUID` | 금융 상품 고유 ID |
| `company` | `text` | 금융사 이름 |
| `product_name` | `text` | 상품명 |
| `product_type` | `text` | '대출' 또는 '보험' |
| `details` | `jsonb` | 이자율, 한도, 조건 등 |

#### 5. `matches` - 금융 상품 매칭 결과
> AI가 사용자에게 어떤 금융 상품을 어떤 조건으로 매칭했는지 기록합니다.

| 컬럼명 | 데이터 타입 | 설명 |
| :--- | :--- | :--- |
| `id` | `UUID` | 매칭 기록 고유 ID |
| `user_id` | `UUID` | 매칭된 사용자 (users.id) |
| `product_id` | `UUID` | 매칭된 금융 상품 (financial_products.id) |
| `conditions` | `jsonb` | 사용자에게 제공된 최종 금리, 한도 등 |
| `created_at` | `timestamptz` | 매칭 생성 시각 |

---

## 🚀 프로젝트 로드맵 (Roadmap)

1.  **기반 공사 (✅ 완료)**: 개발 환경 구축, Docker Compose 기반 인프라 구성 완료.
2.  **인증 시스템 구축 (✅ 완료)**: Supabase Auth를 활용한 구글 소셜 로그인 구현 완료.
3.  **데이터베이스 서버 구축 (✅ 완료)**: PostgreSQL을 Docker Compose로 구성, 테이블 생성 완료.
4.  **데이터 수집 시스템 (🔄 진행중)**: 엔카 크롤러 구현 완료, Airflow 통합 예정.
5.  **백엔드 API 개발**: 차량 데이터 CRUD, 추천 시스템, 금융 매칭 API 구현.
6.  **AI 모델 개발**: 차량 추천 및 리스크 분석 모델 개발 및 API 연동.
7.  **프론트엔드 화면 구현**: 사용자 대시보드, 추천 결과, 금융 매칭 UI 개발.
8.  **성능 최적화 및 배포**: 대용량 데이터 처리 최적화, 클라우드 배포.

### 📊 Airflow 통합 계획 (예정)

**현재 상태**: 엔카 크롤러가 구현되어 있으며, 수동 실행으로 데이터 수집 중

**Airflow 통합 목표**:
- **자동화된 스케줄링**: 매일 새벽 2시 자동 크롤링 실행
- **모니터링 및 알림**: 크롤링 실패 시 Slack/이메일 알림
- **재시도 로직**: 네트워크 오류 시 자동 재시도 (3회)
- **데이터 품질 검증**: 수집된 데이터 무결성 검증
- **확장성**: 다른 차량 사이트 크롤러 추가 시 통합 관리

**구현 예정 DAG 구조**:
```
daily_car_crawling_dag:
├── check_database_connection     # DB 연결 상태 확인
├── crawl_korean_cars            # 국산차 크롤링 (현재 크롤러 활용)
├── crawl_foreign_cars           # 수입차 크롤링 (현재 크롤러 활용)
├── data_quality_check           # 수집 데이터 품질 검증
├── send_success_notification    # 성공 시 알림
└── cleanup_old_data            # 오래된 데이터 정리 (선택적)
```

**기술 스택**:
- **Apache Airflow**: 워크플로우 오케스트레이션
- **Docker Compose**: Airflow 서비스 컨테이너화
- **현재 크롤러**: 기존 `encar_crawler.py` 재활용

---

## 📄 API 문서 (API Documentation)

CarFin 백엔드 API는 FastAPI를 기반으로 하며, 자동으로 생성되는 대화형 API 문서를 제공합니다. 백엔드 서버가 실행 중일 때 다음 URL에서 접근할 수 있습니다:

*   **Swagger UI**: `http://localhost:8000/docs`
*   **ReDoc**: `http://localhost:8000/redoc`

---

## 🗄️ 데이터베이스 마이그레이션 (Database Migrations)

프로젝트는 Alembic을 사용하여 데이터베이스 스키마 변경 사항을 관리합니다. 새로운 마이그레이션을 생성하거나 기존 마이그레이션을 적용하려면 다음 명령어를 사용합니다:

*   **새로운 마이그레이션 스크립트 생성**:
    ```bash
    docker-compose exec backend alembic revision --autogenerate -m "Your migration message"
    ```
    (여기서 "Your migration message"는 변경 내용을 설명하는 메시지로 대체합니다.)

*   **마이그레이션 적용 (최신 버전으로 업데이트)**:
    ```bash
    docker-compose exec backend alembic upgrade head
    ```

---

## ⚙️ 환경 변수 (Environment Variables)

백엔드 서비스는 `.env` 파일을 통해 환경 변수를 관리합니다. `backend/backend/.env.example` 파일을 복사하여 `backend/backend/.env` 파일을 생성하고, 다음 필수 환경 변수를 설정해야 합니다:

*   `DATABASE_URL`: PostgreSQL 데이터베이스 연결 URL (예: `postgresql+asyncpg://carfin_admin:carfin_secure_password_2025@postgres:5432/carfin`)
*   `SUPABASE_URL`: Supabase 프로젝트 URL
*   `SUPABASE_KEY`: Supabase 서비스 역할 키 (또는 공개 API 키)
*   `ENVIRONMENT`: 애플리케이션 환경 (예: `development`, `production`)
*   `DEBUG`: 디버그 모드 활성화 여부 (`True` 또는 `False`)

---

## 🌐 향후 확장 계획

*   **B2B 협업 채널**: 축적된 데이터를 바탕으로 금융사, 보험사, 정비업체 등과 제휴하여 신규 수익 모델을 창출합니다.
*   **정책 및 연구 데이터 제공**: 시장 동향 분석 데이터를 공공/연구 기관에 제공하여 산업 발전에 기여합니다.
*   **글로벌 모델 진출**: 각 국가의 시장 특성에 맞게 시스템을 현지화하여 글로벌 플랫폼으로 확장합니다.