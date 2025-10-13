from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
import sys
sys.path.append('/opt/airflow')
from crawler.chacha_crawler import crawl_kb_chachacha

# 기본 설정
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=30),
}

# DAG 정의
with DAG(
    'chacha_crawling_daily',
    default_args=default_args,
    description='KB 차차차 중고차 매물 일일 크롤링 (차량 정보 + 옵션 + 보험이력)',
    schedule='0 3 * * *',  # 매일 새벽 3시 (엔카 크롤링 후)
    start_date=datetime(2025, 10, 14),  # 현재 날짜로 설정
    catchup=False,
    max_active_runs=1,  # 동시 실행 최대 1개로 제한
    tags=['crawling', 'chacha', 'daily'],
) as dag:

    def start_task():
        """시작 로그 출력"""
        from datetime import datetime
        print(f"[Airflow] 차차차 크롤링 시작: {datetime.now()}")
        return "started"

    def crawl_chacha_task(**context):
        """차차차 크롤링 메인 태스크"""
        try:
            # DAG 실행 시 전달된 파라미터 확인
            dag_run = context.get('dag_run')
            conf = dag_run.conf if dag_run else {}
            skip_cleanup = conf.get('skip_cleanup', False)  # 기본값은 False (삭제함)
            
            print("[Airflow] 차차차 크롤링 시작")
            total = crawl_kb_chachacha(
                cleanup_first=not skip_cleanup  # skip_cleanup이 True면 cleanup_first는 False
            )
            print(f"[Airflow] 차차차 크롤링 완료: {total}건")
            return total
        except Exception as e:
            print(f'[Airflow] 차차차 크롤링 실패: {str(e)}')
            raise

    def end_task():
        """완료 로그 출력"""
        from datetime import datetime
        print(f"[Airflow] 차차차 크롤링 완료: {datetime.now()}")
        return "completed"

    # Task 정의
    start_log = PythonOperator(
        task_id='start',
        python_callable=start_task,
    )

    chacha_crawl = PythonOperator(
        task_id='crawl_chacha',
        python_callable=crawl_chacha_task,
        execution_timeout=timedelta(hours=12),  # 12시간 타임아웃
    )

    end_log = PythonOperator(
        task_id='end',
        python_callable=end_task,
    )

    # Task 의존성 설정
    start_log >> chacha_crawl >> end_log

