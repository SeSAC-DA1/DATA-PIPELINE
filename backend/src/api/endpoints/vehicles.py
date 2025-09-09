"""
차량 관련 API 엔드포인트
크롤링팀과 연동하여 차량 데이터를 관리합니다.
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from pydantic import BaseModel

from ..database.connection import get_database_session
from ..database.models import Vehicle

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
    id: UUID
    source: Optional[str]
    make: Optional[str]
    model: Optional[str]
    year: Optional[int]
    mileage: Optional[int]
    price: Optional[int]
    details: Optional[dict]
    risk_score: Optional[float]
    tco: Optional[int]
    created_at: str
    
    class Config:
        from_attributes = True

class VehicleSearch(BaseModel):
    """차량 검색 스키마"""
    make: Optional[str] = None
    model: Optional[str] = None
    min_year: Optional[int] = None
    max_year: Optional[int] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    max_mileage: Optional[int] = None

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