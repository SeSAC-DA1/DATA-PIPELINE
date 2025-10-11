"""
차차차 크롤링 테스트 (10대만)
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from crawler.chacha_crawler import (
    build_session, get_maker_info, get_car_info_via_api,
    crawl_complete_car_info, save_car_info_to_db
)
from db.connection import session_scope
from db.model import Vehicle, create_tables_if_not_exist

if __name__ == "__main__":
    print("="*80)
    print("차차차 크롤링 테스트 (10대)")
    print("="*80)
    
    # DB 초기화
    create_tables_if_not_exist()
    
    # 세션 생성
    session = build_session()
    
    # 제조사 정보
    print("\n[1단계] 제조사 정보 수집...")
    makers = get_maker_info(session)
    if not makers:
        print("제조사 정보 수집 실패")
        exit(1)
    
    # 현대 차량 10대만 가져오기
    maker_code = None
    for maker in makers:
        if maker['makerName'] == '현대':
            maker_code = maker['makerCode']
            break
    
    if not maker_code:
        print("현대 제조사를 찾을 수 없습니다")
        exit(1)
    
    print(f"[2단계] 현대 차량 10대 carSeq 수집...")
    
    # get_car_seqs_from_page 사용
    from crawler.chacha_crawler import get_car_seqs_from_page
    
    car_seqs = get_car_seqs_from_page(page_num=1, maker_code=maker_code, session=session)
    
    if not car_seqs:
        print("차량 리스트가 비어있습니다")
        exit(1)
    
    # 10대만 선택
    car_seqs = car_seqs[:10]
    print(f"수집된 carSeq: {len(car_seqs)}개")
    print(f"carSeqs: {car_seqs}")
    
    # 이미 DB에 있는지 확인
    with session_scope() as db_session:
        existing_seqs = {str(row[0]) for row in db_session.query(Vehicle.car_seq).filter(
            Vehicle.platform == 'kb_chachacha',
            Vehicle.car_seq.in_(car_seqs)
        ).all()}
        
        print(f"\n[DB 확인] 기존 차량: {len(existing_seqs)}개")
        
        new_seqs = [seq for seq in car_seqs if seq not in existing_seqs]
        print(f"[DB 확인] 신규 차량: {len(new_seqs)}개")
        
        if not new_seqs:
            print("\n모든 차량이 이미 DB에 있습니다. 기존 차량으로 테스트합니다.")
            new_seqs = car_seqs[:3]  # 처음 3대만 테스트
    
    # 크롤링 실행
    print(f"\n[3단계] 차량 정보 크롤링 ({len(new_seqs)}대)...")
    print("="*80)
    
    try:
        records = crawl_complete_car_info(
            car_seqs=new_seqs,
            delay=1.0,
            session=session,
            crawl_insurance=True  # 보험이력 포함
        )
        
        if not records:
            print("\n❌ 크롤링된 데이터가 없습니다.")
            exit(1)
        
        print(f"\n[4단계] DB 저장 ({len(records)}대)...")
        print("="*80)
        
        result = save_car_info_to_db(records)
        
        print(f"\n{'='*80}")
        print(f"✅ 테스트 완료")
        print(f"{'='*80}")
        
        if result:
            saved, skipped, options = result
            print(f"저장: {saved}대")
            print(f"건너뜀: {skipped}대")
            print(f"옵션: {options}개")
        else:
            print("저장된 데이터 없음 (모든 차량이 중복일 수 있음)")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

