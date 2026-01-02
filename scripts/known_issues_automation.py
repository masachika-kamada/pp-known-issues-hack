"""
Power Platform Known Issues 自動取得スクリプト

CORS模倣を使用してブラウザのリフレッシュトークンから
アクセストークンを取得し、Known Issues APIを呼び出します。

使用方法:
  1. 初回: ブラウザのネットワークトレースからHARファイルをエクスポート
  2. python scripts/extract_token.py <har_file> でリフレッシュトークンを抽出
  3. python scripts/known_issues_automation.py で実行

リフレッシュトークンの更新:
  - スクリプトは自動的に新しいリフレッシュトークンを保存します
  - ただし、長期間（90日程度）使用しないと期限切れになります
  - 期限切れの場合は、再度ブラウザからトークンを取得してください
"""

import requests
import json
import base64
import os
import sys
from datetime import datetime
from pathlib import Path

# =============================================================================
# 設定
# =============================================================================

# プロジェクトルートを基準にパスを設定
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"

# .envファイルを読み込む（python-dotenv不要の簡易実装）
def load_dotenv():
    """プロジェクトルートの.envファイルから環境変数を読み込む"""
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key not in os.environ:  # 既存の環境変数を上書きしない
                        os.environ[key] = value

load_dotenv()

# 環境変数から設定を読み込む
TENANT_ID = os.environ.get("TENANT_ID")
API_HOST = os.environ.get("API_HOST")
CLIENT_ID = os.environ.get("CLIENT_ID", "065d9450-1e87-434e-ac2f-69af271549ed")

# 設定の検証
if not TENANT_ID or not API_HOST:
    print("❌ エラー: 必須の環境変数が設定されていません。")
    print()
    print("以下の手順で設定してください:")
    print("  1. .env.example を .env にコピー")
    print("  2. .env ファイルに値を設定")
    print()
    print("必要な環境変数:")
    print("  - TENANT_ID: Azure AD テナントID")
    print("  - API_HOST: Power Platform API のホスト名")
    print("             (HARファイルのリクエストURLから確認)")
    sys.exit(1)


TOKEN_ENDPOINT = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"

# ブラウザが使用する Origin（CORS模倣用）
ORIGIN = "https://admin.powerplatform.microsoft.com"

# Known Issues API
API_URL = f"https://{API_HOST}/support/knownissue/search?api-version=2022-03-01-preview"

# トークン保存ファイル（data/ディレクトリに保存）
REFRESH_TOKEN_FILE = DATA_DIR / "refresh_token.txt"
ACCESS_TOKEN_FILE = DATA_DIR / "access_token.txt"

# 出力ファイル
OUTPUT_FILE = DATA_DIR / "known_issues.json"


# =============================================================================
# トークン管理
# =============================================================================

def decode_jwt(token):
    """JWTトークンをデコード"""
    try:
        parts = token.split('.')
        if len(parts) >= 2:
            payload = parts[1]
            payload += '=' * (4 - len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload)
            return json.loads(decoded)
    except:
        return None


def refresh_access_token(refresh_token):
    """
    CORS模倣でアクセストークンをリフレッシュ
    """
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "*/*",
        "Origin": ORIGIN,
        "Referer": f"{ORIGIN}/",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    }
    
    data = {
        "client_id": CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": "https://api.powerplatform.com/.default openid profile offline_access",
    }
    
    response = requests.post(TOKEN_ENDPOINT, headers=headers, data=data, timeout=30)
    
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data.get("access_token")
        new_refresh_token = token_data.get("refresh_token")
        
        # dataディレクトリが存在しない場合は作成
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # アクセストークンを保存
        with open(ACCESS_TOKEN_FILE, "w") as f:
            f.write(access_token)
        
        # 新しいリフレッシュトークンがあれば保存
        if new_refresh_token and new_refresh_token != refresh_token:
            with open(REFRESH_TOKEN_FILE, "w") as f:
                f.write(new_refresh_token)
            print(f"[INFO] 新しいリフレッシュトークンを保存しました")
        
        return access_token
    else:
        error_data = response.json() if response.text else {}
        error = error_data.get("error", "unknown")
        error_desc = error_data.get("error_description", response.text[:200])
        raise Exception(f"トークンリフレッシュ失敗: {error} - {error_desc}")


# =============================================================================
# API呼び出し
# =============================================================================

def get_known_issues(access_token, product_ids=None, max_count=200):
    """
    Known Issues を取得
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # デフォルトの製品ID（全製品）
    if product_ids is None:
        product_ids = ["00000000-0000-0000-0000-000000000000"]
    
    body = {
        "productIds": product_ids,
        "minMatchingScore": 0.00001,
        "searchText": "*",
        "issueStatus": "Unknown",
        "maxIssueCount": max_count,
        "skip": None,
        "source": "KnownIssueTab",
        "locale": "ja-JP"
    }
    
    response = requests.post(API_URL, headers=headers, json=body, timeout=60)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API呼び出し失敗: {response.status_code} - {response.text[:200]}")


# =============================================================================
# メイン処理
# =============================================================================

def main():
    print("=" * 60)
    print("Power Platform Known Issues 自動取得")
    print(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    # リフレッシュトークンを読み込み
    if not REFRESH_TOKEN_FILE.exists():
        print("❌ リフレッシュトークンが見つかりません。")
        print(f"   期待するファイル: {REFRESH_TOKEN_FILE}")
        print()
        print("初回セットアップ手順:")
        print("  1. Power Platform Admin Center で既知の問題ページを開く")
        print("  2. F12 → Network → HAR形式でエクスポート")
        print("  3. python scripts/extract_token.py <har_file> を実行")
        return 1
    
    with open(REFRESH_TOKEN_FILE, "r") as f:
        refresh_token = f.read().strip()
    
    print(f"[1/3] トークンをリフレッシュ中...")
    try:
        access_token = refresh_access_token(refresh_token)
        print(f"      ✅ 成功")
    except Exception as e:
        print(f"      ❌ 失敗: {e}")
        print()
        print("リフレッシュトークンが期限切れの可能性があります。")
        print("ブラウザから新しいトークンを取得してください。")
        return 1
    
    print(f"[2/3] Known Issues を取得中...")
    try:
        issues = get_known_issues(access_token)
        print(f"      ✅ {len(issues)} 件取得")
    except Exception as e:
        print(f"      ❌ 失敗: {e}")
        return 1
    
    print(f"[3/3] 結果を保存中...")
    
    # 結果を保存
    output_data = {
        "retrieved_at": datetime.now().isoformat(),
        "count": len(issues),
        "issues": issues
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"      ✅ {OUTPUT_FILE} に保存しました")
    print()
    
    # サマリーを表示
    print("=" * 60)
    print("取得結果サマリー")
    print("=" * 60)
    
    # 状態別にカウント
    status_count = {}
    product_count = {}
    
    for issue in issues:
        state = issue.get("state", "Unknown")
        product = issue.get("product", "Unknown")
        
        status_count[state] = status_count.get(state, 0) + 1
        product_count[product] = product_count.get(product, 0) + 1
    
    print("\n状態別:")
    for state, count in sorted(status_count.items()):
        print(f"  {state}: {count} 件")
    
    print("\n製品別 (上位5件):")
    for product, count in sorted(product_count.items(), key=lambda x: -x[1])[:5]:
        print(f"  {product}: {count} 件")
    
    print()
    print("✅ 完了")
    return 0


if __name__ == "__main__":
    exit(main())
