# CORS模倣（CORS Mimicry）技術解説

このドキュメントでは、本プロジェクトで使用している「CORS模倣」の技術的背景と仕組みについて解説します。

---

## 1. 概要

本プロジェクトでは、ブラウザ（SPA）で取得したリフレッシュトークンをPythonから使用するために、「CORS模倣」という手法を採用しています。

本ドキュメントでは以下を説明します：

- CORSの基本概念
- SPAトークンの特性
- CORS模倣が必要な理由
- 実装方法

---

## 2. CORSの基本概念

### 2.1 Same Origin Policy（同一オリジンポリシー）

ブラウザには「同一オリジンポリシー」というセキュリティ機構が実装されています。

**Origin（オリジン）** = プロトコル + ドメイン + ポート

```
https://admin.powerplatform.microsoft.com:443/support/issues
└─────────────────────────────────────────┘
          ↑ これがOrigin
```

### 2.2 Same Origin Policyの目的

異なるOrigin間でのリソースアクセスを制限することで、悪意あるサイトによる情報窃取を防ぎます。

```
【保護されるシナリオ】

悪意あるサイト: https://attacker.example
  │
  │  iframe等で正規サイトを埋め込み
  │  JavaScriptで情報を読み取ろうとする
  ▼
Same Origin Policy により ❌ ブロック
（attacker.example ≠ 正規サイトのOrigin）
```

### 2.3 CORS（Cross-Origin Resource Sharing）

CORSは、**許可されたクロスオリジン通信を安全に行う仕組み**です。

```
【CORSの仕組み】

ブラウザ                                      サーバー
   │                                            │
   │  ① リクエスト                               │
   │  Origin: https://admin.powerplatform...    │
   │ ────────────────────────────────────────►  │
   │                                            │
   │  ② レスポンス                               │
   │  Access-Control-Allow-Origin: https://...  │
   │ ◄────────────────────────────────────────  │
   │                                            │
   ▼ ③ ブラウザが許可されたOriginか確認          │
```

---

## 3. ブラウザが自動付与するヘッダー

ブラウザはセキュリティのため、以下のヘッダーを**自動的に付与**します。これらはJavaScriptから変更できません。

| ヘッダー | 説明 | 例 |
|---------|------|-----|
| `Origin` | リクエスト元のドメイン | `https://admin.powerplatform.microsoft.com` |
| `Sec-Fetch-Site` | リクエストの種類 | `same-origin`, `cross-site` |
| `Sec-Fetch-Mode` | リクエストモード | `cors`, `navigate` |
| `Sec-Fetch-Dest` | リクエストの宛先 | `document`, `empty` |

```javascript
// ブラウザ上のJavaScript
fetch("https://api.example.com", {
    headers: {
        "Origin": "https://other.com"  // ← 無視される
    }
});
// ブラウザは自動的に正しいOriginを付与する
```

---

## 4. SPAトークンの特性

### 4.1 トークンの種類とフラグ

Azure ADは、トークンを発行する際にアプリケーションの種類に応じたフラグを付与します。

| アプリ種類 | 特徴 | トークンの制約 |
|-----------|------|---------------|
| **SPA** | ブラウザ上で動作 | CORSリクエストからのみ使用可能 |
| **Public Client** | デスクトップ/CLI | 制約なし |
| **Confidential Client** | サーバーサイド | Client Secret必須 |

### 4.2 Power Platform Admin Centerの場合

Power Platform Admin Center はSPAとして実装されているため、取得したリフレッシュトークンには「SPAフラグ」が付与されます。

```
┌─────────────────────────────────────┐
│  リフレッシュトークン                   │
│  ┌─────────────────────────────┐    │
│  │ SPAフラグ = true             │    │
│  │ client_id = 065d9450-...    │    │
│  │ scope = api.powerplatform...│    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

### 4.3 Azure ADの検証

Azure ADは、SPAフラグ付きトークンの使用時にOriginヘッダーの存在を確認します。

```
トークン更新リクエスト受信
        ↓
SPAフラグの確認
        ↓
┌─────────────────────────────┐
│ Originヘッダーあり → ✅ 許可  │
│ Originヘッダーなし → ❌ 拒否  │
│   エラー: AADSTS9002327      │
└─────────────────────────────┘
```

---

## 5. CORS模倣の仕組み

### 5.1 課題

| 環境 | Originヘッダー | 結果 |
|------|---------------|------|
| ブラウザから | 自動付与 | 成功 |
| Pythonから（そのまま） | なし | AADSTS9002327 エラー |

### 5.2 解決策

Pythonからリクエストを送信する際に、ブラウザと同等のヘッダーを明示的に設定します。

```python
# src/auth_manager.py より
headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://admin.powerplatform.microsoft.com",
    "Referer": "https://admin.powerplatform.microsoft.com/",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "User-Agent": "Mozilla/5.0 ...",
}
```

### 5.3 動作原理

ブラウザではこれらのヘッダーはJavaScriptから変更できませんが、HTTPクライアント（Python、cURL等）からは自由に設定できます。

```
【ブラウザ】                      【Python + CORS模倣】
     │                               │
     │ Origin自動付与                  │ Origin明示的に設定
     │ （変更不可）                    │
     ▼                               ▼
┌─────────────────────────────────────────┐
│              Azure AD                    │
│                                         │
│   SPAトークン + Originヘッダー = ✅ 許可  │
└─────────────────────────────────────────┘
```

---

## 6. 実装上の注意点

### 6.1 必要なヘッダー

| ヘッダー | 値 | 必須 |
|---------|-----|------|
| `Origin` | `https://admin.powerplatform.microsoft.com` | ✅ |
| `Sec-Fetch-Site` | `cross-site` | ✅ |
| `Sec-Fetch-Mode` | `cors` | ✅ |
| `Sec-Fetch-Dest` | `empty` | ✅ |
| `User-Agent` | ブラウザのUA | 推奨 |
| `Referer` | Originと同じ | 推奨 |

### 6.2 トークンのローテーション

リフレッシュトークンは使用するたびに新しいものが発行される場合があります。新しいトークンを必ず保存してください。

```python
if new_refresh_token and new_refresh_token != refresh_token:
    # 新しいリフレッシュトークンを保存
    save_token(new_refresh_token)
```

---

## 7. 正規の方法との比較

| 項目 | 正規の方法（アプリ登録） | CORS模倣 |
|------|------------------------|----------|
| アプリ登録 | 必要 | 不要 |
| 管理者権限 | 必要（初回のみ） | 不要 |
| 安定性 | ◎ 高い | △ 将来的に動作しなくなる可能性 |
| 公式サポート | ◎ あり | ✕ なし |
| 導入の容易さ | △ 手続きが必要 | ◎ すぐに動作 |

正規の方法（独自アプリ登録）が使用可能な場合は、そちらを推奨します。

---

## 8. まとめ

### 技術的なポイント

1. **CORSはブラウザのセキュリティ機構**であり、一般ユーザーを保護する仕組み
2. **SPAで発行されたトークン**は、CORSリクエストからの使用を前提としている
3. **Azure ADはOriginヘッダーをチェック**してトークンの使用を検証する
4. **HTTPクライアントからは明示的にヘッダーを設定**することで、同等のリクエストを構築できる

### 図解

```
┌────────────────┐
│  ブラウザ(SPA)  │ ─── リフレッシュトークン取得（SPAフラグ付き）
└────────────────┘
        │
        │ HARファイル経由でトークン抽出
        ▼
┌────────────────┐
│    Python      │ ─── CORS模倣ヘッダー付きでトークン更新
└────────────────┘
        │
        ▼
┌────────────────┐
│   Azure AD     │ ─── Originヘッダー確認 → 許可
└────────────────┘
        │
        ▼
┌────────────────┐
│ Power Platform │ ─── Known Issues 取得
│      API       │
└────────────────┘
```

---

## 関連ドキュメント

- [oauth-investigation.md](oauth-investigation.md) - OAuth 2.0 の技術調査（トークンフロー、スコープなど）
- [azure-functions-deploy.md](azure-functions-deploy.md) - Azure Functions デプロイ手順
