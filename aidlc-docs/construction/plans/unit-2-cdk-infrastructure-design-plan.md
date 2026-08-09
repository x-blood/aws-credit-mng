# Infrastructure Design Plan — Unit-2: CDK Infrastructure

## 対象ユニット
Unit-2: CDK Infrastructure（Node.js / TypeScript）

## Plan Checkboxes
- [x] 設計アーティファクト分析（Unit-1 確定内容を反映）
- [x] 質問作成
- [x] ユーザー回答収集
- [x] 回答の矛盾・曖昧さ分析
- [x] infrastructure-design.md 生成
- [x] deployment-architecture.md 生成

---

## 確定済みの設計（Unit-1 および要件定義より）

| 項目 | 内容 |
|---|---|
| リージョン | us-east-1 |
| Lambda × 3 | credit-notifier-monthly / threshold / expiry |
| ランタイム | Python 3.12 |
| メモリ | 256 MB、タイムアウト 60秒 |
| Logs 保持期間 | 90日 |
| DLQ | SQS Standard（credit-notifier-dlq） |
| Secrets Manager | credit-notifier/slack（手動作成済み前提） |
| Lambda Extension | AWS Parameters and Secrets Lambda Extension |
| CDK スタック | 単一スタック |

---

## Question 1: CDK プロジェクトの Node.js パッケージマネージャー

CDK プロジェクトの依存関係管理ツールを選択してください。

A) npm（Node.js 標準、`package-lock.json`）

B) pnpm（高速・省ディスク、`pnpm-lock.yaml`）

C) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 2: Lambda コードのバンドル方法

CDK から Python Lambda コードをパッケージ化する方法を選択してください。

A) `aws-cdk-lib/aws-lambda` の `Code.fromAsset('src')` — Docker なしでシンプルにディレクトリ全体を zip 化（`requirements.txt` の依存は Lambda Layer で別途管理、または Lambda 実行環境の標準パッケージのみ使用）

B) `@aws-cdk/aws-lambda-python-alpha` の `PythonFunction` — Docker を使って `requirements.txt` を自動でバンドル（Docker が必要）

C) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 3: CDK デプロイ時の設定値渡し方

`SLACK_SECRET_ARN` や `AWS_ACCOUNT_ID` などの設定値をどう渡しますか？

A) CDK context（`cdk deploy --context key=value`）— シンプル、CI/CD にも対応しやすい

B) 環境変数（`CDK_DEFAULT_ACCOUNT` など）— AWS CLI の設定から自動取得

C) CDK の `CfnParameter`（CloudFormation パラメータ）— デプロイ時に入力

D) Other (please describe after [Answer]: tag below)

[Answer]: B
