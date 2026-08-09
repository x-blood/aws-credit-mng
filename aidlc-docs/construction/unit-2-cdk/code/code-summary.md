# Code Summary — Unit-2: CDK Infrastructure

## 生成ファイル一覧

### インフラコード（`infra/`）

| ファイル | 説明 |
|---|---|
| `infra/bin/app.ts` | CDK App エントリーポイント（CreditNotifierStack を us-east-1 で定義） |
| `infra/lib/credit-notifier-stack.ts` | メイン CDK スタック（全リソースを単一スタックで定義） |
| `infra/package.json` | npm 依存関係（aws-cdk-lib, scheduler-alpha） |
| `infra/tsconfig.json` | TypeScript コンパイラ設定 |
| `infra/cdk.json` | CDK CLI 設定（feature flags） |

### テストコード（`infra/test/`）

| ファイル | 説明 |
|---|---|
| `infra/test/credit-notifier-stack.test.ts` | アサーションテスト（@aws-cdk/assertions） |

---

## CDK スタック定義リソース一覧

| リソース | 論理 ID | 物理名 |
|---|---|---|
| `AWS::Lambda::Function` | `MonthlyNotifierFunction` | `credit-notifier-monthly` |
| `AWS::Lambda::Function` | `ThresholdCheckerFunction` | `credit-notifier-threshold` |
| `AWS::Lambda::Function` | `ExpiryCheckerFunction` | `credit-notifier-expiry` |
| `AWS::SQS::Queue` | `CreditNotifierDlq` | `credit-notifier-dlq` |
| `AWS::Scheduler::Schedule` | `MonthlySchedule` | `credit-notifier-monthly-schedule` |
| `AWS::Scheduler::Schedule` | `ThresholdSchedule` | `credit-notifier-threshold-schedule` |
| `AWS::Scheduler::Schedule` | `ExpirySchedule` | `credit-notifier-expiry-schedule` |
| `AWS::IAM::Role` | `LambdaExecutionRole` | （CDK 自動命名） |
| `AWS::IAM::Role` | `MonthlyScheduleRole` | （CDK 自動命名） |
| `AWS::IAM::Role` | `ThresholdScheduleRole` | （CDK 自動命名） |
| `AWS::IAM::Role` | `ExpiryScheduleRole` | （CDK 自動命名） |

---

## テストカバレッジ概要

| テストスイート | テスト内容 |
|---|---|
| Lambda Functions | リソース数、メモリ・タイムアウト設定、ハンドラー名、環境変数 |
| SQS DLQ | キュー名、メッセージ保持期間 |
| IAM Policy | billing 権限、Secrets Manager ARN スコープ |
| EventBridge Schedulers | リソース数、cron 式の正確性 |
| CloudFormation Outputs | Lambda ARN × 3 + DLQ URL の出力 |

---

## Lambda コードバンドル方式

`Code.fromAsset` + `BundlingOptions.local` を使用する。

- **通常**: ローカルの `pip` を使って依存パッケージをバンドル（Docker 不要）
- **フォールバック**: `pip` が利用不可の場合のみ Docker コンテナを使用
- **対象ディレクトリ**: `src/`（monthly_notifier / threshold_checker / expiry_checker / common を一括バンドル）
