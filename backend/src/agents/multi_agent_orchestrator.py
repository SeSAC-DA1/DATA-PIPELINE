"""
CarFin 2.0 멀티에이전트 오케스트레이터
CrewAI를 사용하여 3개 전문 에이전트의 협업을 조율하는 핵심 시스템
"""

import os
import json
from typing import Dict, Any, Optional, List
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI

from .chat_agent import ChatAgent
from .vehicle_agent import VehicleRecommendationAgent
from ..core.config import settings

class MultiAgentOrchestrator:
    """
    CarFin 멀티에이전트 오케스트레이터
    - Chat Agent: 대화 관리 및 사용자 의도 파악
    - Vehicle Agent: ML 기반 차량 추천
    - Finance Agent: 금융상품 매칭 (20-30대)
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # 개별 에이전트 초기화
        self.chat_agent_handler = ChatAgent()
        self.vehicle_agent_handler = VehicleRecommendationAgent()
        
        # CrewAI 통합 에이전트들
        self.coordinator_agent = self._create_coordinator_agent()
        self.integration_agent = self._create_integration_agent()
        
    def _create_coordinator_agent(self) -> Agent:
        """코디네이터 에이전트 - 전체 프로세스 관리"""
        return Agent(
            role="CarFin AI 코디네이터",
            goal="사용자 요청을 분석하여 적절한 전문 에이전트에게 배분하고 결과를 통합",
            backstory="""
            당신은 CarFin의 AI 시스템을 총괄하는 코디네이터입니다.
            사용자의 복잡한 요청을 분석하여 Chat, Vehicle, Finance 전문가들에게
            적절히 업무를 배분하고, 각자의 결과를 종합하여 
            완벽한 상담 결과를 만들어냅니다.
            
            특히 20-30대 사용자들의 차량 구매 여정을 깊이 이해하고 있으며,
            각 단계별로 필요한 정보와 서비스를 정확히 파악합니다.
            """,
            verbose=True,
            allow_delegation=True,
            llm=self.llm
        )
    
    def _create_integration_agent(self) -> Agent:
        """통합 에이전트 - 최종 결과 생성"""
        return Agent(
            role="결과 통합 전문가",
            goal="각 전문 에이전트의 결과를 사용자 친화적으로 통합하여 최종 응답 생성",
            backstory="""
            당신은 복잡한 기술적 분석 결과를 일반 사용자가 이해하기 쉽게
            번역하고 정리하는 전문가입니다.
            
            차량 추천, 금융상품 매칭, 기술적 분석 결과를 
            친근하고 실용적인 조언으로 변환하여 
            사용자가 자신 있게 결정할 수 있도록 돕습니다.
            """,
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )
    
    def process_user_request(self, user_message: str, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        사용자 요청 처리 메인 플로우
        1단계: 사용자 의도 파악
        2단계: 적절한 전문 에이전트 호출
        3단계: 결과 통합 및 응답 생성
        """
        
        # 1단계: 사용자 프로필 분석 및 의도 파악
        user_analysis = self._analyze_user_intent(user_message, user_context)
        
        # 2단계: 전문 에이전트들 병렬 실행
        agent_results = self._execute_specialized_agents(user_analysis)
        
        # 3단계: 결과 통합
        final_response = self._integrate_results(user_analysis, agent_results)
        
        return final_response
    
    def _analyze_user_intent(self, user_message: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """1단계: 사용자 의도 및 프로필 분석"""
        
        analysis_task = Task(
            description=f"""
            사용자 메시지를 종합적으로 분석하여 맞춤형 서비스를 위한 프로필을 생성하세요.
            
            사용자 메시지: "{user_message}"
            기존 컨텍스트: {context or '없음'}
            
            다음 정보를 추출하고 분석하세요:
            
            1. 기본 정보 추출:
               - 연령대 (10대/20대/30대/40대+)
               - 예산 범위
               - 차량 용도 (출퇴근/가족용/레저/비즈니스)
               
            2. 서비스 필요도 분석:
               - vehicle_recommendation: 차량 추천 필요 여부 (0-1)
               - finance_consultation: 금융상품 상담 필요 여부 (0-1)
               - comparison_analysis: 차량 비교 분석 필요 여부 (0-1)
               
            3. 우선순위 설정:
               - primary_need: 주요 니즈
               - secondary_needs: 부차적 니즈들
               
            결과를 JSON 형태로 정리하세요:
            {{
                "user_profile": {{
                    "age_group": "연령대",
                    "budget_range": "예산",
                    "usage_purpose": "사용 목적",
                    "preferences": ["선호사항들"]
                }},
                "service_needs": {{
                    "vehicle_recommendation": 0.0-1.0,
                    "finance_consultation": 0.0-1.0,
                    "comparison_analysis": 0.0-1.0
                }},
                "execution_plan": {{
                    "primary_agent": "메인 담당 에이전트",
                    "supporting_agents": ["보조 에이전트들"],
                    "estimated_complexity": "단순/보통/복잡"
                }}
            }}
            """,
            expected_output="사용자 프로필 및 서비스 실행 계획 JSON",
            agent=self.coordinator_agent
        )
        
        analysis_crew = Crew(
            agents=[self.coordinator_agent],
            tasks=[analysis_task],
            process=Process.sequential,
            verbose=False
        )
        
        try:
            result = analysis_crew.kickoff()
            # 실제로는 더 정교한 JSON 파싱 필요
            return self._parse_analysis_result(str(result))
        except Exception as e:
            # 기본 분석 결과 반환
            return {
                "user_profile": {
                    "age_group": "미상",
                    "budget_range": "미상",
                    "usage_purpose": "일반",
                    "preferences": [user_message[:50]]
                },
                "service_needs": {
                    "vehicle_recommendation": 0.8,
                    "finance_consultation": 0.3,
                    "comparison_analysis": 0.2
                },
                "execution_plan": {
                    "primary_agent": "vehicle",
                    "supporting_agents": ["chat"],
                    "estimated_complexity": "보통"
                },
                "error": str(e)
            }
    
    def _execute_specialized_agents(self, user_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """2단계: 전문 에이전트들 실행"""
        
        results = {
            "chat_response": None,
            "vehicle_recommendations": None,
            "finance_options": None
        }
        
        service_needs = user_analysis.get("service_needs", {})
        user_profile = user_analysis.get("user_profile", {})
        
        # Vehicle Agent 실행 (필요도가 0.5 이상일 때)
        if service_needs.get("vehicle_recommendation", 0) >= 0.5:
            try:
                vehicle_prefs = {
                    "budget": {"max": 50000000},  # 기본값
                    "vehicle_type": user_profile.get("usage_purpose", "sedan"),
                    "age_group": user_profile.get("age_group", "30대"),
                    "preferences": user_profile.get("preferences", [])
                }
                
                results["vehicle_recommendations"] = self.vehicle_agent_handler.get_vehicle_recommendations(
                    user_preferences=vehicle_prefs
                )
                
            except Exception as e:
                results["vehicle_recommendations"] = {
                    "error": f"차량 추천 에이전트 오류: {str(e)}",
                    "recommendations": "차량 추천 서비스에 일시적 문제가 발생했습니다."
                }
        
        # Chat Agent 기본 응답 (항상 실행)
        try:
            original_message = user_analysis.get("original_message", "차량 상담 요청")
            results["chat_response"] = self.chat_agent_handler.process_message(
                user_message=original_message,
                context=user_analysis
            )
        except Exception as e:
            results["chat_response"] = f"대화 처리 중 오류 발생: {str(e)}"
        
        # Finance Agent (20-30대만, 추후 구현)
        if (service_needs.get("finance_consultation", 0) >= 0.5 and 
            user_profile.get("age_group") in ["20대", "30대"]):
            results["finance_options"] = {
                "message": "20-30대 맞춤 금융상품 분석 중입니다. (구현 예정)",
                "estimated_products": 3
            }
        
        return results
    
    def _integrate_results(self, user_analysis: Dict[str, Any], agent_results: Dict[str, Any]) -> Dict[str, Any]:
        """3단계: 결과 통합 및 최종 응답 생성"""
        
        integration_task = Task(
            description=f"""
            다음 분석 결과들을 종합하여 사용자에게 도움이 되는 완전한 응답을 생성하세요.
            
            사용자 분석:
            {json.dumps(user_analysis, ensure_ascii=False, indent=2)}
            
            에이전트 결과:
            - 기본 채팅 응답: {agent_results.get('chat_response', '없음')}
            - 차량 추천 결과: {str(agent_results.get('vehicle_recommendations', '없음'))[:200]}...
            - 금융 상품 옵션: {agent_results.get('finance_options', '없음')}
            
            통합 지침:
            1. 사용자 친화적이고 이해하기 쉬운 톤으로 작성
            2. 구체적이고 실행 가능한 조언 제공
            3. 다음 단계 안내 포함
            4. 필요시 추가 질문 유도
            
            응답 구조:
            - 인사 및 상황 이해
            - 주요 추천 내용 (차량/금융)
            - 상세 설명 및 근거
            - 다음 단계 안내
            """,
            expected_output="통합된 사용자 친화적 최종 응답",
            agent=self.integration_agent
        )
        
        integration_crew = Crew(
            agents=[self.integration_agent],
            tasks=[integration_task],
            process=Process.sequential,
            verbose=True
        )
        
        try:
            final_response = integration_crew.kickoff()
            
            return {
                "response": str(final_response),
                "user_analysis": user_analysis,
                "agent_results": agent_results,
                "success": True,
                "timestamp": "2024-09-13",
                "agents_used": list(agent_results.keys())
            }
            
        except Exception as e:
            # 에러 발생 시 기본 응답
            return {
                "response": f"죄송합니다. AI 에이전트 처리 중 오류가 발생했습니다. 기본 응답을 드리겠습니다:\n\n{agent_results.get('chat_response', '차량 상담 서비스를 준비 중입니다.')}",
                "error": str(e),
                "success": False,
                "agent_results": agent_results
            }
    
    def _parse_analysis_result(self, result_str: str) -> Dict[str, Any]:
        """분석 결과 파싱 (실제로는 더 정교한 JSON 파싱 필요)"""
        
        # 간단한 키워드 기반 분석
        result_lower = result_str.lower()
        
        # 연령대 추정
        age_group = "미상"
        if "20대" in result_str or "20살" in result_str:
            age_group = "20대"
        elif "30대" in result_str or "30살" in result_str:
            age_group = "30대"
        elif "40대" in result_str or "40살" in result_str:
            age_group = "40대+"
        
        # 차량 추천 필요도
        vehicle_need = 0.8
        if any(keyword in result_lower for keyword in ["차량", "자동차", "추천", "구매"]):
            vehicle_need = 0.9
        
        # 금융 상담 필요도
        finance_need = 0.3
        if any(keyword in result_lower for keyword in ["대출", "금융", "할부", "리스"]):
            finance_need = 0.8
        
        return {
            "user_profile": {
                "age_group": age_group,
                "budget_range": "미상",
                "usage_purpose": "일반",
                "preferences": [result_str[:100]]
            },
            "service_needs": {
                "vehicle_recommendation": vehicle_need,
                "finance_consultation": finance_need,
                "comparison_analysis": 0.4
            },
            "execution_plan": {
                "primary_agent": "vehicle",
                "supporting_agents": ["chat"],
                "estimated_complexity": "보통"
            },
            "original_message": result_str
        }

# 전역 인스턴스 생성 (싱글톤 패턴)
orchestrator = MultiAgentOrchestrator()