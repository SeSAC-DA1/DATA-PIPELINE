PROMPT_TEMPLATE = """
너는 중고차 추천 전문가야.
아래 조건과 각각의 중요도를 참고해서 추천 차량을 알려줘.

입력 예시:
가격: {Price} ({Weight_Price})
연식: {Year} ({Weight_Year})
주행거리: {Mileage} ({Weight_Mileage})
차종: {Category} ({Weight_Category})
연료: {FuelType} ({Weight_FuelType})
변속기: {Transmission} ({Weight_Transmission})
사고이력 여부: {AccidentHistory} ({Weight_AccidentHistory})
보험 공개여부: {isDisclosed} ({Weight_isDisclosed})

출력:
- 추천 차량 리스트(Top-5)와 선택 이유 한 줄
- 각 차량별 종합 점수(조건별 가중치 적용)
"""

def build_prompt(params: dict) -> str:
    """
    사용자 조건(dict)을 프롬프트 문자열로 변환
    """
    default = {
        'Price': '무관', 'Weight_Price': 0,
        'Year': '무관', 'Weight_Year': 0,
        'Mileage': '무관', 'Weight_Mileage': 0,
        'Category': '무관', 'Weight_Category': 0,
        'FuelType': '무관', 'Weight_FuelType': 0,
        'Transmission': '무관', 'Weight_Transmission': 0,
        'AccidentHistory': '무관', 'Weight_AccidentHistory': 0,
        'isDisclosed': '무관', 'Weight_isDisclosed': 0
    }
    merged = {**default, **params}
    try:
        return PROMPT_TEMPLATE.format(**merged)
    except KeyError as e:
        raise ValueError(f"프롬프트에 필요한 키가 누락되었습니다: {e}")

