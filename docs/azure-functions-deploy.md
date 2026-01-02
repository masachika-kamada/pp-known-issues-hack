# Azure Functions - デプロイガイド

PP Known Issues Hack を定期実行するための Azure Functions 設定です。

## 📁 ファイル構成

| ファイル | 説明 |
|----------|------|
| `function_app.py` | Azure Functions エントリポイント（ルートディレクトリ） |
| `host.json` | Functions ホスト設定（ルートディレクトリ） |
| `local.settings.json` | ローカル開発用設定（Git除外） |
| `config/products.json` | 監視対象の製品フィルタ設定 |
| `config/outputs.json` | 通知・保存設定（オプション） |

## 🏗️ アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                     Azure Functions                         │
├─────────────────────────────────────────────────────────────┤
│  Timer Trigger (毎日 9:00 JST)                              │
│       ↓                                                     │
│  AuthManager                                                │
│       ↓ Key Vault からリフレッシュトークン取得              │
│  Azure Key Vault                                            │
│       ↓ CORS模倣でトークンリフレッシュ                      │
│  Microsoft Entra ID                                         │
│       ↓ アクセストークンで API 呼び出し                     │
│  Power Platform Known Issues API                            │
│       ↓                                                     │
│  結果を返却（または保存）                                   │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 セットアップ手順

### 前提条件

- Azure サブスクリプション
- Azure CLI がインストールされていること
- Azure Functions Core Tools がインストールされていること

### Step 1: Azure リソースの作成

```bash
# リソースグループ作成
az group create --name rg-known-issues --location japaneast

# ストレージアカウント作成
az storage account create \
  --name stknownissues \
  --resource-group rg-known-issues \
  --location japaneast \
  --sku Standard_LRS

# Key Vault 作成
az keyvault create \
  --name kv-known-issues \
  --resource-group rg-known-issues \
  --location japaneast

# Function App 作成
az functionapp create \
  --name func-known-issues \
  --resource-group rg-known-issues \
  --storage-account stknownissues \
  --consumption-plan-location japaneast \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4
```

### Step 2: マネージドID の設定

```bash
# システム割り当てマネージドIDを有効化
az functionapp identity assign \
  --name func-known-issues \
  --resource-group rg-known-issues

# マネージドIDにKey Vaultへのアクセス権を付与
az keyvault set-policy \
  --name kv-known-issues \
  --object-id <マネージドIDのオブジェクトID> \
  --secret-permissions get set
```

### Step 3: シークレットの登録

まず、ローカルで `scripts/` のスクリプトを使用してリフレッシュトークンとAPI_HOSTを取得してから：

```bash
# リフレッシュトークンを Key Vault に登録
az keyvault secret set \
  --vault-name kv-known-issues \
  --name UserRefreshToken \
  --file ../data/refresh_token.txt

# API_HOST を Key Vault に登録
# （.env ファイルから API_HOST の値を確認してください）
az keyvault secret set \
  --vault-name kv-known-issues \
  --name ApiHost \
  --value "<your-api-host>"
```

> **📝 API_HOST の確認方法**
> `.env` ファイルの `API_HOST` の値、または HAR ファイルの Network タブで
> `knownissue` リクエストのホスト名を確認してください。

### Step 4: アプリケーション設定

```bash
az functionapp config appsettings set \
  --name func-known-issues \
  --resource-group rg-known-issues \
  --settings \
    KEY_VAULT_URL="https://kv-known-issues.vault.azure.net/" \
    SECRET_NAME="UserRefreshToken" \
    CLIENT_ID="065d9450-1e87-434e-ac2f-69af271549ed" \
    TENANT_ID="<your-tenant-id>"
```

> **📝 注意**
> - `API_HOST` は Key Vault の `ApiHost` シークレットから自動取得されます
> - 環境変数 `API_HOST` を設定した場合は、そちらが優先されます

### Step 5: デプロイ

```bash
# プロジェクトルートディレクトリから実行
cd known-issue

# デプロイ
func azure functionapp publish func-known-issues
```

## 🎛️ 製品フィルタ設定

`config/products.json` で監視対象の製品を設定できます：

```json
{
  "products": [
    {
      "id": "0ee2e3ac-7684-d519-19e7-b341d426aed7",
      "name": "Power Apps",
      "enabled": true
    },
    ...
  ],
  "settings": {
    "issueStatus": "Active",
    "maxIssueCount": 200,
    "locale": "ja-JP"
  }
}
```

`enabled: true` の製品のみが監視対象になります。

## ⚙️ ローカル開発

### local.settings.json の設定

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "KEY_VAULT_URL": "https://kv-known-issues.vault.azure.net/",
    "SECRET_NAME": "UserRefreshToken",
    "CLIENT_ID": "065d9450-1e87-434e-ac2f-69af271549ed",
    "TENANT_ID": "<your-tenant-id>"
  }
}
```

> **📝 注意**
> - `API_HOST` は Key Vault から取得されるため、ローカル設定に含める必要はありません
> - ローカルで Azure にログインしていれば、Key Vault にアクセスできます（`az login`）

### ローカル実行

```bash
# プロジェクトルートから実行
func start
```

### 手動トリガー

HTTP トリガーでテスト実行：

```bash
curl http://localhost:7071/api/manual_trigger
```

## 📅 スケジュール設定

`function_app.py` のタイマートリガー設定：

```python
@app.schedule(schedule="0 0 9 * * *", ...)
```

これは NCRONTAB 形式で「毎日 9:00 (UTC)」を意味します。

日本時間で毎日 9:00 に実行したい場合は、タイムゾーン設定を追加：

```bash
az functionapp config appsettings set \
  --name func-known-issues \
  --resource-group rg-known-issues \
  --settings WEBSITE_TIME_ZONE="Tokyo Standard Time"
```

そして CRON 式を `0 0 0 * * *` (UTC 0:00 = JST 9:00) に変更。

## 🔧 トラブルシューティング

### Key Vault アクセスエラー

```
Azure Key Vault error: Access denied
```

→ マネージドIDに Key Vault へのアクセス権が付与されているか確認してください。

### トークンリフレッシュ失敗

→ Key Vault に保存されているリフレッシュトークンが期限切れの可能性があります。ローカルで新しいトークンを取得し、再度 Key Vault に登録してください。

## 📖 関連ドキュメント

- [scripts/README.md](../scripts/README.md) - ローカル実行手順
- [docs/oauth-investigation.md](../docs/oauth-investigation.md) - OAuth技術詳細
