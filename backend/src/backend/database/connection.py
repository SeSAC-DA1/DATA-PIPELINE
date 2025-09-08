"""
PostgreSQL 데이터베이스 연결 관리
SQLAlchemy를 사용한 비동기 데이터베이스 연결
"""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import redis.asyncio as redis
from typing import AsyncGenerator

# 데이터베이스 URL 설정
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://carfin_admin:carfin_secure_password_2025@localhost:5432/carfin"
)

# Redis URL 설정
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# SQLAlchemy 설정
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # 운영환경에서는 False
    pool_size=20,
    max_overflow=0,
    pool_pre_ping=True,
    pool_recycle=300,
)

# 비동기 세션 팩토리
AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Base 모델 클래스
Base = declarative_base()

# Redis 클라이언트
redis_client = None

async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """
    데이터베이스 세션을 반환하는 의존성 주입 함수
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def get_redis_client():
    """
    Redis 클라이언트를 반환하는 함수
    """
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return redis_client

async def close_database_connections():
    """
    모든 데이터베이스 연결을 정리하는 함수
    """
    global redis_client
    if redis_client:
        await redis_client.close()
    await engine.dispose()