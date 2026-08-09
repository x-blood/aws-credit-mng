# Components

## システム概要

AWS Credits 月次Slack通知システムは、3つの独立した Lambda 関数と、それらが共有するコモンモジュール群で構成される。全コンポーネントは `src/` 配下に配置し、CDK スタックが1つのスタックとして全リソースを管理する。

---

## Component 1: monthly_notifier（月次通知Lambda）

### 責務
- 毎月1日 09:00 UTC に EventBridge Scheduler から起動される
- `GetCredits` API でクレジット残高一覧を取得する
- `GetCreditAllocationHistory` API で直近3ヶ月の適用履歴を取得する
- 残高サマリーと適用履歴を Block Kit 形式の Slack メッセージとして送信する

### 配置
`src/monthly_notifier/handler.py`

### インターフェース
- **入力**: EventBridge Scheduler イベント（payload は空でよい）
- **出力**: なし（副作用: Slack メッセージ送信）
- **エラー時**: 例外を raise → Lambda → SQS DLQ に退避

---

## Component 2: threshold_checker（日次閾値チェックLambda）

### 責務
- 毎日 00:00 UTC に EventBridge Scheduler から起動される
- `GetCredits` API でクレジット残高合計を取得する
- 残高が設定閾値（デフォルト: $1,000）を下回った場合のみ Slack アラートを送信する
- 閾値は環境変数 `THRESHOLD_AMOUNT` で設定可能

### 配置
`src/threshold_checker/handler.py`

### インターフェース
- **入力**: EventBridge Scheduler イベント
- **出力**: なし（副作用: 条件付き Slack メッセージ送信）
- **エラー時**: 例外を raise → Lambda → SQS DLQ に退避

---

## Component 3: expiry_checker（日次期限切れチェックLambda）

### 責務
- 毎日 01:00 UTC に EventBridge Scheduler から起動される
- `GetCredits` API で全クレジットの期限情報を取得する
- 期限まで 30日以内・7日以内・当日 に該当するクレジットを特定する
- エスカレーションレベル（INFO / WARNING / CRITICAL）に応じた Slack アラートを送信する

### 配置
`src/expiry_checker/handler.py`

### インターフェース
- **入力**: EventBridge Scheduler イベント
- **出力**: なし（副作用: 条件付き Slack メッセージ送信）
- **エラー時**: 例外を raise → Lambda → SQS DLQ に退避

---

## Component 4: common.billing_client（共有 Billing API クライアント）

### 責務
- Boto3 を使用して `billing:GetCredits` / `billing:GetCreditAllocationHistory` を呼び出す
- `ThrottlingException` に対して指数バックオフリトライを実装する
- `partialResults` フラグを検証してデータ完全性を確認する
- ページネーション処理（`GetCreditAllocationHistory`）を一元管理する

### 配置
`src/common/billing_client.py`

### インターフェース
- **入力**: account_id, 日付範囲などのパラメータ
- **出力**: クレジットデータ（dict / list）

---

## Component 5: common.slack_client（共有 Slack 通知クライアント）

### 責務
- Slack `chat.postMessage` API を呼び出す
- Secrets Manager（Lambda Extension キャッシュ経由）から OAuth Token を取得する
- HTTP エラー・レート制限に対するエラーハンドリングを実装する
- 各 Lambda 関数から渡された Block Kit ペイロードをそのまま送信する（Block Kit の構築は各Lambda担当）

### 配置
`src/common/slack_client.py`

### インターフェース
- **入力**: channel_id (str), blocks (list), text (str, fallback)
- **出力**: なし（例外で失敗通知）

---

## Component 6: common.secrets（共有シークレット取得ユーティリティ）

### 責務
- Lambda Extension（AWS Parameters and Secrets Lambda Extension）経由でローカルエンドポイントにアクセスしてシークレットを取得する
- キャッシュミス時は Secrets Manager に直接フォールバックする
- シークレット値を呼び出し元に返す（ログへの出力は禁止）

### 配置
`src/common/secrets.py`

### インターフェース
- **入力**: secret_arn (str)
- **出力**: secret_value (dict)

---

## Component 7: CDK Stack（インフラストラクチャ定義）

### 責務
- 全 AWS リソースを単一 CDK Stack として定義・管理する
- Lambda 関数 × 3（monthly_notifier / threshold_checker / expiry_checker）
- EventBridge Scheduler × 3（各 Lambda に対応）
- SQS DLQ × 1（3 Lambda 共用）
- Secrets Manager シークレット（参照のみ、シークレット値は手動作成）
- IAM ロール × 2（Lambda 実行ロール / Scheduler 実行ロール）

### 配置
`infra/lib/credit_notifier_stack.ts`

### インターフェース
- **入力**: CDK App コンテキスト（env, stackName）
- **出力**: CloudFormation テンプレート（`cdk synth`）
