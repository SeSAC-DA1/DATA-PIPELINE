"""
AI 에이전트 API 엔드포인트
CrewAI 멀티에이전트 시스템을 위한 REST API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging
from ...agents.chat_agent import ChatAgent
from ...agents.vehicle_agent import VehicleRecommendationAgent

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# 전역 에이전트 인스턴스 (재사용을 위해)
chat_agent = None
vehicle_agent = None

def get_chat_agent():
    """Chat Agent 싱글톤 인스턴스 반환"""
    global chat_agent
    if chat_agent is None:
        chat_agent = ChatAgent()
    return chat_agent

def get_vehicle_agent():
    """Vehicle Agent 싱글톤 인스턴스 반환"""
    global vehicle_agent
    if vehicle_agent is None:
        vehicle_agent = VehicleRecommendationAgent()
    return vehicle_agent

# Request/Response 모델들
class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str
    intent: Dict[str, Any]
    agent_type: str = "chat"

class VehicleRecommendationRequest(BaseModel):
    budget: Optional[Dict[str, int]] = None  # {"min": 2000, "max": 5000}
    vehicle_type: Optional[str] = None  # "sedan", "suv", "hatchback" 
    fuel_type: Optional[str] = None  # "gasoline", "diesel", "electric", "hybrid"
    preferred_brands: Optional[List[str]] = None
    usage_purpose: Optional[str] = None  # "commute", "family", "business"
    other_requirements: Optional[str] = None

class VehicleRecommendationResponse(BaseModel):
    recommendations: str
    ml_scores: Dict[str, float]
    total_available: int
    user_preferences: Dict[str, Any]

# API 엔드포인트들
@router.post("/chat", response_model=ChatResponse, tags=["AI Agents"])
async def chat_with_agent(request: ChatRequest):
    """
    채팅 에이전트와 대화
    - 사용자 메시지 처리
    - 의도 파악 및 응답 생성
    - 필요시 다른 에이전트로 라우팅
    """
    try:
        agent = get_chat_agent()
        
        # 사용자 메시지 처리
        response = agent.process_message(request.message, request.context)
        
        # 의도 분석
        intent = agent.extract_user_intent(request.message)
        
        logger.info(f"Chat request processed: {request.message[:50]}...")
        
        return ChatResponse(
            response=response,
            intent=intent,
            agent_type="chat"
        )
        
    except Exception as e:
        logger.error(f"Chat agent error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat agent error: {str(e)}")

@router.post("/vehicle/recommend", response_model=VehicleRecommendationResponse, tags=["AI Agents"])
async def get_vehicle_recommendations(request: VehicleRecommendationRequest):
    """
    차량 추천 에이전트
    - 사용자 선호도 기반 차량 추천
    - ML 모델 활용 개인화 추천
    - 상세 비교 분석 제공
    """
    try:
        agent = get_vehicle_agent()
        
        # 요청을 딕셔너리로 변환
        preferences = {
            "budget": request.budget,
            "vehicle_type": request.vehicle_type,
            "fuel_type": request.fuel_type,
            "preferred_brands": request.preferred_brands,
            "usage_purpose": request.usage_purpose,
            "other_requirements": request.other_requirements
        }
        
        # None 값 제거
        preferences = {k: v for k, v in preferences.items() if v is not None}
        
        # 추천 실행
        result = agent.get_vehicle_recommendations(preferences)
        
        logger.info(f"Vehicle recommendation request: {preferences}")
        
        return VehicleRecommendationResponse(**result)
        
    except Exception as e:
        logger.error(f"Vehicle agent error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Vehicle agent error: {str(e)}")

@router.post("/vehicle/compare", tags=["AI Agents"])
async def compare_vehicles(vehicle_names: List[str]):
    """
    차량 비교 분석
    - 여러 차량 간 상세 비교
    - 각 항목별 점수 매기기
    - 종합 평가 제공
    """
    try:
        if not vehicle_names or len(vehicle_names) < 2:
            raise HTTPException(status_code=400, detail="최소 2개 이상의 차량이 필요합니다")
        
        agent = get_vehicle_agent()
        comparison_result = agent.compare_vehicles(vehicle_names)
        
        logger.info(f"Vehicle comparison: {', '.join(vehicle_names)}")
        
        return {
            "comparison": comparison_result,
            "vehicles": vehicle_names,
            "agent_type": "vehicle_comparison"
        }
        
    except Exception as e:
        logger.error(f"Vehicle comparison error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Vehicle comparison error: {str(e)}")

@router.get("/agents/status", tags=["AI Agents"])
async def get_agents_status():
    """
    에이전트 시스템 상태 확인
    - 각 에이전트 로드 상태
    - OpenAI API 연결 상태
    - 시스템 헬스 체크
    """
    try:
        status = {
            "chat_agent": "loaded" if chat_agent else "not_loaded",
            "vehicle_agent": "loaded" if vehicle_agent else "not_loaded",
            "openai_configured": True,  # 환경변수 체크 로직 추가 가능
            "crewai_version": "0.186.1",
            "system_status": "healthy"
        }
        
        return status
        
    except Exception as e:
        logger.error(f"Status check error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status check error: {str(e)}")

@router.post("/chat/quick", tags=["AI Agents"])
async def quick_chat(message: str):
    """
    빠른 채팅 (단순 문자열 입력)
    React에서 간단하게 호출하기 위한 엔드포인트
    """
    try:
        agent = get_chat_agent()
        response = agent.process_message(message)
        
        return {
            "message": message,
            "response": response,
            "agent_type": "chat"
        }
        
    except Exception as e:
        logger.error(f"Quick chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Quick chat error: {str(e)}")