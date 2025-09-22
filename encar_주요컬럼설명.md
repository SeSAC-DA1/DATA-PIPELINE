## 🚗 엔카 중고차 데이터 주요 컬럼 설명


#### 🏷️ 차량 기본 정보
> 차량의 기본적인 제원과 관련된 정보입니다.

- `vehicleId`: 차량 매물의 고유 ID (엔카 내부 식별자)
- `Market`: 국산/수입 구분
- `Manufacturer`: 제조사 (ex. 현대, 기아, BMW)
- `Model`: 모델명 (ex. 쏘나타, G80)
- `Category`: 차종 (ex. 대형차, SUV)
- `Badge`: 주력 트림 (ex. 2.5 가솔린 2WD)
- `BadgeDetail`: 세부 트림 (ex. 프레스티지)
- `Year`: 최초등록연도 (또는 연식)
- `Mileage`: 주행거리 (km)
- `Transmission`: 변속기 (ex. 오토, 수동)
- `FuelType`: 사용 연료 (ex. 가솔린, 디젤, 하이브리드)
- `Photo` / `Photos`: 대표 이미지 URL / 전체 이미지 URL 배열
- `detail_url`: 해당 차량의 엔카 상세 페이지 URL

---

#### 🏷️ 판매 및 상태 정보
> 판매 형태, 가격, 판매자 등 거래와 관련된 정보입니다.

- `Price`: 판매 가격
- `SellType`: 판매 형태 (ex. 일반, 리스 승계)
- `OfficeCityState`: 차량 소재지 (ex. 서울, 경기)
- `OfficeName`: 판매업체 상호명 (ex. 주식회사 OOO모터스)
- `DealerName`: 딜러 이름
- `ModifiedDate`: 매물 등록 또는 수정 일시
- `Condition`: 상태 태그 (ex. 성능점검, 무사고)
- `Separation`: 매물 구분 태그 (ex. 일반, 인증)
- `Trust` / `ServiceMark`: 엔카 보증 서비스 관련 마크
- `HomeServiceVerification` / `HomeServiceProgress`: 엔카 홈서비스 가능 여부 및 진행 상태

---

#### 🏷️ 성능·점검 기록
> 차량의 성능 점검 및 사고/수리 이력에 대한 정보입니다.

- `WarrantyType`: 보증 유형 (ex. 제조사 보증, 엔카 보증)
- `Tuning`: 튜닝 여부 (ex. 특별이력)
- `ChangeUsage`: 용도 변경 이력 (ex. 영업용, 렌트)
- `AccidentHistory`: 사고 이력 여부 (ex. 무사고, 단순교환)
- `SimpleRepair`: 단순 수리 여부 (ex. 없음, 외판)
- `Recall`: 리콜 대상 여부
- `RecallStatus`: 리콜 이행 여부

---

#### 🏷️ 보험 이력
> 보험개발원에서 제공하는 사고 및 수리 비용에 대한 정보입니다.

- `vehicleNo`: 차량 번호판
- `OwnerChangeCnt`: 소유주 변경 횟수
- `MyAccidentCnt`: 내차 피해 사고 횟수
- `MyAccidentCost`: 내차 피해 사고 금액 (자차 보험 처리)
- `OtherAccidentCnt`: 타차 가해 사고 횟수
- `OtherAccidentCost`: 타차 가해 사고 금액 (대물 보험 처리)
- `isDisclosed`: 보험 이력 공개 여부

---

#### 🏷️ 기타 정보
> 광고, 리스 등 부가적인 정보입니다.

- `AdWords` / `Hotmark` / `Powerpack`: 프로모션, 광고 관련 내부 태그
- `BrandAuthCmnt`: 브랜드 공식 인증 중고차 코멘트
- `Lease` / `LeaseType`: 리스 차량 여부 및 종류
- `MonthLeasePrice`: 월 리스료
- `Deposit`: 리스 보증금
- `ResidualValue`: 리스 잔존가치
- `Succession`: 리스 승계 가능 여부