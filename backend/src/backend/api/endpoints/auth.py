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

@router.get("/auth/google", tags=["Authentication"])
async def google_login():
    """
    Google OAuth 로그인 URL을 수동으로 생성합니다.
    """
    try:
        import os
        from urllib.parse import urlencode
        
        google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        if not google_client_id:
            raise HTTPException(status_code=500, detail="Google Client ID가 설정되지 않았습니다")
        
        # Google OAuth URL 수동 생성
        params = {
            'client_id': google_client_id,
            'redirect_uri': 'http://localhost:8000/api/auth/google/callback',
            'scope': 'openid email profile',
            'response_type': 'code',
            'access_type': 'offline',
            'prompt': 'consent'
        }
        
        google_auth_url = f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"
        
        return {"oauth_url": google_auth_url}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth URL 생성 실패: {str(e)}")

@router.get("/auth/google/callback", tags=["Authentication"])
async def google_callback(code: str, state: str = None):
    """
    Google OAuth 콜백을 처리합니다.
    Google에서 authorization code를 받아 access token으로 교환합니다.
    """
    try:
        import requests
        import os
        
        google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        
        if not google_client_id or not google_client_secret:
            raise HTTPException(status_code=500, detail="Google OAuth 설정이 완료되지 않았습니다")
        
        # Authorization code를 access token으로 교환
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            'client_id': google_client_id,
            'client_secret': google_client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': 'http://localhost:8000/api/auth/google/callback'
        }
        
        token_response = requests.post(token_url, data=token_data)
        token_json = token_response.json()
        
        if 'access_token' not in token_json:
            raise HTTPException(status_code=400, detail="Google OAuth 토큰 교환 실패")
        
        # Google API로 사용자 정보 가져오기
        user_info_url = f"https://www.googleapis.com/oauth2/v2/userinfo?access_token={token_json['access_token']}"
        user_response = requests.get(user_info_url)
        user_data = user_response.json()
        
        # 사용자를 Supabase에 저장하거나 업데이트
        try:
            # 기존 사용자 확인
            existing_user = supabase_client.table('users').select('*').eq('email', user_data['email']).execute()
            
            if existing_user.data:
                # 기존 사용자
                user_id = existing_user.data[0]['id']
            else:
                # 새 사용자 생성
                new_user = supabase_client.table('users').insert({
                    'email': user_data['email'],
                    'password': '',  # OAuth 사용자는 비밀번호 없음
                    'user_profile': {
                        'google_id': user_data['id'],
                        'name': user_data['name'],
                        'picture': user_data['picture'],
                        'oauth_provider': 'google'
                    }
                }).execute()
                user_id = new_user.data[0]['id']
            
            # 테스트 페이지로 리디렉션 (실제 프로덕션에서는 프론트엔드 URL로 변경)
            from fastapi.responses import RedirectResponse
            
            # 성공 정보를 쿼리 파라미터로 전달
            redirect_url = f"http://localhost:8000/test_login.html?login=success&email={user_data['email']}&name={user_data['name']}"
            return RedirectResponse(url=redirect_url)
            
        except Exception as db_error:
            raise HTTPException(status_code=500, detail=f"사용자 정보 저장 실패: {str(db_error)}")
        
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