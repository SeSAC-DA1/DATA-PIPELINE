"""
차량 관련 API 엔드포인트
크롤링팀과 연동하여 차량 데이터를 관리합니다.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from pydantic import BaseModel, Field, ConfigDict

from ...database.connection import get_database_session
from ...database.models import Vehicle

router = APIRouter()

# Pydantic 모델 정의
class VehicleCreate(BaseModel):
    """차량 데이터 생성 스키마"""
    source: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    mileage: Optional[int] = None
    price: Optional[int] = None
    details: Optional[dict] = None
    risk_score: Optional[float] = None
    tco: Optional[int] = None

class VehicleResponse(BaseModel):
    """차량 데이터 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    source: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    mileage: Optional[int] = None
    price: Optional[int] = None
    details: Optional[dict] = None
    risk_score: Optional[float] = None
    tco: Optional[int] = None

class VehicleSearch(BaseModel):
    """차량 검색 스키마"""
    make: Optional[str] = None
    model: Optional[str] = None
    min_year: Optional[int] = None
    max_year: Optional[int] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    max_mileage: Optional[int] = None

class UserVehicleSearch(BaseModel):
    """사용자 친화적 차량 검색 스키마"""
    budget: Optional[int] = None  # 예산 (만원)
    fuelType: Optional[str] = None  # 연료 타입
    purpose: Optional[str] = None  # 사용 목적
    location: Optional[str] = None  # 지역
    preferences: Optional[list] = None  # 선호사항 배열

@router.post("/vehicles", response_model=VehicleResponse)
async def create_vehicle(
    vehicle_data: VehicleCreate,
    db: AsyncSession = Depends(get_database_session)
):
    """
    새로운 차량 데이터 생성 (크롤링팀용)
    """
    try:
        vehicle = Vehicle(**vehicle_data.dict())
        db.add(vehicle)
        await db.commit()
        await db.refresh(vehicle)
        return vehicle
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"차량 생성 실패: {str(e)}")

@router.post("/vehicles/bulk", response_model=List[VehicleResponse])
async def create_vehicles_bulk(
    vehicles_data: List[VehicleCreate],
    db: AsyncSession = Depends(get_database_session)
):
    """
    대량 차량 데이터 생성 (크롤링팀용)
    """
    try:
        vehicles = [Vehicle(**vehicle_data.dict()) for vehicle_data in vehicles_data]
        db.add_all(vehicles)
        await db.commit()
        
        # 생성된 차량들을 다시 조회
        for vehicle in vehicles:
            await db.refresh(vehicle)
        
        return vehicles
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"대량 차량 생성 실패: {str(e)}")

@router.get("/vehicles", response_model=List[VehicleResponse])
async def get_vehicles(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    make: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    min_price: Optional[int] = Query(None),
    max_price: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_database_session)
):
    """
    차량 목록 조회 (필터링 및 페이징)
    """
    try:
        query = select(Vehicle)
        
        # 필터 적용
        filters = []
        if make:
            filters.append(Vehicle.make.ilike(f"%{make}%"))
        if model:
            filters.append(Vehicle.model.ilike(f"%{model}%"))
        if min_price:
            filters.append(Vehicle.price >= min_price)
        if max_price:
            filters.append(Vehicle.price <= max_price)
        
        if filters:
            query = query.where(and_(*filters))
        
        query = query.offset(skip).limit(limit).order_by(Vehicle.created_at.desc())
        result = await db.execute(query)
        vehicles = result.scalars().all()
        
        return vehicles
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"차량 조회 실패: {str(e)}")

@router.get("/vehicles/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(
    vehicle_id: UUID,
    db: AsyncSession = Depends(get_database_session)
):
    """
    특정 차량 상세 조회
    """
    try:
        query = select(Vehicle).where(Vehicle.id == vehicle_id)
        result = await db.execute(query)
        vehicle = result.scalar_one_or_none()
        
        if not vehicle:
            raise HTTPException(status_code=404, detail="차량을 찾을 수 없습니다.")
        
        return vehicle
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"차량 조회 실패: {str(e)}")

@router.post("/vehicles/search", response_model=List[VehicleResponse])
async def search_vehicles(
    search_params: VehicleSearch,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_database_session)
):
    """
    고급 차량 검색
    """
    try:
        query = select(Vehicle)
        
        # 검색 조건 적용
        filters = []
        if search_params.make:
            filters.append(Vehicle.make.ilike(f"%{search_params.make}%"))
        if search_params.model:
            filters.append(Vehicle.model.ilike(f"%{search_params.model}%"))
        if search_params.min_year:
            filters.append(Vehicle.year >= search_params.min_year)
        if search_params.max_year:
            filters.append(Vehicle.year <= search_params.max_year)
        if search_params.min_price:
            filters.append(Vehicle.price >= search_params.min_price)
        if search_params.max_price:
            filters.append(Vehicle.price <= search_params.max_price)
        if search_params.max_mileage:
            filters.append(Vehicle.mileage <= search_params.max_mileage)
        
        if filters:
            query = query.where(and_(*filters))
        
        query = query.offset(skip).limit(limit).order_by(Vehicle.created_at.desc())
        result = await db.execute(query)
        vehicles = result.scalars().all()
        
        return vehicles
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"차량 검색 실패: {str(e)}")

@router.post("/vehicles/search/user", response_model=List[VehicleResponse])
async def search_vehicles_by_user_profile(
    search_params: UserVehicleSearch,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_database_session)
):
    """
    사용자 프로필 기반 차량 검색 (3-agent system용)
    """
    try:
        query = select(Vehicle)
        filters = []

        # 예산 기반 가격 필터
        if search_params.budget:
            max_budget = int(search_params.budget * 1.1)  # 10% 여유
            min_budget = int(search_params.budget * 0.7)  # 30% 할인 고려
            filters.append(Vehicle.price.between(min_budget, max_budget))

        # 연료 타입 필터 (details JSONB 컬럼 활용)
        if search_params.fuelType:
            if search_params.fuelType in ['가솔린', 'gasoline']:
                filters.append(Vehicle.details['fuel_type'].astext.ilike('%gasoline%'))
            elif search_params.fuelType in ['디젤', 'diesel']:
                filters.append(Vehicle.details['fuel_type'].astext.ilike('%diesel%'))
            elif search_params.fuelType in ['하이브리드', 'hybrid']:
                filters.append(Vehicle.details['fuel_type'].astext.ilike('%hybrid%'))
            elif search_params.fuelType in ['전기차', 'electric']:
                filters.append(Vehicle.details['fuel_type'].astext.ilike('%electric%'))

        # 사용 목적에 따른 차량 타입 매핑
        if search_params.purpose:
            if search_params.purpose in ['출퇴근', 'commute', '시내운전']:
                # 소형차, 경차 우선
                filters.append(or_(
                    Vehicle.details['category'].astext.ilike('%compact%'),
                    Vehicle.details['category'].astext.ilike('%sedan%')
                ))
            elif search_params.purpose in ['가족여행', 'family', '대가족']:
                # SUV, MPV 우선
                filters.append(or_(
                    Vehicle.details['category'].astext.ilike('%suv%'),
                    Vehicle.details['category'].astext.ilike('%mpv%')
                ))
            elif search_params.purpose in ['레저', 'leisure', '캠핑']:
                # SUV, 픽업트럭 우선
                filters.append(or_(
                    Vehicle.details['category'].astext.ilike('%suv%'),
                    Vehicle.details['category'].astext.ilike('%pickup%')
                ))

        # 선호사항 처리
        if search_params.preferences:
            preference_filters = []
            for pref in search_params.preferences:
                if pref in ['저연비', 'fuel_efficient']:
                    preference_filters.append(Vehicle.details['fuel_efficiency'].astext.cast(Float) > 10.0)
                elif pref in ['안전성', 'safety']:
                    preference_filters.append(Vehicle.details['safety_rating'].astext.cast(Float) >= 4.0)
                elif pref in ['럭셔리', 'luxury']:
                    preference_filters.append(Vehicle.details['luxury_features'].astext != 'null')
                elif pref in ['스포츠', 'sports']:
                    preference_filters.append(Vehicle.details['performance'].astext != 'null')

            if preference_filters:
                filters.append(or_(*preference_filters))

        # 기본 품질 필터 (사고이력, 침수이력 제외)
        filters.append(or_(
            Vehicle.details['accident_history'].astext == 'false',
            Vehicle.details['accident_history'].astext.is_(None)
        ))
        filters.append(or_(
            Vehicle.details['flood_history'].astext == 'false',
            Vehicle.details['flood_history'].astext.is_(None)
        ))

        if filters:
            query = query.where(and_(*filters))

        # 리스크 스코어 기준 정렬 (낮을수록 좋음), 가격 순
        query = query.order_by(Vehicle.risk_score.asc().nulls_last(), Vehicle.price.asc())
        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        vehicles = result.scalars().all()

        return vehicles

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"사용자 기반 차량 검색 실패: {str(e)}")

@router.delete("/vehicles/{vehicle_id}")
async def delete_vehicle(
    vehicle_id: UUID,
    db: AsyncSession = Depends(get_database_session)
):
    """
    차량 삭제
    """
    try:
        query = select(Vehicle).where(Vehicle.id == vehicle_id)
        result = await db.execute(query)
        vehicle = result.scalar_one_or_none()
        
        if not vehicle:
            raise HTTPException(status_code=404, detail="차량을 찾을 수 없습니다.")
        
        await db.delete(vehicle)
        await db.commit()
        
        return {"message": "차량이 성공적으로 삭제되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"차량 삭제 실패: {str(e)}")