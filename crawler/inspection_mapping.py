# =============================================================================
# 검사 항목 일반화 매핑 (엔카 + 차차차 공통)
# =============================================================================

# =============================================================================
# 상태 코드 → 일반화 Enum 매핑 (INNER 전용)
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

# 상태 텍스트 → 일반화 Enum 매핑 (INNER 전용, 차차차용)
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
# 외판/골격 랭크 매핑 (OUTER)
# =============================================================================

RANK_MAPPING = {
    'RANK_ONE': 'OUTER_1',
    'RANK_TWO': 'OUTER_2',
    'RANK_A': 'STRUCT_A',
    'RANK_B': 'STRUCT_B',
    'RANK_C': 'STRUCT_C',
}

# =============================================================================
# 외판/골격 손상 유형 매핑 (OUTER) - 엔카 + 차차차 공통
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
# 공통 검사 항목 코드 (INNER) - 플랫폼 독립적
# =============================================================================

COMMON_INNER_ITEMS = {
    # 자기진단 (OBD)
    'obd_engine': '자기진단-원동기',
    'obd_transmission': '자기진단-변속기',
    
    # 원동기
    'engine_idle_state': '작동상태(공회전)',
    'engine_rocker_cover': '실린더 커버(로커암 커버)',
    'engine_cylinder_head_gasket': '실린더 헤드/개스킷',
    'engine_cylinder_block_oil_pan': '실린더 블록/오일팬',
    'engine_oil_volume': '오일 유량',
    'coolant_cylinder_head_gasket': '냉각수-실린더 헤드/개스킷',
    'coolant_water_pump': '냉각수-워터펌프',
    'coolant_radiator': '냉각수-라디에이터',
    'coolant_volume': '냉각수 수량',
    'engine_common_rail': '커먼레일',
    
    # 변속기 (자동)
    'at_oil_leak': '자동변속기-오일누유',
    'at_oil_volume_state': '자동변속기-오일유량 및 상태',
    'at_idle_state': '자동변속기-작동상태(공회전)',
    
    # 변속기 (수동)
    'mt_oil_leak': '수동변속기-오일누유',
    'mt_gear_device': '수동변속기-기어변속장치',
    'mt_oil_volume_state': '수동변속기-오일유량 및 상태',
    'mt_idle_state': '수동변속기-작동상태(공회전)',
    
    # 동력전달
    'power_clutch_assembly': '클러치 어셈블리',
    'power_cv_joint': '등속조인트',
    'power_shaft_bearing': '추진축 및 베어링',
    'power_differential_gear': '디퍼렌셜 기어',
    
    # 조향
    'steering_oil_leak': '동력조향 작동 오일 누유',
    'steering_pump': '스티어링 펌프',
    'steering_gear': '스티어링 기어(MDPS포함)',
    'steering_joint': '스티어링 조인트',
    'steering_high_pressure_hose': '파워고압호스',
    'steering_tie_rod_ball_joint': '타이로드엔드 및 볼 조인트',
    
    # 제동
    'brake_master_cylinder_oil_leak': '브레이크 마스터 실린더오일 누유',
    'brake_oil_leak': '브레이크 오일 누유',
    'brake_servo_state': '배력장치 상태',
    
    # 전기
    'electric_generator_output': '발전기 출력',
    'electric_starting_motor': '시동 모터',
    'electric_wiper_motor': '와이퍼 모터 기능',
    'electric_inside_motor': '실내송풍 모터',
    'electric_radiator_fan_motor': '라디에이터 팬 모터',
    'electric_window_motor': '윈도우 모터',
    
    # 연료
    'fuel_leak': '연료누출(LP가스포함)',
    
    # 전동화 (EV/HEV - 차차차)
    'ev_charging_port_insulation': '충전구 절연',
    'ev_drive_shaft_insulation': '구동축 절연',
    'ev_wiring_state': '고전압 배선 상태',
}

# =============================================================================
# 공통 외판/골격 부위 코드 (OUTER) - 플랫폼 독립적
# =============================================================================

COMMON_OUTER_PARTS = {
    # 1랭크 외판
    'hood': '후드',
    'front_bumper': '프론트 범퍼',
    'fender_fl': '프론트 휀더(좌)',
    'fender_fr': '프론트 휀더(우)',
    'door_fl': '프론트 도어(좌)',
    'door_fr': '프론트 도어(우)',
    'door_rl': '리어 도어(좌)',
    'door_rr': '리어 도어(우)',
    'trunk_lid': '트렁크 리드',
    'rear_bumper': '리어 범퍼',
    'radiator_support': '라디에이터 서포트(볼트체결부품)',
    
    # 2랭크 외판
    'quarter_panel_l': '쿼터 패널(좌)',
    'quarter_panel_r': '쿼터 패널(우)',
    'roof_panel': '루프 패널',
    'side_sill_panel_l': '사이드 실 패널(좌)',
    'side_sill_panel_r': '사이드 실 패널(우)',
    
    # A랭크 골격
    'front_panel': '프론트 패널',
    'cross_member': '크로스 멤버',
    'inside_panel_l': '인사이드 패널(좌)',
    'inside_panel_r': '인사이드 패널(우)',
    'side_member_l': '사이드 멤버(좌)',
    'side_member_r': '사이드 멤버(우)',
    'wheel_house_l': '휠하우스(좌)',
    'wheel_house_r': '휠하우스(우)',
    'dash_panel': '대쉬 패널',
    'floor_panel': '플로어 패널',
    
    # B, C랭크 골격
    'pillar_a_l': '필러 패널 A(좌)',
    'pillar_a_r': '필러 패널 A(우)',
    'pillar_b_l': '필러 패널 B(좌)',
    'pillar_b_r': '필러 패널 B(우)',
    'pillar_c_l': '필러 패널 C(좌)',
    'pillar_c_r': '필러 패널 C(우)',
    'package_tray': '패키지 트레이',
    'rear_panel': '리어 패널',
    'trunk_floor': '트렁크 플로어',
    'side_member_rear_l': '사이드 멤버 리어(좌)',
    'side_member_rear_r': '사이드 멤버 리어(우)',
    
    # 기타 부품 (차차차 전용)
    'headlamp_fl': '헤드램프(좌)',
    'headlamp_fr': '헤드램프(우)',
    'tire_fl': '타이어(운전석 앞)',
    'tire_fr': '타이어(동반석 앞)',
    'tire_rl': '타이어(운전석 뒤)',
    'tire_rr': '타이어(동반석 뒤)',
    'wheel_fl': '휠(운전석 앞)',
    'wheel_fr': '휠(동반석 앞)',
    'wheel_rl': '휠(운전석 뒤)',
    'wheel_rr': '휠(동반석 뒤)',
    'windshield_front': '앞유리',
    'windshield_rear': '뒷유리',
    'mirror_l': '백미러(좌)',
    'mirror_r': '백미러(우)',
    'taillight_l': '리어콤비램프(좌)',
    'taillight_r': '리어콤비램프(우)',
}

# =============================================================================
# 엔카 → 공통 코드 매핑 (INNER)
# =============================================================================

ENCAR_INNER_MAPPING = {
    # S00: 자기진단
    's001': 'obd_engine',
    's002': 'obd_transmission',
    
    # S01: 원동기
    's003': 'engine_idle_state',
    's004': 'engine_rocker_cover',
    's005': 'engine_cylinder_head_gasket',
    's006': 'engine_cylinder_block_oil_pan',
    's007': 'engine_oil_volume',
    's008': 'coolant_cylinder_head_gasket',
    's009': 'coolant_water_pump',
    's010': 'coolant_radiator',
    's011': 'coolant_volume',
    's012': 'engine_common_rail',
    
    # S02: 변속기
    's013': 'at_oil_leak',
    's014': 'at_oil_volume_state',
    's015': 'at_idle_state',
    's016': 'mt_oil_leak',
    's017': 'mt_gear_device',
    's018': 'mt_oil_volume_state',
    's019': 'mt_idle_state',
    
    # S03: 동력전달
    's020': 'power_clutch_assembly',
    's021': 'power_cv_joint',
    's022': 'power_shaft_bearing',
    's037': 'power_differential_gear',
    
    # S04: 조향
    's023': 'steering_oil_leak',
    's025': 'steering_pump',
    's024': 'steering_gear',
    's038': 'steering_joint',
    's039': 'steering_high_pressure_hose',
    's026': 'steering_tie_rod_ball_joint',
    
    # S05: 제동
    's027': 'brake_master_cylinder_oil_leak',
    's028': 'brake_oil_leak',
    's029': 'brake_servo_state',
    
    # S06: 전기
    's030': 'electric_generator_output',
    's031': 'electric_starting_motor',
    's032': 'electric_wiper_motor',
    's033': 'electric_inside_motor',
    's034': 'electric_radiator_fan_motor',
    's035': 'electric_window_motor',
    
    # S07: 연료
    's036': 'fuel_leak',
}

# =============================================================================
# 엔카 → 공통 코드 매핑 (OUTER)
# =============================================================================

ENCAR_OUTER_MAPPING = {
    # 1랭크 외판
    'P011': 'hood',
    'P012': 'front_bumper',
    'P021': 'fender_fl',
    'P022': 'fender_fr',
    'P031': 'door_fl',
    'P032': 'door_fr',
    'P033': 'door_rl',
    'P034': 'door_rr',
    'P041': 'trunk_lid',
    'P042': 'rear_bumper',
    'P051': 'radiator_support',
    
    # 2랭크 외판
    'P061': 'quarter_panel_l',
    'P062': 'quarter_panel_r',
    'P071': 'roof_panel',
    'P081': 'side_sill_panel_l',
    'P082': 'side_sill_panel_r',
    
    # A랭크 골격
    'PA11': 'front_panel',
    'PA21': 'cross_member',
    'PA31': 'inside_panel_l',
    'PA32': 'inside_panel_r',
    'PA41': 'side_member_l',
    'PA42': 'side_member_r',
    'PA51': 'wheel_house_l',
    'PA52': 'wheel_house_r',
    'PA61': 'dash_panel',
    'PA71': 'floor_panel',
    
    # B, C랭크 골격
    'PB11': 'pillar_a_l',
    'PB12': 'pillar_a_r',
    'PB21': 'pillar_b_l',
    'PB22': 'pillar_b_r',
    'PB31': 'pillar_c_l',
    'PB32': 'pillar_c_r',
    'PB41': 'package_tray',
    'PB51': 'rear_panel',
    'PB61': 'trunk_floor',
    'PB71': 'side_member_rear_l',
    'PB72': 'side_member_rear_r',
    
    # P14x 체계 (필러 패널 - B랭크)
    'P141': 'pillar_a_l',      # 필러 패널(앞)(좌)
    'P142': 'pillar_b_l',      # 필러 패널(중)(좌) - 추정
    'P143': 'pillar_c_l',      # 필러 패널(뒤)(좌)
    'P144': 'pillar_a_r',      # 필러 패널(앞)(우)
    'P145': 'pillar_b_r',      # 필러 패널(중)(우) - 추정
    'P146': 'pillar_c_r',      # 필러 패널(뒤)(우)
    
    # P1xx 체계 (A랭크 골격 - 추가 코드)
    'P111': 'inside_panel_l',  # 인사이드 패널(좌)
    'P112': 'inside_panel_r',  # 인사이드 패널(우) - 추정
    'P171': 'trunk_floor',     # 트렁크 플로어
    'P181': 'rear_panel',      # 리어 패널
}

# =============================================================================
# 차차차 → 공통 코드 매핑 (INNER)
# =============================================================================

CHACHA_INNER_MAPPING = {
    # 원동기
    'motorRunState': 'engine_idle_state',
    'rockerArmCover': 'engine_rocker_cover',
    'motorCylinderHead': 'engine_cylinder_head_gasket',
    'motorCylinderBlock': 'engine_cylinder_block_oil_pan',
    'oilPan': 'engine_cylinder_block_oil_pan',  # 중복 매핑
    'motorOilVolumPollution': 'engine_oil_volume',
    'motorCwCylinderGasket': 'coolant_cylinder_head_gasket',
    'motorCwCylinderBlock': 'coolant_cylinder_head_gasket',  # 중복 매핑
    'motorCwWaterPump': 'coolant_water_pump',
    'motorCwRadiator': 'coolant_radiator',
    'motorCwOilVolumePollution': 'coolant_volume',
    'motorHighCompressPump': 'engine_common_rail',
    'motorCompressState': 'engine_idle_state',  # 압축상태도 작동상태로
    
    # 변속기 (자동)
    'atOilLeak': 'at_oil_leak',
    'atOilVolumeSate': 'at_oil_volume_state',
    'atRunState': 'at_idle_state',
    'atStoleDrive': 'at_idle_state',  # 중복 매핑
    'atStoleRear': 'at_idle_state',   # 중복 매핑
    
    # 변속기 (수동)
    'mtOilLeak': 'mt_oil_leak',
    'mtDevice': 'mt_gear_device',
    'mtOilVolumeSate': 'mt_oil_volume_state',
    'mtRunState': 'mt_idle_state',
    
    # 동력전달
    'powerClutchAssembly': 'power_clutch_assembly',
    'powerCVJoint': 'power_cv_joint',
    'powerShaftBearing': 'power_shaft_bearing',
    'differentialGbn': 'power_differential_gear',
    
    # 조향
    'steeringOilVolumeLeak': 'steering_oil_leak',
    'steeringPump': 'steering_pump',
    'steeringGear': 'steering_gear',
    'steeringJointGbn': 'steering_joint',
    'powerHighPressureGbn': 'steering_high_pressure_hose',
    'steeringTieLoadEndBallJoint': 'steering_tie_rod_ball_joint',
    
    # 제동
    'brakeMasterCylinderOilLeak': 'brake_master_cylinder_oil_leak',
    'breakOilLeak': 'brake_oil_leak',  # break 오타
    'breakServoState': 'brake_servo_state',
    'breakOilVolumeState': 'brake_oil_leak',  # 중복 매핑
    
    # 전기
    'electricPowerState': 'electric_generator_output',
    'electricStartingMotor': 'electric_starting_motor',
    'electricWiperMotor': 'electric_wiper_motor',
    'electricInsideMotor': 'electric_inside_motor',
    'electricRadiatorFanMotor': 'electric_radiator_fan_motor',
    'electricWindowMotorRun': 'electric_window_motor',
    'etcWindowMotorRun': 'electric_window_motor',  # 중복 매핑
    
    # 연료
    'etcGasLeak': 'fuel_leak',
    
    # 전동화 (EV/HEV)
    'chargeInsulationGbn': 'ev_charging_port_insulation',
    'driveShaftIsolationGbn': 'ev_drive_shaft_insulation',
    'wiringStateGbn': 'ev_wiring_state',
    
    # === HTML 폼 타입 (checkbox 필드명) ===
    # 자기진단
    'engine': 'obd_engine',           # engine_1, engine_2
    'transmission': 'obd_transmission',  # transmission_1, transmission_2
    
    # 원동기
    'engine_status': 'engine_idle_state',
    'engine_locker': 'engine_rocker_cover',
    'engine_head': 'engine_cylinder_head_gasket',
    'engine_oilfan': 'engine_cylinder_block_oil_pan',
    'engine_oilq': 'engine_oil_volume',
    'engine_cylinder': 'coolant_cylinder_head_gasket',
    'engine_pump': 'coolant_water_pump',
    'engine_radiator': 'coolant_radiator',
    'engine_waterq': 'coolant_volume',
    'engine_highpress': 'engine_common_rail',
    
    # 변속기 (자동)
    'at_oilleakage': 'at_oil_leak',
    'at_oilstatus': 'at_oil_volume_state',
    'at_status': 'at_idle_state',
    
    # 변속기 (수동)
    'mt_oilleakage': 'mt_oil_leak',
    'mt_trans': 'mt_gear_device',
    'mt_oilstatus': 'mt_oil_volume_state',
    'mt_status': 'mt_idle_state',
    
    # 동력전달
    'force_clutch': 'power_clutch_assembly',
    'force_joint': 'power_cv_joint',
    'force_bearing': 'power_shaft_bearing',
    'force_differentialgear': 'power_differential_gear',
    
    # 조향
    'steering_oilleakage': 'steering_oil_leak',
    'steering_pump': 'steering_pump',
    'steering_gear': 'steering_gear',
    'power_steeringjoint': 'steering_joint',
    'power_highpressurehose': 'steering_high_pressure_hose',
    'steering_joint': 'steering_tie_rod_ball_joint',
    
    # 제동
    'brake_cylinderoil': 'brake_master_cylinder_oil_leak',
    'brake_oilleakage': 'brake_oil_leak',
    'brake_status': 'brake_servo_state',
    
    # 전기
    'elec_output': 'electric_generator_output',
    'elec_motor': 'electric_starting_motor',
    'elec_wiper': 'electric_wiper_motor',
    'elec_wind': 'electric_inside_motor',
    'elec_fan': 'electric_radiator_fan_motor',
    'elec_window': 'electric_window_motor',
    
    # 고전원 전기장치
    'ress_insulationstatus': 'ev_charging_port_insulation',
    'ress_isolationstatus': 'ev_drive_shaft_insulation',
    'ress_wirestatus': 'ev_wiring_state',
    
    # 연료
    'etc_fuelleakage': 'fuel_leak',
}

# =============================================================================
# 차차차 → 공통 코드 매핑 (OUTER)
# =============================================================================

CHACHA_OUTER_MAPPING = {
    # === HTML 폼 타입 (checkbox 필드명) ===
    # 1랭크 외판
    'part_1lank_1': 'hood',                    # 1.후드
    'part_1lank_2': 'fender_fr',               # 2.프론트휀더 (좌우 통합, 우측으로 매핑)
    'part_1lank_3': 'door_fl',                 # 3.도어 (좌우 통합, 좌측 전방으로 매핑)
    'part_1lank_4': 'trunk_lid',               # 4.트렁크리드
    'part_1lank_5': 'radiator_support',        # 5.라디에이터 서포트
    
    # 2랭크 외판
    'part_2lank_6': 'quarter_panel_l',         # 6.쿼터패널 (좌측으로 매핑)
    'part_2lank_7': 'roof_panel',              # 7.루프패널
    'part_2lank_8': 'side_sill_panel_l',       # 8.사이드실 패널 (좌측으로 매핑)
    
    # A랭크 골격
    'main_alank_1': 'front_panel',             # 9.프론트패널
    'main_alank_2': 'cross_member',            # 10.크로스멤버
    'main_alank_3': 'inside_panel_l',          # 11.인사이드패널 (좌측으로 매핑)
    'main_alank_4': 'trunk_floor',             # 17.트렁크플로어
    'main_alank_5': 'rear_panel',              # 18.리어패널
    
    # B랭크 골격
    'main_blank_1': 'side_member_l',           # 12.사이드멤버 (좌측으로 매핑)
    'main_blank_2': 'wheel_house_l',           # 13.휠하우스 (좌측으로 매핑)
    'main_blank_3': 'pillar_a_l',              # 14.필러패널 (좌측으로 매핑)
    'main_blank_4': 'package_tray',            # 19.패키지트레이
    'main_blank_a': 'pillar_a_l',              # 필러패널 A
    'main_blank_b': 'pillar_b_l',              # 필러패널 B
    'main_blank_c': 'pillar_c_l',              # 필러패널 C
    
    # C랭크 골격
    'main_clank_1': 'dash_panel',              # 15.대쉬패널
    'main_clank_2': 'floor_panel',             # 16.플로어패널
    
    # === carplane_position 타입 (부위번호 매핑) ===
    # JavaScript $_mapping 및 $_partInfo 기반 정확한 매핑
    # 1랭크 외판
    'part-28': 'hood',                     # h01: 후드 (group 1)
    'part-27': 'hood',                     # h01: 후드 (sub)
    'part-22': 'fender_fl',                # h02: 프런트휀더 운전석 (group 2)
    'part-43': 'fender_fl',                # h02: 프런트휀더 운전석 (sub)
    'part-39': 'fender_fr',                # h03: 프런트휀더 동반석 (group 2)
    'part-59': 'fender_fr',                # h03: 프런트휀더 동반석 (sub)
    'part-82': 'door_fl',                  # h04: 도어 운전석앞 (group 3)
    'part-62': 'door_fl',                  # h04: 도어 운전석앞 (sub)
    'part-99': 'door_fr',                  # h05: 도어 동반석앞 (group 3)
    'part-79': 'door_fr',                  # h05: 도어 동반석앞 (sub)
    'part-102': 'door_rl',                 # h06: 도어 운전석뒤 (group 3)
    'part-122': 'door_rl',                 # h06: 도어 운전석뒤 (sub)
    'part-139': 'door_rr',                 # h07: 도어 동반석뒤 (group 3)
    'part-119': 'door_rr',                 # h07: 도어 동반석뒤 (sub)
    'part-168': 'trunk_lid',               # h08: 트렁크리드 (group 4)
    'part-167': 'trunk_lid',               # h08: 트렁크리드 (sub)
    'part-14': 'radiator_support',         # h09: 라디에터서포트패널 (group 5)
    'part-13': 'radiator_support',         # h09: 라디에터서포트패널 (sub)
    'part-8': 'front_bumper',              # h37: 앞범퍼
    'part-188': 'rear_bumper',             # h38: 뒷범퍼
    
    # 2랭크 외판
    'part-163': 'quarter_panel_l',         # h10: 쿼터패널 운전석 (group 6)
    'part-162': 'quarter_panel_l',         # h10: 쿼터패널 운전석 (sub)
    'part-179': 'quarter_panel_r',         # h11: 쿼터패널 동반석 (group 6)
    'part-199': 'quarter_panel_r',         # h11: 쿼터패널 동반석 (sub)
    'part-107': 'roof_panel',              # h12: 루프패널 (group 7)
    'part-108': 'roof_panel',              # h12: 루프패널 (sub)
    'part-81': 'side_sill_panel_l',        # h13: 사이드실패널 운전석 (group 8)
    'part-101': 'side_sill_panel_l',       # h13: 사이드실패널 운전석 (sub)
    'part-100': 'side_sill_panel_r',       # h14: 사이드실패널 동반석 (group 8)
    'part-120': 'side_sill_panel_r',       # h14: 사이드실패널 동반석 (sub)
    
    # A랭크 골격
    'part-33': 'front_panel',              # h15: 프런트패널 (group 9)
    'part-33-sub': 'front_panel',          # h15: 프런트패널 (sub)
    'part-73': 'cross_member',             # h33: 크로스멤버 (group 10)
    'part-73-sub': 'cross_member',         # h33: 크로스멤버 (sub)
    'part-32': 'inside_panel_l',           # h17: 인사이드패널 운전석 (group 11)
    'part-32-sub': 'inside_panel_l',       # h17: 인사이드패널 운전석 (sub)
    'part-34': 'inside_panel_r',           # h18: 인사이드패널 동반석 (group 11)
    'part-34-sub': 'inside_panel_r',       # h18: 인사이드패널 동반석 (sub)
    'part-53': 'side_member_l',            # h19: 사이드멤버 운전석앞 (group 12)
    'part-53-sub': 'side_member_l',        # h19: 사이드멤버 운전석앞 (sub)
    'part-54': 'side_member_l',            # h20: 사이드멤버 동반석앞 (group 12)
    'part-54-sub': 'side_member_l',        # h20: 사이드멤버 동반석앞 (sub)
    'part-172': 'side_member_r',           # h21: 사이드멤버 운전석뒤 (group 12)
    'part-172-sub': 'side_member_r',       # h21: 사이드멤버 운전석뒤 (sub)
    'part-174': 'side_member_r',           # h22: 사이드멤버 동반석뒤 (group 12)
    'part-174-sub': 'side_member_r',       # h22: 사이드멤버 동반석뒤 (sub)
    'part-52': 'wheel_house_l',            # h23: 휠하우스 운전석앞 (group 13)
    'part-52-sub': 'wheel_house_l',        # h23: 휠하우스 운전석앞 (sub)
    'part-55': 'wheel_house_l',            # h24: 휠하우스 동반석앞 (group 13)
    'part-55-sub': 'wheel_house_l',        # h24: 휠하우스 동반석앞 (sub)
    'part-152': 'wheel_house_r',           # h25: 휠하우스 운전석뒤 (group 13)
    'part-152-sub': 'wheel_house_r',       # h25: 휠하우스 운전석뒤 (sub)
    'part-154': 'wheel_house_r',           # h26: 휠하우스 동반석뒤 (group 13)
    'part-154-sub': 'wheel_house_r',       # h26: 휠하우스 동반석뒤 (sub)
    'part-173': 'trunk_floor',             # h35: 트렁크플로어 (group 17)
    'part-173-sub': 'trunk_floor',         # h35: 트렁크플로어 (sub)
    'part-194': 'rear_panel',              # h36: 리어패널 (group 18)
    'part-193': 'rear_panel',              # h36: 리어패널 (sub)
    
    # B랭크 골격
    'part-63': 'pillar_a_l',               # h27: A필러 운전석 (group 14)
    'part-84': 'pillar_a_l',               # h27: A필러 운전석 (sub)
    'part-78': 'pillar_a_r',               # h28: A필러 동반석 (group 14)
    'part-97': 'pillar_a_r',               # h28: A필러 동반석 (sub)
    'part-103': 'pillar_b_l',              # h29: B필러 운전석 (group 14)
    'part-104': 'pillar_b_l',              # h29: B필러 운전석 (sub)
    'part-118': 'pillar_b_r',              # h30: B필러 동반석 (group 14)
    'part-117': 'pillar_b_r',              # h30: B필러 동반석 (sub)
    'part-144': 'pillar_c_l',              # h31: C필러 운전석 (group 14)
    'part-124': 'pillar_c_l',              # h31: C필러 운전석 (sub)
    'part-137': 'pillar_c_r',              # h32: C필러 동반석 (group 14)
    'part-157': 'pillar_c_r',              # h32: C필러 동반석 (sub)
    'part-153': 'package_tray',            # h61: 패키지트레이 (group 27)
    'part-153-sub': 'package_tray',        # h61: 패키지트레이 (sub)
    
    # C랭크 골격
    'part-74': 'dash_panel',               # h60: 대쉬패널 (group 26)
    'part-74-sub': 'dash_panel',           # h60: 대쉬패널 (sub)
    'part-94': 'floor_panel',              # h34: 플로어패널 (group 16)
    'part-93': 'floor_panel',              # h34: 플로어패널 (sub)
    
    # 기타 부위 (세부)
    'part-1': 'headlamp_fl',               # h43: 운전석 헤드램프
    'part-20': 'headlamp_fr',              # h44: 동반석 헤드램프
    'part-21': 'tire_fl',                  # h51: 운전석 앞 타이어
    'part-40': 'tire_fr',                  # h52: 동반석 앞 타이어
    'part-141': 'tire_rl',                 # h53: 운전석 뒤 타이어
    'part-180': 'tire_rr',                 # h54: 동반석 뒤 타이어
    'part-42': 'wheel_fl',                 # h55: 운전석 앞 휠
    'part-60': 'wheel_fr',                 # h56: 동반석 앞 휠
    'part-142': 'wheel_rl',                # h57: 운전석 뒤 휠
    'part-160': 'wheel_rr',                # h58: 동반석 뒤 휠
    'part-68': 'windshield_front',         # h39: 앞유리
    'part-66': 'mirror_l',                 # h41: 운전석 백미러
    'part-69': 'mirror_r',                 # h42: 동반석 백미러
    'part-148': 'windshield_rear',         # h40: 뒤유리
    'part-183': 'taillight_l',             # h45: 운전석 백라이트
    'part-198': 'taillight_r',             # h46: 동반석 백라이트
}

# =============================================================================
# 보증 유형 매핑 (공통화)
# =============================================================================

GUARANTY_TYPE_MAPPING = {
    # 엔카
    '1': 'SELF',           # 자가보증
    '2': 'INSURANCE',      # 보험사보증
    
    # 차차차 (필드명)
    'guarantee_type_1': 'SELF',      # 자가보증
    'guarantee_type_2': 'INSURANCE',  # 보험사보증
}

# =============================================================================
# 헬퍼 함수
# =============================================================================

def normalize_guaranty_type(guaranty_code: str = None, form_data: dict = None) -> str:
    """
    보증 유형을 공통 코드로 변환
    
    Args:
        guaranty_code: 엔카 보증 코드 ('1', '2')
        form_data: 차차차 폼 데이터 (guarantee_type_1, guarantee_type_2 체크 확인)
    
    Returns:
        str: 'SELF', 'INSURANCE' 또는 None
    """
    # 엔카
    if guaranty_code:
        return GUARANTY_TYPE_MAPPING.get(guaranty_code)
    
    # 차차차
    if form_data:
        if form_data.get('guarantee_type_1') == 'V':
            return 'SELF'
        elif form_data.get('guarantee_type_2') == 'V':
            return 'INSURANCE'
    
    return None

def normalize_status(status_code: str, status_title: str = None) -> dict:
    """
    상태 코드/텍스트를 일반화 Enum으로 변환 (INNER 전용)
    
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
    외판/골격 랭크를 일반화 (OUTER 전용)
    
    Args:
        rank_attribute: 'RANK_ONE', 'RANK_A' 등
    
    Returns:
        str: 'OUTER_1', 'STRUCT_A' 등
    """
    return RANK_MAPPING.get(rank_attribute)

def normalize_damage_types(status_codes: list) -> dict:
    """
    손상 유형 코드들을 Boolean 플래그로 변환 (OUTER 전용)
    
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

def map_to_common_inner_code(platform_code: str, platform: str) -> str:
    """
    플랫폼별 INNER 코드를 공통 코드로 변환
    
    Args:
        platform_code: 플랫폼별 코드 ('s004', 'rockerArmCover' 등)
        platform: 'encar' 또는 'chacha'
    
    Returns:
        str: 공통 코드 ('engine_rocker_cover' 등) 또는 원본 코드 (매핑 없을 시)
    """
    if platform == 'encar':
        return ENCAR_INNER_MAPPING.get(platform_code, platform_code)
    elif platform == 'chacha':
        return CHACHA_INNER_MAPPING.get(platform_code, platform_code)
    return platform_code

def map_to_common_outer_code(platform_code: str, platform: str) -> str:
    """
    플랫폼별 OUTER 코드를 공통 코드로 변환
    
    Args:
        platform_code: 플랫폼별 코드 ('P011', 차차차 carCheck 파싱 결과 등)
        platform: 'encar' 또는 'chacha'
    
    Returns:
        str: 공통 코드 ('hood' 등) 또는 원본 코드 (매핑 없을 시)
    """
    if platform == 'encar':
        return ENCAR_OUTER_MAPPING.get(platform_code, platform_code)
    elif platform == 'chacha':
        return CHACHA_OUTER_MAPPING.get(platform_code, platform_code)
    return platform_code

def get_common_item_name(common_code: str, detail_type: str) -> str:
    """
    공통 코드로 한글명 조회
    
    Args:
        common_code: 공통 코드 ('engine_rocker_cover', 'hood' 등)
        detail_type: 'INNER' 또는 'OUTER'
    
    Returns:
        str: 한글명 ('실린더 커버', '후드' 등) 또는 원본 코드 (매핑 없을 시)
    """
    if detail_type == 'INNER':
        return COMMON_INNER_ITEMS.get(common_code, common_code)
    elif detail_type == 'OUTER':
        return COMMON_OUTER_PARTS.get(common_code, common_code)
    return common_code

def parse_chacha_html_field(field_name: str, field_value: str, form_data: dict) -> tuple:
    """
    차차차 HTML 폼 필드를 파싱하여 (공통코드, 상태) 반환
    
    Args:
        field_name: 필드명 (예: 'engine_status_1', 'part_1lank_2')
        field_value: 필드값 (예: 'V' 또는 '')
        form_data: 전체 폼 데이터 (다른 필드 참조 필요 시)
    
    Returns:
        tuple: (common_code, status_dict) 또는 (None, None)
        - common_code: 공통 항목 코드
        - status_dict: {'good_bad': 'GOOD'} 또는 {'leak_level': 'NONE'} 등
    
    Example:
        parse_chacha_html_field('engine_status_1', 'V', {...})
        → ('engine_idle_state', {'good_bad': 'GOOD'})
    """
    if field_value != 'V':
        return (None, None)
    
    # 필드명에서 번호 추출
    parts = field_name.rsplit('_', 1)
    if len(parts) != 2:
        return (None, None)
    
    base_name, option_num = parts[0], parts[1]
    
    # INNER 항목 처리
    if base_name in CHACHA_INNER_MAPPING:
        common_code = CHACHA_INNER_MAPPING[base_name]
        
        # 상태 결정 (option_num에 따라)
        status_map = {
            # 양호/불량 패턴
            '1': {'good_bad': 'GOOD'},
            '2': {'good_bad': 'BAD'},
        }
        
        # 누유/누수 패턴 (1:없음, 2:미세, 3:누유/누수)
        if 'leak' in common_code or 'oil' in base_name.lower():
            status_map = {
                '1': {'leak_level': 'NONE'},
                '2': {'leak_level': 'MINOR'},
                '3': {'leak_level': 'LEAK'},
            }
        
        # 적정/부족/과다 패턴 (1:적정, 2:부족, 3:과다)
        if 'volume' in common_code or 'oilq' in base_name or 'waterq' in base_name or 'oilstatus' in base_name:
            status_map = {
                '1': {'level_state': 'ADEQ'},
                '2': {'level_state': 'LACK'},
                '3': {'level_state': 'OVER'},
            }
        
        status_dict = status_map.get(option_num, {})
        return (common_code, status_dict)
    
    # OUTER 항목 처리
    if base_name in CHACHA_OUTER_MAPPING:
        common_code = CHACHA_OUTER_MAPPING[base_name]
        # 외판은 체크박스만 있고 상태는 별도 처리 (carplane_position)
        return (common_code, {})
    
    return (None, None)

# JavaScript $_mapping을 Python dict로 변환 (hNN → common_code)
HNN_TO_COMMON_CODE = {
    'h01': 'hood',                    # 후드
    'h02': 'fender_fl',               # 프런트휀더 운전석
    'h03': 'fender_fr',               # 프런트휀더 동반석
    'h04': 'door_fl',                 # 도어 운전석앞
    'h05': 'door_fr',                 # 도어 동반석앞
    'h06': 'door_rl',                 # 도어 운전석뒤
    'h07': 'door_rr',                 # 도어 동반석뒤
    'h08': 'trunk_lid',               # 트렁크리드
    'h09': 'radiator_support',        # 라디에터서포트패널
    'h10': 'quarter_panel_l',         # 쿼터패널 운전석
    'h11': 'quarter_panel_r',         # 쿼터패널 동반석
    'h12': 'roof_panel',              # 루프패널
    'h13': 'side_sill_panel_l',       # 사이드실패널 운전석
    'h14': 'side_sill_panel_r',       # 사이드실패널 동반석
    'h15': 'front_panel',             # 프런트패널
    'h17': 'inside_panel_l',          # 인사이드패널 운전석
    'h18': 'inside_panel_r',          # 인사이드패널 동반석
    'h19': 'side_member_l',           # 사이드멤버 운전석앞
    'h20': 'side_member_l',           # 사이드멤버 동반석앞
    'h21': 'side_member_r',           # 사이드멤버 운전석뒤
    'h22': 'side_member_r',           # 사이드멤버 동반석뒤
    'h23': 'wheel_house_l',           # 휠하우스 운전석앞
    'h24': 'wheel_house_l',           # 휠하우스 동반석앞
    'h25': 'wheel_house_r',           # 휠하우스 운전석뒤
    'h26': 'wheel_house_r',           # 휠하우스 동반석뒤
    'h27': 'pillar_a_l',              # A필러 운전석
    'h28': 'pillar_a_r',              # A필러 동반석
    'h29': 'pillar_b_l',              # B필러 운전석
    'h30': 'pillar_b_r',              # B필러 동반석
    'h31': 'pillar_c_l',              # C필러 운전석
    'h32': 'pillar_c_r',              # C필러 동반석
    'h33': 'cross_member',            # 크로스멤버
    'h34': 'floor_panel',             # 플로어패널
    'h35': 'trunk_floor',             # 트렁크플로어
    'h36': 'rear_panel',              # 리어패널
    'h37': 'front_bumper',            # 앞범퍼
    'h38': 'rear_bumper',             # 뒷범퍼
    'h39': 'windshield_front',        # 앞유리
    'h40': 'windshield_rear',         # 뒤유리
    'h41': 'mirror_l',                # 백미러 운전석
    'h42': 'mirror_r',                # 백미러 동반석
    'h43': 'headlamp_fl',             # 헤드램프 운전석
    'h44': 'headlamp_fr',             # 헤드램프 동반석
    'h45': 'taillight_l',             # 리어콤비램프 운전석
    'h46': 'taillight_r',             # 리어콤비램프 동반석
    'h51': 'tire_fl',                 # 타이어 운전석 앞
    'h52': 'tire_fr',                 # 타이어 동반석 앞
    'h53': 'tire_rl',                 # 타이어 운전석 뒤
    'h54': 'tire_rr',                 # 타이어 동반석 뒤
    'h55': 'wheel_fl',                # 휠 운전석 앞
    'h56': 'wheel_fr',                # 휠 동반석 앞
    'h57': 'wheel_rl',                # 휠 운전석 뒤
    'h58': 'wheel_rr',                # 휠 동반석 뒤
    'h60': 'dash_panel',              # 대쉬패널
    'h61': 'package_tray',            # 패키지트레이
}

def parse_chacha_carplane_position(carplane_json: str, platform: str = 'chacha') -> list:
    """
    차차차 carplane_position JSON을 파싱하여 외판/골격 손상 리스트 반환
    
    Args:
        carplane_json: JSON 문자열 (예: '{"h02x":{"x":[13,10]}, "h06w":{"w":[6,14]}}')
        platform: 'chacha'
    
    Returns:
        list: [(common_code, damage_type, rank), ...]
        - common_code: 공통 부위 코드 ('fender_fl', 'door_rl' 등)
        - damage_type: 손상 유형 ('X', 'W', 'A', 'U', 'C', 'T')
        - rank: 랭크 (OUTER_1, OUTER_2, STRUCT_A, STRUCT_B)
    
    Example:
        parse_chacha_carplane_position('{"h02x":{"x":[13,10]}, "h06w":{"w":[6,14]}}')
        → [('fender_fl', 'X', 'OUTER_1'), ('door_rl', 'W', 'OUTER_1')]
    """
    import json
    
    if not carplane_json:
        return []
    
    try:
        data = json.loads(carplane_json)
    except:
        return []
    
    results = []
    
    for key, value in data.items():
        # key 형식: h02x (h + 부위번호(2자리) + 손상유형(1자리))
        if not key.startswith('h') or len(key) < 4:
            continue
        
        h_num = key[:-1]  # 'h02'
        damage_char = key[-1]  # 'x', 'w', 'a', 'u', 'c', 't'
        
        # hNN → 공통 코드 매핑
        common_code = HNN_TO_COMMON_CODE.get(h_num)
        if not common_code:
            continue
        
        # 손상 유형 매핑
        damage_type = damage_char.upper()  # 'X', 'W', 'A', 'U', 'C', 'T'
        
        # 랭크 추정 (공통 코드로 판단)
        rank = None
        if common_code in ['hood', 'front_bumper', 'fender_fl', 'fender_fr', 'door_fl', 'door_fr', 
                          'door_rl', 'door_rr', 'trunk_lid', 'rear_bumper', 'radiator_support']:
            rank = 'OUTER_1'
        elif common_code in ['quarter_panel_l', 'quarter_panel_r', 'roof_panel', 
                            'side_sill_panel_l', 'side_sill_panel_r']:
            rank = 'OUTER_2'
        elif common_code in ['front_panel', 'cross_member', 'inside_panel_l', 'inside_panel_r',
                            'side_member_l', 'side_member_r', 'wheel_house_l', 'wheel_house_r',
                            'dash_panel', 'floor_panel', 'trunk_floor', 'rear_panel']:
            rank = 'STRUCT_A'
        elif common_code in ['pillar_a_l', 'pillar_a_r', 'pillar_b_l', 'pillar_b_r',
                            'pillar_c_l', 'pillar_c_r', 'package_tray', 
                            'side_member_rear_l', 'side_member_rear_r']:
            rank = 'STRUCT_B'
        
        results.append((common_code, damage_type, rank))
    
    return results