# AWS Credit Notifier

AWS Credits Detail Page API（2026年6月発表）を活用し、クレジット残高・利用状況を定期的に Slack に通知するサーバーレスシステム。

## アーキテクチャ

- **Lambda (Python 3.12)** × 3: 月次レポート / 日次閾値チェック / 日次期限切れチェック
- **EventBridge Scheduler** × 3: 各 Lambda を cron で起動
- **SSM Parameter Store**: Slack OAuth Token / Channel ID を管理
- **SQS DLQ**: Lambda 失敗時のイベント退避
- **AWS CDK (TypeScript)**: 全インフラを IaC で管理

## 通知種別

| 通知 | スケジュール | 説明 |
|---|---|---|
| 月次レポート | 毎月1日 09:00 UTC | 確定残高・推定残高・推定使用額・適用履歴を Slack に送信 |
| 閾値アラート | 毎日 00:00 UTC | 残高が閾値（デフォルト $20）を下回ったら送信 |
| 期限切れアラート | 毎日 01:00 UTC | 30日以内に期限切れのクレジットを3段階で通知 |

## プロジェクト構造

```
aws-credit-mng/
├── src/                          # Lambda アプリケーションコード (Python 3.12)
│   ├── monthly_notifier/
│   │   └── handler.py            # 月次通知 Lambda
│   ├── threshold_checker/
│   │   └── handler.py            # 日次閾値チェック Lambda
│   ├── expiry_checker/
│   │   └── handler.py            # 日次期限切れチェック Lambda
│   └── common/
│       ├── billing_client.py     # AWS Billing API クライアント（リトライ・ページネーション）
│       ├── credit_utils.py       # クレジット判定共通ユーティリティ
│       ├── slack_client.py       # Slack chat.postMessage クライアント
│       └── secrets.py            # SSM Parameter Store ユーティリティ
├── infra/                        # AWS CDK インフラ (TypeScript)
│   ├── bin/app.ts
│   ├── lib/credit-notifier-stack.ts
│   └── cdk.json
├── tests/                        # pytest テストスイート
├── requirements.txt              # Lambda 本番依存
├── requirements-dev.txt          # 開発・テスト依存
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
pip install -r requirements-dev.txt
cd infra && npm install
```

### 2. SSM Parameter Store にパラメータを作成

Slack Bot Token と Channel ID を us-east-1 に作成します。

```bash
# Slack Bot Token（chat:write スコープが必要）
aws secretsmanager create-secret ... # または SSM で管理
aws ssm put-parameter \
  --name /credit-notifier/slack-bot-token \
  --value "xoxb-your-token" \
  --type SecureString \
  --region us-east-1

# Slack Channel ID
aws ssm put-parameter \
  --name /credit-notifier/slack-channel-id \
  --value "C0123456789" \
  --type String \
  --region us-east-1
```

> 既存の SSM パラメータから値をコピーする場合は、値を取得して上記コマンドで新規作成してください。

### 3. テスト実行

```bash
# Python テスト（46件）
python3 -m pytest tests/ -v

# CDK テスト（19件）
cd infra && npm test
```

### 4. CDK Bootstrap（初回のみ）

```bash
cd infra
cdk bootstrap aws://XXXXXXXXXXXX/us-east-1
```

### 5. デプロイ

```bash
cd infra
cdk deploy
```

> `cdk.json` に `"requireApproval": "never"` が設定されているため、承認なしでデプロイされます。

### 6. 動作確認

```bash
# 月次レポートを手動起動
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
| `AWS_ACCOUNT_ID` | ✅ | AWS アカウント ID |
| `SLACK_BOT_TOKEN_PARAM` | ✅ | SSM パラメータ名（Bot Token） |
| `SLACK_CHANNEL_ID_PARAM` | ✅ | SSM パラメータ名（Channel ID） |
| `THRESHOLD_AMOUNT` | — | 閾値（USD）。デフォルト: `20.0` |
| `MONTHS_BACK` | — | 適用履歴取得月数。デフォルト: `3` |

## 実装上の注意点

### Billing API の仕様

- エンドポイントは `us-east-1` 固定
- `GetCredits` にページネーターなし（全件一括返却）
- `GetCreditAllocationHistory` にページネーターなし（手動 nextToken ループ必要）
- SDK の自動リトライ未対応のため、`ThrottlingException` に対する指数バックオフを自前実装
- `creditStatus` は `"ENABLED"` / `"DISABLED"` 等（`"ACTIVE"` ではない）
- 日付フィールドは `"2027-11-30 23:59:59+00:00"`（スペース区切り）で返る（`T` 区切りではない）
- `payer_flag=True` を指定しないと管理アカウント配下のクレジットが取得できない
- `remainingAmount` / `estimatedAmount` のフィールド名は `currencyAmount` / `currencyCode`（`amount` / `unit` ではない）

## コスト

月次コスト約 **$0.00**（Lambda・Scheduler は無料枠内、SSM Parameter Store は無料）

## 参考

- [AWS Credits Detail Page ブログ](https://aws.amazon.com/blogs/aws-cloud-financial-management/introducing-the-aws-credits-detail-page/)
- [Billing API リファレンス（GetCredits）](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_billing_GetCredits.html)
- [Billing API リファレンス（GetCreditAllocationHistory）](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_billing_GetCreditAllocationHistory.html)
