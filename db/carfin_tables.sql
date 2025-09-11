-- 1. 엔카 차량 크롤링 목록
CREATE TABLE IF NOT EXISTS vehicles (
    vehicleId INT NOT NULL,         -- 차량 고유 ID
    Market VARCHAR(16),             -- 국내차/외제차
    Manufacturer VARCHAR(100),      -- 제조사
    Model VARCHAR(150),             -- 모델명
    Category VARCHAR(150),          -- 차종
    Badge VARCHAR(100),             -- 트림/등급
    BadgeDetail VARCHAR(150),       -- 트림 상세
    Transmission VARCHAR(50),       -- 변속기
    FuelType VARCHAR(50),           -- 연료
    Year INT,                       -- 최초등록연도 (또는 연식)
    Mileage INT,                    -- 주행거리 (㎞)
    Price INT,                      -- 판매가 (원)
    SellType VARCHAR(50),           -- 판매형태 (일반/리스 등)
    OfficeCityState VARCHAR(100),   -- 차량 소재지
    detail_url VARCHAR(1024),       -- 상세 페이지 URL
    Photo VARCHAR(1024),            -- 차량 이미지 URL
    PRIMARY KEY (vehicleId)
);


-- 2. 차량Id + 차량번호
CREATE TABLE IF NOT EXISTS vehicles_info (
    vehicleId INT PRIMARY KEY,    -- 차량 고유 ID
    vehicleNo VARCHAR(20),        -- 차량 번호판
    FOREIGN KEY (vehicleId) REFERENCES vehicles(vehicleId)
);

-- 3. 보험이력 목록
CREATE TABLE IF NOT EXISTS vehicles_inspect (
    vehicleId INT PRIMARY KEY,    -- 차량 고유 ID
    WarrantyType VARCHAR(50),     -- 보증유형
    Tuning VARCHAR(50),           -- 튜닝 여부
    ChangeUsage VARCHAR(16),      -- 용도변경 여부
    Recall VARCHAR(16),           -- 리콜대상 여부
    RecallStatus VARCHAR(16),     -- 리콜대상 여부
    AccidentHistory VARCHAR(16),  -- 사고이력 여부
    SimpleRepair VARCHAR(16),     -- 단순수리 여부
    FOREIGN KEY (vehicleId) REFERENCES vehicles(vehicleId)
);
