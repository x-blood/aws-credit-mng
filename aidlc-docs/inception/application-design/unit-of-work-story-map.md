# Unit of Work Story Map

## 概要
本プロジェクトは User Stories フェーズをスキップしたため、
機能要件（FR）を Story の代替として各ユニットにマッピングする。

---

## Unit-1: Lambda Application（Python）へのマッピング

| 機能要件 | 担当コンポーネント | 説明 |
|---|---|---|
| FR-01: クレジット残高取得 | `common/billing_client.py` | `GetCredits` API 呼び出し・リトライ |
| FR-02: クレジット適用履歴取得 | `common/billing_client.py` | `GetCreditAllocationHistory` API・ページネーション |
| FR-03: 月次定期通知 | `monthly_notifier/handler.py` | Block Kit 構築・Slack 送信 |
| FR-04: 残高閾値アラート | `threshold_checker/handler.py` | 閾値判定・条件付き Slack 送信 |
| FR-05: 期限切れアラート（30日/7日/当日） | `expiry_checker/handler.py` | 期限分類・エスカレーション通知 |
| FR-06: エラーハンドリング・リトライ | `common/billing_client.py`, `common/slack_client.py` | 指数バックオフ・DLQ 退避 |
| NFR-01: セキュリティ（シークレット管理） | `common/secrets.py` | Lambda Extension キャッシュ・Secrets Manager |

## Unit-2: CDK Infrastructure（TypeScript）へのマッピング

| 機能要件 | 担当コンポーネント | 説明 |
|---|---|---|
| FR-03: 月次スケジュール | `credit_notifier_stack.ts` | EventBridge Scheduler（cron 0 9 1 * ? *） |
| FR-04: 日次閾値チェックスケジュール | `credit_notifier_stack.ts` | EventBridge Scheduler（cron 0 0 * * ? *） |
| FR-05: 日次期限切れチェックスケジュール | `credit_notifier_stack.ts` | EventBridge Scheduler（cron 0 1 * * ? *） |
| FR-06: DLQ 設定 | `credit_notifier_stack.ts` | SQS DLQ（Lambda の deadLetterQueue） |
| FR-07: IaC による全リソース管理 | `credit_notifier_stack.ts` | Lambda, Scheduler, IAM, DLQ, Secrets 参照 |
| NFR-01: IAM 最小権限ポリシー | `credit_notifier_stack.ts` | Lambda 実行ロール・Scheduler ロール |
| NFR-02: Lambda 設定 | `credit_notifier_stack.ts` | タイムアウト60秒・メモリ256MB |
| NFR-03: CloudWatch Logs | `credit_notifier_stack.ts` | ロググループ自動作成・保持期間設定 |

---

## 全機能要件のカバレッジ確認

| 機能要件 | Unit-1 | Unit-2 | カバー済み |
|---|---|---|---|
| FR-01 クレジット残高取得 | ✅ | — | ✅ |
| FR-02 適用履歴取得 | ✅ | — | ✅ |
| FR-03 月次定期通知 | ✅（ロジック）| ✅（スケジュール）| ✅ |
| FR-04 残高閾値アラート | ✅（ロジック）| ✅（スケジュール）| ✅ |
| FR-05 期限切れアラート | ✅（ロジック）| ✅（スケジュール）| ✅ |
| FR-06 エラーハンドリング | ✅（コード）| ✅（DLQ設定）| ✅ |
| FR-07 IaC 管理 | — | ✅ | ✅ |
| NFR-01 セキュリティ | ✅（シークレット）| ✅（IAM）| ✅ |
| NFR-02 信頼性 | ✅（リトライ）| ✅（DLQ・タイムアウト）| ✅ |
| NFR-03 運用性 | ✅（ログ出力）| ✅（CW Logs）| ✅ |
| NFR-04 コスト | ✅（Extension活用）| ✅（無料枠内構成）| ✅ |
| NFR-05 テスト | ✅（pytest/moto）| ✅（cdk synth）| ✅ |

**全 FR / NFR がいずれかのユニットでカバーされている。**
