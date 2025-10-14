from datetime import datetime, timedelta
import pytz
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
import sys
sys.path.append('/opt/airflow')
from crawler.getcha_crawler import execute_full_crawling
from utils.slack_alert import dag_success_slack_alert, get_default_args

# 기본 설정 (공통 함수 사용)
default_args = get_default_args(retries=2, retry_delay_minutes=10)

# DAG 정의
with DAG(
    'getcha_review_weekly',
    default_args=default_args,
    description='Getcha 차량 오너 리뷰 주간 크롤링',
    schedule='0 1 * * 0',  # 매주 일요일 새벽 1시
    start_date=datetime(2024, 1, 1, tzinfo=pytz.timezone('Asia/Seoul')),  # 과거 & KST
    catchup=False,
    max_active_runs=1,  # 동시 실행 최대 1개로 제한
    tags=['crawling', 'getcha', 'review', 'weekly'],
) as dag:

    def start_task():
        """시작 로그 출력"""
        from datetime import datetime
        print(f"[Airflow] Getcha 리뷰 크롤링 시작: {datetime.now()}")
        return "started"

    def crawl_getcha_task():
        """Getcha 리뷰 크롤링 메인 태스크"""
        try:
            print("[Airflow] Getcha 리뷰 크롤링 시작")
            reviews = execute_full_crawling(
                start_page=1,
                end_page=None,  # 전체 페이지
                topic_id=11
            )
            print(f"[Airflow] Getcha 리뷰 크롤링 완료: {len(reviews)}건")
            return len(reviews)
        except Exception as e:
            print(f'[Airflow] Getcha 리뷰 크롤링 실패: {str(e)}')
            raise

    def end_task():
        """완료 로그 출력"""
        from datetime import datetime
        print(f"[Airflow] Getcha 리뷰 크롤링 완료: {datetime.now()}")
        return "completed"

    # Task 정의
    start_log = PythonOperator(
        task_id='start',
        python_callable=start_task,
    )

    getcha_crawl = PythonOperator(
        task_id='crawl_getcha_reviews',
        python_callable=crawl_getcha_task,
        execution_timeout=timedelta(hours=2), 
    )

    end_log = PythonOperator(
        task_id='end',
        python_callable=end_task,
        on_success_callback=dag_success_slack_alert,  # DAG 전체 성공 시 Slack 알림
    )

    # Task 의존성 설정
    start_log >> getcha_crawl >> end_log

