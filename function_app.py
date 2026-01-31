import azure.functions as func
import logging
import json
from src.auth_manager import AuthManager
from src import api_client
from src import state_manager
from src import notifier

app = func.FunctionApp()

# TZ=Asia/Tokyo が設定されているため、cron式はJST基準
# 毎日 JST 9:00 にトリガー
@app.schedule(schedule="0 0 9 * * *", arg_name="myTimer", run_on_startup=False,
              use_monitor=True) 
def timer_trigger(myTimer: func.TimerRequest) -> None:
    """毎日 JST 9:00 にジョブを実行"""
    if myTimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Python timer trigger function started.')
    
    try:
        run_job()
    except Exception as e:
        logging.error(f"Job failed: {e}", exc_info=True)
        raise  # エラーを再スローして Azure Functions に失敗を通知

# TZ=Asia/Tokyo が設定されているため、cron式はJST基準
# 毎日 JST 21:00 にトークンをリフレッシュ
@app.schedule(schedule="0 0 21 * * *", arg_name="myTimer", run_on_startup=False,
              use_monitor=True)
def token_refresh_trigger(myTimer: func.TimerRequest) -> None:
    """毎日 JST 21:00 にトークンをリフレッシュ"""
    if myTimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Token refresh trigger started.')
    
    try:
        refresh_token_only()
    except Exception as e:
        logging.error(f"Token refresh failed: {e}", exc_info=True)
        raise  # エラーを再スローして Azure Functions に失敗を通知

@app.route(route="manual_trigger", auth_level=func.AuthLevel.FUNCTION)
def manual_trigger(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    
    try:
        data = run_job()
        return func.HttpResponse(
            json.dumps(data, indent=2, ensure_ascii=False),
            mimetype="application/json",
            status_code=200
        )
    except Exception as e:
        return func.HttpResponse(
            f"Job failed: {str(e)}",
            status_code=500
        )

def run_job():
    """
    メインジョブ: 既知の問題を取得し、前回実行以降の更新をフィルタリング
    """
    logging.info("Initializing AuthManager...")
    auth_manager = AuthManager()
    
    logging.info("Getting access token...")
    token = auth_manager.get_access_token()
    
    logging.info("Fetching known issues...")
    all_data = api_client.get_known_issues(token)
    
    total_count = len(all_data) if isinstance(all_data, list) else 0
    logging.info(f"Retrieved {total_count} total issues.")
    
    # 前回実行日時を取得してフィルタリング
    last_run = state_manager.get_last_run_time()
    logging.info(f"Filtering issues changed since: {last_run}")
    
    if isinstance(all_data, list):
        new_items = state_manager.filter_by_changed_date(all_data, last_run)
    else:
        new_items = []
    
    logging.info(f"Found {len(new_items)} new/updated issues since last run.")
    
    # 現在時刻を保存（次回実行の基準に）
    state_manager.save_last_run_time()
    
    # 通知を送信（0件でも送信）
    if new_items:
        logging.info(f"New issues to notify: {[item.get('workItemId') for item in new_items]}")
    else:
        logging.info("No new issues, but sending notification anyway.")
    
    notification_sent = notifier.send_notification(new_items, total_count)
    logging.info(f"Notification sent: {notification_sent}")
    
    # 戻り値は新しいアイテムのみ
    return {
        "total_count": total_count,
        "new_count": len(new_items),
        "last_run": last_run.isoformat(),
        "new_items": new_items
    }

def refresh_token_only():
    """トークンのリフレッシュのみを行う（API呼び出しなし）"""
    logging.info("Initializing AuthManager for token refresh...")
    auth_manager = AuthManager()
    
    logging.info("Refreshing access token...")
    token = auth_manager.get_access_token()
    
    # トークンの一部をログに出力（確認用）
    logging.info(f"Token refreshed successfully. Token starts with: {token[:20]}...")
    logging.info("Token refresh completed. Key Vault updated with new refresh token.")