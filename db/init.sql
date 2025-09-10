-- PostgreSQL UUID 확장 설치
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. users 테이블 생성
-- 서비스에 가입한 사용자의 기본 정보와 AI 추천에 필요한 프로필 데이터를 저장합니다.
CREATE TABLE users (
    id UUID PRIMARY KEY, -- 사용자 고유 식별자 (Supabase auth.users.id와 동일)
    email TEXT UNIQUE NOT NULL, -- 로그인에 사용될 이메일 주소 (고유값, 필수)
    user_profile JSONB, -- 사용자의 라이프스타일, 선호도, 예산 등 추천에 필요한 정보
    created_at TIMESTAMPTZ DEFAULT NOW() -- 사용자 가입일
);
COMMENT ON TABLE users IS '사용자 정보';

-- 2. vehicles 테이블 생성 (엔카 크롤링 최적화)
-- 외부 사이트에서 수집한 중고차 매물의 상세 정보와 AI 분석 결과를 저장합니다.
CREATE TABLE IF NOT EXISTS vehicles (
    id INT NOT NULL PRIMARY KEY, -- 차량 고유 ID (엔카 기준)
    Market VARCHAR(16), -- 국내차/외제차 구분
    Manufacturer VARCHAR(100), -- 제조사 (예: '현대', '기아', 'BMW')
    Model VARCHAR(150), -- 모델명 (예: '쏘나타', '아반떼')
    Category VARCHAR(150), -- 차종 (세단, SUV, 해치백 등)
    Badge VARCHAR(100), -- 트림/등급 (예: 'LX', 'VIP')
    BadgeDetail VARCHAR(150), -- 트림 상세 정보
    Transmission VARCHAR(50), -- 변속기 (자동/수동/CVT)
    FuelType VARCHAR(50), -- 연료 타입 (가솔린, 디젤, 하이브리드 등)
    Year INT, -- 최초등록연도 (또는 연식)
    Mileage INT, -- 주행거리 (㎞)
    Price INT, -- 판매가 (원)
    SellType VARCHAR(50), -- 판매형태 (일반/리스/렌트 등)
    OfficeCityState VARCHAR(100), -- 차량 소재지 (시/도 정보)
    detail_url VARCHAR(1024), -- 상세 페이지 URL
    Photo VARCHAR(1024), -- 차량 이미지 URL
    -- AI 분석 결과 컬럼 추가
    risk_score FLOAT, -- AI가 분석한 차량의 리스크 점수
    tco INTEGER, -- AI가 분석한 5년 총 소유 비용 (만원)
    created_at TIMESTAMPTZ DEFAULT NOW(), -- 데이터 생성일
    updated_at TIMESTAMPTZ -- 데이터 마지막 수정일
);
COMMENT ON TABLE vehicles IS '엔카 크롤링 차량 매물 정보';

-- 조회 성능 최적화를 위한 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_vehicles_maker_model ON vehicles(Manufacturer, Model);
CREATE INDEX IF NOT EXISTS idx_vehicles_year ON vehicles(Year);
CREATE INDEX IF NOT EXISTS idx_vehicles_price ON vehicles(Price);
CREATE INDEX IF NOT EXISTS idx_vehicles_office ON vehicles(OfficeCityState);
CREATE INDEX IF NOT EXISTS idx_vehicles_market ON vehicles(Market);
CREATE INDEX IF NOT EXISTS idx_vehicles_category ON vehicles(Category);
CREATE INDEX IF NOT EXISTS idx_vehicles_fueltype ON vehicles(FuelType);

-- 3. loan_product 테이블 생성
-- 대출 상품의 기본 정보를 저장합니다.
CREATE TABLE loan_product (
  product_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, -- 상품 고유 식별자
  bank_code    VARCHAR(20)  NOT NULL,              -- 은행 코드 (KB, NH, SC 등)
  product_title VARCHAR(120) NOT NULL,             -- 대출상품명
  product_code VARCHAR(40)   NULL,                 -- 내부 관리 코드/슬러그
  product_url  VARCHAR(255)  NULL,                 -- 상품 상세 URL
  product_type VARCHAR(20)   NOT NULL DEFAULT 'LOAN', -- 상품 유형 (LOAN, INSURANCE 등)
  target_customer VARCHAR(50) NULL,                -- 대상 고객군 (신입사원, 프리랜서 등)
  loan_limit   BIGINT       NULL,                  -- 대출 한도 (원)
  description  TEXT         NULL,                  -- 상품 설명
  is_active    BOOLEAN      NOT NULL DEFAULT true, -- 활성 상태
  created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(), -- 생성일
  updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(), -- 수정일
  
  CONSTRAINT uk_bank_title UNIQUE (bank_code, product_title) -- 은행별 상품명 중복 방지
);
COMMENT ON TABLE loan_product IS '대출 상품 기본 정보';

-- loan_product 테이블 인덱스 생성
CREATE INDEX idx_loan_product_bank_code ON loan_product(bank_code);
CREATE INDEX idx_loan_product_type ON loan_product(product_type);
CREATE INDEX idx_loan_product_active ON loan_product(is_active);

-- 4. loan_rates 테이블 생성  
-- 대출 상품별 기간별 금리 정보를 저장합니다.
CREATE TABLE loan_rates (
  rate_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,  -- 금리 정보 고유 식별자
  product_id   BIGINT       NOT NULL,              -- 상품 ID (FK)
  effective_date DATE       NOT NULL,              -- 기준일자
  term_months  SMALLINT     NOT NULL,              -- 대출 기간 (개월)
  base_rate    DECIMAL(5,2) NOT NULL,              -- 기준금리 (%)
  spread_rate  DECIMAL(5,2) NOT NULL DEFAULT 0.00, -- 가산금리 (%)
  pref_rate    DECIMAL(5,2) NOT NULL DEFAULT 0.00, -- 우대금리 (%)
  min_rate     DECIMAL(5,2) NOT NULL,              -- 최저 적용금리 (%)
  max_rate     DECIMAL(5,2) NOT NULL,              -- 최고 적용금리 (%)
  credit_score_min SMALLINT NULL,                  -- 최소 신용점수 요건
  credit_score_max SMALLINT NULL,                  -- 최대 신용점수 구간
  income_requirement BIGINT NULL,                  -- 최소 소득 요건 (원)
  source_url   VARCHAR(255) NULL,                  -- 크롤링 원본 URL
  scraped_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(), -- 크롤링 시각
  created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(), -- 생성일
  
  CONSTRAINT uk_product_date_term UNIQUE (product_id, effective_date, term_months), -- 상품별 날짜별 기간별 중복 방지
  CONSTRAINT fk_rates_product
    FOREIGN KEY (product_id) REFERENCES loan_product(product_id)
    ON UPDATE CASCADE ON DELETE RESTRICT -- 상품 삭제시 금리 정보는 보존
);
COMMENT ON TABLE loan_rates IS '대출 상품별 기간별 금리 정보';

-- loan_rates 테이블 인덱스 생성
CREATE INDEX idx_loan_rates_effective_date ON loan_rates(effective_date);
CREATE INDEX idx_loan_rates_term_months ON loan_rates(term_months);
CREATE INDEX idx_loan_rates_min_rate ON loan_rates(min_rate);
CREATE INDEX idx_loan_rates_credit_score ON loan_rates(credit_score_min, credit_score_max);

-- 5. recommendations 테이블 생성
-- AI가 각 사용자에게 어떤 차량을 추천했는지 기록합니다.
CREATE TABLE recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), -- 추천 기록 고유 식별자 (Primary Key)
    user_id UUID REFERENCES users(id) ON DELETE CASCADE, -- 추천 받은 사용자 (users 테이블의 id 참조)
    vehicle_id INT REFERENCES vehicles(id) ON DELETE CASCADE, -- 추천된 차량 (vehicles 테이블의 id 참조)
    score FLOAT, -- AI 모델이 이 추천을 얼마나 확신하는지에 대한 점수
    created_at TIMESTAMPTZ DEFAULT NOW() -- 추천 생성 시각
);
COMMENT ON TABLE recommendations IS '개인화 추천 결과';

-- 6. matches 테이블 생성
-- AI가 사용자에게 어떤 대출 상품을 어떤 조건으로 매칭했는지 기록합니다.
CREATE TABLE matches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), -- 매칭 기록 고유 식별자 (Primary Key)
    user_id UUID REFERENCES users(id) ON DELETE CASCADE, -- 매칭된 사용자 (users 테이블의 id 참조)
    product_id BIGINT REFERENCES loan_product(product_id) ON DELETE CASCADE, -- 매칭된 대출 상품 (loan_product 테이블의 product_id 참조)
    conditions JSONB, -- 사용자에게 제공되는 최종 금리, 한도 등 맞춤 조건
    created_at TIMESTAMPTZ DEFAULT NOW() -- 매칭 생성 시각
);
COMMENT ON TABLE matches IS '대출 상품 매칭 결과';
