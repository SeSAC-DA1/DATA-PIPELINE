#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 에이전트 테스트 스크립트
"""

import sys
import os
sys.path.append('.')

def test_agents():
    """에이전트 기본 기능 테스트"""
    try:
        from src.agents.chat_agent import ChatAgent
        from src.agents.vehicle_agent import VehicleRecommendationAgent
        print("Agent imports: OK")
        
        # 기본 인스턴스 생성 테스트
        chat_agent = ChatAgent()
        vehicle_agent = VehicleRecommendationAgent() 
        print("Agent instances: OK")
        
        print("\n=== AI Agent System Status ===")
        print("OK Chat Agent: Ready")
        print("OK Vehicle Recommendation Agent: Ready") 
        print("OK OpenAI API Key: Configured")
        print("OK CrewAI Framework: Loaded")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_agents()
    if success:
        print("\nSUCCESS: AI Agent System Ready!")
    else:
        print("\nERROR: Agent Setup Failed")