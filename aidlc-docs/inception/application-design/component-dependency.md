# Component Dependencies

## 依存関係マトリクス

| コンポーネント | 依存先 | 依存種別 | 方向 |
|---|---|---|---|
| monthly_notifier | common/billing_client | 実行時依存 | → |
| monthly_notifier | common/slack_client | 実行時依存 | → |
| threshold_checker | common/billing_client | 実行時依存 | → |
| threshold_checker | common/slack_client | 実行時依存 | → |
| expiry_checker | common/billing_client | 実行時依存 | → |
| expiry_checker | common/slack_client | 実行時依存 | → |
| common/slack_client | common/secrets | 実行時依存 | → |
| common/billing_client | AWS Billing API (外部) | ネットワーク依存 | → |
| common/slack_client | Slack API (外部) | ネットワーク依存 | → |
| common/secrets | Lambda Extension (外部) | ネットワーク依存（localhost） | → |
| common/secrets | AWS Secrets Manager (外部) | ネットワーク依存（フォールバック） | → |
| CDK Stack | monthly_notifier | デプロイ依存 | → |
| CDK Stack | threshold_checker | デプロイ依存 | → |
| CDK Stack | expiry_checker | デプロイ依存 | → |
| EventBridge Scheduler | monthly_notifier | 起動依存 | → |
| EventBridge Scheduler | threshold_checker | 起動依存 | → |
| EventBridge Scheduler | expiry_checker | 起動依存 | → |
| monthly_notifier | SQS DLQ | エラー時依存 | → |
| threshold_checker | SQS DLQ | エラー時依存 | → |
| expiry_checker | SQS DLQ | エラー時依存 | → |

---

## 依存関係図

```
EventBridge Schedulers (x3)
  monthly-credit-report  ----invoke---->  monthly_notifier
  daily-threshold-check  ----invoke---->  threshold_checker
  daily-expiry-check     ----invoke---->  expiry_checker

monthly_notifier  \
threshold_checker  +---> common/billing_client ---> AWS Billing API
expiry_checker    /                                  (us-east-1)

monthly_notifier  \
threshold_checker  +---> common/slack_client ---> common/secrets ---> Lambda Extension
expiry_checker    /          |                                    \--> Secrets Manager
                             +---> Slack API (chat.postMessage)

monthly_notifier  \
threshold_checker  +---> SQS DLQ  (on error)
expiry_checker    /

CDK Stack --deploy--> [All Lambda functions + Schedulers + IAM + DLQ]
```

---

## 疎結合設計の方針

- **Lambda 関数間は直接通信しない** — EventBridge Scheduler が独立してトリガー
- **共有コードは `src/common/` モジュールとして管理** — Lambda Layer は使用しない（同一リポジトリで管理しやすいため）
- **Block Kit 構築は各 Lambda が担当** — 各通知タイプのメッセージ構造が異なるため独立性を維持
- **Secrets Manager アクセスは Lambda Extension 経由でキャッシュ** — 日次 × 3 起動 × シークレット取得 = コスト最適化
- **SQS DLQ は3 Lambda 共用** — 月次通知システムの規模ではシンプルな共用が適切

---

## データフロー

### 月次通知フロー
```
Scheduler trigger
  -> get_credits(account_id, start_date=-365d)
  -> get_credit_allocation_history(account_id, start_date=-90d, end_date=now)
  -> _summarize_credits(credits)
  -> _build_monthly_blocks(credits, history)
  -> post_message(channel_id, blocks)
```

### 閾値チェックフロー
```
Scheduler trigger
  -> get_credits(account_id, start_date=-365d)
  -> sum(credit.remainingAmount for credit in credits)
  -> if total < THRESHOLD_AMOUNT:
       _build_threshold_blocks(credits, total, threshold)
       post_message(channel_id, blocks)
  -> else: no-op (ログのみ)
```

### 期限切れチェックフロー
```
Scheduler trigger
  -> get_credits(account_id, start_date=-365d)
  -> _classify_expiring_credits(credits, today)
  -> if any classified:
       _build_expiry_blocks(classified)
       post_message(channel_id, blocks)
  -> else: no-op (ログのみ)
```
