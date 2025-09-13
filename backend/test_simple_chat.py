"""
간단한 테스트용 FastAPI 앱
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Simple ChatBot Test")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    message: str
    response: str
    agent_type: str = "simple"

@app.post("/simple-chat")
async def simple_chat(request: ChatRequest):
    user_message = request.message
    
    # 키워드 기반 응답
    if any(keyword in user_message.lower() for keyword in ['차량', '자동차', '추천']):
        response = f"""안녕하세요! "{user_message}"에 대해 답변드리겠습니다.

🚗 **차량 추천 서비스**
- 현재 AI 에이전트 시스템 구축 중입니다
- CrewAI 기반 멀티에이전트 추천 시스템  
- 개인 맞춤형 차량 분석 및 추천

곧 완전한 AI 추천 서비스를 제공할 예정입니다!"""

    elif any(keyword in user_message.lower() for keyword in ['금융', '대출']):
        response = f"""금융 상품에 대해 문의해주셨네요!

💰 **자동차 금융 상품**
- 20-30대 맞춤 대출 상품
- 리스 vs 대출 비교 분석
- 신용등급별 맞춤 추천

더 자세한 상담을 위해 AI 상담 에이전트를 준비 중입니다."""

    else:
        response = f"""안녕하세요! CarFin AI 어시스턴트입니다. 🤖

현재 제공 가능한 서비스:
✨ 차량 정보 및 추천 문의
💰 자동차 금융 상품 안내
📊 차량 비교 분석 정보

무엇을 도와드릴까요?"""

    return ChatResponse(
        message=user_message,
        response=response,
        agent_type="simple_test"
    )

@app.get("/")
def read_root():
    return {"message": "Simple ChatBot API is running!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)