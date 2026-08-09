# Infrastructure Design — Unit-1: Lambda Application

## インフラ設計サマリー

| 項目 | 内容 |
|---|---|
| クラウドプロバイダー | AWS |
| デプロイリージョン | us-east-1（Billing API と同一リージョン、レイテンシ最小） |
| コンピュート | AWS Lambda (Python 3.12) × 3 関数 |
| ストレージ | なし（ステートレス設計） |
| メッセージング | SQS Standard Queue（DLQ、3 Lambda 共用） |
| シークレット管理 | AWS Secrets Manager + Lambda Extension |
| スケジューラ | EventBridge Scheduler × 3 |
| モニタリング | CloudWatch Logs（保持期間: 90日） |
| DLQ アラート | なし（手動確認） |

---

## Lambda 関数設定

### monthly_notifier

| 設定項目 | 値 |
|---|---|
| 関数名 | `credit-notifier-monthly` |
| ランタイム | Python 3.12 |
| ハンドラー | `monthly_notifier.handler.handler` |
| メモリ | 256 MB |
| タイムアウト | 60 秒 |
| コードパス | `src/monthly_notifier/` + `src/common/` |
| ロググループ | `/aws/lambda/credit-notifier-monthly` |
| ログ保持期間 | 90 日 |
| DLQ | `credit-notifier-dlq`（共用） |
| レイヤー | AWS Parameters and Secrets Lambda Extension（最新版） |

#### 環境変数

| 変数名 | 値 | 説明 |
|---|---|---|
| `SLACK_SECRET_ARN` | （デプロイ時設定） | Secrets Manager シークレット ARN |
| `SLACK_CHANNEL_ID` | （デプロイ時設定） | Slack 送信先チャンネル ID |
| `AWS_ACCOUNT_ID` | （デプロイ時設定） | AWSアカウントID（Billing API 用） |
| `MONTHS_BACK` | `3` | 適用履歴取得月数（デフォルト） |

---

### threshold_checker

| 設定項目 | 値 |
|---|---|
| 関数名 | `credit-notifier-threshold` |
| ランタイム | Python 3.12 |
| ハンドラー | `threshold_checker.handler.handler` |
| メモリ | 256 MB |
| タイムアウト | 60 秒 |
| コードパス | `src/threshold_checker/` + `src/common/` |
| ロググループ | `/aws/lambda/credit-notifier-threshold` |
| ログ保持期間 | 90 日 |
| DLQ | `credit-notifier-dlq`（共用） |
| レイヤー | AWS Parameters and Secrets Lambda Extension（最新版） |

#### 環境変数

| 変数名 | 値 | 説明 |
|---|---|---|
| `SLACK_SECRET_ARN` | （デプロイ時設定） | Secrets Manager シークレット ARN |
| `SLACK_CHANNEL_ID` | （デプロイ時設定） | Slack 送信先チャンネル ID |
| `AWS_ACCOUNT_ID` | （デプロイ時設定） | AWSアカウントID |
| `THRESHOLD_AMOUNT` | `1000.0` | 閾値（USD、デフォルト） |

---

### expiry_checker

| 設定項目 | 値 |
|---|---|
| 関数名 | `credit-notifier-expiry` |
| ランタイム | Python 3.12 |
| ハンドラー | `expiry_checker.handler.handler` |
| メモリ | 256 MB |
| タイムアウト | 60 秒 |
| コードパス | `src/expiry_checker/` + `src/common/` |
| ロググループ | `/aws/lambda/credit-notifier-expiry` |
| ログ保持期間 | 90 日 |
| DLQ | `credit-notifier-dlq`（共用） |
| レイヤー | AWS Parameters and Secrets Lambda Extension（最新版） |

#### 環境変数

| 変数名 | 値 | 説明 |
|---|---|---|
| `SLACK_SECRET_ARN` | （デプロイ時設定） | Secrets Manager シークレット ARN |
| `SLACK_CHANNEL_ID` | （デプロイ時設定） | Slack 送信先チャンネル ID |
| `AWS_ACCOUNT_ID` | （デプロイ時設定） | AWSアカウントID |

---

## SQS DLQ 設定

| 設定項目 | 値 |
|---|---|
| キュー名 | `credit-notifier-dlq` |
| キュータイプ | Standard |
| メッセージ保持期間 | 14 日 |
| 可視性タイムアウト | 300 秒（Lambda タイムアウト × 5） |
| 暗号化 | SSE-SQS（デフォルト） |
| アラーム | なし |

---

## Secrets Manager 設定

| 設定項目 | 値 |
|---|---|
| シークレット名 | `credit-notifier/slack` |
| リージョン | us-east-1 |
| 作成方法 | 手動作成（CDK はシークレット値を管理しない） |
| ローテーション | なし（手動更新） |

### シークレット JSON 構造

```json
{
  "slack_bot_token": "xoxb-xxxxxxxxxxxx-xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx",
  "slack_channel_id": "C0123456789"
}
```

---

## Lambda Extension 設定

| 設定項目 | 値 |
|---|---|
| Extension | AWS Parameters and Secrets Lambda Extension |
| レイヤー ARN | `arn:aws:lambda:us-east-1:177933569100:layer:AWS-Parameters-and-Secrets-Lambda-Extension:12`（最新版を CDK で参照） |
| キャッシュ TTL | 300 秒（デフォルト） |
| ローカルエンドポイント | `http://localhost:2773` |

---

## IAM ロール設計

### Lambda 実行ロール（`CreditNotifierLambdaRole`）

全 3 Lambda 関数が共用する実行ロール。

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BillingCreditsRead",
      "Effect": "Allow",
      "Action": [
        "billing:GetCredits",
        "billing:GetCreditAllocationHistory"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SecretsManagerAccess",
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:us-east-1:${AccountId}:secret:credit-notifier/slack*"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:${AccountId}:log-group:/aws/lambda/credit-notifier-*:*"
    },
    {
      "Sid": "SQSDLQSend",
      "Effect": "Allow",
      "Action": "sqs:SendMessage",
      "Resource": "arn:aws:sqs:us-east-1:${AccountId}:credit-notifier-dlq"
    }
  ]
}
```

---

## EventBridge Scheduler 設定（参照）

（Unit-2 CDK インフラで定義。Unit-1 の Lambda ARN を参照する）

| スケジューラ | cron 式 | ターゲット |
|---|---|---|
| `monthly-credit-report` | `cron(0 9 1 * ? *)` | `credit-notifier-monthly` |
| `daily-threshold-check` | `cron(0 0 * * ? *)` | `credit-notifier-threshold` |
| `daily-expiry-check` | `cron(0 1 * * ? *)` | `credit-notifier-expiry` |
