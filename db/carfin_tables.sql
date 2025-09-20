-- 1. 차량 정보테이블
CREATE TABLE IF NOT EXISTS vehicles (
    VehicleId INT NOT NULL AUTO_INCREMENT,   -- 차량 고유 ID (내부 PK)
    CarSeq INT NOT NULL,                     -- 내부 식별자
    VehicleNo VARCHAR(20) NOT NULL,          -- 차량번호판
    Platform VARCHAR(16),                    -- 플랫폼 
    Origin VARCHAR(16),                      -- 시장 (국산/수입)
    CarType VARCHAR(16),                     -- 차종
    Manufacturer VARCHAR(20),                -- 제조사
    Model  VARCHAR(50),                      -- 모델명
    Generation VARCHAR(50),                  -- 세대(Badge)
    Trim VARCHAR(50),                        -- 트림(BadgeDetail)
    FuelType VARCHAR(16),                    -- 연료
    Transmission VARCHAR(16),                -- 변속기
    ColorName VARCHAR(50),                   -- 차량색상
    ModelYear INT,                           -- 차량연식
    FirstRegistrationDate INT,               -- 차량등록일
    Distance INT,                            -- 주행거리 (km)
    Price INT,                               -- 판매가
    OriginPrice INT,                         -- 출시가 
    SellType VARCHAR(50),                    -- 판매형태
    Location VARCHAR(20),                    -- 차량소재지
    DetailURL VARCHAR(1024),                 -- 상세 페이지 URL
    Photo VARCHAR(1024),                     -- 차량 이미지 URL
    PRIMARY KEY (VehicleId),
    UNIQUE KEY uniq_vehicle_no (VehicleNo)
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