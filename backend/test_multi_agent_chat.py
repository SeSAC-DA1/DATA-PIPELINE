"""
CarFin 2.0 멀티에이전트 시스템 테스트 API
CrewAI 3개 에이전트 협업 시스템 실제 테스트
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn

# 멀티에이전트 오케스트레이터 import
try:
    from src.agents.multi_agent_orchestrator import MultiAgentOrchestrator
    MULTI_AGENT_AVAILABLE = True
except ImportError as e:
    print(f"멀티에이전트 시스템 로드 실패: {e}")
    MULTI_AGENT_AVAILABLE = False

app = FastAPI(title="CarFin 2.0 Multi-Agent System Test")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 요청/응답 모델
class MultiAgentChatRequest(BaseModel):
    message: str
    user_context: Optional[Dict[str, Any]] = None

class MultiAgentChatResponse(BaseModel):
    response: str
    success: bool
    agents_used: list
    user_analysis: Optional[Dict[str, Any]] = None
    debug_info: Optional[Dict[str, Any]] = None

class SystemStatusResponse(BaseModel):
    status: str
    multi_agent_available: bool
    openai_configured: bool
    agents_loaded: Dict[str, bool]

@app.get("/", response_model=Dict[str, str])
def root():
    return {"message": "CarFin 2.0 Multi-Agent System API is running!"}

@app.get("/system-status", response_model=SystemStatusResponse)
def get_system_status():
    """시스템 상태 확인"""
    
    openai_configured = bool(os.getenv("OPENAI_API_KEY"))
    
    agents_status = {
        "multi_agent_orchestrator": MULTI_AGENT_AVAILABLE,
        "chat_agent": False,
        "vehicle_agent": False,
        "finance_agent": False
    }
    
    if MULTI_AGENT_AVAILABLE:
        try:
            # 에이전트 로드 테스트
            orchestrator = MultiAgentOrchestrator()
            agents_status["chat_agent"] = hasattr(orchestrator, 'chat_agent_handler')
            agents_status["vehicle_agent"] = hasattr(orchestrator, 'vehicle_agent_handler')
            agents_status["finance_agent"] = True  # 기본값 (추후 구현)
        except Exception as e:
            print(f"에이전트 상태 확인 실패: {e}")
    
    return SystemStatusResponse(
        status="operational" if MULTI_AGENT_AVAILABLE and openai_configured else "limited",
        multi_agent_available=MULTI_AGENT_AVAILABLE,
        openai_configured=openai_configured,
        agents_loaded=agents_status
    )

@app.post("/multi-agent-chat", response_model=MultiAgentChatResponse)
async def multi_agent_chat(request: MultiAgentChatRequest):
    """멀티에이전트 시스템을 통한 채팅"""
    
    if not MULTI_AGENT_AVAILABLE:
        return MultiAgentChatResponse(
            response="멀티에이전트 시스템이 로드되지 않았습니다. /system-status에서 상태를 확인하세요.",
            success=False,
            agents_used=["fallback"],
            debug_info={"error": "Multi-agent system not available"}
        )
    
    if not os.getenv("OPENAI_API_KEY"):
        return MultiAgentChatResponse(
            response="OpenAI API 키가 설정되지 않았습니다.",
            success=False,
            agents_used=["error"],
            debug_info={"error": "OpenAI API key not configured"}
        )
    
    try:
        # 멀티에이전트 오케스트레이터 실행
        orchestrator = MultiAgentOrchestrator()
        
        print(f"멀티에이전트 처리 시작: {request.message[:50]}...")
        
        result = orchestrator.process_user_request(
            user_message=request.message,
            user_context=request.user_context
        )
        
        print(f"멀티에이전트 처리 완료: 성공={result.get('success', False)}")
        
        return MultiAgentChatResponse(
            response=result.get("response", "응답 생성 실패"),
            success=result.get("success", False),
            agents_used=result.get("agents_used", []),
            user_analysis=result.get("user_analysis"),
            debug_info={
                "agent_results": result.get("agent_results", {}),
                "timestamp": result.get("timestamp"),
                "processing_time": "측정 중"
            }
        )
        
    except Exception as e:
        print(f"멀티에이전트 처리 오류: {e}")
        
        return MultiAgentChatResponse(
            response=f"""죄송합니다. AI 에이전트 시스템에 일시적인 문제가 발생했습니다.

**CarFin 2.0 서비스 안내**
- 현재 멀티에이전트 시스템 구축 중입니다
- Chat Agent, Vehicle Agent, Finance Agent 협업 시스템
- CrewAI + MCP 프로토콜 기반 지능형 추천

**에러 정보**: {str(e)[:100]}...

기본 상담이 필요하시면 /simple-chat을 이용해주세요.""",
            success=False,
            agents_used=["error_handler"],
            debug_info={"error": str(e)}
        )

@app.post("/simple-chat")
async def simple_chat_fallback(request: MultiAgentChatRequest):
    """기본 챗봇 (멀티에이전트 실패 시 대체)"""
    
    user_message = request.message.lower()
    
    if any(keyword in user_message for keyword in ['차량', '자동차', '추천']):
        response = f"""안녕하세요! "{request.message}"에 대해 답변드리겠습니다.

**CarFin 2.0 멀티에이전트 시스템**
- CrewAI 기반 3개 전문 AI 에이전트
- Chat Agent: 대화 관리 및 의도 파악  
- Vehicle Agent: ML 기반 개인화 추천
- Finance Agent: 20-30대 특화 금융상품

**현재 상태**: 개발 및 테스트 중
완전한 AI 추천 서비스를 준비하고 있습니다!

멀티에이전트 시스템을 테스트하려면 `/multi-agent-chat`을 이용해주세요."""

    else:
        response = f"""CarFin 2.0 AI 어시스턴트입니다!

**제공 서비스**:
- 차량 추천 및 비교 분석
- 20-30대 맞춤 금융상품 
- 데이터 기반 의사결정 지원

**멀티에이전트 시스템**:
- CrewAI 3개 전문 AI 협업
- MCP 프로토콜 데이터 표준화
- PyCaret ML 하이브리드 추천

무엇을 도와드릴까요?"""

    return MultiAgentChatResponse(
        response=response,
        success=True,
        agents_used=["simple_chat"],
        debug_info={"mode": "fallback"}
    )

@app.get("/test-agents")
async def test_individual_agents():
    """개별 에이전트 테스트"""
    
    if not MULTI_AGENT_AVAILABLE:
        return {"error": "Multi-agent system not available"}
    
    test_results = {}
    
    try:
        orchestrator = MultiAgentOrchestrator()
        
        # Chat Agent 테스트
        try:
            chat_result = orchestrator.chat_agent_handler.process_message("안녕하세요")
            test_results["chat_agent"] = {
                "status": "success",
                "response": str(chat_result)[:100] + "..."
            }
        except Exception as e:
            test_results["chat_agent"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Vehicle Agent 테스트
        try:
            vehicle_result = orchestrator.vehicle_agent_handler.get_vehicle_recommendations(
                user_preferences={"budget": {"max": 30000000}, "vehicle_type": "sedan"}
            )
            test_results["vehicle_agent"] = {
                "status": "success",
                "recommendations_count": len(vehicle_result.get("recommendations", ""))
            }
        except Exception as e:
            test_results["vehicle_agent"] = {
                "status": "error", 
                "error": str(e)
            }
        
        test_results["overall_status"] = "multi_agent_system_loaded"
        
    except Exception as e:
        test_results = {
            "overall_status": "failed",
            "error": str(e)
        }
    
    return test_results

if __name__ == "__main__":
    print("CarFin 2.0 Multi-Agent System Starting...")
    print(f"Multi-Agent Available: {MULTI_AGENT_AVAILABLE}")
    print(f"OpenAI Configured: {bool(os.getenv('OPENAI_API_KEY'))}")
    
    uvicorn.run(app, host="0.0.0.0", port=8002)