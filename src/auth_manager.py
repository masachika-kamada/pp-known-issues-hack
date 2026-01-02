import logging
import requests
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from . import config


class AuthManager:
    """
    CORS模倣を使用してトークンをリフレッシュするAuthManager
    
    Key VaultからリフレッシュトークンとAPI_HOSTを取得し、
    ブラウザを模倣したリクエストでトークンをリフレッシュします。
    """
    
    def __init__(self):
        self.kv_url = config.KEY_VAULT_URL
        self.secret_name = config.SECRET_NAME
        self.client_id = config.CLIENT_ID
        self.tenant_id = config.TENANT_ID
        
        if not self.kv_url:
            raise ValueError("KEY_VAULT_URL is not set")
        if not self.tenant_id:
            raise ValueError("TENANT_ID is not set")

        # Initialize Key Vault Client
        credential = DefaultAzureCredential()
        self.secret_client = SecretClient(vault_url=self.kv_url, credential=credential)
        
        # Token endpoint
        self.token_endpoint = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        
        # CORS模倣用のOrigin
        self.origin = "https://admin.powerplatform.microsoft.com"

    def get_api_host(self) -> str:
        """Key VaultからAPI_HOSTを取得（環境変数がない場合）"""
        # 環境変数に設定されている場合はそちらを優先
        if config.API_HOST:
            return config.API_HOST
        
        # Key Vaultから取得
        try:
            secret = self.secret_client.get_secret("ApiHost")
            return secret.value
        except Exception as e:
            logging.error(f"Failed to get ApiHost from Key Vault: {e}")
            raise ValueError("API_HOST is not set in environment or Key Vault")

    def get_access_token(self) -> str:
        """
        CORS模倣でアクセストークンを取得
        
        Key Vaultからリフレッシュトークンを取得し、
        ブラウザを模倣したリクエストでトークンをリフレッシュします。
        新しいリフレッシュトークンが返された場合はKey Vaultを更新します。
        """
        logging.info("Retrieving refresh token from Key Vault...")
        try:
            secret = self.secret_client.get_secret(self.secret_name)
            refresh_token = secret.value
        except Exception as e:
            logging.error(f"Failed to get secret from Key Vault: {e}")
            raise

        logging.info("Acquiring token with CORS mimicry...")
        
        # CORS模倣ヘッダー
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "*/*",
            "Origin": self.origin,
            "Referer": f"{self.origin}/",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        }
        
        data = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": "https://api.powerplatform.com/.default openid profile offline_access",
        }
        
        response = requests.post(self.token_endpoint, headers=headers, data=data, timeout=30)
        
        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            error = error_data.get("error", "unknown")
            error_desc = error_data.get("error_description", response.text[:200])
            error_msg = f"Token refresh failed: {error} - {error_desc}"
            logging.error(error_msg)
            raise Exception(error_msg)
        
        result = response.json()
        access_token = result.get("access_token")
        new_refresh_token = result.get("refresh_token")
        
        # 新しいリフレッシュトークンがあればKey Vaultを更新
        if new_refresh_token and new_refresh_token != refresh_token:
            logging.info("New refresh token received. Updating Key Vault...")
            try:
                self.secret_client.set_secret(self.secret_name, new_refresh_token)
                logging.info("Key Vault updated successfully.")
            except Exception as e:
                logging.warning(f"Failed to update Key Vault: {e}")
                # トークン更新に失敗してもアクセストークンは取得できているので続行
        
        return access_token
