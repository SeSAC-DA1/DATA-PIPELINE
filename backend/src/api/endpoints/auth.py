from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from ...core.config import supabase_client

router = APIRouter()

class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: dict

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/auth/login", response_model=AuthResponse, tags=["Authentication"])
async def login(credentials: LoginRequest):
    """
    이메일/비밀번호로 로그인합니다.
    """
    try:
        response = supabase_client.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        
        if response.user:
            return AuthResponse(
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
                user=response.user.model_dump()
            )
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



@router.post("/auth/logout", tags=["Authentication"])
async def logout():
    """
    로그아웃을 처리합니다.
    """
    try:
        response = supabase_client.auth.sign_out()
        return {"message": "Successfully logged out"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/auth/me", tags=["Authentication"])
async def get_current_user(authorization: Optional[str] = None):
    """
    현재 로그인한 사용자 정보를 가져옵니다.
    Header: Authorization: Bearer <access_token>
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    try:
        # Bearer 토큰 추출
        token = authorization.replace("Bearer ", "")
        
        # 사용자 정보 조회
        response = supabase_client.auth.get_user(token)
        
        if response.user:
            return {"user": response.user.model_dump()}
        raise HTTPException(status_code=401, detail="Invalid token")
        
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))