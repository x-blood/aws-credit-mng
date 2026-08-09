# Code Generation Plan — Unit-1: Lambda Application

## ユニット概要
- **ユニット**: Unit-1: Lambda Application（Python 3.12）
- **ワークスペースルート**: `/Users/yasuyukisato/tech/my/aws-credit-mng`
- **アプリコード配置**: `src/` + `tests/`（ワークスペースルート直下）
- **ドキュメント**: `aidlc-docs/construction/unit-1-lambda/code/`

## 実装対象機能要件
- FR-01: クレジット残高取得（billing_client）
- FR-02: 適用履歴取得（billing_client）
- FR-03: 月次定期通知（monthly_notifier）
- FR-04: 残高閾値アラート（threshold_checker）
- FR-05: 期限切れアラート（expiry_checker）
- FR-06: エラーハンドリング・リトライ（billing_client, slack_client）
- NFR-01: シークレット管理（secrets）

---

## Generation Steps

### Step 1: プロジェクト構造セットアップ
- [x] `src/monthly_notifier/__init__.py` 作成（空）
- [x] `src/threshold_checker/__init__.py` 作成（空）
- [x] `src/expiry_checker/__init__.py` 作成（空）
- [x] `src/common/__init__.py` 作成（空）
- [x] `tests/__init__.py` 作成（空）
- [x] `requirements.txt` 作成
- [x] `requirements-dev.txt` 作成

### Step 2: common/secrets.py 生成
- [x] `src/common/secrets.py` 生成
  - Lambda Extension 経由シークレット取得
  - Boto3 フォールバック実装
  - BR-10 準拠（トークン値ログ出力禁止）

### Step 3: common/billing_client.py 生成
- [x] `src/common/billing_client.py` 生成
  - `get_credits()` 実装（BR-08 指数バックオフ）
  - `get_credit_allocation_history()` 実装（ページネーション、partialResults）
  - `_retry_with_backoff()` 実装

### Step 4: common/slack_client.py 生成
- [x] `src/common/slack_client.py` 生成
  - `post_message()` 実装
  - Rate Limit (429) 処理
  - BR-07 環境変数バリデーション
  - BR-10 準拠（トークン値ログ出力禁止）

### Step 5: monthly_notifier/handler.py 生成
- [x] `src/monthly_notifier/handler.py` 生成
  - `handler()` エントリーポイント
  - `_summarize_credits()` (BR-01, BR-02, BR-11)
  - `_build_monthly_blocks()` (BR-06 partialResults警告)

### Step 6: threshold_checker/handler.py 生成
- [x] `src/threshold_checker/handler.py` 生成
  - `handler()` エントリーポイント
  - `_check_threshold()` (BR-03)
  - `_build_threshold_blocks()`

### Step 7: expiry_checker/handler.py 生成
- [x] `src/expiry_checker/handler.py` 生成
  - `handler()` エントリーポイント
  - `_classify_expiring_credits()` (BR-04, BR-05)
  - `_build_expiry_blocks()`

### Step 8: tests/test_billing_client.py 生成
- [x] `tests/test_billing_client.py` 生成
  - moto で billing API モック
  - `get_credits()` 正常系・ThrottlingException リトライ・partialResults テスト

### Step 9: tests/test_monthly_notifier.py 生成
- [x] `tests/test_monthly_notifier.py` 生成
  - `_summarize_credits()` 単体テスト（ACTIVE絞り込み・合計・最短期限）
  - `handler()` 統合テスト（モック Billing API + Slack）
  - partialResults=True 時の警告ブロック追加テスト

### Step 10: tests/test_threshold_checker.py 生成
- [x] `tests/test_threshold_checker.py` 生成
  - `_check_threshold()` 境界値テスト
  - 閾値以下でアラート送信・閾値以上で送信なしテスト

### Step 11: tests/test_expiry_checker.py 生成
- [x] `tests/test_expiry_checker.py` 生成
  - `_classify_expiring_credits()` 境界値テスト（0日/7日/30日/31日）
  - `remainingAmount == 0` 除外テスト
  - 期限切れ対象なし時に通知なしテスト

### Step 12: conftest.py 生成
- [x] `tests/conftest.py` 生成
  - pytest フィクスチャ（AWS credentials モック、環境変数セットアップ）

### Step 13: ドキュメント生成
- [x] `aidlc-docs/construction/unit-1-lambda/code/code-summary.md` 生成
- [x] `README.md` 作成（セットアップ・デプロイ手順）
