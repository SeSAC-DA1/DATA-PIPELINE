from datetime import datetime, timedelta
import pytz
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
import sys
sys.path.append('/opt/airflow')
from crawler.chacha_crawler import crawl_kb_chachacha
from utils.slack_alert import dag_success_slack_alert, get_default_args

# 기본 설정 (공통 함수 사용)
default_args = get_default_args(retries=3, retry_delay_minutes=30)

# DAG 정의
with DAG(
    'chacha_crawling_daily',
    default_args=default_args,
    description='KB 차차차 중고차 매물 일일 크롤링 (차량 정보 + 옵션 + 보험이력)',
    schedule='0 3 * * *',  # 매일 새벽 3시 (엔카 크롤링 후)
    start_date=datetime(2024, 1, 1, tzinfo=pytz.timezone('Asia/Seoul')),  # 과거 & KST
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
        on_success_callback=dag_success_slack_alert,  # DAG 전체 성공 시 Slack 알림
    )

    # Task 의존성 설정
    start_log >> chacha_crawl >> end_log

