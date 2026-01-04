"""
Power Automate Webhook への通知モジュール
"""
import os
import logging
import requests
from typing import List, Dict, Any


def get_webhook_url() -> str:
    """Webhook URL を環境変数から取得"""
    url = os.environ.get("POWER_AUTOMATE_WEBHOOK_URL")
    if not url:
        raise ValueError("POWER_AUTOMATE_WEBHOOK_URL is not set")
    return url


def send_notification(new_items: List[Dict[str, Any]], total_count: int) -> bool:
    """
    Power Automate に通知を送信
    
    Args:
        new_items: 新規/更新されたアイテムのリスト
        total_count: 全件数
    
    Returns:
        成功した場合 True
    """
    try:
        webhook_url = get_webhook_url()
    except ValueError as e:
        logging.warning(f"Notification skipped: {e}")
        return False
    
    # 通知用のペイロードを作成
    payload = {
        "total_count": total_count,
        "new_count": len(new_items),
        "items": [
            {
                "workItemId": item.get("workItemId", ""),
                "title": item.get("title", ""),
                "product": item.get("product", ""),
                "state": item.get("state", ""),
                "changedDate": item.get("changedDate", ""),
                "description": _truncate(item.get("description", ""), 500)
            }
            for item in new_items
        ]
    }
    
    logging.info(f"Sending notification for {len(new_items)} items...")
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code in [200, 202]:
            logging.info(f"Notification sent successfully. Status: {response.status_code}")
            return True
        else:
            logging.error(f"Notification failed. Status: {response.status_code}, Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Notification request failed: {e}")
        return False


def _truncate(text: str, max_length: int) -> str:
    """テキストを指定長で切り詰め"""
    if not text:
        return ""
    # HTMLタグを簡易的に除去
    import re
    text = re.sub(r'<[^>]+>', '', text)
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text
