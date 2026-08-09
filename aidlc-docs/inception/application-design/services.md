# Services

## サービスレイヤー設計

本システムはサーバーレスアーキテクチャのため、従来のサービスレイヤーに相当する役割を
EventBridge Scheduler と Lambda 関数のオーケストレーションが担う。

---

## Service 1: SchedulingService（EventBridge Scheduler）

### 責務
Lambda 関数を定義されたスケジュールで起動するトリガーサービス。
コードとしては CDK スタックで定義される。

### スケジュール定義

| スケジューラ名 | cron 式 | ターゲット Lambda | 説明 |
|---|---|---|---|
| `monthly-credit-report` | `cron(0 9 1 * ? *)` | monthly_notifier | 毎月1日 09:00 UTC |
| `daily-threshold-check` | `cron(0 0 * * ? *)` | threshold_checker | 毎日 00:00 UTC |
| `daily-expiry-check` | `cron(0 1 * * ? *)` | expiry_checker | 毎日 01:00 UTC |

### 設定
- **フレキシブルタイムウィンドウ**: OFF（固定時刻起動）
- **リトライ**: 最大3回
- **DLQ**: なし（Scheduler 自体の DLQ は不要。Lambda 側 DLQ で対応）
- **実行ロール**: `SchedulerExecutionRole`（`lambda:InvokeFunction` のみ）

---

## Service 2: CreditDataService（Billing API 統合）

### 責務
AWS Billing API (`billing:GetCredits`, `billing:GetCreditAllocationHistory`) を
抽象化し、各 Lambda 関数にクレジットデータを提供するサービス層。
`common/billing_client.py` として実装される。

### オーケストレーションパターン
```
Lambda handler
    └─> CreditDataService.get_credits()
            └─> Boto3 billing client (us-east-1)
                    └─> [ThrottlingException] → 指数バックオフリトライ
                    └─> [Success] → CreditData list を返す
    └─> CreditDataService.get_credit_allocation_history()
            └─> Boto3 billing client (us-east-1)
                    └─> [ページネーション] → nextToken ループ
                    └─> [partialResults=true] → 警告ログ付きで返す
```

---

## Service 3: NotificationService（Slack 通知統合）

### 責務
Slack `chat.postMessage` API を抽象化し、各 Lambda 関数の Block Kit ペイロードを
Slack チャネルに配信するサービス層。`common/slack_client.py` として実装される。

### オーケストレーションパターン
```
Lambda handler
    └─> NotificationService.post_message(channel_id, blocks, text)
            └─> SecretsService.get_secret(SLACK_SECRET_ARN)
                    └─> Lambda Extension ローカルエンドポイント (http://localhost:2773)
                            └─> [キャッシュヒット] → token 返却
                            └─> [キャッシュミス] → Secrets Manager API → token 返却
            └─> Slack API (https://slack.com/api/chat.postMessage)
                    └─> [HTTP 200, ok=true] → 完了
                    └─> [HTTP 429 rate limit] → Retry-After ヘッダーに従い待機後リトライ
                    └─> [HTTP エラー / ok=false] → SlackApiError raise
```

---

## Service 4: SecretsService（シークレット管理）

### 責務
Lambda Extension キャッシュを活用してシークレットへのアクセスを最適化する。
`common/secrets.py` として実装される。

### 設定
- **Extension ARN**: `arn:aws:lambda:ap-northeast-1:133490724226:layer:AWS-Parameters-and-Secrets-Lambda-Extension:11`（最新版を CDK で参照）
- **キャッシュ TTL**: 300秒（デフォルト）
- **フォールバック**: Extension 未起動時は Boto3 で直接取得

---

## サービス間インタラクション図

```
EventBridge Scheduler
        |
        | invoke (cron)
        v
+---------------------------+
| Lambda Function           |
| (monthly / threshold /    |
|  expiry)                  |
|                           |
|  1. CreditDataService     |----> AWS Billing API (us-east-1)
|     get_credits()         |<---- CreditData[]
|                           |
|  2. [ビジネスロジック]    |
|     (条件判定・Block Kit   |
|      構築)                |
|                           |
|  3. NotificationService   |----> SecretsService ---> Lambda Extension
|     post_message()        |                      --> Secrets Manager
|                           |----> Slack API
+---------------------------+
        |
        | [例外発生時]
        v
    SQS DLQ
```
