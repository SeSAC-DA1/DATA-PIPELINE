from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

# 기본 설정
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
}

# DAG 정의
with DAG(
    'getcha_review_weekly',
    default_args=default_args,
    description='Getcha 차량 오너 리뷰 주간 크롤링',
    schedule='0 1 * * 0',  # 매주 일요일 새벽 1시
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['crawling', 'getcha', 'review', 'weekly'],
) as dag:

    def start_task():
        """시작 로그 출력"""
        from datetime import datetime
        print(f"[Airflow] Getcha 리뷰 크롤링 시작: {datetime.now()}")
        return "started"

    def crawl_getcha_task():
        """Getcha 리뷰 크롤링 태스크"""
        import sys
        sys.path.append('/opt/airflow')
        from crawler.getcha_crawler import execute_full_crawling
        
        print("[Airflow] Getcha 리뷰 크롤링 시작")
        reviews = execute_full_crawling(
            start_page=1,
            end_page=None,  # 전체 페이지
            topic_id=11
        )
        print(f"[Airflow] Getcha 리뷰 크롤링 완료: {len(reviews)}건")
        return len(reviews)

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
    )

    # Task 의존성 설정
    start_log >> getcha_crawl >> end_log

