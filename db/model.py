from sqlalchemy import Column, String, Integer, ForeignKey, Index, UniqueConstraint, Text, Boolean
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
            
            return {
                'vehicle_count': vehicle_count,
                'option_master_count': option_master_count,
                'vehicle_option_count': vehicle_option_count
            }
    except Exception as e:
        print(f"[DB 상태 확인 실패] {e}")
        return None

