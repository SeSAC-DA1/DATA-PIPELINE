from datetime import datetime
from bs4 import BeautifulSoup
import pandas as pd
import requests
import re
import time
import json
from urllib.parse import urljoin, urlparse

class KBChachachaCrawler:
    def __init__(self):
        self.base_url = "https://www.kbchachacha.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.cars_data = []
        
    def get_car_list_page(self, page=1, region="", brand="", model="", year_from="", year_to="", price_from="", price_to=""):
        """
        KB차차차 중고차 매물 목록 페이지를 가져옵니다.
        """
        # 검색 파라미터 설정
        params = {
            'page': page,
            'region': region,
            'brand': brand,
            'model': model,
            'year_from': year_from,
            'year_to': year_to,
            'price_from': price_from,
            'price_to': price_to
        }
        
        # 빈 파라미터 제거
        params = {k: v for k, v in params.items() if v}
        
        try:
            # 중고차 매물 목록 URL (실제 URL은 사이트 구조에 따라 조정 필요)
            url = f"{self.base_url}/used-car/list"
            response = self.session.get(url, params=params, timeout=10)
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
        
        # 차량 매물 리스트 선택자 (실제 사이트 구조에 따라 조정 필요)
        car_items = soup.select('.car-item, .vehicle-item, .list-item')  # 여러 가능한 선택자 시도
        
        if not car_items:
            # 다른 가능한 선택자들 시도
            car_items = soup.select('[class*="car"], [class*="vehicle"], [class*="item"]')
        
        for item in car_items:
            try:
                car_info = self.extract_car_info(item)
                if car_info:
                    cars.append(car_info)
            except Exception as e:
                print(f"차량 정보 추출 오류: {e}")
                continue
                
        return cars
    
    def extract_car_info(self, item):
        """
        개별 차량 매물에서 정보를 추출합니다.
        """
        car_info = {
            'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'source': 'KB차차차'
        }
        
        try:
            # 차량명 추출
            title_selectors = [
                '.car-title', '.vehicle-title', '.title', 
                'h3', 'h4', '[class*="title"]'
            ]
            title = self.extract_text_by_selectors(item, title_selectors)
            car_info['car_name'] = title
            
            # 가격 추출
            price_selectors = [
                '.price', '.car-price', '.vehicle-price',
                '[class*="price"]', '.amount'
            ]
            price_text = self.extract_text_by_selectors(item, price_selectors)
            car_info['price'] = self.clean_price(price_text)
            
            # 연식 추출
            year_selectors = [
                '.year', '.car-year', '.vehicle-year',
                '[class*="year"]', '.model-year'
            ]
            year_text = self.extract_text_by_selectors(item, year_selectors)
            car_info['year'] = self.clean_year(year_text)
            
            # 주행거리 추출
            mileage_selectors = [
                '.mileage', '.km', '.distance',
                '[class*="mileage"]', '[class*="km"]'
            ]
            mileage_text = self.extract_text_by_selectors(item, mileage_selectors)
            car_info['mileage'] = self.clean_mileage(mileage_text)
            
            # 연료 추출
            fuel_selectors = [
                '.fuel', '.fuel-type', '.energy',
                '[class*="fuel"]', '[class*="energy"]'
            ]
            fuel_text = self.extract_text_by_selectors(item, fuel_selectors)
            car_info['fuel_type'] = fuel_text
            
            # 지역 추출
            location_selectors = [
                '.location', '.region', '.area',
                '[class*="location"]', '[class*="region"]'
            ]
            location_text = self.extract_text_by_selectors(item, location_selectors)
            car_info['location'] = location_text
            
            # 상세 페이지 링크 추출
            link_element = item.select_one('a')
            if link_element:
                href = link_element.get('href')
                if href:
                    car_info['detail_url'] = urljoin(self.base_url, href)
            
            # 이미지 URL 추출
            img_element = item.select_one('img')
            if img_element:
                src = img_element.get('src') or img_element.get('data-src')
                if src:
                    car_info['image_url'] = urljoin(self.base_url, src)
            
            # 차량 ID 추출 (URL에서)
            if 'detail_url' in car_info:
                car_id = self.extract_car_id_from_url(car_info['detail_url'])
                car_info['car_id'] = car_id
            
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
                return int(price_match.group().replace(',', ''))
            except ValueError:
                return None
        return None
    
    def clean_year(self, year_text):
        """
        연식 텍스트를 정리합니다.
        """
        if not year_text:
            return None
        
        # 4자리 연도 추출
        year_match = re.search(r'20\d{2}', year_text)
        if year_match:
            return int(year_match.group())
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
    
    def extract_car_id_from_url(self, url):
        """
        URL에서 차량 ID를 추출합니다.
        """
        if not url:
            return None
        
        # URL에서 ID 패턴 추출 (사이트 구조에 따라 조정)
        id_patterns = [
            r'/car/(\d+)',
            r'/vehicle/(\d+)',
            r'/detail/(\d+)',
            r'id=(\d+)',
            r'carId=(\d+)'
        ]
        
        for pattern in id_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def get_car_detail(self, detail_url):
        """
        차량 상세 페이지에서 추가 정보를 가져옵니다.
        """
        try:
            response = self.session.get(detail_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            detail_info = {}
            
            # 상세 정보 추출 (사이트 구조에 따라 조정)
            detail_selectors = {
                'transmission': ['.transmission', '[class*="transmission"]'],
                'engine': ['.engine', '[class*="engine"]'],
                'color': ['.color', '[class*="color"]'],
                'accident_history': ['.accident', '[class*="accident"]'],
                'description': ['.description', '.detail', '[class*="description"]']
            }
            
            for key, selectors in detail_selectors.items():
                for selector in selectors:
                    element = soup.select_one(selector)
                    if element:
                        detail_info[key] = element.get_text(strip=True)
                        break
            
            return detail_info
            
        except Exception as e:
            print(f"상세 정보 가져오기 오류: {e}")
            return {}
    
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
            
            # 상세 정보 가져오기 (선택사항)
            for car in cars:
                if 'detail_url' in car:
                    detail_info = self.get_car_detail(car['detail_url'])
                    car.update(detail_info)
                    time.sleep(delay)  # 서버 부하 방지
            
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
        if 'price' in df.columns:
            print(f"\n가격 통계:")
            print(f"평균 가격: {df['price'].mean():,.0f}원")
            print(f"최저 가격: {df['price'].min():,.0f}원")
            print(f"최고 가격: {df['price'].max():,.0f}원")
    else:
        print("수집된 데이터가 없습니다.")

if __name__ == "__main__":
    main()
