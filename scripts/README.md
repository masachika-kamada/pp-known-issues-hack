# Scripts - スクリプト実行ガイド

PP Known Issues Hack のローカル実行スクリプト群です。

## 📁 ファイル構成

| ファイル | 説明 |
|----------|------|
| `extract_token.py` | HARファイルからリフレッシュトークンを抽出 |
| `known_issues_automation.py` | Known Issues API を呼び出してデータを取得 |
| `*.har` | ネットワークトレースファイル（Git除外） |

## 🚀 クイックスタート

### 前提条件

1. Python 3.10+ がインストールされていること
2. プロジェクトルートに `.env` ファイルが設定されていること

### Step 1: 環境変数の設定

プロジェクトルートで `.env` ファイルを作成：

```bash
cd ..
cp .env.example .env
# .env を編集してテナントIDを設定
```

### Step 2: リフレッシュトークンの取得

#### 2-1. HARファイルのエクスポート

1. **Power Platform Admin Center** にアクセス
   - https://admin.powerplatform.microsoft.com/
2. 左メニューから **サポート** → **既知の問題** を開く
3. **F12** で開発者ツールを開く
4. **Network** タブを選択
5. **Preserve log** にチェック ✅
6. ページをリロード（F5）
7. Network タブ内で右クリック → **Save all as HAR with content**
8. このディレクトリ（`scripts/`）に保存

#### 2-2. トークンの抽出

```bash
python extract_token.py network_trace.har
```

成功すると `../data/refresh_token.txt` が作成されます。

### Step 3: Known Issues の取得

```bash
python known_issues_automation.py
```

成功すると `../data/known_issues.json` に結果が保存されます。

## 📝 出力例

```
============================================================
Power Platform Known Issues 自動取得
実行日時: 2026-01-03 02:37:12
============================================================

[1/3] トークンをリフレッシュ中...
[INFO] 新しいリフレッシュトークンを保存しました
      ✅ 成功
[2/3] Known Issues を取得中...
      ✅ 200 件取得
[3/3] 結果を保存中...
      ✅ data/known_issues.json に保存しました

============================================================
取得結果サマリー
============================================================

状態別:
  Active: 109 件
  Resolved: 91 件

製品別 (上位5件):
  Dynamics 365 Finance: 69 件
  Dynamics 365 Supply Chain Management: 61 件
  ...

✅ 完了
```

## ⚠️ トラブルシューティング

### 環境変数エラー

```
❌ エラー: 環境変数 TENANT_ID が設定されていません。
```

→ プロジェクトルートの `.env` ファイルにテナントIDを設定してください。

### トークンリフレッシュ失敗

```
❌ トークンリフレッシュ失敗: invalid_grant
```

→ リフレッシュトークンが期限切れです。再度HARファイルをエクスポートしてトークンを抽出してください。

### HARファイルにトークンが見つからない

```
❌ Power Platform API 用のトークンが見つかりませんでした。
```

→ 以下を確認してください：
- 「既知の問題」ページを開いた状態でHARをエクスポートしましたか？
- 「Preserve log」にチェックを入れましたか？
- ページをリロードしましたか？

## 🔧 技術詳細

### API_HOST の確認方法

Power Platform API のホスト名は HAR ファイルから確認できます：

1. Power Platform Admin Center で既知の問題ページを開く
2. F12 で開発者ツールを開く
3. Network タブで `knownissue` でフィルタ
4. リクエストURLからホスト名部分をコピー

例:
```
URL: https://xxxxxx.tenant.api.powerplatform.com/support/knownissue/search?...
         └────────────────────────────────────────┘
                    ↑ この部分を API_HOST に設定
```

### CORS模倣について

このスクリプトはブラウザのSPAトークンをサーバーサイドから使用するため、CORS関連のヘッダーを模倣しています。詳細は [docs/oauth-investigation.md](../docs/oauth-investigation.md) を参照してください。
