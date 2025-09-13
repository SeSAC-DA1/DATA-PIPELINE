"""
차량 추천 에이전트 - 사용자의 요구사항에 맞는 차량을 추천하는 전문 에이전트
PyCaret ML 모델과 연동하여 개인화된 추천 제공
"""

import os
from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from ..database.models import Vehicle
from ..core.config import settings

class VehicleRecommendationAgent:
    """
    차량 추천 전문 에이전트
    - 사용자 선호도 기반 차량 추천
    - PyCaret ML 모델 활용
    - 실시간 재고 및 가격 정보 제공
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,  # 더 정확한 추천을 위해 낮은 temperature
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        self.agent = Agent(
            role="차량 추천 전문가",
            goal="사용자의 예산, 선호도, 라이프스타일에 맞는 최적의 차량을 추천하기",
            backstory="""
            당신은 15년 경력의 자동차 전문가입니다.
            다양한 브랜드의 차량 특성을 깊이 이해하고 있으며,
            특히 20-30대 고객들의 라이프스타일과 니즈를 잘 파악합니다.
            
            연비, 안전성, 디자인, 실용성 등 다양한 요소를 종합적으로 고려하여
            고객에게 최적의 차량을 추천합니다.
            
            최신 시장 동향과 가격 정보도 정확히 알고 있어
            합리적인 구매 결정을 도와줍니다.
            """,
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )
    
    def create_recommendation_task(self, user_preferences: Dict[str, Any]) -> Task:
        """사용자 선호도 기반 차량 추천 태스크 생성"""
        
        return Task(
            description=f"""
            사용자 요구사항을 분석하여 최적의 차량을 추천하세요.
            
            사용자 정보:
            - 예산: {user_preferences.get('budget', '정보 없음')}
            - 차량 타입: {user_preferences.get('vehicle_type', '정보 없음')}
            - 연료 타입: {user_preferences.get('fuel_type', '정보 없음')}
            - 브랜드 선호: {user_preferences.get('preferred_brands', '정보 없음')}
            - 주요 용도: {user_preferences.get('usage_purpose', '정보 없음')}
            - 기타 요구사항: {user_preferences.get('other_requirements', '정보 없음')}
            
            다음 기준으로 추천하세요:
            1. 예산 범위에 맞는 차량들
            2. 사용자의 라이프스타일에 적합한 차량
            3. 연비 효율성과 유지비
            4. 안전성 평가 및 옵션
            5. 재판매 가치
            
            추천 결과는 다음 형식으로 제공하세요:
            - 1순위 추천차량 (상세 이유)
            - 2순위 추천차량 (상세 이유)  
            - 3순위 추천차량 (상세 이유)
            - 각 차량의 장단점 비교
            - 구매 시 고려사항
            """,
            expected_output="상위 3개 차량 추천 목록과 상세한 추천 이유",
            agent=self.agent
        )
    
    def get_vehicle_recommendations(
        self, 
        user_preferences: Dict[str, Any],
        db_session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """차량 추천 실행"""
        
        # 데이터베이스에서 차량 정보 조회 (실제 구현 시)
        available_vehicles = self._get_available_vehicles(user_preferences, db_session)
        
        # ML 모델 예측 (PyCaret 연동 부분 - 추후 구현)
        ml_predictions = self._get_ml_predictions(user_preferences, available_vehicles)
        
        # CrewAI 에이전트를 통한 추천
        task = self.create_recommendation_task(user_preferences)
        
        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            verbose=True
        )
        
        result = crew.kickoff()
        
        return {
            "recommendations": str(result),
            "ml_scores": ml_predictions,
            "total_available": len(available_vehicles),
            "user_preferences": user_preferences
        }
    
    def _get_available_vehicles(
        self, 
        preferences: Dict[str, Any], 
        db_session: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """데이터베이스에서 조건에 맞는 차량 조회"""
        
        # 실제 DB 연동 로직 (추후 구현)
        # if db_session:
        #     query = db_session.query(Vehicle)
        #     
        #     if preferences.get('budget'):
        #         budget_range = preferences['budget']
        #         query = query.filter(Vehicle.price <= budget_range.get('max', 100000000))
        #     
        #     vehicles = query.all()
        #     return [vehicle.to_dict() for vehicle in vehicles]
        
        # 임시 데이터 (개발용)
        return [
            {
                "id": 1,
                "name": "현대 아반떼",
                "price": 25000000,
                "fuel_type": "gasoline",
                "vehicle_type": "sedan"
            },
            {
                "id": 2, 
                "name": "기아 셀토스",
                "price": 30000000,
                "fuel_type": "gasoline",
                "vehicle_type": "suv"
            }
        ]
    
    def _get_ml_predictions(
        self, 
        preferences: Dict[str, Any], 
        vehicles: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """PyCaret ML 모델을 통한 차량 추천 점수 계산"""
        
        # PyCaret 모델 연동 로직 (추후 구현)
        # 현재는 임시 점수 반환
        scores = {}
        for vehicle in vehicles:
            # 간단한 점수 계산 로직 (실제로는 ML 모델 사용)
            base_score = 0.7
            
            # 예산 적합성
            if preferences.get('budget'):
                budget_max = preferences['budget'].get('max', 50000000)
                if vehicle['price'] <= budget_max:
                    base_score += 0.2
            
            # 차량 타입 일치
            if preferences.get('vehicle_type') == vehicle.get('vehicle_type'):
                base_score += 0.1
                
            scores[vehicle['name']] = min(base_score, 1.0)
        
        return scores
    
    def create_comparison_task(self, vehicle_list: List[str]) -> Task:
        """차량 비교 분석 태스크"""
        
        return Task(
            description=f"""
            다음 차량들을 상세히 비교 분석하세요: {', '.join(vehicle_list)}
            
            비교 항목:
            1. 가격 대비 성능
            2. 연비 효율성
            3. 안전성 평가
            4. 실내 공간 및 편의성
            5. 유지비 및 서비스
            6. 재판매 가치
            7. 디자인 및 브랜드 이미지
            
            각 항목별로 점수를 매기고 종합 평가를 제공하세요.
            """,
            expected_output="차량별 상세 비교표와 종합 평가",
            agent=self.agent
        )
    
    def compare_vehicles(self, vehicle_list: List[str]) -> str:
        """차량 비교 분석 실행"""
        
        task = self.create_comparison_task(vehicle_list)
        
        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            verbose=True
        )
        
        result = crew.kickoff()
        return str(result)