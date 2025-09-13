"""
간단한 AI 에이전트 API - 직접 엔드포인트
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import sys

# 현재 디렉토리를 Python path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, '..', '..', '..')
sys.path.insert(0, backend_dir)

router = APIRouter()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    message: str
    response: str
    agent_type: str = "chat"

@router.post("/simple-chat", response_model=ChatResponse, tags=["Simple Agents"])
async def simple_chat(request: ChatRequest):
    """
    간단한 채팅 API
    CrewAI 에이전트 없이 기본 응답 제공
    """
    try:
        user_message = request.message
        
        # 간단한 키워드 기반 응답
        if any(keyword in user_message.lower() for keyword in ['차량', '자동차', '추천', 'car']):
            response = f"""안녕하세요! "{user_message}"에 대해 답변드리겠습니다.

🚗 **차량 추천 서비스**
- 현재 AI 에이전트 시스템 구축 중입니다
- CrewAI 기반 멀티에이전트 추천 시스템
- 개인 맞춤형 차량 분석 및 추천

곧 완전한 AI 추천 서비스를 제공할 예정입니다!"""

        elif any(keyword in user_message.lower() for keyword in ['금융', '대출', '리스', '렌트']):
            response = f"""금융 상품에 대해 문의해주셨네요!

💰 **자동차 금융 상품**
- 20-30대 맞춤 대출 상품
- 리스 vs 대출 비교 분석  
- 신용등급별 맞춤 추천
- 최저금리 상품 안내

더 자세한 상담을 위해 AI 상담 에이전트를 준비 중입니다."""

        elif any(keyword in user_message.lower() for keyword in ['안녕', 'hello', 'hi', '도움']):
            response = f"""안녕하세요! CarFin AI 어시스턴트입니다. 🤖

현재 제공 가능한 서비스:
✨ 차량 정보 및 추천 문의
💰 자동차 금융 상품 안내  
📊 차량 비교 분석 정보
🔍 맞춤형 상담 서비스

무엇을 도와드릴까요?"""
        
        else:
            response = f""""{user_message}"에 대해 답변드리겠습니다.

현재 CarFin AI 시스템을 구축 중입니다:
- CrewAI 멀티에이전트 시스템
- 개인화된 차량 추천 알고리즘
- 실시간 금융 상품 비교

더 구체적인 질문이 있으시면 언제든 말씀해주세요!"""

        return ChatResponse(
            message=user_message,
            response=response,
            agent_type="simple_chat"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat processing error: {str(e)}")

@router.get("/test-agent", tags=["Simple Agents"])
async def test_agent():
    """에이전트 테스트 엔드포인트"""
    try:
        # 실제 에이전트 임포트 테스트
        from src.agents.chat_agent import ChatAgent
        
        agent = ChatAgent()
        test_response = "CrewAI Chat Agent loaded successfully!"
        
        return {
            "status": "success",
            "message": "AI 에이전트가 정상적으로 로드되었습니다",
            "agent_response": test_response,
            "agent_loaded": True
        }
        
    except Exception as e:
        return {
            "status": "error", 
            "message": f"AI 에이전트 로드 실패: {str(e)}",
            "agent_loaded": False
        }

@router.post("/crew-chat", response_model=ChatResponse, tags=["CrewAI Agents"])
async def crew_chat(request: ChatRequest):
    """
    실제 CrewAI 에이전트를 사용한 채팅
    """
    try:
        from src.agents.chat_agent import ChatAgent
        
        # CrewAI 에이전트 생성
        chat_agent = ChatAgent()
        
        # 실제 AI 응답 생성
        ai_response = chat_agent.process_message(request.message)
        
        return ChatResponse(
            message=request.message,
            response=str(ai_response),
            agent_type="crewai_chat"
        )
        
    except Exception as e:
        # 에러 발생 시 기본 응답
        return ChatResponse(
            message=request.message,
            response=f"CrewAI 에이전트 처리 중 오류가 발생했습니다: {str(e)}\n\n기본 응답 모드로 전환됩니다.",
            agent_type="fallback"
        )