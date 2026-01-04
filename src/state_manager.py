"""
前回実行日時を Azure Blob Storage で管理するモジュール
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from azure.storage.blob import BlobServiceClient


# 定数
CONTAINER_NAME = "function-state"
BLOB_NAME = "last-run-time.txt"


def get_blob_client():
    """Blob クライアントを取得"""
    connection_string = os.environ.get("AzureWebJobsStorage")
    if not connection_string:
        raise ValueError("AzureWebJobsStorage is not set")
    
    blob_service = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service.get_container_client(CONTAINER_NAME)
    
    # コンテナがなければ作成
    try:
        container_client.create_container()
        logging.info(f"Created container: {CONTAINER_NAME}")
    except Exception:
        # 既に存在する場合は無視
        pass
    
    return container_client.get_blob_client(BLOB_NAME)


def get_last_run_time() -> datetime:
    """
    前回実行日時を取得
    
    Returns:
        前回実行日時（なければ24時間前）
    """
    try:
        blob_client = get_blob_client()
        data = blob_client.download_blob().readall().decode('utf-8')
        last_run = datetime.fromisoformat(data.strip())
        logging.info(f"Last run time: {last_run}")
        return last_run
    except Exception as e:
        # Blob が存在しない場合は24時間前を返す
        logging.info(f"No previous run time found, using 24h ago: {e}")
        return datetime.now(timezone.utc) - timedelta(hours=24)


def save_last_run_time(run_time: datetime = None):
    """
    実行日時を保存
    
    Args:
        run_time: 保存する日時（省略時は現在時刻）
    """
    if run_time is None:
        run_time = datetime.now(timezone.utc)
    
    try:
        blob_client = get_blob_client()
        blob_client.upload_blob(
            run_time.isoformat(),
            overwrite=True
        )
        logging.info(f"Saved run time: {run_time}")
    except Exception as e:
        logging.error(f"Failed to save run time: {e}")
        raise


def filter_by_changed_date(items: list, since: datetime) -> list:
    """
    changedDate でフィルタリング
    
    Args:
        items: APIから取得したアイテムリスト
        since: この日時より後に変更されたものを抽出
    
    Returns:
        フィルタされたアイテムリスト
    """
    filtered = []
    for item in items:
        changed_date_str = item.get('changedDate')
        if not changed_date_str:
            continue
        
        # ISO形式の日付をパース（末尾のZをUTCに変換）
        try:
            changed_date = datetime.fromisoformat(
                changed_date_str.replace('Z', '+00:00')
            )
            if changed_date > since:
                filtered.append(item)
        except ValueError as e:
            logging.warning(f"Failed to parse date {changed_date_str}: {e}")
    
    return filtered
