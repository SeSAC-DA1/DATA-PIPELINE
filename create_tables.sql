-- 1. users 테이블 생성
-- 서비스에 가입한 사용자의 기본 정보와 AI 추천에 필요한 프로필 데이터를 저장합니다.
CREATE TABLE users (
    id UUID PRIMARY KEY, -- 사용자 고유 식별자 (Supabase auth.users.id와 동일)
    email TEXT UNIQUE NOT NULL, -- 로그인에 사용될 이메일 주소 (고유값, 필수)
    user_profile JSONB, -- 사용자의 라이프스타일, 선호도, 예산 등 추천에 필요한 정보
    created_at TIMESTAMPTZ DEFAULT NOW() -- 사용자 가입일
);
COMMENT ON TABLE users IS '사용자 정보';

-- 2. vehicles 테이블 생성
-- 외부 사이트에서 수집한 중고차 매물의 상세 정보와 AI 분석 결과를 저장합니다.
CREATE TABLE vehicles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), -- 차량 매물 고유 식별자 (Primary Key)
    source TEXT, -- 데이터 출처 (예: '엔카', 'KB차차차')
    make TEXT, -- 제조사 (예: '현대')
    model TEXT, -- 모델명 (예: '쏘나타')
    year INTEGER, -- 연식
    mileage INTEGER, -- 주행거리 (km)
    price INTEGER, -- 판매 가격 (만원 단위)
    details JSONB, -- 사고 이력, 옵션, 색상 등 기타 상세 정보
    risk_score FLOAT, -- AI가 분석한 차량의 리스크 점수
    tco INTEGER, -- AI가 분석한 5년 총 소유 비용
    created_at TIMESTAMPTZ DEFAULT NOW(), -- 데이터 생성일
    updated_at TIMESTAMPTZ -- 데이터 마지막 수정일
);
COMMENT ON TABLE vehicles IS '차량 매물 정보';

-- 3. financial_products 테이블 생성
-- 제휴된 캐피탈사의 대출, 보험 상품의 정보를 저장합니다.
CREATE TABLE financial_products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), -- 금융 상품 고유 식별자 (Primary Key)
    company TEXT, -- 금융사 이름 (예: '현대캐피탈')
    product_name TEXT, -- 상품명 (예: '중고차 안심론')
    product_type TEXT, -- 상품 종류 ('대출', '보험')
    details JSONB, -- 이자율, 한도, 조건 등 상세 정보
    created_at TIMESTAMPTZ DEFAULT NOW() -- 상품 정보 생성일
);
COMMENT ON TABLE financial_products IS '금융 상품 정보';

-- 4. recommendations 테이블 생성
-- AI가 각 사용자에게 어떤 차량을 추천했는지 기록합니다.
CREATE TABLE recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), -- 추천 기록 고유 식별자 (Primary Key)
    user_id UUID REFERENCES users(id) ON DELETE CASCADE, -- 추천 받은 사용자 (users 테이블의 id 참조)
    vehicle_id UUID REFERENCES vehicles(id) ON DELETE CASCADE, -- 추천된 차량 (vehicles 테이블의 id 참조)
    score FLOAT, -- AI 모델이 이 추천을 얼마나 확신하는지에 대한 점수
    created_at TIMESTAMPTZ DEFAULT NOW() -- 추천 생성 시각
);
COMMENT ON TABLE recommendations IS '개인화 추천 결과';

-- 5. matches 테이블 생성
-- AI가 사용자에게 어떤 금융 상품을 어떤 조건으로 매칭했는지 기록합니다.
CREATE TABLE matches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), -- 매칭 기록 고유 식별자 (Primary Key)
    user_id UUID REFERENCES users(id) ON DELETE CASCADE, -- 매칭된 사용자 (users 테이블의 id 참조)
    product_id UUID REFERENCES financial_products(id) ON DELETE CASCADE, -- 매칭된 금융 상품 (financial_products 테이블의 id 참조)
    conditions JSONB, -- 사용자에게 제공되는 최종 금리, 한도 등 맞춤 조건
    created_at TIMESTAMPTZ DEFAULT NOW() -- 매칭 생성 시각
);
COMMENT ON TABLE matches IS '금융 상품 매칭 결과';

-- 6. loan_rates 테이블 생성
-- 특정 금융 상품의 기간별 금리 정보를 저장합니다.
CREATE TABLE loan_rates (
  product_id     UUID        NOT NULL REFERENCES financial_products(id) ON DELETE CASCADE, -- 금융 상품 ID (FK)
  effective_date DATE        NOT NULL,                  -- 기준일자
  term_months    SMALLINT    NOT NULL,                  -- 만기 (6, 12, ...)
  base_rate      DECIMAL(5,2) NOT NULL,                 -- 기준금리(%)
  spread_rate    DECIMAL(5,2) NOT NULL,                 -- 가산금리(%)
  pref_rate      DECIMAL(5,2) NOT NULL,                 -- 우대금리(%)
  min_rate       DECIMAL(5,2) NOT NULL,                 -- 최저금리(%)
  max_rate       DECIMAL(5,2) NOT NULL,                 -- 최고금리(%)
  source_url     VARCHAR(255) NULL,                     -- 크롤링 원본
  scraped_at     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (product_id, effective_date, term_months), -- 복합 기본 키
  INDEX idx_loan_rates_date (effective_date)
);
COMMENT ON TABLE loan_rates IS '기간별 대출 금리 정보';

-- 7. 캐글 csv파일 고객 정보
CREATE TABLE customers (
    sk_id_curr                  INTEGER PRIMARY KEY,              -- 고객 ID

    -- 0/1을 그대로 저장 (boolean 아님)
    code_gender                 SMALLINT NOT NULL CHECK (code_gender IN (0,1)),
    flag_own_car                SMALLINT NOT NULL CHECK (flag_own_car IN (0,1)),
    flag_own_realty             SMALLINT NOT NULL CHECK (flag_own_realty IN (0,1)),

    cnt_children                SMALLINT        CHECK (cnt_children >= 0),
    amt_income_total            NUMERIC(14,2)   CHECK (amt_income_total >= 0),
    amt_credit                  NUMERIC(14,2)   CHECK (amt_credit >= 0),
    amt_annuity                 NUMERIC(14,2),

    name_type_suite             TEXT,
    name_income_type            TEXT,
    name_education_type         TEXT,
    name_housing_type           TEXT,
    

    region_population_relative  NUMERIC(8,6),
    days_birth                  INTEGER,        -- 음수(과거 일수)
    days_employed               INTEGER,        -- 특수 큰값(미취업 플래그) 사전 처리 권장
    days_id_publish             INTEGER,
    own_car_age                 SMALLINT,
    cnt_fam_members             SMALLINT        CHECK (cnt_fam_members >= 0),
    hour_appr_process_start     SMALLINT        CHECK (hour_appr_process_start BETWEEN 0 AND 23),

    organization_type           TEXT,

    ext_source_1                NUMERIC(10,8),  -- 0~1, 결측 허용
    ext_source_2                NUMERIC(10,8),
    ext_source_3                NUMERIC(10,8),

    days_last_phone_change      INTEGER,
    amt_req_credit_bureau_year  SMALLINT        CHECK (amt_req_credit_bureau_year >= 0),

);
