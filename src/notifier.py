"""
通知モジュール - メール通知（SendGrid/SMTP）とWebhook通知をサポート
"""
import os
import logging
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any


# 通知方式の定数
NOTIFY_MODE_WEBHOOK = "webhook"
NOTIFY_MODE_EMAIL = "email"
NOTIFY_MODE_SENDGRID = "sendgrid"
NOTIFY_MODE_ACS = "acs"  # Azure Communication Services


def get_notify_mode() -> str:
    """通知方式を環境変数から取得（デフォルトはwebhook）"""
    return os.environ.get("NOTIFY_MODE", NOTIFY_MODE_WEBHOOK).lower()


def get_email_subject(item_count: int) -> str:
    """メール件名を取得（環境変数でカスタマイズ可能）"""
    template = os.environ.get(
        "EMAIL_SUBJECT", 
        "[Power Platform] {count}件の既知の問題が更新されました"
    )
    return template.format(count=item_count)


def get_webhook_url() -> str:
    """Webhook URL を環境変数から取得"""
    url = os.environ.get("POWER_AUTOMATE_WEBHOOK_URL")
    if not url:
        raise ValueError("POWER_AUTOMATE_WEBHOOK_URL is not set")
    return url


def get_sendgrid_config() -> Dict[str, str]:
    """SendGrid設定を環境変数から取得"""
    config = {
        "api_key": os.environ.get("SENDGRID_API_KEY"),
        "from_address": os.environ.get("EMAIL_FROM"),
        "from_name": os.environ.get("EMAIL_FROM_NAME", "Power Platform Monitor"),
        "to_address": os.environ.get("EMAIL_TO"),
    }
    
    required = ["api_key", "from_address", "to_address"]
    missing = [k for k in required if not config.get(k)]
    if missing:
        raise ValueError(f"Missing SendGrid config: {', '.join(missing)}")
    
    return config


def get_smtp_config() -> Dict[str, str]:
    """SMTP設定を環境変数から取得"""
    config = {
        "smtp_server": os.environ.get("SMTP_SERVER", "smtp.office365.com"),
        "smtp_port": int(os.environ.get("SMTP_PORT", "587")),
        "smtp_user": os.environ.get("SMTP_USER"),
        "smtp_password": os.environ.get("SMTP_PASSWORD"),
        "from_address": os.environ.get("EMAIL_FROM"),
        "from_name": os.environ.get("EMAIL_FROM_NAME", "Power Platform Monitor"),
        "to_address": os.environ.get("EMAIL_TO"),
    }
    
    required = ["smtp_user", "smtp_password", "from_address", "to_address"]
    missing = [k for k in required if not config.get(k)]
    if missing:
        raise ValueError(f"Missing SMTP config: {', '.join(missing)}")
    
    return config


def get_acs_config() -> Dict[str, str]:
    """Azure Communication Services設定を環境変数から取得"""
    config = {
        "connection_string": os.environ.get("ACS_CONNECTION_STRING"),
        "from_address": os.environ.get("EMAIL_FROM"),
        "to_address": os.environ.get("EMAIL_TO"),
    }
    
    required = ["connection_string", "from_address", "to_address"]
    missing = [k for k in required if not config.get(k)]
    if missing:
        raise ValueError(f"Missing ACS config: {', '.join(missing)}")
    
    return config


def send_notification(new_items: List[Dict[str, Any]], total_count: int) -> bool:
    """
    通知を送信（環境変数の設定に応じてACS/SendGrid/SMTP/Webhook）
    
    Args:
        new_items: 新規/更新されたアイテムのリスト
        total_count: 全件数
    
    Returns:
        成功した場合 True
    """
    mode = get_notify_mode()
    
    if mode == NOTIFY_MODE_ACS:
        return send_acs_notification(new_items, total_count)
    elif mode == NOTIFY_MODE_SENDGRID:
        return send_sendgrid_notification(new_items, total_count)
    elif mode == NOTIFY_MODE_EMAIL:
        return send_smtp_notification(new_items, total_count)
    else:
        return send_webhook_notification(new_items, total_count)


def send_acs_notification(new_items: List[Dict[str, Any]], total_count: int) -> bool:
    """Azure Communication Services でメール送信"""
    try:
        config = get_acs_config()
    except ValueError as e:
        logging.warning(f"ACS notification skipped: {e}")
        return False
    
    logging.info(f"Sending ACS email notification for {len(new_items)} items...")
    
    subject = get_email_subject(len(new_items))
    body = _create_email_body(new_items, total_count)
    
    try:
        from azure.communication.email import EmailClient
        
        client = EmailClient.from_connection_string(config["connection_string"])
        
        message = {
            "senderAddress": config["from_address"],
            "recipients": {
                "to": [{"address": config["to_address"]}]
            },
            "content": {
                "subject": subject,
                "plainText": body["text"],
                "html": body["html"]
            }
        }
        
        poller = client.begin_send(message)
        result = poller.result()
        
        logging.info(f"ACS email sent successfully. Message ID: {result['id']}")
        return True
        
    except Exception as e:
        logging.error(f"ACS email notification failed: {e}")
        return False


def send_sendgrid_notification(new_items: List[Dict[str, Any]], total_count: int) -> bool:
    """SendGrid API でメール送信"""
    try:
        config = get_sendgrid_config()
    except ValueError as e:
        logging.warning(f"SendGrid notification skipped: {e}")
        return False
    
    logging.info(f"Sending SendGrid notification for {len(new_items)} items...")
    
    subject = get_email_subject(len(new_items))
    body = _create_email_body(new_items, total_count)
    
    # SendGrid API v3 のペイロード
    payload = {
        "personalizations": [
            {
                "to": [{"email": config["to_address"]}],
                "subject": subject
            }
        ],
        "from": {
            "email": config["from_address"],
            "name": config["from_name"]
        },
        "content": [
            {"type": "text/plain", "value": body["text"]},
            {"type": "text/html", "value": body["html"]}
        ]
    }
    
    try:
        response = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            json=payload,
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json"
            },
            timeout=30
        )
        
        # SendGridは成功時に202を返す
        if response.status_code == 202:
            logging.info(f"SendGrid notification sent successfully to {config['to_address']}")
            return True
        else:
            logging.error(f"SendGrid notification failed. Status: {response.status_code}, Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.RequestException as e:
        logging.error(f"SendGrid notification request failed: {e}")
        return False


def send_webhook_notification(new_items: List[Dict[str, Any]], total_count: int) -> bool:
    """Power Automate Webhook に通知を送信"""
    try:
        webhook_url = get_webhook_url()
    except ValueError as e:
        logging.warning(f"Webhook notification skipped: {e}")
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
    
    logging.info(f"Sending webhook notification for {len(new_items)} items...")
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code in [200, 202]:
            logging.info(f"Webhook notification sent successfully. Status: {response.status_code}")
            return True
        else:
            logging.error(f"Webhook notification failed. Status: {response.status_code}, Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Webhook notification request failed: {e}")
        return False


def send_smtp_notification(new_items: List[Dict[str, Any]], total_count: int) -> bool:
    """SMTPでメール送信"""
    try:
        config = get_smtp_config()
    except ValueError as e:
        logging.warning(f"SMTP notification skipped: {e}")
        return False
    
    logging.info(f"Sending SMTP notification for {len(new_items)} items...")
    
    subject = get_email_subject(len(new_items))
    body = _create_email_body(new_items, total_count)
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{config['from_name']} <{config['from_address']}>"
        msg["To"] = config["to_address"]
        
        text_part = MIMEText(body["text"], "plain", "utf-8")
        html_part = MIMEText(body["html"], "html", "utf-8")
        msg.attach(text_part)
        msg.attach(html_part)
        
        with smtplib.SMTP(config["smtp_server"], config["smtp_port"]) as server:
            server.starttls()
            server.login(config["smtp_user"], config["smtp_password"])
            server.send_message(msg)
        
        logging.info(f"SMTP notification sent successfully to {config['to_address']}")
        return True
        
    except smtplib.SMTPException as e:
        logging.error(f"SMTP notification failed: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error sending email: {e}")
        return False


def _create_email_body(items: List[Dict[str, Any]], total_count: int) -> Dict[str, str]:
    """メール本文を作成（テキストとHTML）"""
    
    # プレーンテキスト版
    text_lines = [
        f"Power Platform Known Issues 更新通知",
        f"",
        f"全件数: {total_count}件",
        f"更新件数: {len(items)}件",
        f"",
        "=" * 50,
    ]
    
    if items:
        for item in items:
            text_lines.extend([
                f"",
                f"■ {item.get('title', 'No Title')}",
                f"  Work Item ID: {item.get('workItemId', '')}",
                f"  製品: {item.get('product', '')}",
                f"  状態: {item.get('state', '')}",
                f"  更新日時: {item.get('changedDate', '')}",
                f"  概要: {_truncate(item.get('description', ''), 200)}",
                "",
            ])
    else:
        text_lines.extend([
            f"",
            f"本日の更新はありませんでした。",
            f"",
        ])
    
    # HTML版
    html_items = ""
    if items:
        for item in items:
            html_items += f"""
            <div style="margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 5px;">
                <h3 style="margin: 0 0 10px 0; color: #0078d4;">{item.get('title', 'No Title')}</h3>
                <table style="font-size: 14px;">
                    <tr><td style="padding: 2px 10px 2px 0; color: #666;">Work Item ID:</td><td>{item.get('workItemId', '')}</td></tr>
                    <tr><td style="padding: 2px 10px 2px 0; color: #666;">製品:</td><td>{item.get('product', '')}</td></tr>
                    <tr><td style="padding: 2px 10px 2px 0; color: #666;">状態:</td><td>{item.get('state', '')}</td></tr>
                    <tr><td style="padding: 2px 10px 2px 0; color: #666;">更新日時:</td><td>{item.get('changedDate', '')}</td></tr>
                </table>
                <p style="margin: 10px 0 0 0; font-size: 13px; color: #333;">{_truncate(item.get('description', ''), 300)}</p>
            </div>
            """
    else:
        html_items = """
        <div style="padding: 30px; text-align: center; background-color: #f8f9fa; border-radius: 5px;">
            <p style="font-size: 18px; color: #28a745; margin: 0;">✅ 本日の更新はありませんでした</p>
            <p style="font-size: 14px; color: #666; margin-top: 10px;">システムは正常に稼働しています。</p>
        </div>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: 'Segoe UI', sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #0078d4; border-bottom: 2px solid #0078d4; padding-bottom: 10px;">
            Power Platform Known Issues 更新通知
        </h1>
        <p style="font-size: 16px;">
            <strong>全件数:</strong> {total_count}件 | 
            <strong>更新件数:</strong> {len(items)}件
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        {html_items}
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; color: #999;">
            このメールは Power Platform Known Issues 自動監視システムから送信されました。
        </p>
    </body>
    </html>
    """
    
    return {
        "text": "\n".join(text_lines),
        "html": html
    }


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
