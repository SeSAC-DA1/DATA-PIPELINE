from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# 설정 파일에서 Supabase 클라이언트를 가져옵니다.
from ...core.config import supabase_client

# 이 파일의 API 엔드포인트들을 위한 라우터를 생성합니다.
router = APIRouter()

# --- Pydantic Models ---
class UserResponse(BaseModel):
    id: str
    email: str
    created_at: str

@router.get("/users", response_model=List[UserResponse], tags=["Users"])
async def get_users():
    """
    모든 사용자 목록을 조회합니다.
    참고: 실제 프로덕션 환경에서는 이 엔드포인트를 관리자만 접근할 수 있도록 보호해야 합니다.
    """
    try:
        response = supabase_client.table('users').select("id, email, created_at").execute()
        return response.data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")