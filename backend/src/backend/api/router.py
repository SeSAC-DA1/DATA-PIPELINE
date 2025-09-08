from fastapi import APIRouter
from backend.api.endpoints import users

# 메인 API 라우터를 생성합니다.
api_router = APIRouter()

# users.py에서 생성한 라우터를 메인 라우터에 포함시킵니다.
# prefix="/api/v1" 와 같이 버전 관리를 위한 접두사를 추가할 수도 있습니다.
api_router.include_router(users.router, prefix="", tags=["users"])

# 만약 다른 엔드포인트 파일(예: products.py)이 있다면 아래와 같이 추가합니다.
# from backend.api.endpoints import products
# api_router.include_router(products.router, prefix="/products", tags=["products"])
