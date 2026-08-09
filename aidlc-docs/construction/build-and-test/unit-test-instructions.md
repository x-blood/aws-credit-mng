# Unit Test Execution

## Python ユニットテスト（Unit-1: Lambda Application）

### 実行方法

```bash
cd /Users/yasuyukisato/tech/my/aws-credit-mng
python3 -m pytest tests/ -v --tb=short
```

### カバレッジ付きで実行

```bash
python3 -m pytest tests/ -v --cov=src --cov-report=term-missing
```

### 期待結果

```
45 passed in X.XXs
```

### テストスイート一覧

| ファイル | テストクラス | テスト数 | 内容 |
|---|---|---|---|
| `test_billing_client.py` | `TestRetryWithBackoff` | 4 | 指数バックオフリトライ（成功・リトライ・上限・非スロットリング） |
| `test_billing_client.py` | `TestGetCredits` | 3 | GetCredits API（正常・空・payerFlag） |
| `test_billing_client.py` | `TestGetCreditAllocationHistory` | 3 | 適用履歴（正常・ページネーション・partialResults） |
| `test_expiry_checker.py` | `TestClassifyExpiringCredits` | 10 | 期限分類境界値（0/1/7/8/30/31日・残高0除外・INACTIVE除外） |
| `test_expiry_checker.py` | `TestBuildExpiryBlocks` | 2 | Block Kit（全レベル・空レベル省略） |
| `test_expiry_checker.py` | `TestExpiryHandler` | 2 | ハンドラー統合（アラート送信・送信なし） |
| `test_monthly_notifier.py` | `TestSummarizeCredits` | 4 | 残高集計（ACTIVE絞り込み・合計・最短期限） |
| `test_monthly_notifier.py` | `TestBuildMonthlyBlocks` | 5 | Block Kit（ヘッダー・警告なし・警告あり・履歴・見込み） |
| `test_monthly_notifier.py` | `TestMonthlyHandler` | 2 | ハンドラー統合（送信・Slackエラー伝播） |
| `test_threshold_checker.py` | `TestCheckThreshold` | 4 | 閾値判定境界値（以下・同値・以上・0） |
| `test_threshold_checker.py` | `TestBuildThresholdBlocks` | 3 | Block Kit（ヘッダー・不足額・上位5件） |
| `test_threshold_checker.py` | `TestThresholdHandler` | 3 | ハンドラー統合（アラート・送信なし・INACTIVE除外） |

---

## Node.js ユニットテスト（Unit-2: CDK Infrastructure）

### 実行方法

```bash
cd /Users/yasuyukisato/tech/my/aws-credit-mng/infra
npm test
```

### TypeScript 型チェック

```bash
npx tsc --noEmit
```

### 期待結果

```
19 passed in XX.XXXs
```

### テストスイート一覧

| テストスイート | テスト数 | 内容 |
|---|---|---|
| Lambda Functions | 9 | リソース数・メモリ・タイムアウト・ハンドラー・環境変数 |
| SQS Dead Letter Queue | 2 | キュー名・保持期間 |
| IAM Policy | 2 | billing 権限・Secrets Manager ARN スコープ |
| EventBridge Schedulers | 4 | リソース数・cron 式（3スケジュール） |
| CloudFormation Outputs | 2 | Lambda ARN × 3 + DLQ URL |

---

## テスト失敗時の対処

```bash
# 特定のテストのみ実行
python3 -m pytest tests/test_billing_client.py -v

# 特定のテストクラスのみ実行
python3 -m pytest tests/test_expiry_checker.py::TestClassifyExpiringCredits -v

# CDK テストをデバッグモードで実行
cd infra && npm test -- --verbose
```
