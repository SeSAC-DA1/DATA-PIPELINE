"""
보험이력 크롤링 테스트 (쿠키 추출 + Requests 방식)
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from crawler.chacha_crawler import crawl_insurance_history_batch

if __name__ == "__main__":
    print("=" * 80)
    print("보험이력 크롤링 테스트 (쿠키 추출 + Requests)")
    print("=" * 80)
    
    # 테스트할 차량 (보험이력이 있는 차량)
    test_car_seqs = ["25574426"]  # 보험이력이 확인된 차량
    
    print(f"\n[설정] 테스트 차량: {test_car_seqs}")
    print("[주의] .env 파일에 NAVER_ID, NAVER_PASSWORD 설정 필요!\n")
    
    input("엔터를 눌러 시작... (Ctrl+C로 취소)")
    
    # 크롤링 실행
    results = crawl_insurance_history_batch(car_seqs=test_car_seqs)
    
    if results:
        print(f"\n{'=' * 80}")
        print("📊 크롤링 결과 요약")
        print("=" * 80)
        
        total_my_accident = 0
        total_other_accident = 0
        total_cost = 0
        total_rental = 0
        total_business = 0
        total_owner_change = 0
        
        for result in results:
            my_cnt = result['my_accident_cnt']
            other_cnt = result['other_accident_cnt']
            total_my_accident += my_cnt
            total_other_accident += other_cnt
            total_cost += result['my_accident_cost'] + result['other_accident_cost']
            total_rental += result['rental']
            total_business += result['business']
            total_owner_change += result['owner_change_cnt']
            
            print(f"\n📌 carSeq: {result['car_seq']}")
            print(f"   ├─ 플랫폼: {result['platform']}")
            print(f"   ├─ 사고이력:")
            print(f"   │  ├─ 내차 피해: {my_cnt}회 / {result['my_accident_cost']:,}원")
            print(f"   │  ├─ 상대차 피해: {other_cnt}회 / {result['other_accident_cost']:,}원")
            print(f"   │  └─ 총 사고: {result['total_accident_cnt']}회")
            print(f"   ├─ 특수 사고:")
            print(f"   │  ├─ 전손: {result['total_loss_cnt']}회 {f'({result['total_loss_date']})' if result['total_loss_date'] else ''}")
            print(f"   │  ├─ 도난: {result['robber_cnt']}회 {f'({result['robber_date']})' if result['robber_date'] else ''}")
            print(f"   │  └─ 침수: {result['flood_part_loss_cnt']}회 {f'({result['flood_date']})' if result['flood_date'] else ''}")
            print(f"   ├─ 특수 용도:")
            print(f"   │  ├─ 렌터카: {'있음 ⚠️' if result['rental'] else '없음 ✅'}")
            print(f"   │  ├─ 영업용: {'있음 ⚠️' if result['business'] else '없음 ✅'}")
            print(f"   │  └─ 관용: {'있음 ⚠️' if result['government'] else '없음 ✅'}")
            print(f"   ├─ 변경 이력:")
            print(f"   │  ├─ 소유자 변경: {result['owner_change_cnt']}회")
            print(f"   │  └─ 차량번호 변경: {result['car_no_change_cnt']}회")
            
            if result['not_join_periods']:
                print(f"   ├─ 미가입 기간: {result['not_join_periods']}")
            
            if result['details']:
                print(f"   └─ 상세 이력:")
                for idx, detail in enumerate(result['details'], 1):
                    print(f"      {idx}. {detail['date']}")
                    if detail['my_car_insurance']:
                        print(f"         - 내차보험(처리): {detail['my_car_insurance']:,}원")
                    if detail['my_car_other']:
                        print(f"         - 상대보험(처리): {detail['my_car_other']:,}원")
                    if detail['other_car_insurance']:
                        print(f"         - 상대차 내차보험(처리): {detail['other_car_insurance']:,}원")
        
        print(f"\n{'=' * 80}")
        print(f"📈 전체 통계")
        print(f"{'=' * 80}")
        print(f"  - 총 크롤링 차량: {len(results)}대")
        print(f"  - 내차 피해 건수: {total_my_accident}회")
        print(f"  - 상대차 피해 건수: {total_other_accident}회")
        print(f"  - 총 손해액: {total_cost:,}원")
        print(f"  - 렌터카 이력: {total_rental}대")
        print(f"  - 영업용 이력: {total_business}대")
        print(f"  - 평균 소유자 변경: {total_owner_change / len(results):.1f}회")
        
    else:
        print("\n❌ 크롤링 결과가 없습니다.")
        print("   - 로그인 실패 또는 차량 데이터가 없을 수 있습니다.")
    
    print(f"\n{'=' * 80}")
    print("✅ 테스트 완료")
    print(f"{'=' * 80}")
    print(f"\n💾 결과 파일: insurance_history_results.json")
