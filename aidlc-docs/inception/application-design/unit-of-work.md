# Unit of Work

## 分解方針

システムを2つの独立した開発単位（Unit of Work）に分解する。
各ユニットは独立して実装・テスト・レビュー可能であり、Unit-2 は Unit-1 のデプロイ先を定義するため Unit-1 完了後に着手する。

---

## Unit-1: Lambda Application（Python）

### 概要
AWS Billing API からクレジット情報を取得し、Slack に通知するアプリケーションロジック全体。

### 責務
- 月次クレジット残高レポートの生成と Slack 送信（monthly_notifier）
- 日次残高閾値チェックと条件付き Slack アラート（threshold_checker）
- 日次クレジット期限切れチェックと Slack エスカレーションアラート（expiry_checker）
- 共有 Billing API クライアント（リトライ・ページネーション）
- 共有 Slack 通知クライアント（OAuth Token 管理）
- 共有シークレット取得ユーティリティ（Lambda Extension キャッシュ）

### コード配置
```
src/
├── monthly_notifier/
│   └── handler.py
├── threshold_checker/
│   └── handler.py
├── expiry_checker/
│   └── handler.py
└── common/
    ├── billing_client.py
    ├── slack_client.py
    └── secrets.py
tests/
├── test_monthly_notifier.py
├── test_threshold_checker.py
├── test_expiry_checker.py
└── test_billing_client.py
requirements.txt
requirements-dev.txt
```

### 含まれるコンポーネント
| コンポーネント | ファイル |
|---|---|
| monthly_notifier | `src/monthly_notifier/handler.py` |
| threshold_checker | `src/threshold_checker/handler.py` |
| expiry_checker | `src/expiry_checker/handler.py` |
| common/billing_client | `src/common/billing_client.py` |
| common/slack_client | `src/common/slack_client.py` |
| common/secrets | `src/common/secrets.py` |

### 技術スタック
- **言語**: Python 3.12
- **主要ライブラリ**: boto3, requests
- **テスト**: pytest, moto, pytest-mock

### Construction フェーズのステージ
- **Functional Design**: EXECUTE（Billing API データ加工・閾値判定・期限分類・Block Kit 構築ロジック）
- **NFR Requirements**: SKIPPED（NFR は要件定義で確定済み）
- **NFR Design**: SKIPPED
- **Infrastructure Design**: EXECUTE（Lambda 設定・環境変数・Secrets Manager 参照方法）
- **Code Generation**: EXECUTE

---

## Unit-2: CDK Infrastructure（TypeScript）

### 概要
AWS CDK（Node.js / TypeScript）による全 AWS インフラリソースの定義。
Unit-1 の Lambda 関数をデプロイ先として参照する。

### 責務
- Lambda 関数 × 3 の CDK 定義（コード参照・環境変数・タイムアウト・メモリ）
- EventBridge Scheduler × 3 の CDK 定義（cron式・IAM ロール・リトライ設定）
- SQS DLQ × 1 の CDK 定義（3 Lambda 共用）
- IAM ロール × 2 の CDK 定義（Lambda 実行ロール・Scheduler 実行ロール）
- Secrets Manager シークレット参照の CDK 定義（値は手動作成、ARN 参照のみ）
- Lambda Extension レイヤー参照の CDK 定義

### コード配置
```
infra/
├── bin/
│   └── app.ts
├── lib/
│   └── credit_notifier_stack.ts
├── package.json
├── tsconfig.json
└── cdk.json
```

### 含まれるコンポーネント
| コンポーネント | ファイル |
|---|---|
| CDK App エントリーポイント | `infra/bin/app.ts` |
| CreditNotifierStack | `infra/lib/credit_notifier_stack.ts` |

### 技術スタック
- **言語**: TypeScript
- **主要ライブラリ**: aws-cdk-lib, constructs
- **Node.js**: 20.x（CDK CLI 実行環境）

### Construction フェーズのステージ
- **Functional Design**: SKIPPED（インフラ定義のみ、ビジネスロジックなし）
- **NFR Requirements**: SKIPPED
- **NFR Design**: SKIPPED
- **Infrastructure Design**: EXECUTE（CDK スタック全体のリソース構成・IAM ポリシー詳細・環境変数設計）
- **Code Generation**: EXECUTE

---

## 開発順序

```
Unit-1（Lambda Application）
  ├── Functional Design
  ├── Infrastructure Design
  └── Code Generation
        |
        v  [Unit-1 完了後]
Unit-2（CDK Infrastructure）
  ├── Infrastructure Design（Unit-1 の Lambda ARN を参照）
  └── Code Generation
        |
        v  [Unit-2 完了後]
Build and Test
```

Unit-2 の CDK スタックは Unit-1 の Lambda 関数コードパスを参照するため、
Unit-1 の Code Generation 完了後に Unit-2 に着手する。
