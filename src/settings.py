"""
設定ファイルを読み込むモジュール
"""
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

# プロジェクトルートを基準にconfig/を探す
def _find_config_dir() -> Path:
    """設定ディレクトリを探す"""
    # Azure Functions の場合は環境変数で指定可能
    config_path = os.getenv("CONFIG_PATH")
    if config_path:
        return Path(config_path)
    
    # 現在のファイルから辿る
    current = Path(__file__).parent
    while current != current.parent:
        config_dir = current / "config"
        if config_dir.exists():
            return config_dir
        current = current.parent
    
    # フォールバック: カレントディレクトリ
    return Path.cwd() / "config"


CONFIG_DIR = _find_config_dir()


def load_products_config() -> Dict[str, Any]:
    """products.json を読み込む"""
    config_file = CONFIG_DIR / "products.json"
    if not config_file.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {config_file}")
    
    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


def load_outputs_config() -> Dict[str, Any]:
    """outputs.json を読み込む"""
    config_file = CONFIG_DIR / "outputs.json"
    if not config_file.exists():
        # オプション機能なので存在しない場合は空を返す
        return {"storage": {"enabled": False}, "notifications": {}}
    
    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


def get_enabled_product_ids() -> List[str]:
    """有効な製品IDのリストを取得"""
    config = load_products_config()
    return [
        p["id"] for p in config.get("products", [])
        if p.get("enabled", False)
    ]


def get_issue_settings() -> Dict[str, Any]:
    """issueStatus, maxIssueCount, locale などの設定を取得"""
    config = load_products_config()
    return config.get("settings", {
        "issueStatus": "Active",
        "maxIssueCount": 200,
        "locale": "ja-JP"
    })


def get_storage_config() -> Optional[Dict[str, Any]]:
    """ストレージ設定を取得（無効なら None）"""
    config = load_outputs_config()
    storage = config.get("storage", {})
    if storage.get("enabled", False):
        return storage
    return None


def get_notification_configs() -> Dict[str, Dict[str, Any]]:
    """有効な通知設定を取得"""
    config = load_outputs_config()
    notifications = config.get("notifications", {})
    return {
        key: value for key, value in notifications.items()
        if value.get("enabled", False)
    }
