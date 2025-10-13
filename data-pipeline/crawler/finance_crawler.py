from datetime import datetime
from bs4 import BeautifulSoup
import pandas as pd
import requests
import re


#국민은행 자동차 대출상품 크롤링
res = requests.get('https://obank.kbstar.com/quics?page=C103573')
soup = BeautifulSoup(res.text , 'html.parser')
title_tag = soup.select('.title')

result = []
for tag in title_tag:
  temp = {}
  # strong 태그에서 제목 추출
  strong_tag = tag.select_one('strong')
  if strong_tag:
    temp['title'] = strong_tag.get_text(strip=True)
  else:
    temp['title'] = None
  
  # onclick에서 ln_code 추출
  onclick = tag.attrs['onclick']
  ln_code = re.search(r'LN\d+', onclick)
  if ln_code:
    temp['ln_code'] = ln_code.group()
  
    
  result.append(temp)

print(result)

loan_data = []

for item in result:
    ln_res = requests.get(f'https://obank.kbstar.com/quics?page=C103573&cc=b104363:b104516&isNew=N&prcode={item["ln_code"]}&QSL=F')
    soup = BeautifulSoup(ln_res.text , 'html.parser')
    loan_rate = soup.select('td[align="center"]')

    # 크롤링한 데이터에서 금리 정보 추출 (숫자만)
    rate_values = []
    for i, td in enumerate(loan_rate[:12]):
        text = td.get_text(strip=True)
        # 숫자 패턴 찾기 (소수점 포함)
        match = re.search(r'(\d+\.?\d*)', text)
        if match:
            try:
                rate_values.append(float(match.group(1)))
            except ValueError:
                rate_values.append(None)
        else:
            rate_values.append(None)

    # 인덱스 0, 6번 제외하고 가져오기
    exclude_indices = [0, 6]
    filtered_rates = []
    for i, value in enumerate(rate_values):
        if i not in exclude_indices and value is not None:
            filtered_rates.append(value)
    
    # 기준금리, 가산금리, 우대금리, 최저금리, 최고금리 순서로 2번 반복
    rate_labels = ['base_rate', 'spread_rate', 'pref_rate', 'min_rate', 'max_rate']
    loan_terms = [6, 12]  # 2번 반복이므로 2개 기간

    # 기본 정보 설정
    bank_code = 'KB'
    effective_date = datetime.now().strftime('%Y-%m-%d')
    source_url = f'https://obank.kbstar.com/quics?page=C103573&cc=b104363:b104516&isNew=N&prcode={item["ln_code"]}&QSL=F'

    # 데이터 매칭 - 5개씩 묶어서 처리
    for i, term in enumerate(loan_terms):
        start_idx = i * 5  # 각 기간마다 5개 금리
        end_idx = start_idx + 5
        
        if end_idx <= len(filtered_rates):
            term_rates = filtered_rates[start_idx:end_idx]
            
            loan_record = {
                'product_name': item['title'],  # 상품명 추가
                'ln_code': item['ln_code'],     # 상품코드 추가
                'bank_code': bank_code,
                'effective_date': effective_date,
                'term_months': term,
                'base_rate': term_rates[0] if len(term_rates) > 0 else None,
                'spread_rate': term_rates[1] if len(term_rates) > 1 else None,
                'pref_rate': term_rates[2] if len(term_rates) > 2 else None,
                'min_rate': term_rates[3] if len(term_rates) > 3 else None,
                'max_rate': term_rates[4] if len(term_rates) > 4 else None,
                'source_url': source_url,
                'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            loan_data.append(loan_record)

# DataFrame 생성
df = pd.DataFrame(loan_data)
print("\n생성된 데이터셋:")
print(df)
  





