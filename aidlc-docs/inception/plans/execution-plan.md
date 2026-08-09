# Execution Plan

## Detailed Analysis Summary

### Change Impact Assessment
- **User-facing changes**: No（内部自動化ツール。エンドユーザーへの直接影響なし）
- **Structural changes**: Yes（新規サーバーレスアーキテクチャの構築）
- **Data model changes**: No（永続的データモデルなし。APIレスポンスのみ処理）
- **API changes**: Yes（Billing API / Slack API の統合）
- **NFR impact**: Yes（IAM最小権限、DLQ、リトライロジック）

### Risk Assessment
- **Risk Level**: Low-Medium
- **Rollback Complexity**: Easy（CDK destroy で全リソース削除可能）
- **Testing Complexity**: Moderate（Billing API のモック化が必要）

---

## Workflow Visualization

```
INCEPTION PHASE
  [x] Workspace Detection       - COMPLETED
  [x] Requirements Analysis     - COMPLETED
  [-] Reverse Engineering       - SKIPPED (Greenfield)
  [-] User Stories              - SKIPPED (内部自動化ツール)
  [x] Workflow Planning         - IN PROGRESS
  [>] Application Design        - EXECUTE
  [>] Units Generation          - EXECUTE
  
CONSTRUCTION PHASE
  [>] Functional Design         - EXECUTE (per unit)
  [-] NFR Requirements          - SKIPPED (NFR要件は要件定義で確定済み)
  [-] NFR Design                - SKIPPED (NFR Requirementsスキップのため)
  [>] Infrastructure Design     - EXECUTE (per unit)
  [>] Code Generation           - EXECUTE (ALWAYS)
  [>] Build and Test            - EXECUTE (ALWAYS)

OPERATIONS PHASE
  [-] Operations                - PLACEHOLDER
```

---

## Phases to Execute

### INCEPTION PHASE
- [x] Workspace Detection — COMPLETED
- [x] Requirements Analysis — COMPLETED
- [-] Reverse Engineering — SKIPPED（Greenfieldのため）
- [-] User Stories — SKIPPED（内部自動化ツール、ユーザーペルソナ不要）
- [x] Workflow Planning — IN PROGRESS (このドキュメント)
- [>] Application Design — **EXECUTE**
  - **Rationale**: 3つの Lambda 関数（月次通知・閾値チェック・期限チェック）と共有レイヤー、CDK スタックという新規コンポーネントを設計する必要がある
- [>] Units Generation — **EXECUTE**
  - **Rationale**: Lambda アプリケーションコードと CDK インフラコードで分離した開発単位が必要。複数コンポーネントの構造化が有益

### CONSTRUCTION PHASE（Per-Unit Loop）

**Unit 1: Lambda アプリケーション（Python）**
- [>] Functional Design — **EXECUTE**
  - **Rationale**: Billing API データの加工ロジック、閾値判定、期限チェック、Slack Block Kit フォーマットの詳細設計が必要
- [-] NFR Requirements — **SKIPPED**
  - **Rationale**: NFR（IAM権限・リトライ・DLQ・タイムアウト）は要件定義フェーズで既に確定。別途NFR Assessment は不要
- [-] NFR Design — **SKIPPED**
  - **Rationale**: NFR Requirements スキップのため
- [>] Infrastructure Design — **EXECUTE**
  - **Rationale**: Lambda設定（メモリ・タイムアウト・環境変数）、Secrets Manager参照方法の具体的なマッピングが必要
- [>] Code Generation — **EXECUTE**（ALWAYS）

**Unit 2: CDK インフラストラクチャ（TypeScript）**
- [-] Functional Design — **SKIPPED**
  - **Rationale**: CDK はインフラ定義。ビジネスロジックの詳細設計は不要
- [-] NFR Requirements — **SKIPPED**
- [-] NFR Design — **SKIPPED**
- [>] Infrastructure Design — **EXECUTE**
  - **Rationale**: CDK スタック構成（Scheduler × 3、Lambda × 3、SQS DLQ、Secrets Manager、IAM ロール × 2）の詳細設計
- [>] Code Generation — **EXECUTE**（ALWAYS）

**Build and Test（全Unit完了後）**
- [>] Build and Test — **EXECUTE**（ALWAYS）

### OPERATIONS PHASE
- [-] Operations — PLACEHOLDER（将来の展開用）

---

## Estimated Timeline

- **Total Stages to Execute**: 8（Application Design, Units Generation, FD×1, ID×2, CG×2, Build and Test）
- **Stages to Skip**: 8（RE, US, NFR Req×2, NFR Design×2, FD×1, Ops）
- **Estimated Duration**: 中程度の複雑さ。Moderate

---

## Success Criteria

- **Primary Goal**: AWS Credits 残高・期限情報を自動的に Slack に通知するサーバーレスシステムが `cdk deploy` 1コマンドでデプロイできること
- **Key Deliverables**:
  - Lambda 関数（Python 3.12）× 3（月次通知・日次閾値・日次期限）
  - CDK スタック（TypeScript）
  - IAM ポリシー（最小権限）
  - pytest テストスイート（moto使用）
  - README（デプロイ手順）
- **Quality Gates**:
  - `cdk synth` でエラーなし
  - `pytest` 全テストパス
  - Lambda ローカル実行テスト成功
