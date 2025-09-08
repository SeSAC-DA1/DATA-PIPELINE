from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# 설정 파일에서 Supabase 클라이언트를 가져옵니다.
from backend.core.config import supabase_client

# 이 파일의 API 엔드포인트들을 위한 라우터를 생성합니다.
router = APIRouter()

# --- Pydantic Models ---
# request body나 response body의 데이터 타입을 정의합니다.
class UserCreate(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    created_at: str

# --- API Endpoints ---

@router.post("/users", response_model=UserResponse, tags=["Users"])
async def create_user(user: UserCreate):
    """
    새로운 사용자를 생성합니다.
    - **email**: 사용자 이메일
    - **password**: 사용자 비밀번호 (주의: 현재 해싱되지 않음)
    """
    try:
        response = supabase_client.table('users').insert({
            "email": user.email,
            "password": user.password # 중요: 실제 앱에서는 반드시 해싱해야 합니다.
        }).execute()

        if response.data and len(response.data) > 0:
            created_user = response.data[0]
            return UserResponse(
                id=created_user['id'],
                email=created_user['email'],
                created_at=created_user['created_at']
            )
        raise HTTPException(status_code=500, detail="User creation failed unexpectedly.")

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/users", response_model=List[UserResponse], tags=["Users"])
async def get_users():
    """
    모든 사용자 목록을 조회합니다.
    """
    try:
        response = supabase_client.table('users').select("id, email, created_at").execute()
        return response.data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
