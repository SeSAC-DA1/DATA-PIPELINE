-- 1. 엔카 차량 크롤링 목록
CREATE TABLE IF NOT EXISTS vehicles (
    Id INT NOT NULL, -- 차량 고유 ID
    Market VARCHAR(16), -- 국내차/외제차
    Manufacturer VARCHAR(100), -- 제조사
    Model VARCHAR(150), -- 모델명
    Category VARCHAR(150), -- 차종
    Badge VARCHAR(100), -- 트림/등급
    BadgeDetail VARCHAR(150), -- 트림 상세
    Transmission VARCHAR(50), -- 변속기
    FuelType VARCHAR(50), -- 연료
    Year INT, -- 최초등록연도 (또는 연식)
    Mileage INT, -- 주행거리 (㎞)
    Price INT, -- 판매가 (원)
    SellType VARCHAR(50), -- 판매형태 (일반/리스 등)
    OfficeCityState VARCHAR(100), -- 차량 소재지
    detail_url VARCHAR(1024), -- 상세 페이지 URL
    Photo VARCHAR(1024), -- 차량 이미지 URL
    PRIMARY KEY (Id)
);