# Requirements Document

## Intent Analysis Summary

- **User Request**: AWS Credits Detail Page API を活用し、クレジット残高・利用状況を定期的にSlack通知するサーバーレスアプリケーションの実装
- **参照ドキュメント**: `docs/quick.md`（Amazon Q Blog Draft）
- **Request Type**: New Project（Greenfield）
- **Scope Estimate**: Multiple Components（Lambda、EventBridge Scheduler、CDK、Slack API）
- **Complexity Estimate**: Moderate（サーバーレス + API統合 + IaC）

---

## Functional Requirements

### FR-01: クレジット残高取得
- AWS Billing API（`billing:GetCredits`）を呼び出し、アカウントに紐づく全クレジットの残高を取得する
- us-east-1 エンドポイントを使用する
- `remainingAmount`（確定残高）と `estimatedAmount`（見込み残高）の両方を取得する
- `applicableProductNames`、`startDate`、`endDate`、`exhaustDate` なども取得する

### FR-02: クレジット適用履歴取得
- AWS Billing API（`billing:GetCreditAllocationHistory`）を呼び出し、月次の適用履歴を取得する
- ページネーション（`nextToken`）に対応する
- `partialResults` フラグと `failedMonths` を検証し、データ完全性を確認する
- デフォルトで直近3ヶ月分を取得する

### FR-03: 月次定期通知（Slack）
- EventBridge Scheduler（`cron(0 9 1 * ? *)`）で毎月1日 09:00 UTC に Lambda を起動する
- Lambda が取得したクレジット情報を Slack の `chat.postMessage` API で通知する
- Block Kit 形式のメッセージを使用する（残高合計、今月適用額、有効期限最短、クレジット数）
- Slack チャネルと OAuth トークンは AWS Secrets Manager で管理する

### FR-04: 残高閾値アラート通知
- クレジット残高が設定した閾値（デフォルト: $1,000）を下回った場合に即時通知する
- 閾値は環境変数または Secrets Manager で設定可能とする
- アラート通知は月次通知とは独立したメッセージとして送信する
- EventBridge Scheduler で日次チェック（毎日 00:00 UTC）を実施する

### FR-05: クレジット期限切れアラート
- クレジットの有効期限が 30日前・7日前・当日 に近づいた場合にSlack通知する
- 期限切れアラート用の EventBridge Scheduler ルールを別途作成する（毎日 01:00 UTC）
- 対象クレジットの `creditId`、`description`、`remainingAmount`、`endDate` を通知に含める
- エスカレーションレベル（30日前: INFO、7日前: WARNING、当日: CRITICAL）をメッセージで表現する

### FR-06: エラーハンドリングとリトライ
- `ThrottlingException` に対して指数バックオフ（初回1秒、最大32秒）でリトライする
- Lambda 関数に DLQ（SQS）を設定し、失敗時にイベントを退避させる
- Slack 配信失敗時も DLQ で捕捉する
- `partialResults = true` の場合、通知メッセージに「データが不完全です」旨を明記する

### FR-07: IaC による全リソース管理
- 全 AWS リソースを AWS CDK（Node.js / TypeScript）で定義・管理する
- Lambda 関数本体は Python 3.12 で実装する
- CDK スタック: Lambda、EventBridge Scheduler（3ルール）、Secrets Manager、SQS DLQ、IAM ロール
- `cdk deploy` 1コマンドでデプロイ可能とする

---

## Non-Functional Requirements

### NFR-01: セキュリティ（最小権限）
- Lambda 実行ロールは以下の権限に限定する:
  - `billing:GetCredits`、`billing:GetCreditAllocationHistory`（Resource: `*`）
  - `secretsmanager:GetSecretValue`（特定シークレット ARN にスコープ）
  - `logs:CreateLogGroup`、`logs:CreateLogStream`、`logs:PutLogEvents`（特定ロググループ）
  - `sqs:SendMessage`（DLQ ARN にスコープ）
- EventBridge Scheduler 用ロールは Lambda 実行ロールと分離し、`lambda:InvokeFunction` のみ付与
- Slack OAuth トークンは Secrets Manager に保存し、コードにハードコードしない

### NFR-02: 信頼性
- Lambda タイムアウト: 60秒
- Lambda メモリ: 256MB
- EventBridge Scheduler リトライ: 最大3回
- DLQ メッセージ保持期間: 14日

### NFR-03: 運用性
- Lambda ログは CloudWatch Logs に出力する（ロググループ: `/aws/lambda/credit-notifier-*`）
- CDK デプロイ時にスタック名・環境を区別できるようにする（`dev` / `prod`）
- Secrets Manager シークレット名は環境変数 `SLACK_SECRET_ARN` で指定する

### NFR-04: コスト
- 月次通知 + 日次チェック（閾値・期限切れ）の合計: Lambda 呼び出し月約 62回（無料枠内）
- Secrets Manager: 月約 $0.40（シークレット1件）
- SQS DLQ: 実質無料（低頻度）
- EventBridge Scheduler: 月約62スケジュール（無料枠内）

### NFR-05: テスト
- Lambda 関数の単体テスト（pytest）を実装する
- モック（`moto`）を使用して Billing API・Secrets Manager をスタブ化する
- プロパティベーステストは対象外（シンプルな統合レイヤーのため）

---

## アーキテクチャ概要

```
EventBridge Scheduler (月次: cron 0 9 1 * ? *)
EventBridge Scheduler (日次閾値: cron 0 0 * * ? *)
EventBridge Scheduler (日次期限: cron 0 1 * * ? *)
         |
         v
    Lambda (Python 3.12)
         |
    +----+----+----+
    |         |    |
    v         v    v
Billing API  Secrets  Slack
(us-east-1)  Manager  chat.postMessage
                          |
                          v
                    Slack Channel
                          |
                 [失敗時] DLQ (SQS)
```

---

## 技術スタック

| コンポーネント | 技術 |
|---|---|
| IaC | AWS CDK (Node.js / TypeScript) |
| Lambda ランタイム | Python 3.12 |
| Billing API クライアント | Boto3 |
| Slack 通知方式 | `chat.postMessage` API (OAuth Token) |
| シークレット管理 | AWS Secrets Manager |
| スケジューラ | EventBridge Scheduler |
| エラー退避 | SQS Dead Letter Queue |
| テスト | pytest + moto |

---

## スコープ外

- Cost Explorer 連携（部門別レポート）: スコープ外
- Organizations / Consolidated Billing: スコープ外（単一アカウント）
- セキュリティ拡張ルール（AI-DLC extension）: 無効
- 耐障害性ベースライン（AI-DLC extension）: 無効
- プロパティベーステスト（AI-DLC extension）: 無効
