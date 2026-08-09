# Application Design — 統合ドキュメント

## システム概要

**システム名**: AWS Credits Slack 通知システム  
**アーキテクチャ**: Serverless（Lambda + EventBridge Scheduler + Secrets Manager + SQS）  
**IaC**: AWS CDK（Node.js / TypeScript）  
**Lambda ランタイム**: Python 3.12  

---

## プロジェクト構造

```
aws-credit-mng/
├── src/                          # Lambda アプリケーションコード (Python)
│   ├── monthly_notifier/
│   │   └── handler.py            # 月次通知 Lambda エントリーポイント
│   ├── threshold_checker/
│   │   └── handler.py            # 日次閾値チェック Lambda エントリーポイント
│   ├── expiry_checker/
│   │   └── handler.py            # 日次期限切れチェック Lambda エントリーポイント
│   └── common/
│       ├── billing_client.py     # AWS Billing API クライアント（共有）
│       ├── slack_client.py       # Slack chat.postMessage クライアント（共有）
│       └── secrets.py            # Secrets Manager / Lambda Extension ユーティリティ（共有）
├── infra/                        # CDK インフラコード (TypeScript)
│   ├── bin/
│   │   └── app.ts                # CDK App エントリーポイント
│   ├── lib/
│   │   └── credit_notifier_stack.ts  # メイン CDK スタック（全リソース）
│   └── package.json
├── tests/                        # pytest テストスイート
│   ├── test_monthly_notifier.py
│   ├── test_threshold_checker.py
│   ├── test_expiry_checker.py
│   └── test_billing_client.py
├── requirements.txt              # Lambda 本番依存 (boto3, requests)
├── requirements-dev.txt          # 開発依存 (pytest, moto, pytest-mock)
└── README.md
```

---

## コンポーネント一覧

| ID | 名前 | 種別 | 配置 | 責務要約 |
|---|---|---|---|---|
| C1 | monthly_notifier | Lambda 関数 | `src/monthly_notifier/handler.py` | 月次クレジット残高レポートを Slack に送信 |
| C2 | threshold_checker | Lambda 関数 | `src/threshold_checker/handler.py` | 残高が閾値以下なら Slack アラート送信 |
| C3 | expiry_checker | Lambda 関数 | `src/expiry_checker/handler.py` | 期限切れ間近クレジットを Slack アラート送信 |
| C4 | common/billing_client | 共有モジュール | `src/common/billing_client.py` | Billing API 抽象化・リトライ・ページネーション |
| C5 | common/slack_client | 共有モジュール | `src/common/slack_client.py` | Slack API 抽象化・エラーハンドリング |
| C6 | common/secrets | 共有モジュール | `src/common/secrets.py` | Lambda Extension 経由シークレット取得 |
| C7 | CDK Stack | インフラ定義 | `infra/lib/credit_notifier_stack.ts` | 全 AWS リソースの定義・管理 |

---

## サービスレイヤー

| サービス | 実装 | 説明 |
|---|---|---|
| SchedulingService | EventBridge Scheduler × 3 | cron 起動（月次・日次×2） |
| CreditDataService | common/billing_client.py | Billing API 統合 |
| NotificationService | common/slack_client.py | Slack 通知配信 |
| SecretsService | common/secrets.py | シークレット管理・キャッシュ |

---

## アーキテクチャ図

```
+--------------------------------------------------+
|              EventBridge Schedulers              |
|  monthly(cron 0 9 1 * ? *)                      |
|  threshold(cron 0 0 * * ? *)                    |
|  expiry(cron 0 1 * * ? *)                       |
+--------+-----------+------------+---------------+
         |           |            |
         v           v            v
+--------+--+ +------+----+ +----+--------+
|monthly    | |threshold  | |expiry       |
|_notifier  | |_checker   | |_checker     |
|           | |           | |             |
| - Block   | | - Thresh  | | - Classify  |
|   Kit     | |   hold    | |   (30/7/0d) |
|   build   | |   check   | | - Block     |
|           | | - Block   | |   Kit build |
+-----+-----+ +----+------+ +-----+-------+
      |             |              |
      +------+-------+------+------+
             |                    |
             v                    v
    +--------+--------+   +-------+-------+
    | common/         |   | common/       |
    | billing_client  |   | slack_client  |
    |                 |   |               |
    | GetCredits      |   | post_message  |
    | GetAllocation   |   | (OAuth Token) |
    | History         |   +-------+-------+
    | (retry/paging)  |           |
    +--------+--------+   +-------+-------+
             |            | common/       |
             v            | secrets       |
    AWS Billing API       | (Ext cache /  |
    (us-east-1)           |  fallback SM) |
                          +-------+-------+
                                  |
                          +-------+-------+
                          | Lambda Ext    |
                          | / Secrets Mgr |
                          +---------------+
                                  |
                          Slack API
                          chat.postMessage
                                  |
                          Slack Channel

    [all 3 lambdas]
           |
    [on error]
           v
       SQS DLQ
```

---

## 主要設計決定

| 決定事項 | 選択肢 | 理由 |
|---|---|---|
| Lambda 分割 | 3関数分離 | 各ロールが独立してデプロイ・スケール・デバッグ可能 |
| 共有コード管理 | `src/common/` モジュール | Lambda Layer より同一リポジトリでの管理が容易 |
| Block Kit 構築 | 各 Lambda が独立して担当 | 月次・閾値・期限の各メッセージ構造が異なるため |
| Secrets Manager | Lambda Extension キャッシュ | 日次起動でのコスト最適化、API コール削減 |
| CDK スタック | 単一スタック | システム規模が小さく、単一スタックで十分シンプル |

---

## 詳細ドキュメント

- [components.md](components.md) — 各コンポーネントの詳細説明
- [component-methods.md](component-methods.md) — メソッドシグネチャ・入出力型
- [services.md](services.md) — サービスレイヤー設計・オーケストレーションパターン
- [component-dependency.md](component-dependency.md) — 依存関係マトリクス・データフロー
