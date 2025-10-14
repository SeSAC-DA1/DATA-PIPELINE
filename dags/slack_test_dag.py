
from datetime import datetime, timedelta
import pytz
from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator
import sys
sys.path.append('/opt/airflow')
from utils.slack_alert import task_fail_slack_alert, task_success_slack_alert, dag_success_slack_alert, get_default_args

# 기본 설정 (공통 함수 사용)
default_args = get_default_args(retries=0, retry_delay_minutes=1)

# DAG 정의
with DAG(
    'slack_test_dag',
    default_args=default_args,
    description='Slack 알림 테스트용 DAG',
    schedule=None,  # 수동 실행만 (DAG ON 해도 자동 실행 안 됨)
    start_date=datetime(2024, 1, 1, tzinfo=pytz.timezone('Asia/Seoul')),  # 과거 & KST
    catchup=False,
    max_active_runs=1,
    tags=['test', 'slack'],
) as dag:

    def success_task():
        """성공 테스트용 태스크"""
        print("✅ Slack 알림 테스트 - 성공 태스크 실행")
        return "success"

    def fail_task():
        """실패 테스트용 태스크"""
        print("❌ Slack 알림 테스트 - 실패 태스크 실행")
        raise Exception("의도적인 실패 - Slack 알림 테스트용")

    def dag_complete_task():
        """DAG 완료 테스트용 태스크"""
        print("🎉 Slack 테스트 DAG 완료")
        return "completed"

    # 성공 테스트 태스크
    success_test = PythonOperator(
        task_id='success_test',
        python_callable=success_task,
        on_success_callback=task_success_slack_alert,  # 성공 시 Slack 알림
    )

    # 실패 테스트 태스크 (BashOperator 사용)
    fail_test_bash = BashOperator(
        task_id='fail_test_bash',
        bash_command='exit 1',  # 의도적으로 실패
        # on_failure_callback은 default_args에서 자동 적용됨
    )

    # 실패 테스트 태스크 (PythonOperator 사용)
    fail_test_python = PythonOperator(
        task_id='fail_test_python',
        python_callable=fail_task,
        # on_failure_callback은 default_args에서 자동 적용됨
    )

    # DAG 완료 알림 태스크
    dag_complete = PythonOperator(
        task_id='dag_complete',
        python_callable=dag_complete_task,  # lambda 제거
        on_success_callback=dag_success_slack_alert,  # DAG 완료 시 Slack 알림
    )

    # Task 의존성 설정 (실패 태스크들을 병렬로 실행)
    success_test >> [fail_test_bash, fail_test_python] >> dag_complete
