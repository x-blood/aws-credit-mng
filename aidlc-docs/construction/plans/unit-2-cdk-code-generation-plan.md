# Code Generation Plan — Unit-2: CDK Infrastructure

## ユニット概要
- **ユニット**: Unit-2: CDK Infrastructure（Node.js / TypeScript）
- **ワークスペースルート**: `/Users/yasuyukisato/tech/my/aws-credit-mng`
- **アプリコード配置**: `infra/`（ワークスペースルート直下）
- **ドキュメント**: `aidlc-docs/construction/unit-2-cdk/code/`

## 実装対象
- FR-03〜05: EventBridge Scheduler × 3（月次・閾値・期限）
- FR-06: SQS DLQ
- FR-07: IaC による全リソース管理
- NFR-01: IAM 最小権限ポリシー
- NFR-02: Lambda 設定（256MB / 60s / 90日ログ）

---

## Generation Steps

### Step 1: CDK プロジェクト構造セットアップ
- [x] `infra/package.json` 作成
- [x] `infra/tsconfig.json` 作成
- [x] `infra/cdk.json` 作成
- [x] `infra/bin/app.ts` 作成

### Step 2: CDK スタック本体生成
- [x] `infra/lib/credit-notifier-stack.ts` 作成

### Step 3: CDK テスト生成
- [x] `infra/test/credit-notifier-stack.test.ts` 作成

### Step 4: ドキュメント生成
- [x] `aidlc-docs/construction/unit-2-cdk/code/code-summary.md` 作成
