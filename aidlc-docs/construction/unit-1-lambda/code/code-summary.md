# Code Summary — Unit-1: Lambda Application

## 生成ファイル一覧

### アプリケーションコード（`src/`）

| ファイル | 説明 | FR/BR |
|---|---|---|
| `src/common/__init__.py` | パッケージ初期化 | — |
| `src/common/billing_client.py` | Billing API クライアント（リトライ・ページネーション） | FR-01, FR-02, BR-08 |
| `src/common/slack_client.py` | Slack chat.postMessage クライアント | FR-03〜05, BR-07, BR-10 |
| `src/common/secrets.py` | Lambda Extension + Boto3 フォールバック | NFR-01, BR-10 |
| `src/monthly_notifier/__init__.py` | パッケージ初期化 | — |
| `src/monthly_notifier/handler.py` | 月次クレジットレポート Lambda | FR-01〜03, BR-01, BR-02, BR-06, BR-11 |
| `src/threshold_checker/__init__.py` | パッケージ初期化 | — |
| `src/threshold_checker/handler.py` | 日次残高閾値チェック Lambda | FR-04, BR-01〜03 |
| `src/expiry_checker/__init__.py` | パッケージ初期化 | — |
| `src/expiry_checker/handler.py` | 日次期限切れチェック Lambda | FR-05, BR-01, BR-04, BR-05 |

### テストコード（`tests/`）

| ファイル | 説明 |
|---|---|
| `tests/__init__.py` | パッケージ初期化 |
| `tests/conftest.py` | pytest フィクスチャ・テストデータヘルパー |
| `tests/test_billing_client.py` | billing_client 単体テスト（リトライ・ページネーション） |
| `tests/test_monthly_notifier.py` | monthly_notifier 単体・統合テスト |
| `tests/test_threshold_checker.py` | threshold_checker 単体・統合テスト |
| `tests/test_expiry_checker.py` | expiry_checker 単体・統合テスト |

### 依存管理

| ファイル | 説明 |
|---|---|
| `requirements.txt` | Lambda 本番依存（boto3, requests） |
| `requirements-dev.txt` | 開発・テスト依存（pytest, moto, responses） |

## テストカバレッジ概要

| コンポーネント | テストクラス | 主なテストケース |
|---|---|---|
| billing_client | `TestRetryWithBackoff` | 初回成功・リトライ成功・最大リトライ超過・非スロットリングエラー |
| billing_client | `TestGetCredits` | 正常系・空レスポンス・payerFlag |
| billing_client | `TestGetCreditAllocationHistory` | 正常系・ページネーション・partialResults |
| monthly_notifier | `TestSummarizeCredits` | ACTIVE絞り込み・合計計算・最短期限選択 |
| monthly_notifier | `TestBuildMonthlyBlocks` | Block Kit構造・partialResults警告・isEstimatedBill |
| monthly_notifier | `TestMonthlyHandler` | 正常送信・Slackエラー伝播 |
| threshold_checker | `TestCheckThreshold` | 境界値（以下/同値/以上/0） |
| threshold_checker | `TestBuildThresholdBlocks` | ヘッダー・不足額表示・上位5件制限 |
| threshold_checker | `TestThresholdHandler` | アラート送信・送信なし・INACTIVE除外 |
| expiry_checker | `TestClassifyExpiringCredits` | 境界値（0/1/7/8/30/31日）・残高0除外・INACTIVE除外 |
| expiry_checker | `TestBuildExpiryBlocks` | 全レベル表示・空レベル省略 |
| expiry_checker | `TestExpiryHandler` | アラート送信・対象なし時送信なし |

## ビジネスルール適用確認

| BR | ルール | 実装ファイル | テストカバー |
|---|---|---|---|
| BR-01 | ACTIVE のみ | 全ハンドラー | ✅ |
| BR-02 | remainingAmount 合算 | monthly, threshold | ✅ |
| BR-03 | 閾値毎日通知 | threshold | ✅ |
| BR-04 | 期限分類境界値 | expiry | ✅ |
| BR-05 | remainingAmount > 0 | expiry | ✅ |
| BR-06 | partialResults 警告 | monthly | ✅ |
| BR-07 | 環境変数バリデーション | slack_client | ✅ |
| BR-08 | 指数バックオフリトライ | billing_client | ✅ |
| BR-10 | トークン値ログ禁止 | secrets, slack_client | コードレビューで確認 |
| BR-11 | 最短期限選択 | monthly | ✅ |
