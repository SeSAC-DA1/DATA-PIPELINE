"""
PostgreSQL 데이터베이스 연결 관리
SQLAlchemy를 사용한 비동기 데이터베이스 연결
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from typing import AsyncGenerator
from ..core.config import settings

# SQLAlchemy 설정
engine = create_async_engine(
    settings.database_url,
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

async def close_database_connections():
    """
    데이터베이스 연결을 정리하는 함수
    """
    await engine.dispose()