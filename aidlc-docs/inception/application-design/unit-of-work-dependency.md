# Unit of Work Dependencies

## ユニット間依存マトリクス

| ユニット | 依存先 | 依存種別 | 方向 | 説明 |
|---|---|---|---|---|
| Unit-2（CDK） | Unit-1（Lambda） | デプロイ依存 | Unit-2 → Unit-1 | CDK スタックが Lambda コードパスを参照 |

**Unit-1 は Unit-2 に依存しない** — Lambda アプリケーションコードは CDK 定義を参照しない。

---

## 依存関係図

```
Unit-1: Lambda Application (Python)
  src/monthly_notifier/
  src/threshold_checker/
  src/expiry_checker/
  src/common/
  tests/
        |
        | [コードパス参照]
        | Unit-1 完了後に着手可能
        v
Unit-2: CDK Infrastructure (TypeScript)
  infra/lib/credit_notifier_stack.ts
        |
        | [cdk deploy]
        v
  AWS リソース
  (Lambda × 3, Scheduler × 3, DLQ, IAM, Secrets)
```

---

## ユニット内部依存（Unit-1）

```
monthly_notifier/handler.py
    → common/billing_client.py  (GetCredits, GetCreditAllocationHistory)
    → common/slack_client.py    (post_message)
        → common/secrets.py     (get_secret via Lambda Extension)

threshold_checker/handler.py
    → common/billing_client.py
    → common/slack_client.py
        → common/secrets.py

expiry_checker/handler.py
    → common/billing_client.py
    → common/slack_client.py
        → common/secrets.py
```

## ユニット内部依存（Unit-2）

```
infra/bin/app.ts
    → infra/lib/credit_notifier_stack.ts
        → src/monthly_notifier/   [lambda.Code.fromAsset]
        → src/threshold_checker/  [lambda.Code.fromAsset]
        → src/expiry_checker/     [lambda.Code.fromAsset]
```

---

## 外部依存（ランタイム）

| ユニット | 外部依存 | エンドポイント | 認証 |
|---|---|---|---|
| Unit-1 | AWS Billing API | `billing.us-east-1.amazonaws.com` | IAM / SigV4 |
| Unit-1 | AWS Secrets Manager | `secretsmanager.ap-northeast-1.amazonaws.com` | IAM / SigV4 |
| Unit-1 | Lambda Extension（localhost） | `http://localhost:2773` | X-Aws-Parameters-Secrets-Token ヘッダー |
| Unit-1 | Slack API | `https://slack.com/api/chat.postMessage` | OAuth Bearer Token |
| Unit-2 | AWS CloudFormation | CDK デプロイ時 | IAM |

---

## 開発・テスト依存

| フェーズ | Unit-1 | Unit-2 |
|---|---|---|
| 実装 | 独立して開発可能 | Unit-1 完了後 |
| 単体テスト | pytest + moto（AWS モック）で独立実行可能 | `cdk synth` でテンプレート検証 |
| 結合テスト | Unit-2 デプロイ後に AWS 環境で検証 | Unit-1 デプロイ前提 |
