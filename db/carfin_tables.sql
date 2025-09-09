-- 1. 엔카 차량 크롤링 목록
CREATE TABLE vehicles (
    Id TEXT PRIMARY KEY, -- 차량 고유 ID
    Manufacturer TEXT, -- 제조사
    Model TEXT, -- 모델명
    Category TEXT, -- 차종 (경차/소형차/…)
    Badge TEXT, -- 트림/등급
    BadgeDetail TEXT, -- 트림 상세
    Transmission TEXT, -- 변속기
    FuelType TEXT, -- 연료
    Year INTEGER, -- 최초등록연도 (또는 연식)
    Mileage INTEGER, -- 주행거리 (㎞)
    Price INTEGER, -- 판매가 (원)
    SellType TEXT, -- 판매형태 (일반/리스 등)
    OfficeCityState TEXT, -- 차량 소재지
    detail_url TEXT, -- 상세 페이지 URL
    Photo TEXT -- 차량 이미지 URL
);