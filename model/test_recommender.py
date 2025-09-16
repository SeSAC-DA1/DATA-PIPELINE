from llm_prompt import build_prompt
from car_recommender import get_top_recommendations

user_input = {
    "Price": 20000000, "Weight_Price": 0.3,
    "Year": 2018, "Weight_Year": 0.2,
    "Mileage": 50000, "Weight_Mileage": 0.2,
    "Category": "SUV", "Weight_Category": 0.1,
    "FuelType": "디젤", "Weight_FuelType": 0.1,
    "Transmission": "자동", "Weight_Transmission": 0.1,
    "AccidentHistory": "무사고", "Weight_AccidentHistory": 0.2,
    "isDisclosed": 1, "Weight_isDisclosed": 0.1
}

prompt = build_prompt(user_input)
print("=== 생성된 프롬프트 ===")
print(prompt)

top_vehicles = get_top_recommendations(user_input, top_n=5)
print("=== 추천 차량 리스트 ===")
for vehicle in top_vehicles:
    print(f"추천 차량: {vehicle['Manufacturer']} {vehicle['Model']} (점수: {vehicle['score']})")
