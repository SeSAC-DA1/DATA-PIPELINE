"""
Airflow Slack 알림 유틸리티 (공식 Provider 사용)

DAG Task 실패/성공 시 Slack으로 알림을 전송합니다.
Apache Airflow Providers - Slack을 사용합니다.
"""
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
from airflow.models import TaskInstance


def task_fail_slack_alert(context):
    """
    Task 실패 시 Slack 알림 전송
    
    DAG의 default_args에 on_failure_callback으로 등록하여 사용
    
    Args:
        context: Airflow context dictionary
    """
    ti: TaskInstance = context.get('task_instance')
    dag_id = context.get('dag').dag_id
    task_id = ti.task_id
    execution_date = context.get('execution_date')
    log_url = ti.log_url
    exception = context.get('exception')
    
    # Slack 메시지 구성
    slack_msg = f"""
:red_circle: *Airflow Task 실패 알림*

*DAG*: `{dag_id}`
*Task*: `{task_id}`
*실행 시간*: {execution_date.strftime('%Y-%m-%d %H:%M:%S') if execution_date else 'N/A'}
*오류*: {str(exception)[:500] if exception else 'Unknown error'}

<{log_url}|로그 보기>
    """.strip()
    
    # SlackWebhookOperator로 메시지 전송
    try:
        alert = SlackWebhookOperator(
            task_id='slack_failed_alert',
            http_conn_id='slack_webhook',
            message=slack_msg,
            username='Airflow',
        )
        return alert.execute(context=context)
    except Exception as e:
        print(f"❌ Slack 알림 전송 실패: {str(e)}")
        print("⚠️ Airflow UI에서 Connection 'slack_webhook'을 확인해주세요.")


def task_success_slack_alert(context):
    """
    Task 성공 시 Slack 알림 전송
    
    DAG의 default_args에 on_success_callback으로 등록하여 사용
    
    Args:
        context: Airflow context dictionary
    """
    ti: TaskInstance = context.get('task_instance')
    dag_id = context.get('dag').dag_id
    task_id = ti.task_id
    execution_date = context.get('execution_date')
    
    # Slack 메시지 구성
    slack_msg = f"""
:white_check_mark: *Airflow Task 완료*

*DAG*: `{dag_id}`
*Task*: `{task_id}`
*실행 시간*: {execution_date.strftime('%Y-%m-%d %H:%M:%S') if execution_date else 'N/A'}
    """.strip()
    
    # SlackWebhookOperator로 메시지 전송
    try:
        alert = SlackWebhookOperator(
            task_id='slack_success_alert',
            http_conn_id='slack_webhook',
            message=slack_msg,
            username='Airflow',
        )
        return alert.execute(context=context)
    except Exception as e:
        print(f"❌ Slack 알림 전송 실패: {str(e)}")
        print("⚠️ Airflow UI에서 Connection 'slack_webhook'을 확인해주세요.")


def dag_success_slack_alert(context):
    """
    DAG 전체 성공 시 Slack 알림 전송
    
    마지막 Task에 on_success_callback으로 등록하여 사용
    
    Args:
        context: Airflow context dictionary
    """
    dag_id = context.get('dag').dag_id
    execution_date = context.get('execution_date')
    
    # Slack 메시지 구성
    slack_msg = f"""
:tada: *Airflow DAG 완료*

*DAG*: `{dag_id}`
*실행 시간*: {execution_date.strftime('%Y-%m-%d %H:%M:%S') if execution_date else 'N/A'}
*상태*: 모든 Task 성공
    """.strip()
    
    # SlackWebhookOperator로 메시지 전송
    try:
        alert = SlackWebhookOperator(
            task_id='slack_dag_success_alert',
            http_conn_id='slack_webhook',
            message=slack_msg,
            username='Airflow',
        )
        return alert.execute(context=context)
    except Exception as e:
        print(f"❌ Slack 알림 전송 실패: {str(e)}")
        print("⚠️ Airflow UI에서 Connection 'slack_webhook'을 확인해주세요.")
