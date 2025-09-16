"""
CarFin AI Backend - FastAPI 애플리케이션 메인 모듈
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from .api.router import api_router
from .core.config import settings, supabase_client
from .database.connection import get_database_session, close_database_connections

# FastAPI 애플리케이션을 생성합니다.
app = FastAPI(
    title=settings.project_name,
    description="CarFin AI 서비스의 백엔드 API - PostgreSQL 기반",
    version="1.0.0",
    debug=settings.debug
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 포함
app.include_router(api_router, prefix=settings.api_v1_str)

@app.get("/health", tags=["Health"])
async def health_check(
    db: AsyncSession = Depends(get_database_session)
):
    """
    서버 상태 및 데이터베이스 연결 확인
    """
    try:
        # PostgreSQL 연결 확인
        await db.execute(text("SELECT 1"))
        postgres_status = "Connected"
    except Exception as e:
        postgres_status = f"Failed: {str(e)}"
    
    
    # Supabase Auth 상태 확인
    supabase_status = "Connected" if supabase_client else "Not configured"
    
    return {
        "status": "ok",
        "environment": settings.environment,
        "databases": {
            "postgresql": postgres_status,
            "supabase_auth": supabase_status
        }
    }

@app.get("/", tags=["Root"])
def read_root():
    """
    루트 엔드포인트
    """
    return {
        "message": "CarFin AI Backend API",
        "version": "1.0.0",
        "environment": settings.environment,
        "docs": "/docs"
    }

@app.on_event("shutdown")
async def shutdown_event():
    """
    애플리케이션 종료시 리소스 정리
    """
    await close_database_connections()
