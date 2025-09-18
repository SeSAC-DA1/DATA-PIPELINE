"""
애플리케이션 설정 관리
환경 변수와 설정 클래스
"""

import os
from pydantic_settings import BaseSettings
from supabase import create_client, Client
from dotenv import load_dotenv

# .env 파일을 읽어옵니다.
load_dotenv()

class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # 데이터베이스 설정
    database_url: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://carfin_admin:carfin_secure_password_2025@postgres:5432/carfin"
    )
    
    # Supabase 설정 (인증용)
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")
    supabase_service_key: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    
    # Google OAuth 설정
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    
    # OpenAI API 설정
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    
    # API 설정
    api_v1_str: str = "/api/v1"
    project_name: str = "CarFin AI Backend"
    
    # 환경 설정
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "True").lower() == "true"
    
    # 보안 설정
    secret_key: str = os.getenv("SECRET_KEY", "carfin-secret-key-2025")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    model_config = {"env_file": ".env", "extra": "ignore"}

# 전역 설정 인스턴스
settings = Settings()

# Supabase 클라이언트 (인증용으로만 사용)
supabase_client: Client = None
if settings.supabase_url and settings.supabase_service_key:
    supabase_client = create_client(settings.supabase_url, settings.supabase_service_key)
