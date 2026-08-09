# Deployment Architecture — Unit-1: Lambda Application

## デプロイ概要

```
AWS Account (us-east-1)
|
+-- EventBridge Scheduler
|     monthly-credit-report  (cron 0 9 1 * ? *)
|     daily-threshold-check  (cron 0 0 * * ? *)
|     daily-expiry-check     (cron 0 1 * * ? *)
|         |
|         | invoke (SchedulerExecutionRole: lambda:InvokeFunction)
|         v
+-- Lambda Functions
|     credit-notifier-monthly   (Python 3.12, 256MB, 60s timeout)
|     credit-notifier-threshold (Python 3.12, 256MB, 60s timeout)
|     credit-notifier-expiry    (Python 3.12, 256MB, 60s timeout)
|         |                |
|         | [on error]     | [runtime]
|         v                v
|     SQS DLQ         Lambda Extension (localhost:2773)
|     credit-notifier-dlq    |
|     (14d retention)        v
|                       Secrets Manager
|                       credit-notifier/slack
|                       (slack_bot_token, slack_channel_id)
|
+-- External APIs
|     AWS Billing API     (billing.us-east-1.amazonaws.com)
|     Slack API           (slack.com/api/chat.postMessage)
|
+-- CloudWatch Logs
      /aws/lambda/credit-notifier-monthly   (90日保持)
      /aws/lambda/credit-notifier-threshold (90日保持)
      /aws/lambda/credit-notifier-expiry    (90日保持)
```

---

## コードパッケージ構成

CDK は `lambda.Code.fromAsset()` で各 Lambda 関数の `src/` ディレクトリをパッケージ化する。
各 Lambda に `src/common/` を含めるため、CDK のバンドル設定で共通モジュールをインクルードする。

```
パッケージ構成（Lambda デプロイ zip）:
  monthly_notifier パッケージ:
    monthly_notifier/handler.py
    common/billing_client.py
    common/slack_client.py
    common/secrets.py

  threshold_checker パッケージ:
    threshold_checker/handler.py
    common/billing_client.py
    common/slack_client.py
    common/secrets.py

  expiry_checker パッケージ:
    expiry_checker/handler.py
    common/billing_client.py
    common/slack_client.py
    common/secrets.py
```

CDK での実装方針:
- `src/` 全体を `lambda.Code.fromAsset('src')` でパッケージ化
- `requirements.txt` の依存関係は CDK の `PythonFunction` Construct（`aws-cdk-lib/aws-lambda-python-alpha`）でバンドル
- または `requirements.txt` を pip install したレイヤーとして分離

---

## デプロイフロー

```
1. [開発者] cdk bootstrap（初回のみ）
2. [開発者] Secrets Manager に slack シークレットを手動作成
             aws secretsmanager create-secret \
               --name credit-notifier/slack \
               --region us-east-1 \
               --secret-string '{"slack_bot_token":"xoxb-...","slack_channel_id":"C..."}'
3. [開発者] cdk deploy
             → CloudFormation スタック作成
             → Lambda 関数デプロイ
             → EventBridge Scheduler 作成
             → SQS DLQ 作成
             → IAM ロール作成
4. [確認] AWS コンソールまたは CLI で Lambda テスト起動
             aws lambda invoke \
               --function-name credit-notifier-monthly \
               --region us-east-1 \
               output.json
5. [確認] CloudWatch Logs でログ確認
```

---

## 環境変数一覧（全関数共通 + 個別）

### 共通環境変数（CDK で全関数に設定）

| 変数名 | 設定方法 | 説明 |
|---|---|---|
| `SLACK_SECRET_ARN` | CDK context または SSM | Secrets Manager ARN |
| `SLACK_CHANNEL_ID` | CDK context または SSM | Slack チャンネル ID |
| `AWS_ACCOUNT_ID` | CDK `Stack.account` | AWS アカウント ID |

### 関数固有環境変数

| 関数 | 変数名 | デフォルト値 | 説明 |
|---|---|---|---|
| monthly_notifier | `MONTHS_BACK` | `3` | 適用履歴取得月数 |
| threshold_checker | `THRESHOLD_AMOUNT` | `1000.0` | 閾値（USD） |

---

## 依存パッケージ

### requirements.txt（Lambda 本番依存）

```
boto3>=1.34.0
requests>=2.31.0
```

### requirements-dev.txt（開発・テスト依存）

```
pytest>=8.0.0
pytest-mock>=3.12.0
moto[billing,secretsmanager,sqs]>=5.0.0
boto3>=1.34.0
requests>=2.31.0
```

---

## コスト見積もり（月次）

| サービス | 利用量 | コスト |
|---|---|---|
| Lambda 呼び出し | 月次1回 + 日次2回 × 31日 = 63回 | 無料枠内（月100万回まで無料） |
| Lambda 実行時間 | 63回 × 60秒 × 256MB = 約968 GB秒 | 無料枠内（月400,000 GB秒まで無料） |
| SQS DLQ | ほぼ0（エラー発生時のみ） | ほぼ $0 |
| Secrets Manager | 1シークレット + 63APIコール（Extension キャッシュで削減） | 約 $0.40/月 |
| CloudWatch Logs | 少量のログ（63回 × 数KB） | 約 $0.01/月 |
| **合計** | | **約 $0.41/月** |
