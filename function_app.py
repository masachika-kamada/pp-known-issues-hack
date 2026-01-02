import azure.functions as func
import logging
import json
from src.auth_manager import AuthManager
from src import api_client

app = func.FunctionApp()

@app.schedule(schedule="0 0 9 * * *", arg_name="myTimer", run_on_startup=False,
              use_monitor=False) 
def timer_trigger(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Python timer trigger function started.')
    
    try:
        run_job()
    except Exception as e:
        logging.error(f"Job failed: {e}")

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
    logging.info("Initializing AuthManager...")
    auth_manager = AuthManager()
    
    logging.info("Getting API host from config or Key Vault...")
    api_host = auth_manager.get_api_host()
    logging.info(f"API host: {api_host[:20]}...")  # ホスト名の一部のみログ
    
    logging.info("Getting access token...")
    token = auth_manager.get_access_token()
    
    logging.info("Fetching known issues...")
    data = api_client.get_known_issues(token, api_host=api_host)
    
    logging.info(f"Successfully retrieved {len(data) if isinstance(data, list) else 'unknown count of'} issues.")
    
    # 日付フィルタリングの例 (API側でフィルタできない場合)
    # from datetime import datetime, timedelta
    # threshold_date = datetime.now() - timedelta(days=7)
    # filtered_data = [
    #     item for item in data.get('value', []) 
    #     if datetime.fromisoformat(item.get('createdDateTime', '').replace('Z', '+00:00')) > threshold_date.astimezone()
    # ]
    
    # ここでTeams通知などの後続処理を行う
    # logging.info(json.dumps(data, indent=2)) 
    
    return data
