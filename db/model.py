from sqlalchemy import Column, String, Integer, ForeignKey, Index, UniqueConstraint, Text, Boolean, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from .connection import session_scope, Engine

Base = declarative_base()

class Vehicle(Base):
    __tablename__ = 'vehicles'
    
    vehicleid = Column(Integer, primary_key=True, autoincrement=True)
    carseq = Column(Integer, nullable=False)
    vehicleno = Column(String, nullable=False, unique=True)
    platform = Column(String)
    origin = Column(String)
    cartype = Column(String)
    manufacturer = Column(String)
    model = Column(String)
    generation = Column(String)
    trim = Column(String)
    fueltype = Column(String)
    transmission = Column(String)
    displacement = Column(Integer)  # 배기량 (cc 단위)
    colorname = Column(String)
    modelyear = Column(Integer)
    firstregistrationdate = Column(Integer)
    distance = Column(Integer)
    price = Column(Integer)
    originprice = Column(Integer)
    selltype = Column(String)
    location = Column(String) 
    detailurl = Column(String)
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
    vehicle_id = Column(Integer, ForeignKey('vehicles.vehicleid'), nullable=False)
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
    vehicle_id = Column(Integer, ForeignKey('vehicles.vehicleid'), nullable=False)
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
            
            return {
                'vehicle_count': vehicle_count,
                'option_master_count': option_master_count,
                'vehicle_option_count': vehicle_option_count,
                'insurance_history_count': insurance_history_count
            }
    except Exception as e:
        print(f"[DB 상태 확인 실패] {e}")
        return None

