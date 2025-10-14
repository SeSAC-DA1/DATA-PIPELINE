
from datetime import timedelta
from airflow.providers.slack.notifications.slack_webhook import SlackWebhookNotifier


# Task 실패 시 Slack 알림
task_fail_slack_alert = SlackWebhookNotifier(
    slack_webhook_conn_id='slack_webhook',
    text="""
:red_circle: *Airflow Task 실패 알림*

*DAG*: `{{ dag.dag_id }}`
*Task*: `{{ ti.task_id }}`
*실행 시간*: {{ ts }}
*상태*: {{ ti.state }}
*오류*: {{ exception }}

<{{ ti.log_url }}|로그 보기>
    """.strip()
)


# Task 성공 시 Slack 알림
task_success_slack_alert = SlackWebhookNotifier(
    slack_webhook_conn_id='slack_webhook',
    text="""
:white_check_mark: *Airflow Task 완료*

*DAG*: `{{ dag.dag_id }}`
*Task*: `{{ ti.task_id }}`
*실행 시간*: {{ ts }}
*상태*: {{ ti.state }}
    """.strip()
)


# DAG 전체 성공 시 Slack 알림
dag_success_slack_alert = SlackWebhookNotifier(
    slack_webhook_conn_id='slack_webhook',
    text="""
:tada: *Airflow DAG 완료*

*DAG*: `{{ dag.dag_id }}`
*실행 시간*: {{ ts }}
*상태*: 모든 Task 성공 완료
    """.strip()
)


# 공통 DAG 설정 (중복 제거용)
def get_default_args(retries=3, retry_delay_minutes=30):
    return {
        'owner': 'airflow',
        'depends_on_past': False,
        'email_on_failure': False,
        'email_on_retry': False,
        'retries': retries,
        'retry_delay': timedelta(minutes=retry_delay_minutes),
        'on_failure_callback': task_fail_slack_alert,  # Task 실패 시 Slack 알림
    }
