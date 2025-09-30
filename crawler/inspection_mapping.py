# =============================================================================
# 상태 코드 → 일반화 Enum 매핑
# =============================================================================

STATUS_CODE_MAPPING = {
    # 양호/불량
    '1': {'good_bad': 'GOOD'},
    '10': {'good_bad': 'BAD'},
    
    # 누유/누수 (없음/미세/누유)
    '3': {'leak_level': 'NONE'},
    '4': {'leak_level': 'MINOR'},   # 미세누유
    '5': {'leak_level': 'LEAK'},    # 누유
    '6': {'leak_level': 'MINOR'},   # 미세누유
    '7': {'leak_level': 'LEAK'},    # 누유
    
    # 적정/부족/과다
    '2': {'level_state': 'ADEQ'},   # 적정
    '8': {'level_state': 'LACK'},   # 부족
    '9': {'level_state': 'OVER'},   # 과다
    
    # 있음/없음 (연료 누출 등)
    # '3': 없음, '11': 있음 (필요시 추가)
}

# 상태 텍스트 → 일반화 Enum 매핑 (차차차용)
STATUS_TEXT_MAPPING = {
    # 양호/불량
    '양호': {'good_bad': 'GOOD'},
    '불량': {'good_bad': 'BAD'},
    
    # 누유/누수
    '없음': {'leak_level': 'NONE'},
    '미세누유': {'leak_level': 'MINOR'},
    '미세누수': {'leak_level': 'MINOR'},
    '누유': {'leak_level': 'LEAK'},
    '누수': {'leak_level': 'LEAK'},
    
    # 적정/부족/과다
    '적정': {'level_state': 'ADEQ'},
    '부족': {'level_state': 'LACK'},
    '과다': {'level_state': 'OVER'},
}

# =============================================================================
# 외판/골격 랭크 매핑
# =============================================================================

RANK_MAPPING = {
    'RANK_ONE': 'OUTER_1',
    'RANK_TWO': 'OUTER_2',
    'RANK_A': 'STRUCT_A',
    'RANK_B': 'STRUCT_B',
    'RANK_C': 'STRUCT_C',
}

# =============================================================================
# 외판/골격 손상 유형 매핑 (엔카 + 차차차 공통)
# =============================================================================

DAMAGE_TYPE_MAPPING = {
    'X': 'exchanged',    # 교환
    'W': 'welded',       # 판금 또는 용접
    'A': 'scratched',    # 흠집
    'U': 'uneven',       # 요철
    'C': 'corroded',     # 부식
    'T': 'damaged',      # 손상
}

# =============================================================================
# 헬퍼 함수
# =============================================================================

def normalize_status(status_code: str, status_title: str = None) -> dict:
    """
    상태 코드/텍스트를 일반화 Enum으로 변환
    
    Args:
        status_code: 상태 코드 ('1', '3', '6' 등)
        status_title: 상태 텍스트 ('양호', '미세누유' 등) - 선택적
    
    Returns:
        dict: {'good_bad': 'GOOD'} 또는 {'leak_level': 'MINOR'} 등
    """
    # 코드 우선 매핑
    if status_code and status_code in STATUS_CODE_MAPPING:
        return STATUS_CODE_MAPPING[status_code]
    
    # 텍스트 매핑 (차차차용)
    if status_title and status_title in STATUS_TEXT_MAPPING:
        return STATUS_TEXT_MAPPING[status_title]
    
    return {}

def normalize_rank(rank_attribute: str) -> str:
    """
    외판/골격 랭크를 일반화
    
    Args:
        rank_attribute: 'RANK_ONE', 'RANK_A' 등
    
    Returns:
        str: 'OUTER_1', 'STRUCT_A' 등
    """
    return RANK_MAPPING.get(rank_attribute)

def normalize_damage_types(status_codes: list) -> dict:
    """
    손상 유형 코드들을 Boolean 플래그로 변환
    
    Args:
        status_codes: ['X', '4', 'C'] 등
    
    Returns:
        dict: {'exchanged': True, 'scratched': True, 'corroded': True}
    """
    result = {
        'exchanged': False,
        'welded': False,
        'scratched': False,
        'uneven': False,
        'corroded': False,
        'damaged': False,
    }
    
    for code in status_codes:
        damage_type = DAMAGE_TYPE_MAPPING.get(code)
        if damage_type:
            result[damage_type] = True
    
    return result

# =============================================================================
# 검사 항목 그룹 정의 (참고용)
# =============================================================================

INSPECTION_GROUPS = {
    'S00': '자기진단',      # OBD 스캐너
    'S01': '원동기',
    'S02': '변속기',
    'S03': '동력전달',
    'S04': '조향',
    'S05': '제동',
    'S06': '전기',
    'S07': '연료',
    'S08': '전동화',        # 차차차
}

# 전체 검사 항목 목록 (엔카 API 기준)
INSPECTION_ITEMS = {
    # S00: 자기진단
    's001': '자기진단-원동기',
    's002': '자기진단-변속기',
    
    # S01: 원동기
    's003': '작동상태(공회전)',
    's004': '실린더 커버(로커암 커버)',
    's005': '실린더 헤드/개스킷',
    's006': '실린더 블록/오일팬',
    's007': '오일 유량',
    's008': '실린더 헤드/개스킷(냉각수)',
    's009': '워터펌프',
    's010': '라디에이터',
    's011': '냉각수 수량',
    's012': '커먼레일',
    
    # S02: 변속기
    's013': '오일누유(A/T)',
    's014': '오일유량 및 상태(A/T)',
    's015': '작동상태(공회전)(A/T)',
    's016': '오일누유(M/T)',
    's017': '기어변속장치(M/T)',
    's018': '오일유량 및 상태(M/T)',
    's019': '작동상태(공회전)(M/T)',
    
    # S03: 동력전달
    's020': '클러치 어셈블리',
    's021': '등속조인트',
    's022': '추친축 및 베어링',
    's037': '디피렌셜 기어',
    
    # S04: 조향
    's023': '동력조향 작동 오일 누유',
    's024': '스티어링 기어(MDPS포함)',
    's025': '스티어링 펌프',
    's026': '타이로드엔드 및 볼 조인트',
    's038': '스티어링 조인트',
    's039': '파워고압호스',
    
    # S05: 제동
    's027': '브레이크 마스터 실린더오일 누유',
    's028': '브레이크 오일 누유',
    's029': '배력장치 상태',
    
    # S06: 전기
    's030': '발전기 출력',
    's031': '시동 모터',
    's032': '와이퍼 모터 기능',
    's033': '실내송풍 모터',
    's034': '라디에이터 팬 모터',
    's035': '윈도우 모터',
    
    # S07: 연료
    's036': '연료누출(LP가스포함)',
}
