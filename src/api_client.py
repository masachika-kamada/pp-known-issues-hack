import requests
import logging
from . import config
from .settings import get_enabled_product_ids, get_issue_settings


def get_api_url() -> str:
    """API URLを生成"""
    if not config.API_HOST:
        raise ValueError("API_HOST is not configured")
    return f"https://{config.API_HOST}/support/knownissue/search?api-version=2022-03-01-preview"


def get_known_issues(access_token, payload=None):
    """
    既知の問題APIからデータを取得する
    
    Args:
        access_token: アクセストークン
        payload: リクエストペイロード（省略時は設定ファイルから生成）
    """
    url = get_api_url()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # ペイロードを設定ファイルから生成
    if payload is None:
        product_ids = get_enabled_product_ids()
        settings = get_issue_settings()
        
        if not product_ids:
            logging.warning("No products enabled in config, using all products")
            product_ids = ["00000000-0000-0000-0000-000000000000"]
        
        payload = {
            "productIds": product_ids,
            "minMatchingScore": 0.00001,
            "searchText": "*",
            "issueStatus": settings.get("issueStatus", "Active"),
            "maxIssueCount": settings.get("maxIssueCount", 200),
            "skip": None,
            "source": "KnownIssueTab",
            "locale": settings.get("locale", "ja-JP")
        }
        
        logging.info(f"Filtering by {len(product_ids)} products, status={payload['issueStatus']}")

    logging.info(f"Calling API: {url}")
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"API Request failed: {e}")
        if e.response:
            logging.error(f"Response status: {e.response.status_code}")
            logging.error(f"Response body: {e.response.text}")
        raise
