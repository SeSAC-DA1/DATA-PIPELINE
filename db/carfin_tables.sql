-- 1. 엔카 차량 크롤링 목록
CREATE TABLE IF NOT EXISTS vehicles (
    vehicleId INT NOT NULL AUTO_INCREMENT,         -- 내부 PK
    encarId   INT NOT NULL,                        -- Encar 고유 ID
    vehicleNo VARCHAR(20),                         -- 차량 번호판
    Market VARCHAR(16),                            -- 국내차/외제차
    Category VARCHAR(50),                          -- 차종
    Manufacturer VARCHAR(100),                     -- 제조사
    Model VARCHAR(150),                            -- 모델명
    Badge VARCHAR(100),                            -- 트림/등급
    BadgeDetail VARCHAR(150),                      -- 트림 상세
    ColorName VARCHAR(50),                         -- 색상
    Transmission VARCHAR(50),                      -- 변속기
    FuelType VARCHAR(50),                          -- 연료
    Year INT,                                      -- 최초등록연도
    Mileage INT,                                   -- 주행거리 (km)
    Price INT,                                     -- 판매가
    OriginPrice INT,                               -- 신차판매가
    SellType VARCHAR(50),                          -- 판매형태
    OfficeCityState VARCHAR(100),                  -- 소재지
    detail_url VARCHAR(1024),                      -- 상세 URL
    Photo VARCHAR(1024),                           -- 대표 이미지 URL
    PRIMARY KEY (vehicleId),
    UNIQUE KEY unique_encarId (encarId)
);

-- 2. 성능점검표 목록
CREATE TABLE IF NOT EXISTS vehicles_inspect (
    vehicleId INT PRIMARY KEY,    -- 차량 고유 ID
    WarrantyType VARCHAR(50),     -- 보증유형
    Tuning VARCHAR(50),           -- 튜닝 여부
    ChangeUsage VARCHAR(16),      -- 용도변경 여부
    Recall VARCHAR(16),           -- 리콜대상 여부
    RecallStatus VARCHAR(16),     -- 리콜이행 여부
    AccidentHistory VARCHAR(16),  -- 사고이력 여부
    SimpleRepair VARCHAR(16),     -- 단순수리 여부
    FOREIGN KEY (vehicleId) REFERENCES vehicles(vehicleId)
);

-- 3. 보험이력 목록
CREATE TABLE IF NOT EXISTS vehicles_insurance (
    vehicleId INT PRIMARY KEY,    -- 차량 고유 ID
    vehicleNo VARCHAR(20),        -- 차량번호
    OwnerChangeCnt INT,           -- 소유주 이전 횟수
    MyAccidentCnt INT,            -- 내차 피해 사고이력(횟수)
    MyAccidentCost INT,           -- 내차 피해 사고이력(금액)
    OtherAccidentCnt INT,         -- 타차 가해 사고이력(횟수)
    OtherAccidentCost INT,        -- 타차 가해 사고이력(금액)
    isDisclosed TINYINT(1),       -- 보험이력 공개여부(0:비공개/1:공개)
    FOREIGN KEY (vehicleId) REFERENCES vehicles(vehicleId)
);