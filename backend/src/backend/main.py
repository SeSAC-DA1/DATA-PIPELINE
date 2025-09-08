from fastapi import FastAPI
from backend.api.router import api_router
from backend.core.config import supabase_client

# FastAPI 애플리케이션을 생성합니다.
app = FastAPI(
    title="CarFin AI Backend",
    description="CarFin AI 서비스의 백엔드 API입니다.",
    version="0.1.0"
)

# /api/v1 과 같은 경로에 메인 라우터를 포함시킵니다.
app.include_router(api_router, prefix="/api")

@app.get("/", tags=["Status"])
def read_root():
    """
    서버의 상태 및 데이터베이스 연결 상태를 확인하는 헬스 체크 엔드포인트입니다.
    """
    db_status = "Disconnected"
    try:
        # 간단한 쿼리를 실행하여 DB 연결을 확인합니다.
        supabase_client.table('users').select('id').limit(1).execute()
        db_status = "Connected"
    except Exception as e:
        db_status = f"Connection Failed: {str(e)}"
    
    return {"status": "ok", "database_status": db_status}
