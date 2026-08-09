# Infrastructure Design Plan — Unit-1: Lambda Application

## 対象ユニット
Unit-1: Lambda Application（Python 3.12）

## Plan Checkboxes
- [x] 設計アーティファクト分析
- [x] 質問作成
- [x] ユーザー回答収集
- [x] 回答の矛盾・曖昧さ分析
- [x] infrastructure-design.md 生成
- [x] deployment-architecture.md 生成

---

## 確定済みの設計（変更不要）

| 項目 | 内容 |
|---|---|
| クラウドプロバイダー | AWS |
| コンピュート | AWS Lambda (Python 3.12) |
| ストレージ | なし（ステートレス設計、DynamoDB等不要） |
| メッセージング | SQS DLQ（エラー退避のみ） |
| シークレット管理 | AWS Secrets Manager + Lambda Extension |
| スケジューラ | EventBridge Scheduler |
| モニタリング | CloudWatch Logs（Lambda 自動統合） |

---

## Question 1: デプロイリージョン

Lambda 関数をデプロイするリージョンを選択してください。
（注: Billing API のエンドポイントは us-east-1 固定ですが、Lambda 自体は任意リージョンに配置可能です）

A) ap-northeast-1（東京）— 日本の運用チームに近い

B) us-east-1（バージニア）— Billing API と同一リージョン（ネットワークレイテンシ最小）

C) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 2: CloudWatch Logs 保持期間

Lambda のログ保持期間を選択してください。

A) 14日

B) 30日

C) 90日

D) Other (please describe after [Answer]: tag below)

[Answer]: C

---

## Question 3: Lambda メモリ設定の確認

要件では 256MB を提案しましたが、変更が必要な場合は選択してください。

A) 256MB（提案通り）

B) 512MB（余裕をもたせる）

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 4: DLQ のアラート通知

SQS DLQ にメッセージが溜まった場合のアラート設定を選択してください。

A) CloudWatch Alarm を設定（DLQ の `ApproximateNumberOfMessagesVisible >= 1` でアラーム → Slack または Email）

B) アラームなし（DLQ を定期的に手動確認）

C) Other (please describe after [Answer]: tag below)

[Answer]: B
