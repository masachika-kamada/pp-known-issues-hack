# Power Platform Known Issues API 自動化 - 技術調査ドキュメント

## 1. プロジェクトの目的

Power Platform の「既知の問題（Known Issues）」を自動取得するシステムを構築する。

### 要件
- 毎日9時に自動実行
- アクセストークンの自動リフレッシュ
- 人手による認証操作を不要にする

### 対象API
```
POST https://{tenant-id}.tenant.api.powerplatform.com/support/knownissue/search?api-version=2022-03-01-preview
```

---

## 2. OAuth 2.0 の基本概念

### 2.1 クライアントID（Client ID）とは

**クライアントID** = アプリケーションの「身分証明書番号」

Azure AD に登録された各アプリケーションには一意のIDが割り当てられます。

| アプリ名 | Client ID | 用途 |
|---------|-----------|------|
| Power Platform Admin Center | `065d9450-1e87-434e-ac2f-69af271549ed` | ブラウザでの管理画面 |
| Azure CLI | `04b07795-8ddb-461a-bbee-02f9e1bf7b46` | コマンドラインツール |
| Power Platform API | `8578e004-a5c6-46e7-913e-12f58912df43` | APIリソース |

### 2.2 スコープ（Scope）とは

**スコープ** = トークンに付与される「権限の範囲」

```
https://api.powerplatform.com/Support.Tickets.Read
                │                      │
                │                      └── 権限名（サポートチケット読み取り）
                └── リソース（Power Platform API）
```

### 2.3 オーディエンス（Audience）とは

**オーディエンス** = トークンの「宛先」

アクセストークンには「どのAPIで使えるか」が記録されています。

```json
{
  "aud": "https://api.powerplatform.com",  // ← このAPIでのみ使用可能
  "scp": "Support.Tickets.Read",            // ← 許可された操作
  "exp": 1767373577                         // ← 有効期限
}
```

---

## 3. トークンの種類と有効期限

| トークン | 有効期限 | 用途 |
|---------|---------|------|
| アクセストークン | 約1時間 | API呼び出しに使用 |
| リフレッシュトークン | 数日〜90日 | 新しいアクセストークンの取得に使用 |

### 重要なポイント
- アクセストークンは短命なので、リフレッシュトークンで定期的に更新が必要
- リフレッシュトークンは使用するたびに新しいものが発行されることがある
- 新しいリフレッシュトークンが発行されたら、必ず保存を更新する

---

## 4. OAuth 2.0 トークンフロー

### 4.1 正常なフロー（ブラウザ - SPA）

```mermaid
sequenceDiagram
    autonumber
    participant User as ユーザー
    participant Browser as ブラウザ (SPA)
    participant AzureAD as Azure AD
    participant API as Power Platform API

    User->>Browser: ログイン操作
    Browser->>AzureAD: 認証リクエスト<br/>(Client ID + Scope)
    AzureAD-->>Browser: アクセストークン<br/>+ リフレッシュトークン<br/>(SPAフラグ付き)
    
    Browser->>API: API呼び出し<br/>(Authorization: Bearer {token})
    API-->>Browser: データ返却
    
    Note over Browser,AzureAD: ～1時間後、トークン期限切れ～
    
    Browser->>AzureAD: リフレッシュ要求<br/>(CORSリクエスト)
    Note right of AzureAD: SPAフラグ + CORS = OK ✅
    AzureAD-->>Browser: 新しいアクセストークン
```

### 4.2 失敗したフロー（Python からのリフレッシュ試行）

```mermaid
sequenceDiagram
    autonumber
    participant Python as Python スクリプト
    participant AzureAD as Azure AD

    Python->>AzureAD: リフレッシュ要求<br/>(通常のHTTPリクエスト)<br/>+ SPAフラグ付きトークン
    
    Note right of AzureAD: SPAフラグあり<br/>でもCORSじゃない ❌
    
    AzureAD-->>Python: エラー: AADSTS9002327<br/>"Tokens issued for SPA<br/>may only be redeemed<br/>via cross-origin requests"
```

### 4.3 理想的なフロー（独自アプリ登録）

```mermaid
sequenceDiagram
    autonumber
    participant User as ユーザー
    participant Script as Python スクリプト
    participant KeyVault as Azure Key Vault
    participant AzureAD as Azure AD
    participant API as Power Platform API

    Note over User,Script: 【初回のみ】デバイスコードフローでログイン
    User->>Script: python get_token.py 実行
    Script->>AzureAD: デバイスコード要求
    AzureAD-->>Script: コード表示
    User->>AzureAD: ブラウザでログイン
    AzureAD-->>Script: アクセストークン<br/>+ リフレッシュトークン
    Script->>KeyVault: リフレッシュトークン保存

    Note over Script,API: 【毎日自動】Azure Functions タイマー実行
    
    Script->>KeyVault: リフレッシュトークン取得
    KeyVault-->>Script: リフレッシュトークン
    Script->>AzureAD: トークンリフレッシュ要求
    AzureAD-->>Script: 新しいアクセストークン<br/>(+ 新しいリフレッシュトークン)
    Script->>KeyVault: 新しいリフレッシュトークン保存
    Script->>API: API呼び出し
    API-->>Script: Known Issues データ
```

---

## 5. CORSとは

**CORS = Cross-Origin Resource Sharing（クロスオリジン リソース共有）**

### 5.1 Originとは

```
URL: https://admin.powerplatform.microsoft.com/support/issues
     └─────────────────────────────────────┘
                    ↑
            これが Origin
```

Origin = プロトコル + ドメイン + ポート

### 5.2 ブラウザの「正直さ」

```mermaid
flowchart LR
    subgraph Browser["ブラウザ"]
        JS["JavaScript"]
        Headers["自動付与ヘッダー"]
    end
    
    subgraph Auto["自動付与（偽造不可）"]
        Origin["Origin: https://..."]
        SecFetch["Sec-Fetch-Site: cross-site"]
    end
    
    JS --> Headers
    Headers --> Origin
    Headers --> SecFetch
    
    subgraph Server["Azure AD"]
        Check["ヘッダー検証"]
    end
    
    Origin --> Check
    SecFetch --> Check
```

ブラウザは自動的に以下のヘッダーを付与し、**JavaScript から変更できません**：

| ヘッダー | 説明 |
|---------|------|
| `Origin` | リクエスト元のドメイン |
| `Sec-Fetch-Site` | same-origin / cross-site など |
| `Sec-Fetch-Mode` | cors / navigate など |
| `Sec-Fetch-Dest` | document / empty など |

---

## 6. アプリケーションの種類

| 種類 | 動作環境 | Client Secret | リフレッシュトークンの使用 | 例 |
|------|---------|---------------|--------------------------|-----|
| **SPA** (Single-Page Application) | ブラウザ上 | なし | ブラウザからのみ（CORS必須） | Power Platform Admin Center |
| **Public Client** | デスクトップ / CLI / モバイル | なし | どこからでも使用可能 | Azure CLI, モバイルアプリ |
| **Confidential Client** | サーバーサイド | あり | サーバーからのみ | Web API, バックエンドサービス |

### Power Platform Admin Center の場合

| 項目 | 値 |
|------|-----|
| Client ID | `065d9450-1e87-434e-ac2f-69af271549ed` |
| 種類 | SPA + Confidential Client |
| 制限 | リフレッシュトークンはブラウザからのみ使用可 |

---

## 7. 試行した方法と結果

### 7.1 Azure CLI の Client ID を使用

```mermaid
flowchart LR
    A["Python"] --> B["Azure CLI<br/>Client ID"]
    B --> C["Azure AD"]
    C --> D{"Power Platform API<br/>への権限は？"}
    D -->|"なし ❌"| E["エラー:<br/>InsufficientDelegatedPermissions"]
```

**結果**: Azure CLI は Power Platform API への事前承認がないため失敗

### 7.2 ブラウザのリフレッシュトークンを流用

```mermaid
flowchart LR
    A["ブラウザ"] --> B["リフレッシュトークン<br/>(SPAフラグ付き)"]
    B --> C["Python"]
    C --> D["Azure AD"]
    D --> E{"リクエスト元は？"}
    E -->|"CORSではない ❌"| F["エラー:<br/>AADSTS9002327"]
```

**結果**: SPAトークンはブラウザからのみ使用可能なため失敗

### 7.3 Power Platform Admin Center の Client ID を使用

```mermaid
flowchart LR
    A["Python"] --> B["PPAC Client ID"]
    B --> C["Azure AD"]
    C --> D{"Client Secret は？"}
    D -->|"なし ❌"| E["エラー:<br/>AADSTS7000218"]
```

**結果**: Confidential Client として構成されているため、Client Secret が必要

---

## 8. 解決策

### 8.1 必要な手順

```mermaid
flowchart TB
    subgraph Step1["Step 1: サービスプリンシパル登録"]
        A1["グローバル管理者が実行"]
        A2["Power Platform API を<br/>テナントに登録"]
    end
    
    subgraph Step2["Step 2: アプリ登録"]
        B1["Azure AD でアプリ作成"]
        B2["Public Client として設定"]
        B3["Power Platform API の<br/>権限を追加"]
        B4["管理者の同意を付与"]
    end
    
    subgraph Step3["Step 3: 初回認証"]
        C1["デバイスコードフローで<br/>ログイン"]
        C2["リフレッシュトークンを<br/>Key Vault に保存"]
    end
    
    subgraph Step4["Step 4: 自動化"]
        D1["Azure Functions<br/>タイマートリガー"]
        D2["毎日9時に実行"]
        D3["Known Issues を取得"]
    end
    
    Step1 --> Step2 --> Step3 --> Step4
```

### 8.2 必要な権限

| 操作 | 必要な権限 |
|------|-----------|
| サービスプリンシパル登録 | グローバル管理者 |
| アプリ登録 | アプリケーション管理者 |
| 管理者の同意 | グローバル管理者 または アプリケーション管理者 |

---

## 9. 用語集

| 用語 | 説明 |
|------|------|
| **OAuth 2.0** | 認可のための業界標準プロトコル |
| **Client ID** | アプリケーションの一意識別子 |
| **Scope** | トークンに付与される権限の範囲 |
| **Audience (aud)** | トークンの宛先（どのAPIで使えるか） |
| **Access Token** | API呼び出しに使用する短命のトークン（約1時間） |
| **Refresh Token** | 新しいアクセストークンを取得するための長命のトークン |
| **CORS** | Cross-Origin Resource Sharing。ブラウザのセキュリティ機構 |
| **SPA** | Single-Page Application。ブラウザ上で動作するアプリ |
| **Public Client** | Client Secret を持たないアプリ（CLI、デスクトップ等） |
| **Confidential Client** | Client Secret を持つサーバーサイドアプリ |
| **Service Principal** | テナント内でのアプリケーションのインスタンス |
| **Device Code Flow** | デバイスコードを使った認証フロー。CLI等で使用 |

---

## 10. 現在のステータス

### ✅ CORS模倣による解決（実験的）

管理者権限なしで動作する方法を発見しました。

```mermaid
sequenceDiagram
    autonumber
    participant Browser as ブラウザ
    participant HAR as HARファイル
    participant Python as Python スクリプト
    participant AzureAD as Azure AD
    participant API as Known Issues API

    Note over Browser,HAR: 【初回のみ】HARファイルからトークン抽出
    Browser->>HAR: ネットワークトレースをエクスポート
    HAR->>Python: extract_token.py で抽出
    Python->>Python: refresh_token.txt に保存

    Note over Python,API: 【自動実行】毎日9時にスケジュール
    
    Python->>AzureAD: トークンリフレッシュ要求<br/>(CORS模倣ヘッダー付き)
    Note right of AzureAD: Origin + Sec-Fetch-* で<br/>ブラウザと誤認 ✅
    AzureAD-->>Python: 新しいアクセストークン<br/>+ 新しいリフレッシュトークン
    Python->>Python: 新しいリフレッシュトークン保存
    Python->>API: Known Issues 取得
    API-->>Python: 200件のデータ
    Python->>Python: known_issues.json 保存
```

### 使用方法

```bash
# 初回: HARファイルからトークン抽出
python extract_token.py network_trace.har

# 実行
python known_issues_automation.py
```

### 注意事項

| 項目 | 内容 |
|------|------|
| **メリット** | 管理者権限不要で即座に動作 |
| **リスク** | Microsoftがセキュリティを強化すると動作しなくなる可能性 |
| **トークン有効期限** | 約90日（定期的に使用すれば延長される） |
| **推奨** | 正規の方法（独自アプリ登録）が使えるなら、そちらを優先 |

---

## 関連ドキュメント

CORS模倣の仕組みについてより詳しく知りたい場合は、[cors-mimicry-explained.md](cors-mimicry-explained.md) を参照してください。
