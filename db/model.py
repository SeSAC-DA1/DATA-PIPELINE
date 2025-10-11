from sqlalchemy import Column, String, Integer, ForeignKey, Index, UniqueConstraint, Text, Boolean, DateTime, JSON, Enum, SmallInteger, Float
from sqlalchemy.ext.declarative import declarative_base
from .connection import session_scope, Engine

Base = declarative_base()

#차량 정보
class Vehicle(Base):
    __tablename__ = 'vehicles'
    
    vehicle_id = Column(Integer, primary_key=True, autoincrement=True)
    car_seq = Column(Integer, nullable=False)
    vehicle_no = Column(String, nullable=False, unique=True)
    platform = Column(String)
    origin = Column(String)
    car_type = Column(String)
    manufacturer = Column(String) #제조사
    model_group = Column(String)  # 모델그룹: EV6, 모하비
    model = Column(String)  # 모델명/세대: 더 뉴 EV6, 모하비 더 마스터
    grade = Column(String)  # 등급: 롱레인지 2WD, 디젤 3.0 4WD 6인승
    trim = Column(String)  # 트림: 어스, GT-Line, 마스터즈 그래비티
    fuel_type = Column(String)
    transmission = Column(String)
    displacement = Column(Integer)  # 배기량 (cc 단위)
    color_name = Column(String)
    model_year = Column(Integer)
    first_registration_date = Column(Integer)
    distance = Column(Integer)
    price = Column(Integer)
    origin_price = Column(Integer)
    sell_type = Column(String)
    location = Column(String) 
    detail_url = Column(String)
    photo = Column(String)
    has_options = Column(Boolean, default=None)  # NULL: 미확인, TRUE: 옵션 있음, FALSE: 옵션 없음

#옵션 사전
class OptionMaster(Base):
    __tablename__ = 'option_masters'
    
    option_master_id = Column(Integer, primary_key=True, autoincrement=True)
    option_code = Column(String(50), unique=True, nullable=False)  # 'SUNROOF', 'LDWS' 등
    option_name = Column(String(100), nullable=False)  # '선루프', '차선이탈경고' 등
    option_group = Column(String(50), nullable=False)  # '외관/내장', '안전' 등
    description = Column(Text)  # 옵션 설명
    
    # 인덱스
    __table_args__ = (
        Index('idx_option_code', 'option_code'),
        Index('idx_option_group', 'option_group'),
        Index('idx_option_name', 'option_name'),
    )

#차량 옵션
class VehicleOption(Base):
    __tablename__ = 'vehicle_options'
    
    vehicle_option_id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey('vehicles.vehicle_id'), nullable=False)
    option_master_id = Column(Integer, ForeignKey('option_masters.option_master_id'), nullable=False)
    
    # 인덱스
    __table_args__ = (
        UniqueConstraint('vehicle_id', 'option_master_id', name='uq_vehicle_option'),
        Index('idx_vehicle_option', 'vehicle_id', 'option_master_id'),
    )

# 보험 이력 (일반화된 구조)
class InsuranceHistory(Base):
    __tablename__ = 'insurance_history'
    
    insurance_id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey('vehicles.vehicle_id'), nullable=False)
    platform = Column(String, nullable=False)  # 'encar' 또는 'chacha'
    
    
    # 사고 이력 요약
    my_accident_cnt = Column(Integer, default=0)  # 내차 피해 횟수
    other_accident_cnt = Column(Integer, default=0)  # 상대차 피해 횟수
    my_accident_cost = Column(Integer, default=0)  # 내차 피해 금액
    other_accident_cost = Column(Integer, default=0)  # 상대차 피해 금액
    total_accident_cnt = Column(Integer, default=0)  # 총 사고 횟수
    
    # 특수 사고 이력
    total_loss_cnt = Column(Integer, default=0)  # 전손 횟수
    total_loss_date = Column(String)  # 전손일
    robber_cnt = Column(Integer, default=0)  # 도난 횟수
    robber_date = Column(String)  # 도난일
    flood_total_loss_cnt = Column(Integer, default=0)  # 침수 전손 횟수
    flood_part_loss_cnt = Column(Integer, default=0)  # 침수 부분손 횟수
    flood_date = Column(String)  # 침수일
    
    # 기타 이력
    owner_change_cnt = Column(Integer, default=0)  # 소유자 변경 횟수
    car_no_change_cnt = Column(Integer, default=0)  # 차량번호 변경 횟수
    
    # 특수 용도 이력 (0: 없음, 1: 있음)
    government = Column(Integer, default=0)  # 관용용도
    business = Column(Integer, default=0)  # 영업용도
    rental = Column(Integer, default=0)  # 대여용도(렌터카)
    loan = Column(Integer, default=0)  # 대출/저당
    
    # 미가입 기간 (쉼표로 구분된 문자열)
    not_join_periods = Column(String)  # 미가입 기간들 (예: "202106~202505, 202301~202303")
    
    __table_args__ = (
        Index('idx_insurance_history_vehicle_id', 'vehicle_id'),
        Index('idx_insurance_history_platform', 'platform'),
        UniqueConstraint('vehicle_id', 'platform', name='uq_insurance_history_vehicle_platform'),
    )

# 공통 열거형
GoodBad = Enum('GOOD','BAD', name='goodbad')               # 양호/불량
Leak3 = Enum('NONE','MINOR','LEAK', name='leak3')        # 없음/미세/누유(누수)
Adeq3 = Enum('ADEQ','LACK','OVER', name='adeq3')         # 적정/부족/과다
DetailType = Enum('INNER', 'OUTER', name='detail_type')    # 검사 항목/외판 구분
PanelRank = Enum('OUTER_1','OUTER_2','STRUCT_A','STRUCT_B','STRUCT_C', name='panel_rank')  # 외판/골격 랭크

class Inspection(Base):
    """차량 성능/상태 점검 요약 (엔카 + 차차차 공통)"""
    __tablename__ = 'inspections'
    inspection_id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey('vehicles.vehicle_id', ondelete='CASCADE'))
    platform = Column(String(16), nullable=False)
    
    # 검사 메타정보
    inspected_at = Column(String(8))         # 검사일 (YYYYMMDD)
    valid_from = Column(String(8))           # 유효기간 시작
    valid_to = Column(String(8))             # 유효기간 종료
    mileage_at_inspect = Column(Integer)     # 검사 당시 주행거리
    
    # 요약 플래그 (공통)
    accident_history = Column(Boolean)       # 사고이력 유무
    simple_repair = Column(Boolean)          # 단순수리 유무
    waterlog = Column(Boolean)               # 침수 유무
    fire_history = Column(Boolean)           # 화재 유무
    tuning_exist = Column(Boolean)           # 튜닝 유무
    recall_applicable = Column(Boolean)      # 리콜 대상 유무
    recall_fulfilled = Column(Boolean)       # 리콜 이행 완료 여부
    
    # 주요 점검 결과
    engine_check_ok = Column(Boolean)        # 엔진(원동기) 양호
    trans_check_ok = Column(Boolean)         # 변속기 양호
    
    # 보증 유형 (공통화)
    guaranty_type = Column(String(32))       # 'SELF', 'INSURANCE' 등
    
    # 기타
    image_front = Column(Text)               # 앞면 이미지 URL
    image_rear = Column(Text)                # 뒷면 이미지 URL
    remarks = Column(Text)                   # 특기사항/점검자 의견
    
    __table_args__ = (
        Index('idx_inspection_vehicle', 'vehicle_id'),
        Index('idx_inspection_date', 'inspected_at'),
    )

class InspectionDetail(Base):
    """검사 세부 항목 (검사 항목 + 외판/골격 통합)"""
    __tablename__ = 'inspection_details'
    
    inspection_detail_id = Column(Integer, primary_key=True, autoincrement=True)
    inspection_id = Column(Integer, ForeignKey('inspections.inspection_id', ondelete='CASCADE'), nullable=False)
    
    # 항목 유형 구분
    detail_type = Column(DetailType, nullable=False)
    
    # 계층 정보 (공통)
    group_code = Column(String(8), nullable=False)    # S01(원동기), P0(외판) 등
    group_title = Column(String(32), nullable=False)  # 원동기, 외판 등
    item_code = Column(String(32), nullable=False)    # engine_idle_state, front_fender 등
    item_title = Column(String(64), nullable=False)   # 실린더 커버, 프론트 휀더 등
    
    # === INNER 전용: 일반화 상태 (해당하는 것만 채움) ===
    good_bad = Column(GoodBad)                        # 양호/불량
    leak_level = Column(Leak3)                        # 없음/미세/누유
    level_state = Column(Adeq3)                       # 적정/부족/과다
    
    # === OUTER 전용: 외판/골격 정보 ===
    rank = Column(PanelRank)
    exchanged = Column(Boolean, default=False)        # X: 교환
    welded = Column(Boolean, default=False)           # W: 판금/용접
    scratched = Column(Boolean, default=False)        # A: 흠집
    uneven = Column(Boolean, default=False)           # U: 요철
    corroded = Column(Boolean, default=False)         # C: 부식
    damaged = Column(Boolean, default=False)          # T: 손상
    
    note = Column(String(256))                        # 메모
    
    __table_args__ = (
        Index('idx_detail_inspection', 'inspection_id'),
        Index('idx_detail_type', 'inspection_id', 'detail_type'),
        Index('idx_detail_item', 'inspection_id', 'item_code'),
        Index('idx_detail_group', 'inspection_id', 'group_code'),
    )


class GetchaReview(Base):
    """Getcha 자동차 오너 리뷰 테이블"""
    __tablename__ = 'getcha_reviews'
    
    review_id = Column(Integer, primary_key=True, autoincrement=True)
    id_contents = Column(Integer, unique=True, nullable=False)  # getcha 게시물 ID (중복 방지용)
    
    # 기본 리뷰 정보
    title = Column(String(500), nullable=False)
    created = Column(String(20))  # YYYY-MM-DDTHH:MM:SS 형식
    
    # 차량 정보 (다른 테이블과 명칭 통일)
    manufacturer = Column(String(50))  # 제조사 (현대, 기아, BMW 등)
    model_group = Column(String(100))  # 모델그룹 (EV4, 그랜저, GV70 등)
    grade = Column(String(100))  # 등급 (롱레인지 어스, 시그니처 등)
    model_year = Column(Integer)  # 연식
    price = Column(Integer)  # 최종 거래가
    
    # 평가 항목별 평점 (1.0 ~ 5.0)
    rating_total = Column(Float)  # 총점
    rating_design = Column(Float)  # 디자인
    rating_performance = Column(Float)  # 성능
    rating_option = Column(Float)  # 옵션
    rating_maintenance = Column(Float)  # 유지관리
    
    # 평가 항목별 코멘트
    comment_total = Column(Text)  # 총평
    comment_design = Column(Text)  # 디자인 코멘트
    comment_performance = Column(Text)  # 성능 코멘트
    comment_option = Column(Text)  # 옵션 코멘트
    comment_maintenance = Column(Text)  # 유지관리 코멘트
    
    # 크롤링 메타 정보
    crawled_at = Column(DateTime)
    
    __table_args__ = (
        Index('idx_getcha_review_contents_id', 'id_contents'),
        Index('idx_getcha_review_manufacturer', 'manufacturer'),
        Index('idx_getcha_review_model', 'model_group'),
        Index('idx_getcha_review_year', 'model_year'),
        Index('idx_getcha_review_created', 'created'),
        Index('idx_getcha_review_rating', 'rating_total'),
    )

# =============================================================================
# DB 관리 함수들
# =============================================================================

def create_tables_if_not_exist():
    """테이블이 없으면 생성합니다."""
    try:
        print("[DB 테이블 확인 중...]")
        Base.metadata.create_all(Engine)
        print("[DB 테이블 생성 완료] 모든 테이블이 준비되었습니다.")
    except Exception as e:
        print(f"[DB 테이블 생성 실패] {e}")
        raise

def check_database_status():
    """데이터베이스 상태를 확인합니다."""
    try:
        with session_scope() as session:
            # Vehicle 테이블 확인
            vehicle_count = session.query(Vehicle).count()
            print(f"[DB 상태] Vehicle 테이블: {vehicle_count:,}건")
            
            # OptionMaster 테이블 확인
            option_master_count = session.query(OptionMaster).count()
            print(f"[DB 상태] OptionMaster 테이블: {option_master_count:,}건")
            
            # VehicleOption 테이블 확인
            vehicle_option_count = session.query(VehicleOption).count()
            print(f"[DB 상태] VehicleOption 테이블: {vehicle_option_count:,}건")
            
            # InsuranceHistory 테이블 확인
            insurance_history_count = session.query(InsuranceHistory).count()
            print(f"[DB 상태] InsuranceHistory 테이블: {insurance_history_count:,}건")
            
            # Inspection 테이블 확인
            inspection_count = session.query(Inspection).count()
            print(f"[DB 상태] Inspection 테이블: {inspection_count:,}건")
            
            # GetchaReview 테이블 확인
            getcha_review_count = session.query(GetchaReview).count()
            print(f"[DB 상태] GetchaReview 테이블: {getcha_review_count:,}건")
            
            return {
                'vehicle_count': vehicle_count,
                'option_master_count': option_master_count,
                'vehicle_option_count': vehicle_option_count,
                'insurance_history_count': insurance_history_count,
                'inspection_count': inspection_count,
                'getcha_review_count': getcha_review_count
            }
    except Exception as e:
        print(f"[DB 상태 확인 실패] {e}")
        return None

