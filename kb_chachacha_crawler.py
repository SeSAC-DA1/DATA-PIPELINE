from datetime import datetime
from bs4 import BeautifulSoup
import pandas as pd
import requests
import re
import time
import json

class KBChachachaCrawler:
    def __init__(self):
        self.base_url = "https://www.kbchachacha.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.cars_data = []
        
    def get_car_list_page(self, page=1, sort="-orderDate"):
        """
        KB차차차 중고차 매물 목록 페이지를 가져옵니다.
        사용자가 확인한 올바른 엔드포인트 사용
        """
        url = f"{self.base_url}/public/search/list.empty?page={page}&sort={sort}"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"페이지 요청 오류: {e}")
            return None
    
    def parse_car_list(self, html_content):
        """
        중고차 매물 목록 HTML을 파싱하여 차량 정보를 추출합니다.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        cars = []
        
        # KB차차차의 실제 HTML 구조에 맞는 선택자들
        # 웹사이트 분석 결과를 바탕으로 차량 카드 선택자 시도
        car_selectors = [
            '.car-item',
            '.vehicle-item', 
            '.list-item',
            '[class*="car"]',
            '[class*="vehicle"]',
            '.item',
            'article',
            '.card'
        ]
        
        car_items = []
        for selector in car_selectors:
            items = soup.select(selector)
            if items and len(items) > 5:  # 충분한 수의 아이템이 있으면
                car_items = items
                print(f"차량 목록 발견: {selector} ({len(items)}개)")
                break
        
        if not car_items:
            # 다른 방법으로 차량 정보 찾기
            print("일반적인 선택자로 차량을 찾을 수 없습니다. 전체 HTML 구조 분석...")
            # 모든 링크와 텍스트에서 차량 정보 패턴 찾기
            car_items = self.find_car_info_patterns(soup)
        
        for item in car_items:
            try:
                car_info = self.extract_car_info(item)
                if car_info:
                    cars.append(car_info)
            except Exception as e:
                print(f"차량 정보 추출 오류: {e}")
                continue
                
        return cars
    
    def find_car_info_patterns(self, soup):
        """
        HTML에서 차량 정보 패턴을 찾습니다.
        """
        # 가격 패턴 (예: 1,150만원, 3,650만원)
        price_pattern = r'(\d{1,3}(?:,\d{3})*만원)'
        
        # 차량명 패턴 (브랜드 + 모델)
        car_name_patterns = [
            r'(현대|기아|BMW|벤츠|아우디|제네시스|렉서스|지프|미니|마세라티|KG모빌리티|한국GM|르노코리아)\s+[^0-9]+',
            r'[가-힣]+\s+[가-힣]+(?:\s+[가-힣]+)*'
        ]
        
        # 연식 패턴 (예: 23/04식(23년형), 20/08식(21년형))
        year_pattern = r'(\d{2}/\d{2}식\(\d{2}년형\))'
        
        # 주행거리 패턴 (예: 69,913km, 79,960km)
        mileage_pattern = r'(\d{1,3}(?:,\d{3})*km)'
        
        # 지역 패턴 (예: 울산, 경기, 인천, 서울)
        location_pattern = r'(울산|경기|인천|서울|부산|대구|광주|대전|울산|세종|강원|충북|충남|전북|전남|경북|경남)'
        
        # 모든 텍스트에서 패턴 매칭
        all_text = soup.get_text()
        
        # 가격 위치 찾기
        price_matches = list(re.finditer(price_pattern, all_text))
        
        cars_info = []
        for match in price_matches:
            price_text = match.group(1)
            start_pos = max(0, match.start() - 500)  # 가격 앞 500자
            end_pos = min(len(all_text), match.end() + 200)  # 가격 뒤 200자
            context = all_text[start_pos:end_pos]
            
            # 컨텍스트에서 다른 정보 추출
            car_info = {
                'price': price_text,
                'context': context
            }
            
            # 연식 찾기
            year_match = re.search(year_pattern, context)
            if year_match:
                car_info['year'] = year_match.group(1)
            
            # 주행거리 찾기
            mileage_match = re.search(mileage_pattern, context)
            if mileage_match:
                car_info['mileage'] = mileage_match.group(1)
            
            # 지역 찾기
            location_match = re.search(location_pattern, context)
            if location_match:
                car_info['location'] = location_match.group(1)
            
            # 차량명 찾기
            for pattern in car_name_patterns:
                name_match = re.search(pattern, context)
                if name_match:
                    car_info['car_name'] = name_match.group(0).strip()
                    break
            
            cars_info.append(car_info)
        
        return cars_info
    
    def extract_car_info(self, item):
        """
        개별 차량 매물에서 정보를 추출합니다.
        """
        car_info = {
            'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'source': 'KB차차차'
        }
        
        try:
            # HTML 요소인 경우
            if hasattr(item, 'get_text'):
                text_content = item.get_text()
                
                # 차량명 추출
                title_selectors = [
                    '.car-title', '.vehicle-title', '.title', 
                    'h3', 'h4', '[class*="title"]', 'strong', 'b'
                ]
                title = self.extract_text_by_selectors(item, title_selectors)
                if not title:
                    # 텍스트에서 차량명 패턴 찾기
                    title = self.extract_car_name_from_text(text_content)
                car_info['car_name'] = title
                
                # 가격 추출
                price_selectors = [
                    '.price', '.car-price', '.vehicle-price',
                    '[class*="price"]', '.amount', 'strong', 'b'
                ]
                price_text = self.extract_text_by_selectors(item, price_selectors)
                if not price_text:
                    price_text = self.extract_price_from_text(text_content)
                car_info['price'] = self.clean_price(price_text)
                
                # 연식 추출
                year_text = self.extract_year_from_text(text_content)
                car_info['year'] = year_text
                
                # 주행거리 추출
                mileage_text = self.extract_mileage_from_text(text_content)
                car_info['mileage'] = self.clean_mileage(mileage_text)
                
                # 지역 추출
                location_text = self.extract_location_from_text(text_content)
                car_info['location'] = location_text
                
                # 연료 추출
                fuel_text = self.extract_fuel_from_text(text_content)
                car_info['fuel_type'] = fuel_text
                
                # 상세 페이지 링크 추출
                link_element = item.select_one('a')
                if link_element:
                    href = link_element.get('href')
                    if href:
                        car_info['detail_url'] = self.base_url + href if href.startswith('/') else href
                
                # 이미지 URL 추출
                img_element = item.select_one('img')
                if img_element:
                    src = img_element.get('src') or img_element.get('data-src')
                    if src:
                        car_info['image_url'] = self.base_url + src if src.startswith('/') else src
            
            # 딕셔너리인 경우 (패턴 매칭 결과)
            elif isinstance(item, dict):
                car_info.update(item)
            
            return car_info
            
        except Exception as e:
            print(f"차량 정보 추출 중 오류: {e}")
            return None
    
    def extract_text_by_selectors(self, element, selectors):
        """
        여러 선택자를 시도하여 텍스트를 추출합니다.
        """
        for selector in selectors:
            found = element.select_one(selector)
            if found:
                return found.get_text(strip=True)
        return ""
    
    def extract_car_name_from_text(self, text):
        """텍스트에서 차량명을 추출합니다."""
        patterns = [
            r'(현대|기아|BMW|벤츠|아우디|제네시스|렉서스|지프|미니|마세라티|KG모빌리티|한국GM|르노코리아)\s+[^0-9]+',
            r'[가-힣]+\s+[가-힣]+(?:\s+[가-힣]+)*'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0).strip()
        return ""
    
    def extract_price_from_text(self, text):
        """텍스트에서 가격을 추출합니다."""
        patterns = [
            r'(\d{1,3}(?:,\d{3})*만원)',
            r'(\d{1,3}(?:,\d{3})*원)',
            r'(\d{1,3}(?:,\d{3})*)\s*만'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ""
    
    def extract_year_from_text(self, text):
        """텍스트에서 연식을 추출합니다."""
        pattern = r'(\d{2}/\d{2}식\(\d{2}년형\))'
        match = re.search(pattern, text)
        if match:
            return match.group(1)
        return ""
    
    def extract_mileage_from_text(self, text):
        """텍스트에서 주행거리를 추출합니다."""
        pattern = r'(\d{1,3}(?:,\d{3})*km)'
        match = re.search(pattern, text)
        if match:
            return match.group(1)
        return ""
    
    def extract_location_from_text(self, text):
        """텍스트에서 지역을 추출합니다."""
        pattern = r'(울산|경기|인천|서울|부산|대구|광주|대전|울산|세종|강원|충북|충남|전북|전남|경북|경남)'
        match = re.search(pattern, text)
        if match:
            return match.group(1)
        return ""
    
    def extract_fuel_from_text(self, text):
        """텍스트에서 연료 타입을 추출합니다."""
        patterns = [
            r'(가솔린|디젤|LPG|하이브리드|전기|EV)',
            r'(LPe|GDI|T-GDI|TDI)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ""
    
    def clean_price(self, price_text):
        """
        가격 텍스트를 정리합니다.
        """
        if not price_text:
            return None
        
        # 숫자만 추출
        price_match = re.search(r'[\d,]+', price_text.replace(',', ''))
        if price_match:
            try:
                price_str = price_match.group().replace(',', '')
                if '만원' in price_text:
                    return int(price_str) * 10000
                else:
                    return int(price_str)
            except ValueError:
                return None
        return None
    
    def clean_mileage(self, mileage_text):
        """
        주행거리 텍스트를 정리합니다.
        """
        if not mileage_text:
            return None
        
        # 숫자만 추출
        mileage_match = re.search(r'[\d,]+', mileage_text.replace(',', ''))
        if mileage_match:
            try:
                return int(mileage_match.group().replace(',', ''))
            except ValueError:
                return None
        return None
    
    def crawl_cars(self, max_pages=5, delay=1):
        """
        중고차 매물을 크롤링합니다.
        """
        print("KB차차차 중고차 매물 크롤링 시작...")
        
        for page in range(1, max_pages + 1):
            print(f"페이지 {page} 크롤링 중...")
            
            # 페이지 가져오기
            html_content = self.get_car_list_page(page=page)
            if not html_content:
                print(f"페이지 {page} 로드 실패")
                continue
            
            # 차량 목록 파싱
            cars = self.parse_car_list(html_content)
            if not cars:
                print(f"페이지 {page}에서 차량 정보를 찾을 수 없습니다.")
                break
            
            print(f"페이지 {page}에서 {len(cars)}개 차량 발견")
            
            self.cars_data.extend(cars)
            
            # 페이지 간 지연
            time.sleep(delay)
        
        print(f"크롤링 완료! 총 {len(self.cars_data)}개 차량 수집")
        return self.cars_data
    
    def save_to_csv(self, filename=None):
        """
        수집한 데이터를 CSV 파일로 저장합니다.
        """
        if not self.cars_data:
            print("저장할 데이터가 없습니다.")
            return
        
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'kb_chachacha_cars_{timestamp}.csv'
        
        df = pd.DataFrame(self.cars_data)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"데이터가 {filename}에 저장되었습니다.")
        
        return df
    
    def save_to_json(self, filename=None):
        """
        수집한 데이터를 JSON 파일로 저장합니다.
        """
        if not self.cars_data:
            print("저장할 데이터가 없습니다.")
            return
        
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'kb_chachacha_cars_{timestamp}.json'
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.cars_data, f, ensure_ascii=False, indent=2)
        
        print(f"데이터가 {filename}에 저장되었습니다.")

def main():
    """
    메인 실행 함수
    """
    crawler = KBChachachaCrawler()
    
    # 크롤링 실행
    cars_data = crawler.crawl_cars(max_pages=3, delay=2)  # 3페이지, 2초 지연
    
    if cars_data:
        # 데이터 저장
        df = crawler.save_to_csv()
        crawler.save_to_json()
        
        # 데이터 미리보기
        print("\n=== 수집된 데이터 미리보기 ===")
        print(df.head())
        print(f"\n총 {len(df)}개 차량 데이터 수집 완료")
        
        # 기본 통계
        if 'price' in df.columns and df['price'].notna().any():
            print(f"\n가격 통계:")
            prices = pd.to_numeric(df['price'], errors='coerce')
            print(f"평균 가격: {prices.mean():,.0f}원")
            print(f"최저 가격: {prices.min():,.0f}원")
            print(f"최고 가격: {prices.max():,.0f}원")
        
        if 'location' in df.columns and df['location'].notna().any():
            print(f"\n지역별 차량 수:")
            location_counts = df['location'].value_counts()
            print(location_counts.head(10))
    else:
        print("수집된 데이터가 없습니다.")

if __name__ == "__main__":
    main()




