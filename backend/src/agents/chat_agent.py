"""
채팅 에이전트 - 사용자와의 대화를 담당하는 메인 에이전트
CrewAI를 사용하여 구현된 대화형 AI 에이전트
"""

import os
from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI
from typing import Dict, Any, Optional
from ..core.config import settings

class ChatAgent:
    """
    채팅 에이전트 클래스
    - 사용자와의 자연스러운 대화
    - 차량 및 금융 상품 추천 요청 처리
    - 다른 전문 에이전트들과의 협업 조율
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        self.agent = Agent(
            role="대화 전문 AI 어시스턴트",
            goal="사용자와 자연스럽게 대화하며 차량 및 금융 상품 추천을 도와주기",
            backstory="""
            당신은 CarFin의 친근한 AI 어시스턴트입니다. 
            사용자의 차량 구매 및 금융 상품 선택을 도와주는 전문가로서,
            20-30대 고객의 니즈를 깊이 이해하고 있습니다.
            
            항상 친근하고 전문적인 톤으로 대화하며,
            사용자의 예산, 선호도, 생활패턴을 파악하여
            최적의 추천을 제공합니다.
            """,
            verbose=True,
            allow_delegation=True,
            llm=self.llm
        )
    
    def create_conversation_task(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> Task:
        """사용자 메시지에 대한 대화 태스크 생성"""
        
        context_info = ""
        if context:
            context_info = f"\n현재 컨텍스트: {context}"
        
        return Task(
            description=f"""
            사용자 메시지: "{user_message}"
            {context_info}
            
            다음 사항을 고려하여 응답하세요:
            1. 사용자의 의도 파악 (차량 추천, 금융 상품 문의, 일반 대화 등)
            2. 필요한 정보가 부족하다면 자연스럽게 질문하기
            3. 차량이나 금융 상품 추천이 필요하면 해당 전문 에이전트에게 위임
            4. 친근하고 도움이 되는 톤으로 응답
            
            응답 형식:
            - 자연스러운 대화체
            - 필요시 추가 질문 포함
            - 다음 단계 안내
            """,
            expected_output="사용자에게 도움이 되는 친근한 응답과 필요시 추가 질문",
            agent=self.agent
        )
    
    def process_message(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """사용자 메시지 처리 및 응답 생성"""
        
        task = self.create_conversation_task(user_message, context)
        
        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            verbose=True
        )
        
        result = crew.kickoff()
        return str(result)
    
    def extract_user_intent(self, user_message: str) -> Dict[str, Any]:
        """사용자 의도 추출"""
        
        intent_task = Task(
            description=f"""
            사용자 메시지를 분석하여 의도를 파악하세요: "{user_message}"
            
            다음 카테고리로 분류하고 관련 정보를 추출하세요:
            1. vehicle_recommendation: 차량 추천 요청
            2. finance_inquiry: 금융 상품 문의  
            3. general_chat: 일반 대화
            4. budget_discussion: 예산 관련 논의
            5. specification_inquiry: 차량 사양 문의
            
            JSON 형태로 결과를 반환하세요:
            {{
                "intent": "카테고리",
                "confidence": 0.0-1.0,
                "extracted_info": {{
                    "budget": "예산 정보",
                    "vehicle_type": "차량 타입",
                    "preferences": ["선호사항들"]
                }}
            }}
            """,
            expected_output="사용자 의도 분석 결과 JSON",
            agent=self.agent
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[intent_task],
            verbose=False
        )
        
        try:
            result = crew.kickoff()
            # JSON 파싱 시도 (실제로는 더 정교한 파싱 필요)
            return {
                "intent": "general_chat",
                "confidence": 0.8,
                "extracted_info": {"raw_message": user_message}
            }
        except Exception as e:
            return {
                "intent": "general_chat",
                "confidence": 0.5,
                "extracted_info": {"raw_message": user_message, "error": str(e)}
            }