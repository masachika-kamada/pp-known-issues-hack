"""
メール送信テスト用スクリプト
"""
import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO)

from src.notifier import send_notification, get_notify_mode

print(f"通知モード: {get_notify_mode()}")

# テスト用のダミーデータ
test_items = [{
    'workItemId': 'TEST-001',
    'title': 'テスト: メール送信確認',
    'product': 'Power Automate',
    'state': 'Active',
    'changedDate': '2026-01-06T12:00:00Z',
    'description': 'これはAzure Communication Servicesからのテストメールです。正常に受信できれば設定は完了です。'
}]

print("テストメールを送信中...")
result = send_notification(test_items, total_count=1)

if result:
    print("✅ メール送信成功！受信トレイを確認してください。")
else:
    print("❌ メール送信失敗。ログを確認してください。")
