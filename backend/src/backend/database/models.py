"""
데이터베이스 모델 정의
SQLAlchemy ORM 모델들
"""

import uuid
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey, Index, Date, SmallInteger, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .connection import Base

class User(Base):
    """사용자 정보 테이블 (Supabase Auth와 동기화)"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    user_profile = Column(JSONB, nullable=True)  # 라이프스타일, 선호도, 예산 등
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 관계 설정
    recommendations = relationship("Recommendation", back_populates="user", cascade="all, delete-orphan")
    matches = relationship("Match", back_populates="user", cascade="all, delete-orphan")

class Vehicle(Base):
    """차량 매물 정보 테이블"""
    __tablename__ = "vehicles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String, nullable=True)  # 데이터 출처 (예: '엔카')
    make = Column(String, nullable=True)  # 제조사
    model = Column(String, nullable=True)  # 모델명
    year = Column(Integer, nullable=True)  # 연식
    mileage = Column(Integer, nullable=True)  # 주행거리 (km)
    price = Column(Integer, nullable=True)  # 판매 가격 (만원)
    details = Column(JSONB, nullable=True)  # 사고이력, 옵션, 색상 등
    risk_score = Column(Float, nullable=True)  # AI 리스크 점수
    tco = Column(Integer, nullable=True)  # 5년 총소유비용
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 관계 설정
    recommendations = relationship("Recommendation", back_populates="vehicle")
    
    # 인덱스 설정 (성능 최적화)
    __table_args__ = (
        Index('idx_vehicles_make_model', 'make', 'model'),
        Index('idx_vehicles_price_year', 'price', 'year'),
        Index('idx_vehicles_created_at', 'created_at'),
    )

class FinancialProduct(Base):
    """금융 상품 정보 테이블"""
    __tablename__ = "financial_products"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company = Column(String, nullable=True)  # 금융사 이름
    product_name = Column(String, nullable=True)  # 상품명
    product_type = Column(String, nullable=True)  # '대출' 또는 '보험'
    details = Column(JSONB, nullable=True)  # 이자율, 한도, 조건 등
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계 설정
    matches = relationship("Match", back_populates="product")
    rates = relationship("LoanRate", back_populates="product", cascade="all, delete-orphan")

class Recommendation(Base):
    """개인화 추천 결과 테이블"""
    __tablename__ = "recommendations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey('vehicles.id'), nullable=False)
    score = Column(Float, nullable=True)  # AI 추천 점수
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계 설정
    user = relationship("User", back_populates="recommendations")
    vehicle = relationship("Vehicle", back_populates="recommendations")

class Match(Base):
    """금융 상품 매칭 결과 테이블"""
    __tablename__ = "matches"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey('financial_products.id'), nullable=False)
    conditions = Column(JSONB, nullable=True)  # 맞춤 조건
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계 설정
    user = relationship("User", back_populates="matches")
    product = relationship("FinancialProduct", back_populates="matches")

class LoanRate(Base):
    """기간별 대출 금리 정보 테이블"""
    __tablename__ = "loan_rates"

    product_id = Column(UUID(as_uuid=True), ForeignKey('financial_products.id'), primary_key=True)
    effective_date = Column(Date, primary_key=True)
    term_months = Column(SmallInteger, primary_key=True)
    base_rate = Column(Numeric(5, 2), nullable=False)
    spread_rate = Column(Numeric(5, 2), nullable=False)
    pref_rate = Column(Numeric(5, 2), nullable=False)
    min_rate = Column(Numeric(5, 2), nullable=False)
    max_rate = Column(Numeric(5, 2), nullable=False)
    source_url = Column(String(255), nullable=True)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("FinancialProduct", back_populates="rates")

    __table_args__ = (
        Index('idx_loan_rates_date', 'effective_date'),
    )