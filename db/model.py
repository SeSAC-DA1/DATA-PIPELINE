from sqlalchemy import Column, String, Integer, ForeignKey, Index, UniqueConstraint, Text, Boolean, DateTime, JSON, Enum, SmallInteger
from sqlalchemy.ext.declarative import declarative_base
from .connection import session_scope, Engine

Base = declarative_base()

class Vehicle(Base):
    __tablename__ = 'vehicles'
    
    vehicle_id = Column(Integer, primary_key=True, autoincrement=True)
    car_seq = Column(Integer, nullable=False)
    vehicle_no = Column(String, nullable=False, unique=True)
    platform = Column(String)
    origin = Column(String)
    car_type = Column(String)
    manufacturer = Column(String)
    model = Column(String)
    generation = Column(String)
    trim = Column(String)
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

class OptionMaster(Base):
    __tablename__ = 'option_masters'
    
    option_id = Column(Integer, primary_key=True, autoincrement=True)
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

class VehicleOption(Base):
    __tablename__ = 'vehicle_options'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey('vehicles.vehicle_id'), nullable=False)
    option_id = Column(Integer, ForeignKey('option_masters.option_id'), nullable=False)
    
    # 인덱스
    __table_args__ = (
        UniqueConstraint('vehicle_id', 'option_id', name='uq_vehicle_option'),
        Index('idx_vehicle_option', 'vehicle_id', 'option_id'),
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
Leak3 = Enum('NONE','MINOR','LEAK', name='leak3')        # 없음/미세/누유(누수)
GoodBad = Enum('GOOD','BAD', name='goodbad')               # 양호/불량
Adeq3 = Enum('ADEQ','LACK','OVER', name='adeq3')         # 적정/부족/과다
YesNo = Enum('NO','YES', name='yesno')                   # 없음/있음
TuningOK = Enum('LEGAL','ILLEGAL', name='tuning_ok')
TuningTyp = Enum('STRUCTURE','DEVICE','NONE','UNKNOWN', name='tuning_type')

class Inspection(Base):
    """차량 성능/상태 점검 요약"""
    __tablename__ = 'inspections'

    vehicle_id = Column(Integer, ForeignKey('vehicles.vehicle_id', ondelete='CASCADE'), primary_key=True)
    platform = Column(String(16), nullable=False)
    
    # 검사 메타정보
    source_record_no = Column(String(64))    # master.detail.recordNo
    supply_num = Column(String(64))          # master.supplyNum
    inspected_at = Column(String(8))         # detail.issueDate (YYYYMMDD)
    valid_from = Column(String(8))           # detail.validityStartDate
    valid_to = Column(String(8))             # detail.validityEndDate
    mileage_at_inspect = Column(Integer)     # detail.mileage
    
    # 요약 플래그
    accident_history = Column(Boolean)       # master.accdient
    simple_repair = Column(Boolean)          # master.simpleRepair
    waterlog = Column(Boolean)               # detail.waterlog
    fire_history = Column(Boolean)           # (차차차)
    tuning_exist = Column(Boolean)           # detail.tuning
    recall_applicable = Column(Boolean)      # detail.recall
    
    # 전반 상태
    engine_check_ok = Column(Boolean)        # detail.engineCheck=='Y'
    trans_check_ok = Column(Boolean)         # detail.trnsCheck=='Y'
    car_state_code = Column(String(8))       # carStateType.code
    car_state_title = Column(String(32))     # carStateType.title
    board_state_code = Column(String(8))     # boardStateType.code
    board_state_title = Column(String(32))   # boardStateType.title
    guaranty_code = Column(String(8))        # guarantyType.code
    guaranty_title = Column(String(32))      # guarantyType.title
    
    # 외판/골격 카운트
    outer_1 = Column(SmallInteger, default=0)
    outer_2 = Column(SmallInteger, default=0)
    struct_a = Column(SmallInteger, default=0)
    struct_b = Column(SmallInteger, default=0)
    struct_c = Column(SmallInteger, default=0)
    
    # 기타
    images = Column(Text)                    # 이미지 URL (쉼표 구분)
    remarks = Column(Text)                   # detail.comments
    
    __table_args__ = (
        Index('idx_inspection_vehicle', 'vehicle_id'),
        Index('idx_inspection_date', 'inspected_at'),
    )

class InspectionDetail(Base):
    """검사 세부 항목 (검사 항목 + 외판/골격 통합)"""
    __tablename__ = 'inspection_details'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey('vehicles.vehicle_id', ondelete='CASCADE'), nullable=False)
    
    # 항목 유형 구분
    detail_type = Column(Enum('ITEM', 'PANEL', name='detail_type'), nullable=False)
    
    # 계층 정보 (공통)
    group_code = Column(String(8), nullable=False)    # S01(원동기), P0(외판) 등
    group_title = Column(String(32), nullable=False)  # 원동기, 외판 등
    item_code = Column(String(16), nullable=False)    # s004, p022 등
    item_title = Column(String(64), nullable=False)   # 실린더 커버, 프론트 휀더 등
    parent_code = Column(String(16))                  # 부모 코드
    parent_title = Column(String(64))                 # 부모 이름
    
    # 원본 상태 보존 (공통)
    status_code = Column(String(8))                   # 1, 3, 6, X 등
    status_title = Column(String(32))                 # 양호, 미세누유, 교환 등
    
    # === ITEM 전용: 일반화 상태 (해당하는 것만 채움) ===
    good_bad = Column(GoodBad)                        # 양호/불량
    leak_level = Column(Leak3)                        # 없음/미세/누유
    level_state = Column(Adeq3)                       # 적정/부족/과다
    
    # === PANEL 전용: 외판/골격 정보 ===
    rank = Column(Enum('OUTER_1','OUTER_2','STRUCT_A','STRUCT_B','STRUCT_C', name='panel_rank'))
    exchanged = Column(Boolean, default=False)        # X: 교환
    welded = Column(Boolean, default=False)           # W: 판금/용접
    scratched = Column(Boolean, default=False)        # A: 흠집
    uneven = Column(Boolean, default=False)           # U: 요철
    corroded = Column(Boolean, default=False)         # C: 부식
    damaged = Column(Boolean, default=False)          # T: 손상
    
    note = Column(String(256))                        # 메모
    
    __table_args__ = (
        Index('idx_detail_vehicle', 'vehicle_id'),
        Index('idx_detail_type', 'vehicle_id', 'detail_type'),
        Index('idx_detail_item', 'vehicle_id', 'item_code'),
        Index('idx_detail_group', 'vehicle_id', 'group_code'),
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
            
            return {
                'vehicle_count': vehicle_count,
                'option_master_count': option_master_count,
                'vehicle_option_count': vehicle_option_count,
                'insurance_history_count': insurance_history_count,
                'inspection_count': inspection_count
            }
    except Exception as e:
        print(f"[DB 상태 확인 실패] {e}")
        return None

