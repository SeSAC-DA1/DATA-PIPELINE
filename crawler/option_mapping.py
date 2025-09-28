import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import session_scope
from db.model import OptionMaster, VehicleOption, Vehicle

def initialize_global_options():
    """공통 옵션 마스터를 초기화합니다."""
    global_options_data = [
        # 외관/내장 (22개) - 공통 15개, KB차차차만 5개, 엔카만 2개
        ("SUNROOF", "선루프(일반)", "외관/내장"),
        ("SUNROOF_PANORAMA", "선루프(파노라마)", "외관/내장"),  # KB차차차만
        ("HEADLIGHT_HID", "헤드램프(HID)", "외관/내장"),
        ("HEADLIGHT_LED", "헤드램프(LED)", "외관/내장"),
        ("POWER_TRUNK", "파워 전동 트렁크", "외관/내장"),
        ("GHOST_DOOR", "고스트 도어 클로징", "외관/내장"),
        ("POWER_MIRROR", "전동접이 사이드 미러", "외관/내장"),
        ("MIRROR_TURN_SIGNAL", "방향지시등 일체형 사이드 미러", "외관/내장"),  # KB차차차만
        ("MIRROR_REVERSE_TILT", "후진각도조절 사이드 미러", "외관/내장"),  # KB차차차만
        ("ALUMINUM_WHEEL", "알루미늄 휠", "외관/내장"),
        ("ROOF_RACK", "루프랙", "외관/내장"),
        ("HEATED_STEERING", "열선 스티어링 휠", "외관/내장"),
        ("POWER_STEERING_ADJUST", "전동 조절 스티어링 휠", "외관/내장"),
        ("PADDLE_SHIFT", "패들 시프트", "외관/내장"),
        ("STEERING_REMOTE", "스티어링 휠 리모컨", "외관/내장"),
        ("ECM_MIRROR", "ECM 루미러", "외관/내장"),
        ("HIGHPASS", "하이패스", "외관/내장"),
        ("POWER_DOORLOCK", "파워 도어록", "외관/내장"),  # 엔카만
        ("POWER_WINDOW", "파워 윈도우", "외관/내장"),  # 엔카만
        ("POWER_STEERING", "파워 스티어링", "외관/내장"),
        ("HIGH_BEAM_ASSIST", "하이빔 어시스트", "외관/내장"),  # KB차차차만
        ("ADAPTIVE_HEADLIGHT", "어댑티드 헤드램프", "외관/내장"),  # KB차차차만
        
        # 안전 (24개) - 공통 15개, KB차차차만 9개
        ("AIRBAG_DRIVER", "에어백(운전석)", "안전"),
        ("AIRBAG_PASSENGER", "에어백(동승석)", "안전"),
        ("AIRBAG_SIDE", "에어백(사이드)", "안전"),
        ("AIRBAG_CURTAIN", "에어백(커튼)", "안전"),
        ("ABS", "브레이크 잠김 방지(ABS)", "안전"),
        ("TCS", "미끄럼 방지(TCS)", "안전"),
        ("ESC", "차체자세 제어장치(ESC)", "안전"),
        ("TPMS", "타이어 공기압센서(TPMS)", "안전"),
        ("LDWS", "차선이탈 경보 시스템(LDWS)", "안전"),
        ("ECS", "전자제어 서스펜션(ECS)", "안전"),
        ("PARKING_SENSOR_FRONT", "주차감지센서(전방)", "안전"),
        ("PARKING_SENSOR_REAR", "주차감지센서(후방)", "안전"),
        ("BLIND_SPOT_WARNING", "후측방 경보 시스템", "안전"),
        ("REAR_CAMERA", "후방 카메라", "안전"),
        ("AROUND_VIEW", "360도 어라운드 뷰", "안전"),
        ("AEB", "자동긴급제동(AEB)", "안전"),  # KB차차차만
        ("FRONT_CAMERA", "전방 카메라", "안전"),  # KB차차차만
        ("ACTIVE_HEADREST", "액티브 헤드레스트", "안전"),  # KB차차차만
        ("AUTO_PARKING", "자동주차시스템", "안전"),  # KB차차차만
        ("LKAS", "차선유지지원(LKAS)", "안전"),  # KB차차차만
        ("FCW", "전방추돌경고(FCW)", "안전"),  # KB차차차만
        ("HAS", "경사로 밀림방지(HAS)", "안전"),  # KB차차차만
        ("AIRBAG_KNEE", "에어백(무릎)", "안전"),  # KB차차차만
        ("SAFETY_WINDOW", "세이프티 윈도우", "안전"),  # KB차차차만
        
        # 편의/멀티미디어 (19개) - 공통 14개, KB차차차만 1개, 엔카만 4개
        ("CRUISE_CONTROL", "크루즈 컨트롤(일반)", "편의/멀티미디어"),
        ("ADAPTIVE_CRUISE", "크루즈 컨트롤(어댑티브)", "편의/멀티미디어"),
        ("HUD", "헤드업 디스플레이(HUD)", "편의/멀티미디어"),
        ("EPB", "전자식 주차브레이크(EPB)", "편의/멀티미디어"),
        ("AUTO_AC", "자동 에어컨", "편의/멀티미디어"),
        ("SMART_KEY", "스마트키", "편의/멀티미디어"),
        ("WIRELESS_DOORLOCK", "무선도어 잠금장치", "편의/멀티미디어"),  # 엔카만
        ("RAIN_SENSOR", "레인센서", "편의/멀티미디어"),
        ("AUTO_LIGHT", "오토 라이트", "편의/멀티미디어"),  # 엔카만
        ("CURTAIN_REAR_SEAT", "커튼/블라인드(뒷좌석)", "편의/멀티미디어"),
        ("CURTAIN_REAR", "커튼/블라인드(후방)", "편의/멀티미디어"),  # 엔카만
        ("NAVIGATION", "내비게이션", "편의/멀티미디어"),
        ("FRONT_AV_MONITOR", "앞좌석 AV 모니터", "편의/멀티미디어"),  # 엔카만
        ("REAR_AV_MONITOR", "뒷좌석 AV 모니터", "편의/멀티미디어"),
        ("BLUETOOTH", "블루투스", "편의/멀티미디어"),
        ("CD_PLAYER", "CD 플레이어", "편의/멀티미디어"),
        ("USB_PORT", "USB 단자", "편의/멀티미디어"),
        ("AUX_PORT", "AUX 단자", "편의/멀티미디어"),
        ("NAVIGATION_AFTERMARKET", "내비게이션(비순정)", "편의/멀티미디어"),  # KB차차차만
        
        # 시트 (12개) - 공통 12개
        ("LEATHER_SEAT", "가죽시트", "시트"),
        ("POWER_SEAT_DRIVER", "전동시트(운전석)", "시트"),
        ("POWER_SEAT_PASSENGER", "전동시트(동승석)", "시트"),
        ("POWER_SEAT_REAR", "전동시트(뒷좌석)", "시트"),
        ("HEATED_SEAT_FRONT", "열선시트(앞좌석)", "시트"),
        ("HEATED_SEAT_REAR", "열선시트(뒷좌석)", "시트"),
        ("MEMORY_SEAT_DRIVER", "메모리 시트(운전석)", "시트"),
        ("MEMORY_SEAT_PASSENGER", "메모리 시트(동승석)", "시트"),
        ("VENTILATED_SEAT_DRIVER", "통풍시트(운전석)", "시트"),
        ("VENTILATED_SEAT_PASSENGER", "통풍시트(동승석)", "시트"),
        ("VENTILATED_SEAT_REAR", "통풍시트(뒷좌석)", "시트"),
        ("MASSAGE_SEAT", "마사지 시트", "시트"),
    ]
    
    try:
        saved_count = 0
        existing_count = 0
        with session_scope() as session:
            for option_code, option_name, option_group in global_options_data:
                existing = session.query(OptionMaster).filter(
                    OptionMaster.option_code == option_code
                ).first()
                
                if not existing:
                    global_option = OptionMaster(
                        option_code=option_code,
                        option_name=option_name,
                        option_group=option_group
                    )
                    session.add(global_option)
                    saved_count += 1
                else:
                    existing_count += 1
            
            session.commit()
            print(f"[공통 옵션 초기화 완료] 총 {len(global_options_data)}개 옵션 중 {existing_count}개 기존, {saved_count}개 신규 저장")
            return saved_count
            
    except Exception as e:
        print(f"[공통 옵션 초기화 실패] {e}")
        raise

def convert_platform_options_to_global(platform_options, platform):
    """플랫폼별 옵션 코드를 공통 옵션 코드로 변환합니다."""
       # kb_chachacha 69개
    if platform == 'kb_chachacha':
        OPTION_CODE_MAPPING = {
            # 외관/내장 (039110)
            '100130': 'SUNROOF',                # 썬루프(일반)
            '200130': 'SUNROOF_PANORAMA',       # 썬루프(파노라마)
            '200110': 'POWER_MIRROR',           # 전동접이식 사이드 미러
            '700370': 'MIRROR_TURN_SIGNAL',     # 방향지시등 일체형 사이드 미러
            '700380': 'MIRROR_REVERSE_TILT',    # 후진각도조절 사이드 미러
            '100140': 'HEADLIGHT_HID',          # 헤드램프(HID)
            '700400': 'HEADLIGHT_LED',          # 헤드램프(LED)
            '700390': 'POWER_STEERING_ADJUST',  # 텔레스코프 스티어링 휠
            '500210': 'HEATED_STEERING',        # 열선 스티어링 휠
            '300110': 'STEERING_REMOTE',        # 스티어링 휠 리모컨
            '300190': 'PADDLE_SHIFT',           # 패들시프트
            '200100': 'ALUMINUM_WHEEL',         # 알루미늄휠
            '500140': 'HIGHPASS',               # 하이패스
            '200140': 'ROOF_RACK',              # 루프랙
            '700190': 'CURTAIN_REAR_SEAT',      # 전동햇빛가리개
            '700260': 'GHOST_DOOR',             # 고스트 도어 클로징
            '500200': 'POWER_TRUNK',            # 전동트렁크
            '700110': 'HIGH_BEAM_ASSIST',       # 하이빔 어시스트
            '700140': 'ADAPTIVE_HEADLIGHT',     # 어댑티드 헤드램프
            
            # 시트 (039120)
            '300120': 'LEATHER_SEAT',           # 가죽시트
            '100100': 'HEATED_SEAT_FRONT',      # 열선시트(앞좌석)
            '700160': 'HEATED_SEAT_REAR',       # 열선시트(뒷좌석)
            '100110': 'VENTILATED_SEAT_DRIVER', # 통풍시트(운전석)
            '700200': 'VENTILATED_SEAT_PASSENGER', # 통풍시트(동승석)
            '700210': 'VENTILATED_SEAT_REAR',   # 통풍시트(뒷좌석)
            '300130': 'POWER_SEAT_DRIVER',      # 전동시트(운전석)
            '300140': 'POWER_SEAT_PASSENGER',   # 전동시트(동승석)
            '300150': 'POWER_SEAT_REAR',        # 전동시트(뒷좌석)
            '300160': 'MEMORY_SEAT_DRIVER',     # 메모리시트(운전석)
            '700150': 'MEMORY_SEAT_PASSENGER',  # 메모리시트(동승석)
            '300170': 'MASSAGE_SEAT',           # 안마시트
            
            # 안전 (039130)
            '400100': 'AIRBAG_DRIVER',          # 에어백(운전석)
            '400110': 'AIRBAG_PASSENGER',       # 에어백(동승석)
            '100170': 'AIRBAG_SIDE',            # 에어백(사이드&커튼)
            '700220': 'AIRBAG_KNEE',             # 에어백(무릎)
            '400190': 'LDWS',                   # 차선이탈경보(LDWS)
            '700410': 'LKAS',                   # 차선유지지원(LKAS)
            '700420': 'BLIND_SPOT_WARNING',     # 후측방 경보시스템(BSD)
            '700430': 'FCW',                    # 전방추돌경고(FCW)
            '400130': 'AROUND_VIEW',            # 어라운드뷰(AVM)
            '700250': 'AEB',                    # 자동긴급제동(AEB)
            '400150': 'ABS',                    # 브레이크 잠김 방지(ABS)
            '400170': 'TCS',                    # 미끄럼방지(TCS)
            '400180': 'ESC',                    # 차체자세제어장치(ESC)
            '700440': 'HAS',                    # 경사로 밀림방지(HAS)
            '400160': 'ECS',                    # 전자제어 서스펜션(ECS)
            '400210': 'TPMS',                   # 타이어 공기압감지(TPMS)
            '700230': 'PARKING_SENSOR_FRONT',   # 주차감지센서(전방)
            '100120': 'PARKING_SENSOR_REAR',    # 주차감지센서(후방)
            '700240': 'FRONT_CAMERA',           # 전방카메라
            '400120': 'REAR_CAMERA',            # 후방카메라
            '700450': 'SAFETY_WINDOW',          # 세이프티 윈도우
            '700460': 'ACTIVE_HEADREST',        # 액티브 헤드레스트
            
            # 편의/멀티미디어 (039140)
            '100160': 'NAVIGATION',             # 내비게이션(순정)
            '700310': 'NAVIGATION_AFTERMARKET', # 내비게이션 (비순정)
            '500190': 'CRUISE_CONTROL',         # 크루즈컨트롤(일반)
            '700470': 'ADAPTIVE_CRUISE',        # 크루즈컨트롤(어댑티브)
            '500150': 'AUTO_PARKING',           # 자동주차시스템(ASPAS)
            '500170': 'HUD',                    # 헤드업 디스플레이(HUD)
            '500160': 'EPB',                    # 전자식주차브레이크(EPB)
            '100150': 'SMART_KEY',              # 스마트키
            '500120': 'AUTO_AC',                # 풀오토에어컨
            '500230': 'RAIN_SENSOR',            # 레인센서와이퍼
            '600100': 'CD_PLAYER',              # CD플레이어
            '600150': 'USB_PORT',               # USB
            '700320': 'BLUETOOTH',              # 블루투스
            '600180': 'REAR_AV_MONITOR',        # 뒷좌석모니터
            '600140': 'AUX_PORT',               # AUX
            '500180': 'POWER_STEERING',         # 파워 스티어링
        }
    else:  # encar 62개
        OPTION_CODE_MAPPING = {
            # 외관/내장
            '010': 'SUNROOF',                    # 선루프
            '029': 'HEADLIGHT_HID',              # 헤드램프(HID)
            '075': 'HEADLIGHT_LED',              # 헤드램프(LED)
            '059': 'POWER_TRUNK',                # 파워 전동 트렁크
            '080': 'GHOST_DOOR',                 # 고스트 도어 클로징
            '024': 'POWER_MIRROR',               # 전동접이 사이드 미러
            '017': 'ALUMINUM_WHEEL',             # 알루미늄 휠
            '062': 'ROOF_RACK',                  # 루프랙
            '082': 'HEATED_STEERING',            # 열선 스티어링 휠
            '083': 'POWER_STEERING_ADJUST',      # 전동 조절 스티어링 휠
            '084': 'PADDLE_SHIFT',               # 패들 시프트
            '031': 'STEERING_REMOTE',            # 스티어링 휠 리모컨
            '030': 'ECM_MIRROR',                 # ECM 루미러
            '074': 'HIGHPASS',                   # 하이패스
            '006': 'POWER_DOORLOCK',             # 파워 도어록
            '008': 'POWER_STEERING',             # 파워 스티어링 휠
            '007': 'POWER_WINDOW',               # 파워 윈도우
            
            # 안전
            '026': 'AIRBAG_DRIVER',              # 에어백(운전석)
            '027': 'AIRBAG_PASSENGER',           # 에어백(동승석)
            '020': 'AIRBAG_SIDE',                # 에어백(사이드)
            '056': 'AIRBAG_CURTAIN',             # 에어백(커튼)
            '001': 'ABS',                        # 브레이크 잠김 방지(ABS)
            '019': 'TCS',                        # 미끄럼 방지(TCS)
            '055': 'ESC',                        # 차체자세 제어장치(ESC)
            '033': 'TPMS',                       # 타이어 공기압센서(TPMS)
            '088': 'LDWS',                       # 차선이탈 경보 시스템(LDWS)
            '002': 'ECS',                        # 전자제어 서스펜션(ECS)
            '085': 'PARKING_SENSOR_FRONT',       # 주차감지센서(전방)
            '032': 'PARKING_SENSOR_REAR',        # 주차감지센서(후방)
            '086': 'BLIND_SPOT_WARNING',         # 후측방 경보 시스템
            '058': 'REAR_CAMERA',                # 후방 카메라
            '087': 'AROUND_VIEW',                # 360도 어라운드 뷰
            
            # 편의/멀티미디어
            '068': 'CRUISE_CONTROL',             # 크루즈 컨트롤(일반)
            '079': 'ADAPTIVE_CRUISE',            # 크루즈 컨트롤(어댑티브)
            '095': 'HUD',                        # 헤드업 디스플레이(HUD)
            '094': 'EPB',                        # 전자식 주차브레이크(EPB)
            '023': 'AUTO_AC',                    # 자동 에어컨
            '057': 'SMART_KEY',                  # 스마트키
            '015': 'WIRELESS_DOORLOCK',          # 무선도어 잠금장치
            '081': 'RAIN_SENSOR',                # 레인센서
            '097': 'AUTO_LIGHT',                 # 오토 라이트
            '092': 'CURTAIN_REAR_SEAT',          # 커튼/블라인드(뒷좌석)
            '093': 'CURTAIN_REAR',               # 커튼/블라인드(후방)
            '089': 'POWER_SEAT_REAR',            # 전동시트(뒷좌석)
            '005': 'NAVIGATION',                 # 내비게이션
            '004': 'FRONT_AV_MONITOR',           # 앞좌석 AV 모니터
            '054': 'REAR_AV_MONITOR',            # 뒷좌석 AV 모니터
            '096': 'BLUETOOTH',                  # 블루투스
            '003': 'CD_PLAYER',                  # CD 플레이어
            '072': 'USB_PORT',                   # USB 단자
            '071': 'AUX_PORT',                   # AUX 단자
            
            # 시트
            '014': 'LEATHER_SEAT',               # 가죽시트
            '021': 'POWER_SEAT_DRIVER',          # 전동시트(운전석)
            '035': 'POWER_SEAT_PASSENGER',       # 전동시트(동승석)
            '022': 'HEATED_SEAT_FRONT',          # 열선시트(앞좌석)
            '063': 'HEATED_SEAT_REAR',           # 열선시트(뒷좌석)
            '051': 'MEMORY_SEAT_DRIVER',         # 메모리 시트(운전석)
            '078': 'MEMORY_SEAT_PASSENGER',      # 메모리 시트(동승석)
            '034': 'VENTILATED_SEAT_DRIVER',     # 통풍시트(운전석)
            '077': 'VENTILATED_SEAT_PASSENGER',  # 통풍시트(동승석)
            '090': 'VENTILATED_SEAT_REAR',       # 통풍시트(뒷좌석)
            '091': 'MASSAGE_SEAT'                # 마사지 시트
        }
    
    # 최적화: set을 사용한 중복 제거
    global_options = set()
    for platform_code in platform_options:
        global_code = OPTION_CODE_MAPPING.get(platform_code)
        if global_code:
            global_options.add(global_code)
    
    return list(global_options)

