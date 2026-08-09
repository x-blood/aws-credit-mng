# Component Methods

詳細なビジネスロジックは CONSTRUCTION フェーズの Functional Design で定義する。
ここではメソッドシグネチャと入出力型を定義する。

---

## monthly_notifier/handler.py

```python
def handler(event: dict, context: LambdaContext) -> None:
    """
    Lambda エントリーポイント。月次クレジット残高レポートを Slack に送信する。
    入力: EventBridge Scheduler イベント（内容は不問）
    出力: なし
    例外: BillingApiError, SlackApiError → DLQ に退避
    """

def _build_monthly_blocks(credits: list, history: list) -> list:
    """
    月次レポート用 Slack Block Kit ペイロードを構築する。
    入力: credits (GetCredits レスポンス), history (GetCreditAllocationHistory レスポンス)
    出力: Slack blocks (list[dict])
    注: 詳細フォーマットロジックは Functional Design で定義
    """

def _summarize_credits(credits: list) -> dict:
    """
    クレジット一覧から残高合計・適用合計・最短期限を集計する。
    入力: credits (list[CreditData])
    出力: summary dict { total_remaining, total_estimated, nearest_expiry, credit_count }
    """
```

---

## threshold_checker/handler.py

```python
def handler(event: dict, context: LambdaContext) -> None:
    """
    Lambda エントリーポイント。残高が閾値を下回った場合のみ Slack アラートを送信する。
    入力: EventBridge Scheduler イベント
    出力: なし
    環境変数: THRESHOLD_AMOUNT (float, default=1000.0)
    """

def _check_threshold(total_remaining: float, threshold: float) -> bool:
    """
    残高が閾値を下回っているか判定する。
    入力: total_remaining (float), threshold (float)
    出力: bool (True = アラート送信要)
    """

def _build_threshold_blocks(credits: list, total_remaining: float, threshold: float) -> list:
    """
    閾値アラート用 Slack Block Kit ペイロードを構築する。
    入力: credits, total_remaining, threshold
    出力: Slack blocks (list[dict])
    """
```

---

## expiry_checker/handler.py

```python
def handler(event: dict, context: LambdaContext) -> None:
    """
    Lambda エントリーポイント。期限切れ間近のクレジットを検出して Slack アラートを送信する。
    入力: EventBridge Scheduler イベント
    出力: なし
    """

def _classify_expiring_credits(credits: list, today: date) -> dict:
    """
    クレジットを期限までの残日数でグループ分けする。
    入力: credits (list[CreditData]), today (date)
    出力: { "critical": [...], "warning": [...], "info": [...] }
    注: critical=当日, warning=7日以内, info=30日以内 の定義は Functional Design で確定
    """

def _build_expiry_blocks(classified: dict) -> list:
    """
    期限切れアラート用 Slack Block Kit ペイロードを構築する。
    入力: classified dict (critical/warning/info ごとのクレジットリスト)
    出力: Slack blocks (list[dict])
    """
```

---

## common/billing_client.py

```python
def get_credits(account_id: str, start_date: datetime, payer_flag: bool = False) -> list:
    """
    billing:GetCredits を呼び出してクレジット一覧を返す。
    入力: account_id (str), start_date (datetime), payer_flag (bool)
    出力: list[CreditData dict]
    例外: BillingApiError (ThrottlingException を含む、バックオフ後も失敗時)
    """

def get_credit_allocation_history(
    account_id: str,
    start_date: datetime,
    end_date: datetime,
    credit_id: str | None = None
) -> list:
    """
    billing:GetCreditAllocationHistory をページネーション込みで呼び出す。
    入力: account_id, start_date, end_date, credit_id (optional filter)
    出力: list[CreditAllocationHistory dict]
    副作用: partialResults=True の場合は警告ログを出力
    例外: BillingApiError
    """

def _retry_with_backoff(func, max_retries: int = 5) -> any:
    """
    指数バックオフリトライラッパー（内部ユーティリティ）。
    初回待機: 1秒, 最大待機: 32秒
    対象例外: ThrottlingException
    """
```

---

## common/slack_client.py

```python
def post_message(channel_id: str, blocks: list, text: str = "") -> None:
    """
    Slack chat.postMessage API を呼び出す。
    入力: channel_id (str), blocks (list[dict]), text (str, 通知フォールバックテキスト)
    出力: なし
    例外: SlackApiError (HTTP エラー・rate limit・API エラーレスポンス)
    """

def _get_token() -> str:
    """
    secrets モジュール経由で Slack OAuth Token を取得する（内部）。
    出力: token (str)
    注: トークン値をログに出力しない
    """
```

---

## common/secrets.py

```python
def get_secret(secret_arn: str) -> dict:
    """
    Lambda Extension ローカルエンドポイント経由でシークレットを取得する。
    Extension 未起動時は Secrets Manager に直接フォールバックする。
    入力: secret_arn (str)
    出力: secret_value (dict)
    例外: SecretsManagerError
    注: 戻り値をログに出力しない
    """
```
