import os
from dotenv import load_dotenv
from supabase import create_client, Client

# .env 파일 로드
load_dotenv()

# Supabase 설정
SUPABASE_URL: str = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY: str = os.environ.get("SUPABASE_SERVICE_KEY")

# Supabase 클라이언트 생성
# 이 클라이언트는 다른 파일에서 가져와서 사용합니다.
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
