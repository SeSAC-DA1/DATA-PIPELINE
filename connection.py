import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

load_dotenv()

def get_url():
  DB_HOST = os.getenv("DB_HOST") 
  DB_USER = os.getenv("DB_USER")
  DB_PASSWORD = os.getenv("DB_PASSWORD")
  DB_NAME = os.getenv("DB_NAME")
  DB_PORT = os.getenv("DB_PORT")

  if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT]):
    raise ValueError("DB 환경변수가 설정되지 않았습니다.")


  url = f"postgresql+psycopg2://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
  return url


#중복 생성 방지를 위해 따로 빼지 않음.
Engine = create_engine(get_url(),pool_pre_ping=True, future=True,pool_recycle=3600)

#세션 팩토리
SessionLocal = sessionmaker(bind=Engine, autoflush= False,expire_on_commit=False,future=True)

@contextmanager
def session_scope():
   s = SessionLocal()
   try:
      #yield는 호출후 바로 종료가 아니라  with 블럭을 만나면 호출후 대기했다가 with 블럭이 끝나면 다시 돌아와서 그 다음 코드를 실행함.
      yield s 
      s.commit()
   except Exception as e:
      s.rollback()
      print(f"DB 오류: {e}")
      raise
   finally:
      s.close()

