"""
HARファイルからPower Platform API用のリフレッシュトークンを抽出

使用方法:
    python scripts/extract_token.py <har_file>

例:
    python scripts/extract_token.py network_trace.har
"""

import json
import base64
import sys
import os
from pathlib import Path

# プロジェクトルートを基準にパスを設定
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"


def decode_jwt(token):
    """JWTトークンをデコードしてペイロードを取得"""
    try:
        parts = token.split('.')
        if len(parts) >= 2:
            payload = parts[1]
            payload += '=' * (4 - len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload)
            return json.loads(decoded)
    except:
        return None


def extract_powerplatform_token(har_file):
    """
    HARファイルからPower Platform API用のリフレッシュトークンを抽出
    """
    print("=" * 60)
    print("Power Platform API トークン抽出ツール")
    print("=" * 60)
    print()
    
    # ファイル存在確認
    if not os.path.exists(har_file):
        print(f"❌ ファイルが見つかりません: {har_file}")
        return None
    
    print(f"読み込み中: {har_file}")
    
    try:
        with open(har_file, 'r', encoding='utf-8') as f:
            har = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ JSONパースエラー: {e}")
        return None
    except Exception as e:
        print(f"❌ ファイル読み込みエラー: {e}")
        return None
    
    print(f"エントリ数: {len(har['log']['entries'])}")
    print()
    print("Power Platform API 用のトークンを検索中...")
    print()
    
    # 全てのトークンを収集
    found_tokens = []
    
    for entry in har['log']['entries']:
        url = entry['request']['url']
        if 'token' in url and 'login.microsoftonline.com' in url:
            response_content = entry.get('response', {}).get('content', {}).get('text', '')
            if response_content and 'refresh_token' in response_content:
                try:
                    token_data = json.loads(response_content)
                    access_token = token_data.get('access_token', '')
                    refresh_token = token_data.get('refresh_token', '')
                    
                    if access_token and refresh_token:
                        claims = decode_jwt(access_token)
                        if claims:
                            aud = claims.get('aud', '')
                            scp = claims.get('scp', '')
                            
                            found_tokens.append({
                                'audience': aud,
                                'scopes': scp,
                                'refresh_token': refresh_token,
                                'is_powerplatform': 'powerplatform' in aud.lower()
                            })
                except:
                    pass
    
    if not found_tokens:
        print("❌ トークンが見つかりませんでした。")
        print()
        print("確認事項:")
        print("  1. Power Platform Admin Center で既知の問題ページを開いた状態でHARをエクスポートしましたか？")
        print("  2. Preserve log にチェックを入れましたか？")
        print("  3. ページをリロードしましたか？")
        return None
    
    print(f"発見したトークン: {len(found_tokens)} 件")
    print()
    
    # Power Platform API用のトークンを探す
    pp_tokens = [t for t in found_tokens if t['is_powerplatform']]
    
    if not pp_tokens:
        print("❌ Power Platform API 用のトークンが見つかりませんでした。")
        print()
        print("発見したトークンのAudience:")
        for t in found_tokens:
            print(f"  - {t['audience']}")
        return None
    
    # 最初のPower Platform トークンを使用
    token = pp_tokens[0]
    
    print("✅ Power Platform API 用のトークンを発見！")
    print()
    print(f"  Audience: {token['audience']}")
    print(f"  Scopes: {token['scopes'][:60]}...")
    print()
    
    # dataディレクトリが存在しない場合は作成
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # リフレッシュトークンを保存
    refresh_token_file = DATA_DIR / "refresh_token.txt"
    with open(refresh_token_file, 'w') as f:
        f.write(token['refresh_token'])
    
    print(f"✅ {refresh_token_file} に保存しました")
    print(f"   トークン: {token['refresh_token'][:50]}...")
    print()
    print("=" * 60)
    print("次のステップ:")
    print("  python scripts/known_issues_automation.py")
    print("=" * 60)
    
    return token['refresh_token']


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print()
        print("使用例:")
        print("  python scripts/extract_token.py network_trace.har")
        print()
        print("HARファイルの取得方法:")
        print("  1. Power Platform Admin Center (https://admin.powerplatform.microsoft.com/) を開く")
        print("  2. サポート → 既知の問題 を開く")
        print("  3. F12 で開発者ツールを開く")
        print("  4. Network タブ → Preserve log にチェック")
        print("  5. ページをリロード (F5)")
        print("  6. Network タブ内で右クリック → Save all as HAR with content")
        sys.exit(1)
    
    har_file = sys.argv[1]
    result = extract_powerplatform_token(har_file)
    
    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
