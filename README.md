# PP Known Issues Hack

> [!NOTE]
> ## 📋 技術検証の結果
> 
> このプロジェクトは Power Platform Known Issues API の非公式アクセス方法を検証したものです。
> 
> ### 検証結果
> 
> CORS模倣方式でのAPI呼び出し自体は成功しましたが、**SPAトークンの24時間制限**により継続的な自動実行には向かないことが判明しました。
> 
> - Power Platform Admin Center の `client_id` は SPA として登録されている
> - SPAのリフレッシュトークンは**セッション開始から24時間で失効**（`AADSTS700084`）
> - リフレッシュしても有効期限は延長されない（Microsoft の仕様）
> 
> ### 参考
> 
> - [Microsoft Q&A: Refresh Token Expiry in Azure AD SPA](https://learn.microsoft.com/en-us/answers/questions/1855103/issue-with-refresh-token-expiry-in-azure-ad-spa-ap)
> - [GitHub MSAL.js Issue #4613](https://github.com/AzureAD/microsoft-authentication-library-for-js/issues/4613)

---

Power Platform の「既知の問題（Known Issues）」を **アプリ登録なし・管理者権限なし** で自動取得するツールです。

## 🎯 概要

Power Platform Admin Center の Known Issues は公式 API が公開されていないため、通常はアプリ登録や管理者権限が必要です。このツールは **ブラウザの認証情報を流用** することで、これらの障壁をバイパスします。

### ✨ 特徴

- 🔓 **アプリ登録不要** - Azure AD へのアプリ登録なしで動作
- 👤 **管理者権限不要** - 一般ユーザーの権限で OK
- 🔄 **トークン自動更新** - リフレッシュトークンのローテーション対応
- ☁️ **Azure Functions 対応** - 定期実行も可能

### ⚠️ 注意事項

このツールは **CORS 模倣** という実験的な方法を使用しています。

| 項目 | 内容 |
|------|------|
| 仕組み | ブラウザからのリクエストを模倣してトークンを取得 |
| メリット | 管理者権限不要で即座に動作 |
| リスク | Microsoft がセキュリティを強化すると動作しなくなる可能性 |
| トークン有効期限 | **24時間（延長不可）** - SPAトークンの仕様により自動化は不可能 |

## 📁 ディレクトリ構成

```
pp-known-issues-hack/
├── .env.example          # 環境変数テンプレート
├── .env                  # ⚠️ Git除外
├── requirements.txt      # 依存関係
│
├── function_app.py       # ☁️ Azure Functions エントリポイント
├── host.json             # Azure Functions 設定
├── local.settings.json   # ⚠️ Git除外（ローカル設定）
│
├── config/               # ⚙️ 設定ファイル
│   ├── products.json     # 製品フィルタ設定
│   └── outputs.json      # 通知・保存設定（オプション）
│
├── scripts/              # 📄 ローカル実行スクリプト
│   ├── README.md         # ← 詳細な使用方法はこちら
│   ├── extract_token.py
│   └── known_issues_automation.py
│
├── data/                 # 📊 出力データ（Git除外）
│   ├── refresh_token.txt
│   ├── access_token.txt
│   └── known_issues.json
│
├── src/                  # 🔧 共通モジュール
│   ├── auth_manager.py
│   ├── api_client.py
│   ├── config.py
│   └── settings.py
│
└── docs/                 # 📖 技術ドキュメント
    ├── azure-functions-deploy.md  # ← デプロイ手順はこちら
    └── oauth-investigation.md
```

## 🚀 クイックスタート

### 1. 環境設定

```bash
# 依存関係インストール
pip install -r requirements.txt

# 環境変数設定
cp .env.example .env
# .env を編集して TENANT_ID を設定
```

### 2. 実行

詳細な手順は [scripts/README.md](scripts/README.md) を参照してください。

```bash
# HARファイルからトークン抽出
python scripts/extract_token.py <har_file>

# Known Issues 取得
python scripts/known_issues_automation.py
```

### 3. Azure Functions デプロイ（オプション）

定期実行が必要な場合は [docs/azure-functions-deploy.md](docs/azure-functions-deploy.md) を参照してください。

## 📖 ドキュメント

| ドキュメント | 内容 |
|-------------|------|
| [scripts/README.md](scripts/README.md) | ローカル実行の詳細手順、トラブルシューティング |
| [docs/azure-functions-deploy.md](docs/azure-functions-deploy.md) | Azure Functions デプロイ手順、Key Vault 設定 |
| [docs/oauth-investigation.md](docs/oauth-investigation.md) | OAuth 2.0 技術調査、トークンフロー |
| [docs/cors-mimicry-explained.md](docs/cors-mimicry-explained.md) | CORS模倣の仕組み解説（なぜ必要か、セキュリティ観点） |

## 📝 ライセンス

MIT License
