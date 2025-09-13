from fastapi import APIRouter
from .endpoints import users, auth, vehicles, agents, simple_agents

# 메인 API 라우터를 생성합니다.
api_router = APIRouter()

# users.py에서 생성한 라우터를 메인 라우터에 포함시킵니다.
api_router.include_router(users.router, prefix="", tags=["users"])

# 인증 라우터 추가
api_router.include_router(auth.router, prefix="", tags=["auth"])

# 차량 라우터 추가
api_router.include_router(vehicles.router, prefix="", tags=["vehicles"])

# 간단한 AI 에이전트 라우터 추가 (우선)
api_router.include_router(simple_agents.router, prefix="/chat", tags=["Simple AI"])

# AI 에이전트 라우터 추가
api_router.include_router(agents.router, prefix="/agents", tags=["AI Agents"])

# 만약 다른 엔드포인트 파일(예: products.py)이 있다면 아래와 같이 추가합니다.
# from backend.api.endpoints import products
# api_router.include_router(products.router, prefix="/products", tags=["products"])
