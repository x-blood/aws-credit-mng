# Deployment Architecture — Unit-2: CDK Infrastructure

## デプロイ概要

```
開発者 PC
  |
  | export SLACK_SECRET_ARN=...
  | export SLACK_CHANNEL_ID=...
  |
  | cdk bootstrap（初回のみ）
  | cdk deploy
  v
CloudFormation（us-east-1）
  |
  +-- Lambda × 3
  |     credit-notifier-monthly   (PythonFunction, 256MB, 60s)
  |     credit-notifier-threshold (PythonFunction, 256MB, 60s)
  |     credit-notifier-expiry    (PythonFunction, 256MB, 60s)
  |       |-- layers: AWS-Parameters-and-Secrets-Lambda-Extension
  |       |-- deadLetterQueue: credit-notifier-dlq
  |       |-- role: CreditNotifierLambdaRole
  |
  +-- EventBridge Scheduler × 3
  |     monthly-schedule  cron(0 9 1 * ? *)  --> monthly
  |     threshold-schedule cron(0 0 * * ? *) --> threshold
  |     expiry-schedule    cron(0 1 * * ? *) --> expiry
  |       |-- role: SchedulerExecutionRole (lambda:InvokeFunction のみ)
  |
  +-- SQS Queue
  |     credit-notifier-dlq (14日保持, 300s visibility)
  |
  +-- IAM
  |     CreditNotifierLambdaRole
  |       billing:GetCredits, billing:GetCreditAllocationHistory
  |       secretsmanager:GetSecretValue (credit-notifier/slack* のみ)
  |       sqs:SendMessage (DLQ のみ)
  |       logs:* (/aws/lambda/credit-notifier-* のみ)
  |     SchedulerExecutionRole × 3
  |       lambda:InvokeFunction (各ターゲット Lambda のみ)
  |
  +-- CloudWatch Log Groups（自動作成）
        /aws/lambda/credit-notifier-monthly   90日保持
        /aws/lambda/credit-notifier-threshold 90日保持
        /aws/lambda/credit-notifier-expiry    90日保持
```

---

## PythonFunction バンドルの仕組み

`Code.fromAsset` + `BundlingOptions.local` を使用する。

```
1. cdk deploy / cdk synth 実行時:
2. local.tryBundle() が呼ばれる
3. pip install -r requirements.txt -t <outputDir> を実行（ローカルの pip を使用）
4. handler.py + 依存ライブラリを <outputDir> にコピー
5. CDK がそのディレクトリを zip 化して S3 アセットバケットにアップロード
6. Lambda 関数としてデプロイ

※ ローカルの pip が利用不可の場合のみ Docker フォールバックが発動する。
  通常の開発環境（Python + pip インストール済み）では Docker は不要。
```

**前提条件**: デプロイ実行環境に Python 3.12 + pip がインストールされていること。

---

## CDK デプロイフロー

```bash
# 1. 前提ツールのインストール確認
node --version   # v20.x 以上
docker --version # Docker Desktop 等が起動していること

# 2. CDK プロジェクトのセットアップ
cd infra
npm install

# 3. 初回のみ: CDK bootstrap
cdk bootstrap aws://XXXXXXXXXXXX/us-east-1

# 4. Secrets Manager シークレットを事前に手動作成（未作成の場合）
aws secretsmanager create-secret \
  --name credit-notifier/slack \
  --region us-east-1 \
  --secret-string '{
    "slack_bot_token": "xoxb-...",
    "slack_channel_id": "C0123456789"
  }'

# 5. 環境変数を設定
export SLACK_SECRET_ARN="arn:aws:secretsmanager:us-east-1:XXXXXXXXXXXX:secret:credit-notifier/slack-XXXXXX"

# 6. デプロイ前に CloudFormation テンプレートを確認
cdk synth

# 7. デプロイ実行
cdk deploy

# 8. 動作確認: Lambda を手動テスト実行
aws lambda invoke \
  --function-name credit-notifier-monthly \
  --region us-east-1 \
  --payload '{}' \
  output.json && cat output.json

# 9. ログ確認
aws logs tail /aws/lambda/credit-notifier-monthly \
  --region us-east-1 \
  --follow
```

---

## CDK スタックのリソース一覧

| リソース | 論理 ID | 物理名 |
|---|---|---|
| Lambda | `MonthlyNotifierFunction` | `credit-notifier-monthly` |
| Lambda | `ThresholdCheckerFunction` | `credit-notifier-threshold` |
| Lambda | `ExpiryCheckerFunction` | `credit-notifier-expiry` |
| SQS | `CreditNotifierDlq` | `credit-notifier-dlq` |
| EventBridge Scheduler | `MonthlySchedule` | `credit-notifier-monthly-schedule` |
| EventBridge Scheduler | `ThresholdSchedule` | `credit-notifier-threshold-schedule` |
| EventBridge Scheduler | `ExpirySchedule` | `credit-notifier-expiry-schedule` |
| IAM Role | `LambdaExecutionRole` | `CreditNotifierStack-LambdaExecutionRole-*` |
| IAM Role | `MonthlySchedulerRole` | `CreditNotifierStack-MonthlySchedulerRole-*` |
| IAM Role | `ThresholdSchedulerRole` | `CreditNotifierStack-ThresholdSchedulerRole-*` |
| IAM Role | `ExpirySchedulerRole` | `CreditNotifierStack-ExpirySchedulerRole-*` |
| CloudWatch Log Group | （自動） | `/aws/lambda/credit-notifier-monthly` 他 |

---

## ロールバック手順

```bash
# スタック全体の削除（全リソースが削除される）
cdk destroy

# Secrets Manager のシークレットは手動で削除が必要
aws secretsmanager delete-secret \
  --secret-id credit-notifier/slack \
  --recovery-window-in-days 7 \
  --region us-east-1
```

---

## npm パッケージバージョン

```json
{
  "dependencies": {
    "aws-cdk-lib": "^2.150.0",
    "constructs": "^10.3.0",
    "@aws-cdk/aws-scheduler-alpha": "^2.150.0-alpha.0",
    "@aws-cdk/aws-scheduler-targets-alpha": "^2.150.0-alpha.0"
  },
  "devDependencies": {
    "aws-cdk": "^2.150.0",
    "typescript": "^5.4.0",
    "@types/node": "^20.0.0",
    "ts-node": "^10.9.0",
    "jest": "^29.0.0",
    "@types/jest": "^29.0.0",
    "ts-jest": "^29.0.0"
  }
}
```

`@aws-cdk/aws-lambda-python-alpha` は不要（Docker バンドルを使わないため）。
