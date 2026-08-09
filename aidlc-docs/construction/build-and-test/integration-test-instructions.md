# Integration Test Instructions

## 概要

本システムは Lambda + EventBridge Scheduler + Secrets Manager + Slack API の統合システムです。
統合テストは AWS 環境にデプロイ後、Lambda を手動起動して実施します。

**前提**: `cdk deploy` が完了していること

---

## Scenario 1: 月次レポート Lambda の手動起動

### 目的
Billing API → Lambda → Slack の End-to-End フローを検証する。

### 実行手順

```bash
# Lambda を手動起動
aws lambda invoke \
  --function-name credit-notifier-monthly \
  --region us-east-1 \
  --payload '{}' \
  --log-type Tail \
  output.json

# レスポンス確認
cat output.json

# Base64 デコードしてログを確認
aws lambda invoke \
  --function-name credit-notifier-monthly \
  --region us-east-1 \
  --payload '{}' \
  --log-type Tail \
  output.json 2>&1 | grep LogResult | awk '{print $2}' | base64 -d
```

### 期待結果
- `output.json` に `null`（正常終了）または エラーなし
- Slack チャンネルに月次レポートメッセージが投稿される
- CloudWatch Logs に `Slack message sent to channel` ログが出力される

---

## Scenario 2: 閾値チェック Lambda の手動起動

```bash
aws lambda invoke \
  --function-name credit-notifier-threshold \
  --region us-east-1 \
  --payload '{}' \
  output.json && cat output.json
```

### 期待結果
- クレジット残高が `THRESHOLD_AMOUNT`（$1,000）を下回っている場合: Slack アラート送信
- 残高が閾値以上の場合: 何も送信されない（ログに `no alert needed` と出力）

---

## Scenario 3: 期限切れチェック Lambda の手動起動

```bash
aws lambda invoke \
  --function-name credit-notifier-expiry \
  --region us-east-1 \
  --payload '{}' \
  output.json && cat output.json
```

### 期待結果
- 30日以内に期限切れのクレジットがある場合: Slack アラート送信
- 該当なし: ログに `No expiring credits found` と出力

---

## CloudWatch Logs での確認

```bash
# 月次 Lambda のログをリアルタイムで確認
aws logs tail /aws/lambda/credit-notifier-monthly \
  --region us-east-1 \
  --follow

# 直近のログを確認
aws logs filter-log-events \
  --log-group-name /aws/lambda/credit-notifier-monthly \
  --region us-east-1 \
  --start-time $(date -v-1H +%s000)
```

---

## DLQ の確認（エラー発生時）

```bash
# DLQ のメッセージ数を確認
aws sqs get-queue-attributes \
  --queue-url $(aws sqs get-queue-url --queue-name credit-notifier-dlq --region us-east-1 --query QueueUrl --output text) \
  --attribute-names ApproximateNumberOfMessages \
  --region us-east-1

# DLQ のメッセージを受信して確認
aws sqs receive-message \
  --queue-url <DLQ_URL> \
  --region us-east-1
```

---

## クリーンアップ（テスト後）

統合テスト専用のリソースは作成しないため、クリーンアップ不要。
全リソースを削除する場合は `cdk destroy` を実行する。
