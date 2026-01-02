import os

# Key Vault & Auth Config
KEY_VAULT_URL = os.environ.get("KEY_VAULT_URL")
SECRET_NAME = os.environ.get("SECRET_NAME", "UserRefreshToken")
CLIENT_ID = os.environ.get("CLIENT_ID")
TENANT_ID = os.environ.get("TENANT_ID")
API_HOST = os.environ.get("API_HOST")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

# Target API Config
# API_HOST 環境変数から動的に生成
TARGET_API_URL = f"https://{API_HOST}/support/knownissue/search?api-version=2022-03-01-preview" if API_HOST else ""

# Scope (必要に応じて変更してください)
SCOPE = os.environ.get("SCOPE", "https://api.powerplatform.com/.default").split(",")
