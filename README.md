# AWS Credit Notifier

AWS Credits Detail Page API を活用し、クレジット残高・利用状況を定期的に Slack に通知するサーバーレスシステム。

## アーキテクチャ

- **Lambda (Python 3.12)** × 3: 月次レポート / 日次閾値チェック / 日次期限切れチェック
- **EventBridge Scheduler** × 3: 各 Lambda を cron で起動
- **Secrets Manager**: Slack OAuth Token を安全に管理
- **SQS DLQ**: Lambda 失敗時のイベント退避
- **AWS CDK (TypeScript)**: 全インフラを IaC で管理

## 通知種別

| 通知 | スケジュール | 説明 |
|---|---|---|
| 月次レポート | 毎月1日 09:00 UTC | 残高合計・適用履歴を Slack に送信 |
| 閾値アラート | 毎日 00:00 UTC | 残高が閾値（デフォルト $1,000）を下回ったら送信 |
| 期限切れアラート | 毎日 01:00 UTC | 30日以内に期限切れのクレジットを3段階で通知 |

## プロジェクト構造

```
aws-credit-mng/
├── src/                          # Lambda アプリケーションコード (Python 3.12)
│   ├── monthly_notifier/
│   │   └── handler.py
│   ├── threshold_checker/
│   │   └── handler.py
│   ├── expiry_checker/
│   │   └── handler.py
│   └── common/
│       ├── billing_client.py     # AWS Billing API クライアント
│       ├── slack_client.py       # Slack chat.postMessage クライアント
│       └── secrets.py            # Secrets Manager ユーティリティ
├── infra/                        # AWS CDK インフラ (TypeScript) ← Unit-2 で生成
├── tests/                        # pytest テストスイート
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## セットアップ

### 前提条件

- Python 3.12+
- Node.js 20.x（CDK 用）
- AWS CLI（設定済み、us-east-1 アクセス権限）
- AWS CDK CLI (`npm install -g aws-cdk`)

### 1. 開発環境セットアップ

```bash
# Python 依存関係インストール
pip install -r requirements-dev.txt
```

### 2. Secrets Manager シークレット作成（手動）

CDK デプロイ前に Slack シークレットを手動で作成します。

```bash
aws secretsmanager create-secret \
  --name credit-notifier/slack \
  --region us-east-1 \
  --secret-string '{
    "slack_bot_token": "xoxb-your-token-here",
    "slack_channel_id": "C0123456789"
  }'
```

Slack Bot の必要スコープ: `chat:write`

### 3. テスト実行

```bash
# プロジェクトルートから実行
pytest tests/ -v
```

### 4. CDK デプロイ

```bash
cd infra
npm install
cdk bootstrap  # 初回のみ
cdk deploy --context slackSecretArn=<SECRET_ARN> --context awsAccountId=<ACCOUNT_ID>
```

### 5. 動作確認

```bash
# 月次レポートを手動でテスト起動
aws lambda invoke \
  --function-name credit-notifier-monthly \
  --region us-east-1 \
  --payload '{}' \
  output.json && cat output.json

# ログ確認
aws logs tail /aws/lambda/credit-notifier-monthly --follow
```

## 環境変数

Lambda 関数は以下の環境変数を参照します（CDK で自動設定）。

| 変数名 | 必須 | 説明 |
|---|---|---|
| `AWS_ACCOUNT_ID` | ✅ | AWSアカウントID |
| `SLACK_SECRET_ARN` | ✅ | Secrets Manager シークレット ARN |
| `SLACK_CHANNEL_ID` | ✅ | Slack 送信先チャンネル ID |
| `THRESHOLD_AMOUNT` | — | 閾値（USD）。デフォルト: `1000.0` |
| `MONTHS_BACK` | — | 適用履歴取得月数。デフォルト: `3` |

## コスト

月次コスト約 **$0.41**（Secrets Manager $0.40 + その他ほぼ無料枠内）

## 参考

- [AWS Credits Detail Page ブログ](https://aws.amazon.com/blogs/aws-cloud-financial-management/introducing-the-aws-credits-detail-page/)
- [Billing API リファレンス](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_billing_GetCredits.html)
