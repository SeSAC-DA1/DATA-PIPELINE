from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
import sys
sys.path.append('/opt/airflow')
from crawler.encar_crawler import crawl_encar
from utils.slack_alert import task_fail_slack_alert, dag_success_slack_alert

# 기본 설정
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=30),
    'on_failure_callback': task_fail_slack_alert,  # Task 실패 시 Slack 알림
}

# DAG 정의
with DAG(
    'encar_crawling_daily',
    default_args=default_args,
    description='엔카 중고차 매물 일일 크롤링 (차량 정보 + 옵션 + 보험이력 + 성능점검)',
    schedule='0 2 * * *',  # 매일 새벽 2시
    start_date=datetime(2025, 10, 14),  # 현재 날짜로 설정
    catchup=False,
    max_active_runs=1,  # 동시 실행 최대 1개로 제한
    tags=['crawling', 'encar', 'daily'],
) as dag:

    def start_task():
        """시작 로그 출력"""
        from datetime import datetime
        print(f"[Airflow] 엔카 크롤링 시작: {datetime.now()}")
        return "started"

    def crawl_encar_task(**context):
        """엔카 크롤링 메인 태스크"""
        try:
            # DAG 실행 시 전달된 파라미터 확인
            dag_run = context.get('dag_run')
            conf = dag_run.conf if dag_run else {}
            skip_cleanup = conf.get('skip_cleanup', False)  # 기본값은 False
            
            print('[Airflow] 엔카 크롤링 시작')
            total = crawl_encar(
                max_pages_per_modelgroup=1000,
                page_size=50,
                cleanup_first=not skip_cleanup  # skip_cleanup이 True면 cleanup_first는 False
            )
            print(f'[Airflow] 엔카 크롤링 완료: {total}건')
            return total
        except Exception as e:
            print(f'[Airflow] 엔카 크롤링 실패: {str(e)}')
            raise

    def end_task():
        """완료 로그 출력"""
        from datetime import datetime
        print(f"[Airflow] 엔카 크롤링 완료: {datetime.now()}")
        return "completed"

    # Task 정의
    start_log = PythonOperator(
        task_id='start',
        python_callable=start_task,
    )

    encar_crawl = PythonOperator(
        task_id='crawl_encar',
        python_callable=crawl_encar_task,
        execution_timeout=timedelta(hours=12),  # 12시간 타임아웃
    )

    end_log = PythonOperator(
        task_id='end',
        python_callable=end_task,
        on_success_callback=dag_success_slack_alert,  # DAG 전체 성공 시 Slack 알림
    )

    # Task 의존성 설정
    start_log >> encar_crawl >> end_log
