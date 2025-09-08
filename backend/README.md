# 🚗 CarFin AI - 백엔드 API 서버

안녕하세요! CarFin AI 프로젝트의 백엔드 API 서버에 오신 것을 환영합니다. 👋

이 프로젝트는 자동차 금융 상품 추천 및 관련 데이터 분석을 위한 AI 기반 서비스의 핵심 백엔드 시스템입니다. FastAPI를 기반으로 구축되어 높은 성능과 안정적인 API를 제공하는 것을 목표로 합니다.

---

## 🎯 주요 목표

*   **확장 가능한 아키텍처:** 새로운 기능(차량, 금융 상품, AI 모델)을 쉽게 추가할 수 있는 유연한 구조를 지향합니다.
*   **안정적인 의존성 관리:** `Poetry`를 사용하여 모든 개발자가 동일한 환경에서 작업할 수 있도록 보장합니다.
*   **손쉬운 배포:** `Docker`를 통해 어떤 환경에서든 몇 가지 명령어로 서버를 실행할 수 있도록 합니다.

## ✨ 주요 기능

*   **사용자 관리:** 기본적인 사용자 생성 및 조회 API
*   **데이터베이스 연동:** Supabase 클라이언트를 통한 안정적인 데이터 관리
*   **상태 확인 API:** 서버 및 데이터베이스의 현재 상태를 모니터링하는 헬스 체크 기능
*   **자동 API 문서:** FastAPI를 통해 API 문서를 자동으로 생성 (`/docs`)

## 🏗️ 아키텍처 개요

프로젝트는 유지보수와 기능 확장을 용이하게 하기 위해 다음과 같은 구조로 설계되었습니다.

```
src/backend/
├── api/          # API 엔드포인트들을 모아놓은 곳
│   ├── endpoints/  # 기능별 API (예: users.py)
│   └── router.py   # 각 엔드포인트들을 하나로 묶어주는 라우터
├── core/         # 프로젝트의 핵심 설정 (예: 환경변수, DB 연결)
│   └── config.py
└── main.py       # FastAPI 앱을 생성하고 전체적으로 조립하는 시작점
```

---

## 🚀 시작하기

이 프로젝트에서 개발을 시작하기 위해 필요한 모든 단계를 안내합니다.

### 1. 사전 요구사항

*   Python (3.10 이상)
*   Poetry (Python 의존성 관리 도구)

### 2. 프로젝트 클론 및 설정

```bash
# 1. 이 저장소를 컴퓨터로 클론합니다.
git clone https://github.com/SeSAC-DA1/backend.git

# 2. 프로젝트 폴더로 이동합니다.
cd backend
```

### 3. 환경 변수 설정

프로젝트가 데이터베이스(Supabase)에 연결하기 위해서는 접속 정보가 필요합니다. `.env.example` 파일을 복사하여 `.env` 파일을 만드세요.

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

그다음, 생성된 `.env` 파일을 열고 실제 Supabase URL과 서비스 키를 입력해주세요.

```env
# .env
SUPABASE_URL="YOUR_SUPABASE_URL"
SUPABASE_SERVICE_KEY="YOUR_SUPABASE_SERVICE_KEY"
```

### 4. 의존성 설치

`Poetry`를 사용하여 프로젝트에 필요한 모든 라이브러리를 설치합니다. 이 명령어 하나면 모든 개발자가 동일한 버전의 라이브러리를 갖게 됩니다.

```bash
poetry install
```

### 5. 서버 실행

이제 개발용 서버를 실행할 준비가 되었습니다! 아래 명령어를 입력하세요.

```bash
poetry run uvicorn backend.main:app --reload
```
*   `--reload` 옵션 덕분에 코드를 수정하고 저장하면 서버가 자동으로 재시작됩니다.

서버가 성공적으로 실행되면, 웹 브라우저에서 [http://127.0.0.1:8000](http://127.0.0.1:8000)으로 접속하여 서버 상태를 확인할 수 있습니다.

### 6. 자동 API 문서 확인

FastAPI의 가장 큰 장점 중 하나! 서버가 실행 중일 때 [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs) 로 접속하면, 사용 가능한 모든 API 목록과 테스트 기능을 제공하는 멋진 문서를 바로 확인할 수 있습니다.

---

## 📦 의존성 관리 가이드

이 프로젝트는 `Poetry`를 사용하여 의존성을 관리합니다. `requirements.txt`를 직접 수정하지 마세요!

*   **새 라이브러리 추가:**
    ```bash
    poetry add <라이브러리 이름>
    ```
*   **개발용 라이브러리 추가 (예: pytest):
    ```bash
    poetry add --group dev <라이브러리 이름>
    ```

## 🐳 Docker로 실행하기

Docker를 사용하면 더 간편하게 서버를 실행할 수 있습니다.

**1. `requirements.txt` 생성:**
Docker는 `Poetry`를 직접 사용하지 않으므로, `Poetry`를 통해 `requirements.txt` 파일을 생성해야 합니다.

```bash
poetry export -f requirements.txt --output requirements.txt --without-hashes
```

**2. Docker 이미지 빌드 및 실행:**

```bash
# 1. Docker 이미지 빌드
docker build -t carfin-backend .

# 2. Docker 컨테이너 실행 (.env 파일의 변수 사용)
docker run -p 8000:8000 --env-file .env carfin-backend
```